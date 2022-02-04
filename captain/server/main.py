from captain.core.serialization import serialize
from captain.core.helpers import set_thread_name
from captain.core.logging import get_logger
from captain.core import (
    DownloadManager,
    DownloadManagerSettings,
    DownloadManagerObserverBase,
    DownloadRequest,
    DownloadManagerEvent,
    DownloadHandle,
)

import yaml
import socketio

from dateutil.parser import parse as parse_date
from pathlib import Path
from typing import Callable
from asyncio import Queue
from aiohttp import web
import aiohttp_cors
import logging
import argparse
import threading
import asyncio
import signal
import sys
import os


sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
routes = web.RouteTableDef()

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s (%(threadName)s) [%(levelname)s] %(message)s (%(filename)s:%(lineno)d)",
)

logger = get_logger()

os.environ["PYTHONWARNINGS"] = "ignore:Unverified HTTPS request"


MANAGER_THREAD_NAME = "DownloadManager"


def get_manager() -> DownloadManager:
    manager = get_manager.manager
    if manager is None:
        raise RuntimeError("download manager not initialized")
    return get_manager.manager


def init_manager(settings: DownloadManagerSettings) -> DownloadManager:
    def manager_thread_endpoint() -> None:
        set_thread_name(MANAGER_THREAD_NAME)
        get_manager().run()

    get_manager.manager = DownloadManager(settings)
    get_manager.manager_thread = threading.Thread(
        target=manager_thread_endpoint, name=MANAGER_THREAD_NAME
    )
    return get_manager.manager


def start_manager() -> None:
    get_manager.manager_thread.start()


def stop_manager() -> None:
    get_manager.manager.stop()
    get_manager.manager_thread.join()


get_manager.manager = None
get_manager.manager_thread = None


class DownloadManagerEventConsumer(DownloadManagerObserverBase):
    def __init__(self, queue: Queue, event_loop):
        self._queue = queue
        self._loop = event_loop

    def handle_event(self, event: DownloadManagerEvent):
        if self._loop.is_closed():
            logger.warning("event loop is closed, not ignoring download manager event")
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)


async def sio_publisher(shared_queue: Queue, emit: Callable):
    logger.info(f"subscriber started")
    while True:
        event: DownloadManagerEvent = await shared_queue.get()
        await emit("download_event", serialize(event))


def build_recap(manager: DownloadManager):
    downloads = manager.get_downloads(blocking=True)
    return {"downloads": downloads, "settings": serialize(manager.settings)}


@sio.on("start_download")
async def on_start_download(_, data):
    download_request = DownloadRequest.parse_obj(data)
    logger.info(f"start download: {download_request}")
    get_manager().start_download(download_request)


@sio.on("reschedule_download")
async def on_reschedule_download(_, data):
    logger.info(f"reschedule download: {data}")
    get_manager().reschedule_download(
        handle=DownloadHandle(handle=data["handle"]),
        start_at=parse_date(data["start_at"]),
    )


@sio.on("pause_download")
async def on_pause_download(_, data):
    logger.info(f"pause download: {data}")
    handle = DownloadHandle(handle=data["handle"])
    get_manager().pause_download(handle)


@sio.on("resume_download")
async def on_start_download(_, data):
    logger.info(f"resume download: {data}")
    handle = DownloadHandle(handle=data["handle"])
    get_manager().resume_download(handle)


@sio.on("stop_download")
async def on_stop_download(_, data):
    logger.info(f"stop download: {data}")
    handle = DownloadHandle(handle=data["handle"])
    get_manager().stop_download(handle)


@sio.on("retry_download")
async def on_retry_download(_, data):
    logger.info(f"retry download: {data}")
    handle = DownloadHandle(handle=data["handle"])
    get_manager().retry_download(handle)


@sio.on("remove_download")
async def on_remove_download(_, data):
    logger.info(f"remove download: {data}")
    manager = get_manager()
    manager.remove_download(
        handle=DownloadHandle(handle=data["handle"]),
        delete_file=data.get("delete_file", False),
        blocking=True,
    )
    await sio.emit("recap", build_recap(manager))


@sio.event
async def connect(sid, _):
    logger.info(f"new client connected: {sid}")
    await sio.emit("recap", build_recap(get_manager()))


@routes.get("/download/{handle}")
async def download_endpoint(request):
    handle = DownloadHandle(handle=request.match_info["handle"])
    file_path: Path = get_manager().get_download_file_path(handle=handle, blocking=True)
    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-disposition": f"attachment; filename={file_path.name}"
        }
    )
    await response.prepare(request)
    with file_path.open("rb") as f:
        while chunk := f.read(2 ** 16):
            await response.write(chunk)
    return response


@routes.post("/api/v1/core/validate_download_directory")
async def validate_download_directory_endpoint(request: web.Request):
    payload = await request.json()
    directory = Path(payload["directory"]).expanduser()
    if not directory.is_dir():
        return web.json_response({"valid": False, "reason": "Does not exist or is not a directory"})
    if not os.access(directory, os.W_OK):
        return web.json_response({"valid": False, "reason": "This directory is not writable"})
    return web.json_response({"valid": True})


def get_arguments_parser():
    parser = argparse.ArgumentParser("captain download manager server")
    parser.add_argument(
        "-c", "--config", type=str, required=True, help="path to configuration file"
    )
    return parser


def signal_handler(*args, **kwargs):
    stop_manager()
    signal.raise_signal(signal.SIGKILL)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    config = get_arguments_parser().parse_args()
    with open(config.config) as cf:
        manager_settings = DownloadManagerSettings.parse_obj(yaml.safe_load(cf))
    shared_queue = Queue()
    manager = init_manager(manager_settings)
    manager.add_observer(
        DownloadManagerEventConsumer(shared_queue, asyncio.get_event_loop())
    )
    start_manager()
    logger.info("download manager started")
    app = web.Application()
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    app.add_routes(routes)
    for route in list(app.router.routes()):
        cors.add(route)
    sio.attach(app)
    sio.start_background_task(sio_publisher, shared_queue, sio.emit)
    logger.info("publisher started")
    web.run_app(
        app,
        host=manager_settings.listen_host,
        port=manager_settings.listen_port,
        access_log=None,
        handle_signals=False,
    )
    logger.info("stopping download manager")
    stop_manager()
    logger.info("leaving")


if __name__ == "__main__":
    main()
