from captain.core import (
    DownloadManager,
    DownloadManagerSettings,
    DownloadManagerObserverBase,
    DownloadRequest,
    DownloadManagerEvent,
    DownloadHandle
)

from dateutil.parser import parse as parse_date
from typing import Callable
from asyncio import Queue
from aiohttp import web
import yaml
import argparse
import threading
import asyncio
import socketio
import logging
import sys
import os

sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins='*')

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger("ws")

os.environ["PYTHONWARNINGS"] = "ignore:Unverified HTTPS request"


def get_manager() -> DownloadManager:
    manager = get_manager.manager
    if manager is None:
        raise RuntimeError("download manager not initialized")
    return get_manager.manager


def init_manager(settings: DownloadManagerSettings) -> DownloadManager:
    get_manager.manager = DownloadManager(settings)
    get_manager.manager_thread = threading.Thread(
        target=get_manager.manager.run)
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
            logger.warning("event loop is closed, not putting download manager event")
            return
        self._loop.call_soon_threadsafe(
            self._queue.put_nowait, event)


async def sio_publisher(shared_queue: Queue, emit: Callable):
    logger.info(f"subscriber started")
    while True:
        event: DownloadManagerEvent = await shared_queue.get()
        await emit("download_event", event.serialize())


def build_recap(manager: DownloadManager):
    downloads = manager.get_downloads(blocking=True)
    return {
        "downloads": downloads,
        "settings": manager.settings.serialize()
    }


@sio.on("start_download")
async def on_start_download(_, data):
    logger.info(f"start download: {data}")
    download_request = DownloadRequest.deserialize(data)
    get_manager().start_download(download_request)


@sio.on("reschedule_download")
async def on_start_download(_, data):
    logger.info(f"reschedule download: {data}")
    get_manager().reschedule_download(
        handle=DownloadHandle(data["handle"]),
        start_at=parse_date(data["start_at"]))


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
    handle = DownloadHandle(data["handle"])
    manager = get_manager()
    manager.remove_download(handle, blocking=True)
    await sio.emit("recap", build_recap(manager))


@sio.event
async def connect(sid, _):
    logger.info(f"new client connected: {sid}")
    await sio.emit("recap", build_recap(get_manager()))


def get_arguments_parser():
    parser = argparse.ArgumentParser("captain download manager server")
    parser.add_argument("-c", "--config", type=str, required=True,
                        help="path to configuration file")
    return parser


def main():
    config = get_arguments_parser().parse_args()
    with open(config.config) as cf:
        manager_settings = DownloadManagerSettings.deserialize(yaml.safe_load(cf))
    shared_queue = Queue()
    manager = init_manager(manager_settings)
    manager.add_observer(
        DownloadManagerEventConsumer(shared_queue, asyncio.get_event_loop()))
    start_manager()
    logger.info("download manager started")
    app = web.Application()
    sio.attach(app)
    sio.start_background_task(sio_publisher, shared_queue, sio.emit)
    logger.info("publisher started")
    web.run_app(app,
                host='127.0.0.1', port=5001,
                access_log=None,
                handle_signals=True)
    logger.info("stopping download manager")
    stop_manager()
    logger.info("leaving")


if __name__ == "__main__":
    main()
