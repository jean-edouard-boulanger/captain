from typing import Optional, Type
from datetime import timedelta, datetime
from pathlib import Path
import multiprocessing
import threading
import signal
import queue

from .logging import get_logger
from .download_listener import MessageBasedDownloadListener
from .download_entities import DownloadHandle, DownloadRequest
from .download_task import DownloadTaskBase, DownloadTask, YoutubeDownloadTask


logger = get_logger()


class _InternalDownloadThread(threading.Thread):
    def __init__(self, task: DownloadTaskBase):
        super().__init__(daemon=False)
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
            message = message_queue.get(timeout=0.5)
            if isinstance(message, _Stop):
                download_thread.stop()
        except queue.Empty:
            pass
        download_thread.join(timeout=0.5)
        if not download_thread.is_alive():
            return


class DownloadProcessWrapper(object):
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

    @property
    def pid(self) -> int:
        return self._process.pid

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def kill(self) -> None:
        logger.info(f"killing child process pid={self.pid} handle='{self._handle}'")
        self._process.kill()

    def start(self) -> None:
        logger.info(f"starting child process pid={self.pid} handle='{self._handle}'")
        self._process.start()

    def stop(self) -> None:
        if self._supports_graceful_stop and self._process.is_alive():
            logger.info(f"gracefully stopping child download process pid={self.pid} handle='{self._handle}'")
            self._message_queue.put(_Stop())
            return
        if self._process.is_alive():
            logger.warning(f"child process pid={self.pid} handle='{self._handle}' does not support"
                           f" graceful stop, killing subprocess")
            self.kill()
        self.join()
        self._listener.download_stopped(update_time=datetime.now(), handle=self._handle)

    def join(self):
        logger.info(f"joining child process pid={self.pid} handle='{self._handle}'")
        self._process.join()


def create_download_process(
    handle: DownloadHandle,
    request: DownloadRequest,
    download_file_path: Path,
    listener: MessageBasedDownloadListener,
    progress_report_interval: Optional[timedelta] = None,
) -> DownloadProcessWrapper:
    message_queue = multiprocessing.Queue()
    task_type = (
        YoutubeDownloadTask
        if "youtube.com" in request.remote_file_url
        else DownloadTask
    )
    return DownloadProcessWrapper(
        handle=handle,
        message_queue=message_queue,
        listener=listener,
        supports_graceful_stop=task_type.supports_graceful_stop,
        download_process=multiprocessing.Process(
            target=_download_process_entrypoint,
            daemon=False,
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
