import os
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, TypedDict

import yt_dlp

from .domain import DownloadHandle, DownloadMetadata, ErrorInfo, YoutubeDownloadRequest
from .download_listener import DownloadListenerBase
from .download_task import DownloadTaskBase
from .errors import NotSupportedError
from .logging import get_logger

logger = get_logger()


class YoutubeProgressNotification(TypedDict):
    filename: str
    total_bytes: int
    downloaded_bytes: int
    speed: float


class YoutubeFinishedNotification(TypedDict):
    pass


class YoutubeErrorNotification(TypedDict):
    pass


class YoutubeDownloadListener(object):
    def _handle_youtube_notification(self, notification: Any) -> None:
        handlers = {
            "downloading": self._handle_youtube_progress,
            "finished": self._handle_youtube_finished,
            "error": self._handle_youtube_error,
        }
        status = notification["status"]
        handlers[status](notification)

    def _handle_youtube_progress(self, notification: YoutubeProgressNotification) -> None:
        pass

    def _handle_youtube_error(self, notification: YoutubeErrorNotification) -> None:
        pass

    def _handle_youtube_finished(self, notification: YoutubeFinishedNotification) -> None:
        pass


class YoutubeDownloadTask(DownloadTaskBase, YoutubeDownloadListener):
    supports_graceful_stop = False

    def __init__(
        self,
        handle: DownloadHandle,
        download_request: YoutubeDownloadRequest,
        existing_metadata: DownloadMetadata,
        work_dir: Path,
        listener: Optional[DownloadListenerBase] = None,
        progress_report_interval: Optional[timedelta] = None,
    ):
        self._handle = handle
        self._request = download_request
        self._metadata = existing_metadata
        self._listener = listener
        self._work_dir = work_dir
        self._notified_started = False

    def _handle_youtube_progress(self, notification: YoutubeProgressNotification) -> None:
        if not self._metadata:
            self._metadata = DownloadMetadata(
                downloaded_file_path=self._work_dir / notification["filename"],
                file_size=notification["total_bytes"],
                resumable=True,
            )
        if not self._notified_started:
            self._listener.download_started(
                update_time=datetime.now(),
                handle=self._handle,
                metadata=self._metadata,
            )
            self._notified_started = True
        self._listener.progress_changed(
            update_time=datetime.now(),
            handle=self._handle,
            downloaded_bytes=notification["downloaded_bytes"],
            average_rate=notification["speed"],
        )

    def run(self):
        try:
            ydl_options = {
                "format": "best",
                "progress_hooks": [self._handle_youtube_notification],
                "logger": logger,
            }
            os.chdir(self._work_dir)
            with yt_dlp.YoutubeDL(ydl_options) as ydl:
                ydl.download([self._request.remote_file_url])
            self._listener.download_complete(update_time=datetime.now(), handle=self._handle)
        except Exception as e:
            self._listener.download_errored(
                datetime.now(),
                self._handle,
                ErrorInfo(
                    message=f"Could not download '{self._request.remote_file_name}': {e}",
                    stack=traceback.format_exc(),
                ),
            )

    def stop(self):
        raise NotSupportedError("YoutubeDownloadTask does not support 'stop'")
