from typing import Optional
from datetime import timedelta
from pathlib import Path
import multiprocessing
import threading

from .download_listener import MessageBasedDownloadListener
from .download_entities import DownloadHandle, DownloadRequest
from .download_task import DownloadTaskBase, DownloadTask
from .logging import get_logger

logger = get_logger()


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
):
    download_task = DownloadTask(
        handle=handle,
        request=request,
        download_file_path=download_file_path,
        listener=listener,
        progress_report_interval=progress_report_interval,
    )
    download_thread = _InternalDownloadThread(download_task)
    download_thread.start()
    while True:
        message = message_queue.get()
        if isinstance(message, _Stop):
            download_thread.stop()
            download_thread.join()
            return


class DownloadProcess(object):
    def __init__(
        self,
        message_queue: multiprocessing.Queue,
        download_process: multiprocessing.Process,
    ):
        self._process = download_process
        self._message_queue = message_queue

    def start(self):
        self._process.start()

    def stop(self):
        self._message_queue.put(_Stop())

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
    return DownloadProcess(
        message_queue=message_queue,
        download_process=multiprocessing.Process(
            target=_download_process_entrypoint,
            args=(
                message_queue,
                handle,
                request,
                download_file_path,
                listener,
                progress_report_interval,
            ),
        ),
    )
