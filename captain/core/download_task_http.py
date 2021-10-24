from .logging import get_logger
from .download_task import DownloadTaskBase
from .download_listener import DownloadListenerBase, NoOpDownloadListener
from .domain import (
    DownloadRequest,
    DownloadMetadata,
    DownloadHandle,
    DataRange,
    ErrorInfo,
)

from requests.auth import HTTPBasicAuth, HTTPProxyAuth, HTTPDigestAuth
import requests.exceptions
import requests

from typing import Optional, List, Union, Dict, Any, BinaryIO
from dataclasses import dataclass
from urllib.parse import urlparse, unquote
from threading import Event
from datetime import datetime, timedelta
from pathlib import Path
import traceback
import os


logger = get_logger()


CHUNK_SIZE = 8192


def _get_next_chunk(download_iter):
    try:
        return next(download_iter)
    except StopIteration:
        return None


def _make_range_header(rng: DataRange):
    return f"bytes={rng.first_byte or 0}-{rng.last_byte or str()}"


def _format_error(e: Exception):
    default_error = "network error"
    logger.info(type(e))
    if isinstance(e, requests.exceptions.RequestException):
        if e.response is None:
            return default_error
        response: requests.Response = e.response
        if response.status_code == 404:
            return "remote resource does not exist"
        if response.status_code == 401:
            return "not authorized to download resource"
    return default_error


AuthMethod = Union[HTTPBasicAuth, HTTPProxyAuth, HTTPDigestAuth]


def _parse_auth_payload(data: Optional[Dict[str, Any]]) -> Optional[AuthMethod]:
    if data is None:
        return None
    if "basic" in data:
        data = data["basic"]
        return HTTPBasicAuth(data["username"], data["password"])
    if "proxy" in data:
        data = data["proxy"]
        return HTTPProxyAuth(data["username"], data["password"])
    if "digest" in data:
        data = data["digest"]
        return HTTPDigestAuth(data["username"], data["password"])
    raise ValueError(
        f"'{list(data.keys())[0]}' is not a supported authentication strategy"
    )


@dataclass
class ProgressSlice:
    start_time: datetime
    end_time: Optional[datetime] = None
    total_bytes: int = 0


class ProgressManager(object):
    def __init__(self):
        self.progress: List[ProgressSlice] = []

    def report_progress(self, total_bytes: float):
        self.progress[-1].total_bytes += total_bytes

    def next_slice(self):
        if len(self.progress) > 0:
            self.progress[-1].end_time = datetime.now()
        self.progress.append(ProgressSlice(datetime.now()))

    @property
    def current_rate(self) -> float:
        current_slice = self.progress[-1]
        time_diff = float((datetime.now() - current_slice.start_time).total_seconds())
        return current_slice.total_bytes / time_diff

    @property
    def current_bytes(self) -> int:
        return self.progress[-1].total_bytes

    @property
    def total_bytes(self):
        return sum(p.total_bytes for p in self.progress)


class HttpDownloadTask(DownloadTaskBase):
    supports_graceful_stop = True

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
        self._download_file_path = download_file_path
        self._listener = listener or NoOpDownloadListener()
        self._stopped_flag = Event()
        self._progress_report_interval = progress_report_interval or timedelta(
            seconds=1
        )

    def _download_loop_impl(
        self, request: requests.Response, download_buffer: BinaryIO
    ):
        download_iter = request.iter_content(chunk_size=CHUNK_SIZE)
        progress_manager = ProgressManager()
        progress_manager.next_slice()
        next_report_cutoff = datetime.now() + self._progress_report_interval
        self._listener.progress_changed(datetime.now(), self._handle, 0, 0.0)
        while True:
            if self._stopped_flag.is_set():
                self._listener.download_stopped(datetime.now(), self._handle)
                return
            next_chunk = _get_next_chunk(download_iter)
            progress_manager.report_progress(len(next_chunk) if next_chunk else 0)
            is_complete = next_chunk is None
            if datetime.now() >= next_report_cutoff or is_complete:
                next_report_cutoff += self._progress_report_interval
                self._listener.progress_changed(
                    datetime.now(),
                    self._handle,
                    progress_manager.current_bytes,
                    progress_manager.current_rate,
                )
                progress_manager.next_slice()
            if is_complete:
                self._listener.download_complete(datetime.now(), self._handle)
                return
            download_buffer.write(next_chunk)

    def _download_loop(self, response: requests.Response) -> None:
        try:
            with self._download_file_path.open("ab") as f:
                self._download_loop_impl(response, f)
        except Exception as e:
            logger.error(f"while downloading file: {e}\n{traceback.format_exc()}")
            self._listener.download_errored(
                datetime.now(),
                self._handle,
                ErrorInfo(
                    message=f"Could not download '{self._request.remote_file_name}': {_format_error(e)}",
                    stack=traceback.format_exc(),
                ),
            )

    def run_impl(self):
        settings = self._request
        url_meta = urlparse(settings.remote_file_url)
        remote_file_name = unquote(os.path.basename(url_meta.path))
        download_metadata = DownloadMetadata(
            remote_file_name=remote_file_name, remote_url=settings.remote_file_url
        )
        request_settings = {"verify": False, "stream": True, "headers": {}}
        if settings.auth_payload:
            request_settings["auth"] = _parse_auth_payload(settings.auth_payload)
        if settings.data_range:
            request_settings["headers"]["Range"] = _make_range_header(
                settings.data_range
            )
        with requests.get(settings.remote_file_url, **request_settings) as response:
            response.raise_for_status()
            headers = response.headers
            logger.debug(f"received headers: {headers}")
            raw_file_size = headers.get("Content-Length")
            download_metadata.file_size = int(raw_file_size) if raw_file_size else None
            download_metadata.file_type = headers.get("Content-Type")
            download_metadata.accept_ranges = headers.get("Accept-Ranges") == "bytes"
            self._listener.download_started(
                datetime.now(), self._handle, download_metadata
            )
            self._download_loop(response)

    def run(self):
        try:
            self.run_impl()
        except Exception as e:
            logger.error(f"while initializing download: {e}\n{traceback.format_exc()}")
            self._listener.download_errored(
                datetime.now(),
                self._handle,
                ErrorInfo(
                    message=f"Could not download '{self._request.remote_file_name}': {_format_error(e)}",
                    stack=traceback.format_exc(),
                ),
            )

    def stop(self):
        logger.info(f"task {self._handle} requested to stop")
        self._stopped_flag.set()
