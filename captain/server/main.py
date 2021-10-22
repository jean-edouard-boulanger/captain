from captain.core.logging import configure_logging, get_logger
from captain.core import (
    DownloadManager,
    DownloadManagerSettings,
    DownloadManagerObserverBase,
    DownloadRequest,
    DownloadManagerEvent,
    DownloadHandle,
    SocketioRpc,
)

from dateutil.parser import parse as parse_date
from pathlib import Path
from typing import Callable
from asyncio import Queue
from aiohttp import web
import aiohttp
import yaml
import argparse
import threading
import asyncio
import socketio
import signal
import os

sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
rpc = SocketioRpc(sio)
app = web.Application()

logger = get_logger()

os.environ["PYTHONWARNINGS"] = "ignore:Unverified HTTPS request"


def get_manager() -> DownloadManager:
    manager = get_manager.manager
    if manager is None:
        raise RuntimeError("download manager not initialized")
    return get_manager.manager


def init_manager(settings: DownloadManagerSettings) -> DownloadManager:
    get_manager.manager = DownloadManager(settings)
    get_manager.manager_thread = threading.Thread(target=get_manager.manager.run)
    return get_manager.manager


def start_manager():
    get_manager.manager_thread.start()


def stop_manager():
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
        await emit("download_event", event.serialize())


def build_recap(manager: DownloadManager):
    downloads = manager.get_downloads(blocking=True)
    return {"downloads": downloads, "settings": manager.settings.serialize()}


@sio.on("start_download")
async def on_start_download(_, data):
    logger.info(f"start download: {data}")
    download_request = DownloadRequest.deserialize(data)
    get_manager().start_download(download_request)


@sio.on("reschedule_download")
async def on_start_download(_, data):
    logger.info(f"reschedule download: {data}")
    get_manager().reschedule_download(
        handle=DownloadHandle(data["handle"]), start_at=parse_date(data["start_at"])
    )


@sio.on("pause_download")
async def on_start_download(_, data):
    logger.info(f"pause download: {data}")
    handle = DownloadHandle(data["handle"])
    get_manager().pause_download(handle)


@sio.on("resume_download")
async def on_start_download(_, data):
    logger.info(f"resume download: {data}")
    handle = DownloadHandle(data["handle"])
    get_manager().resume_download(handle)


@sio.on("stop_download")
async def on_start_download(_, data):
    logger.info(f"stop download: {data}")
    handle = DownloadHandle(data["handle"])
    get_manager().stop_download(handle)


@sio.on("retry_download")
async def on_start_download(_, data):
    logger.info(f"retry download: {data}")
    handle = DownloadHandle(data["handle"])
    get_manager().retry_download(handle)


@sio.on("remove_download")
async def on_start_download(_, data):
    logger.info(f"remove download: {data}")
    manager = get_manager()
    manager.remove_download(
        handle=DownloadHandle(data["handle"]),
        delete_file=data.get("delete_file", False),
        blocking=True,
    )
    await sio.emit("recap", build_recap(manager))


@sio.event
async def connect(sid, _):
    logger.info(f"new client connected: {sid}")
    await sio.emit("recap", build_recap(get_manager()))


@rpc.on("validate_download_directory")
def handle_validate_download_directory(_, request):
    directory = Path(request["directory"]).expanduser()
    if not directory.is_dir():
        return {"valid": False, "reason": "Does not exist or is not a directory"}
    if not os.access(directory, os.W_OK):
        return {"valid": False, "reason": "This directory is not writable"}
    return {"valid": True}


@aiohttp.streamer
async def file_sender(writer, file_path=None):
    with open(file_path, "rb") as f:
        chunk = f.read(2 ** 16)
        while chunk:
            await writer.write(chunk)
            chunk = f.read(2 ** 16)


async def download_handler(request):
    handle = DownloadHandle(request.match_info["handle"])
    entry = get_manager().get_download(handle=handle, blocking=True)
    download_status = entry["state"]["status"]
    logger.info(entry["state"])
    if entry["state"]["status"] != "COMPLETE" or not entry["state"]["file_location"]:
        return web.Response(
            body=f"file for download '{handle.handle}' cannot be downloaded (download status: {download_status})",
            status=404,
        )
    file_path = Path(entry["state"]["file_location"])
    headers = {"Content-disposition": f"attachment; filename={file_path.name}"}
    return web.Response(body=file_sender(file_path=file_path), headers=headers)


def get_arguments_parser():
    parser = argparse.ArgumentParser("captain download manager server")
    parser.add_argument(
        "-c", "--config", type=str, required=True, help="path to configuration file"
    )
    return parser


def signal_handler(*args, **kwargs):
    stop_manager()
    logger.info("download manager stopped")
    signal.raise_signal(signal.SIGKILL)  # TODO: there is probably a better way to stop the web server gracefully


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    config = get_arguments_parser().parse_args()
    with open(config.config) as cf:
        manager_settings = DownloadManagerSettings.deserialize(yaml.safe_load(cf))
    logging_settings = manager_settings.logging_settings
    configure_logging(logging_settings.format, logging_settings.level)
    shared_queue = Queue()
    manager = init_manager(manager_settings)
    manager.add_observer(
        DownloadManagerEventConsumer(shared_queue, asyncio.get_event_loop())
    )
    start_manager()
    logger.info("download manager started")
    app.router.add_get("/download/{handle}", download_handler)
    print(sio)
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
