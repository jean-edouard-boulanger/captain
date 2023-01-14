import multiprocessing
from datetime import datetime
from typing import Any, Dict, Protocol

from .domain import DownloadHandle, DownloadMetadata, ErrorInfo
from .logging import get_logger
from .serialization import serialize
from .worker import Worker

logger = get_logger()


class DownloadListenerBase(Protocol):
    def download_started(self, update_time: datetime, handle: DownloadHandle, metadata: DownloadMetadata):
        raise NotImplementedError("must implement 'download_started'")

    def download_stopped(self, update_time: datetime, handle: DownloadHandle):
        raise NotImplementedError("must implement 'download_started'")

    def progress_changed(
        self,
        update_time: datetime,
        handle: DownloadHandle,
        downloaded_bytes: float,
        average_rate: float,
    ):
        raise NotImplementedError("must implement 'progress_changes'")

    def download_complete(self, update_time: datetime, handle: DownloadHandle):
        raise NotImplementedError("must implement 'download_complete'")

    def download_errored(self, update_time: datetime, handle: DownloadHandle, error_info: ErrorInfo):
        raise NotImplementedError("must implement 'download_errored'")


class NoOpDownloadListener(DownloadListenerBase):
    def download_started(self, update_time: datetime, handle: DownloadHandle, metadata: DownloadMetadata):
        logger.debug(f"download started [{handle}]: {serialize(metadata)}")

    def download_stopped(self, update_time: datetime, handle: DownloadHandle):
        logger.debug(f"download stopped [{handle}]")

    def progress_changed(
        self,
        update_time: datetime,
        handle: DownloadHandle,
        downloaded_bytes: float,
        average_rate: float,
    ):
        pass

    def download_complete(self, update_time: datetime, handle: DownloadHandle):
        logger.debug(f"download complete [{handle}]")

    def download_errored(self, update_time: datetime, handle: DownloadHandle, error_info: ErrorInfo):
        logger.debug(f"download errored: {error_info} [{handle}]")


class MessageBasedDownloadListener(DownloadListenerBase):
    def __init__(self, message_queue: multiprocessing.Queue):
        self._message_queue = message_queue

    def download_started(self, update_time: datetime, handle: DownloadHandle, metadata: DownloadMetadata):
        self._message_queue.put(
            {
                "download_started": {
                    "update_time": update_time,
                    "handle": handle,
                    "metadata": metadata,
                }
            }
        )

    def download_stopped(self, update_time: datetime, handle: DownloadHandle):
        self._message_queue.put({"download_stopped": {"update_time": update_time, "handle": handle}})

    def progress_changed(
        self,
        update_time: datetime,
        handle: DownloadHandle,
        downloaded_bytes: float,
        average_rate: float,
    ):
        self._message_queue.put(
            {
                "progress_changed": {
                    "update_time": update_time,
                    "handle": handle,
                    "downloaded_bytes": downloaded_bytes,
                    "average_rate": average_rate,
                }
            }
        )

    def download_complete(self, update_time: datetime, handle: DownloadHandle):
        self._message_queue.put({"download_complete": {"update_time": update_time, "handle": handle}})

    def download_errored(self, update_time: datetime, handle: DownloadHandle, error_info: ErrorInfo):
        self._message_queue.put(
            {
                "download_errored": {
                    "update_time": update_time,
                    "handle": handle,
                    "error_info": error_info,
                }
            }
        )


class ThreadedDownloadListenerBridge(Worker):
    def __init__(self, listener: DownloadListenerBase):
        super().__init__(multiprocessing.Queue(), name="DownloadListenerBridge")
        self._listener = listener

    def consume_message(self, message: Dict[str, Dict[str, Any]]) -> None:
        try:
            logger.debug(f"download listener bridge consuming message: {message}")
            event_type = list(message.keys())[0]
            event_payload = message[event_type]
            getattr(self._listener, event_type)(**event_payload)
        except Exception as e:
            logger.error(f"download listener bridge failed to handle message {message}: {e}")

    def make_listener(self) -> MessageBasedDownloadListener:
        return MessageBasedDownloadListener(self._message_queue)
