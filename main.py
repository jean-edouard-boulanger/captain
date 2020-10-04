#!/usr/bin/env python3.8
from typing import Callable
import socketio
import asyncio
import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("main")

sio = socketio.AsyncClient(logger=logger)

#DOWNLOAD_URL = "https://163.172.86.8/download/jboulanger/rtorrent/download/DJ%20Tools%20Samples%20Vol%201/Dj%20Tools%20-%20DJ%207Up%20Intros%2C%20Samples%20%2B%20FX%203.mp3"
DOWNLOAD_URL = "https://163.172.86.8/download/jboulanger/rtorrent/download/Bacurau%20Sonata%20Premiere/Bacurau.avi"
#DOWNLOAD_URL = "https://163.172.86.8/download/jboulanger/rtorrent/download/Westworld%20S01%20Season%201%20Complete%20HDTV%20720p%20x265%20AAC%20E-Subs%20%5BGWC%5D/Westworld%20S01E07%20720p%20HDTV%20x265%20AAC%20%5BGWC%5D.mkv"


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
            "auth": {
                "basic": {
                    "username": "jboulanger",
                    "password": "VZYsxl28"
                }
            }
        })
        await asyncio.sleep(1)


async def main():
    await sio.connect("http://127.0.0.1:3001")
    sio.start_background_task(main_loop, sio.emit)
    await sio.wait()


if __name__ == "__main__":
    asyncio.run(main())
