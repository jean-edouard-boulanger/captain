#!/usr/bin/env python3.8
from typing import Callable
from datetime import datetime, timedelta
import socketio
import asyncio
import logging
import sys
import pytz


logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("main")

sio = socketio.AsyncClient(logger=logger)

#DOWNLOAD_URL = ***REMOVED***"
DOWNLOAD_URL = ***REMOVED***"
#DOWNLOAD_URL = ***REMOVED***"


@sio.event
async def connect():
    logger.info("connected")


@sio.on("download_event")
async def on_download_event(data):
    logger.info(f"on_download_event: {data}")


@sio.on("recap")
async def on_recap(data):
    logger.info(f"on_recap: {data}")
    pass


async def main_loop(emit: Callable):
    while True:
        logger.info("starting download")
        await emit("start_download", {
            "remote_file_url": DOWNLOAD_URL,
            "local_dir": "/Users/jboulanger/Downloads",
            "start_at": (datetime.now(pytz.utc) + timedelta(seconds=120)).isoformat(),
            "auth": {
                "basic": {
                    "username": "jboulanger",
                    "password": "***REMOVED***"
                }
            }
        })
        await asyncio.sleep(3600)


async def main():
    await sio.connect("http://127.0.0.1:3001")
    sio.start_background_task(main_loop, sio.emit)
    await sio.wait()


if __name__ == "__main__":
    asyncio.run(main())
