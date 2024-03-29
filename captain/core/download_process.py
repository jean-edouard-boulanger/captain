import multiprocessing
import os
import queue
import signal
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypeAlias

from .constants import DEFAULT_PROGRESS_REPORT_INTERVAL
from .domain import DownloadHandle, DownloadMetadata, DownloadRequest
from .download_listener import MessageBasedDownloadListener
from .download_task import DownloadTaskBase
from .download_task_http import HttpDownloadTask
from .download_task_torrent import TorrentDownloadTask
from .download_task_youtube import YoutubeDownloadTask
from .helpers import make_kwargs, set_thread_name
from .logging import get_logger

logger = get_logger()


class _InternalDownloadThread(threading.Thread):
    def __init__(self, thread_name: str, task: DownloadTaskBase):
        self._thread_name = thread_name
        super().__init__(daemon=False, name=thread_name)
        self._task = task

    def run(self):
        set_thread_name(self._thread_name)
        self._task.run()

    def stop(self):
        self._task.stop()


class _Stop:
    pass


DownloadTaskType: TypeAlias = HttpDownloadTask | YoutubeDownloadTask | TorrentDownloadTask


def _download_process_entrypoint(
    message_queue: multiprocessing.Queue,
    handle: DownloadHandle,
    download_request: DownloadRequest,
    existing_metadata: DownloadMetadata | None,
    work_dir: Path,
    listener: MessageBasedDownloadListener,
    progress_report_interval: timedelta,
    task_type: type[DownloadTaskType],
) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    assert work_dir.is_dir()
    os.chdir(work_dir)
    download_task = task_type(
        handle=handle,
        download_request=download_request.download_method,
        existing_metadata=existing_metadata,
        work_dir=work_dir,
        listener=listener,
        progress_report_interval=progress_report_interval,
    )
    thread_name = f"{task_type.__name__}-{handle}"
    download_thread = _InternalDownloadThread(thread_name, download_task)
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


class DownloadProcessWrapper:
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
        logger.warning(f"killing download child process pid={self.pid} handle='{self._handle}'")
        self._process.kill()

    def start(self) -> None:
        self._process.start()
        logger.info(f"started download child process pid={self.pid} handle='{self._handle}'")

    def stop(self) -> None:
        graceful = self._supports_graceful_stop
        logger.info(f"stopping download child process pid={self.pid} handle={self._handle} graceful={graceful}")
        if graceful and self._process.is_alive():
            self._message_queue.put(_Stop())
        elif self._process.is_alive():
            self.kill()
        self.join()
        self._listener.download_stopped(update_time=datetime.now(), handle=self._handle)

    def join(self):
        logger.info(f"joining download child process pid={self.pid} handle='{self._handle}'")
        self._process.join()


def get_download_task_type(download_request: DownloadRequest) -> type[DownloadTaskType]:
    tasks_mapping = {"http": HttpDownloadTask, "youtube": YoutubeDownloadTask, "torrent": TorrentDownloadTask}
    download_method = download_request.download_method.method
    task_type = tasks_mapping.get(download_method)
    if not task_type:
        raise ValueError(f"unsupported task type: {download_method}")
    return task_type


def create_download_process(
    handle: DownloadHandle,
    download_request: DownloadRequest,
    existing_metadata: DownloadMetadata | None,
    work_dir: Path,
    listener: MessageBasedDownloadListener,
    progress_report_interval: timedelta = DEFAULT_PROGRESS_REPORT_INTERVAL,
) -> DownloadProcessWrapper:
    logger.info(
        "creating download process for"
        f" handle={handle}"
        f" download_request={download_request}"
        f" existing_metadata={existing_metadata}"
        f" work_dir={work_dir}"
    )
    message_queue = multiprocessing.Queue()
    task_type = get_download_task_type(download_request)
    return DownloadProcessWrapper(
        handle=handle,
        message_queue=message_queue,
        listener=listener,
        supports_graceful_stop=task_type.supports_graceful_stop,
        download_process=multiprocessing.Process(
            target=_download_process_entrypoint,
            daemon=False,
            kwargs=make_kwargs(
                message_queue=message_queue,
                handle=handle,
                download_request=download_request,
                existing_metadata=existing_metadata,
                work_dir=work_dir,
                listener=listener,
                progress_report_interval=progress_report_interval,
                task_type=task_type,
            ),
        ),
    )
