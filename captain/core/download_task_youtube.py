from .logging import get_logger
from .errors import NotSupportedError
from .download_listener import DownloadListenerBase
from .domain import (
    DownloadRequest,
    DownloadMetadata,
    DownloadHandle,
    ErrorInfo,
)

import youtube_dl

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import traceback
import shutil
import os


logger = get_logger()


class YoutubeDownloadTask(object):
    supports_graceful_stop = False

    def __init__(
        self,
        handle: DownloadHandle,
        request: DownloadRequest,
        download_file_path: Path,
        listener: Optional[DownloadListenerBase] = None,
        progress_report_interval: Optional[timedelta] = None,
    ):
        self._handle = handle
        self._request = request
        self._listener = listener
        self._download_file_path = download_file_path
        self._metadata_sent = False
        self._last_downloaded_byte: Optional[int] = None
        self._youtube_dl_file_name: Optional[str] = None

    def _progress_hook(self, progress: Dict[str, Any]) -> None:
        status = progress["status"]
        if status == "downloading":
            if not self._metadata_sent:
                self._youtube_dl_file_name = progress["filename"]
                self._listener.download_started(
                    update_time=datetime.now(),
                    handle=self._handle,
                    metadata=DownloadMetadata(
                        remote_url=self._request.remote_file_url,
                        remote_file_name=self._youtube_dl_file_name,
                        file_size=progress["total_bytes"],
                    ),
                )
                self._metadata_sent = True
            downloaded_bytes = progress["downloaded_bytes"]
            self._listener.progress_changed(
                update_time=datetime.now(),
                handle=self._handle,
                downloaded_bytes=(
                    downloaded_bytes
                    if not self._last_downloaded_byte
                    else downloaded_bytes - self._last_downloaded_byte
                ),
                average_rate=progress["speed"],
            )
            self._last_downloaded_byte = downloaded_bytes
        elif status == "finished":
            pass
        elif status == "error":
            pass

    def run(self):
        try:
            ydl_options = {
                "format": "best",
                "progress_hooks": [self._progress_hook],
                "logger": logger,
            }
            os.chdir(self._download_file_path.parent)
            with youtube_dl.YoutubeDL(ydl_options) as ydl:
                ydl.download([self._request.remote_file_url])
            shutil.move(
                self._download_file_path.parent.joinpath(self._youtube_dl_file_name),
                self._download_file_path,
            )
            self._listener.download_complete(
                update_time=datetime.now(), handle=self._handle
            )

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
