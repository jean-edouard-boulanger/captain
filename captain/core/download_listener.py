from .logging import get_logger
from .download_entities import DownloadMetadata, ErrorInfo, DownloadHandle

from datetime import datetime
from typing import Protocol


logger = get_logger()


class DownloadListenerBase(Protocol):
    def download_started(
        self, update_time: datetime, handle: DownloadHandle, metadata: DownloadMetadata
    ):
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

    def download_errored(
        self, update_time: datetime, handle: DownloadHandle, error_info: ErrorInfo
    ):
        raise NotImplementedError("must implement 'download_errored'")


class NoOpDownloadListener(DownloadListenerBase):
    def download_started(
        self, update_time: datetime, handle: DownloadHandle, metadata: DownloadMetadata
    ):
        logger.debug(f"download started [{handle}]: {metadata.serialize()}")

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

    def download_errored(
        self, update_time: datetime, handle: DownloadHandle, error_info: ErrorInfo
    ):
        logger.debug(f"download errored: {error_info} [{handle}]")
