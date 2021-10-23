from typing import Optional, Type
from datetime import timedelta, datetime
from pathlib import Path
import multiprocessing
import threading
import signal
import queue
import os

from .errors import NotSupportedError
from .download_listener import MessageBasedDownloadListener
from .download_entities import DownloadHandle, DownloadRequest
from .download_task import DownloadTaskBase, DownloadTask, YoutubeDownloadTask


class _InternalDownloadThread(threading.Thread):
    def __init__(self, task: DownloadTaskBase):
        super().__init__()
        self._task = task

    def run(self):
        self._task.run()

    def stop(self):
        self._task.stop()


class _Stop(object):
    pass


def _download_process_entrypoint(
    message_queue: multiprocessing.Queue,
    handle: DownloadHandle,
    request: DownloadRequest,
    download_file_path: Path,
    listener: MessageBasedDownloadListener,
    progress_report_interval: Optional[timedelta],
    task_type: Type,
):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    download_task = task_type(
        handle=handle,
        request=request,
        download_file_path=download_file_path,
        listener=listener,
        progress_report_interval=progress_report_interval,
    )
    download_thread = _InternalDownloadThread(download_task)
    download_thread.start()
    while True:
        try:
            message = message_queue.get(timeout=1)
            if isinstance(message, _Stop):
                download_thread.stop()
        except queue.Empty:
            pass
        download_thread.join(timeout=1)
        if not download_thread.is_alive():
            return


class DownloadProcess(object):
    def __init__(
        self,
        handle: DownloadHandle,
        message_queue: multiprocessing.Queue,
        download_process: multiprocessing.Process,
        listener: MessageBasedDownloadListener,
        supports_graceful_stop: bool,
    ):
        self._handle = handle
        self._process = download_process
        self._message_queue = message_queue
        self._listener = listener
        self._supports_graceful_stop = supports_graceful_stop

    def start(self):
        self._process.start()

    def stop(self):
        if self._supports_graceful_stop:
            return self._message_queue.put(_Stop())
        self._process.kill()
        self._process.join()
        self._listener.download_stopped(update_time=datetime.now(), handle=self._handle)

    def join(self):
        self._process.join()


def create_download_process(
    handle: DownloadHandle,
    request: DownloadRequest,
    download_file_path: Path,
    listener: MessageBasedDownloadListener,
    progress_report_interval: Optional[timedelta] = None,
) -> DownloadProcess:
    message_queue = multiprocessing.Queue()
    task_type = (
        YoutubeDownloadTask
        if "youtube.com" in request.remote_file_url
        else DownloadTask
    )
    return DownloadProcess(
        handle=handle,
        message_queue=message_queue,
        listener=listener,
        supports_graceful_stop=task_type.supports_graceful_stop,
        download_process=multiprocessing.Process(
            target=_download_process_entrypoint,
            daemon=True,
            args=(
                message_queue,
                handle,
                request,
                download_file_path,
                listener,
                progress_report_interval,
                task_type,
            ),
        ),
    )
