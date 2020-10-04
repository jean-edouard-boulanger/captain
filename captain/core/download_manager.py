from .download_request import DownloadRequest, DataRange
from .download_task import ThreadedDownloadTask
from .download_handle import DownloadHandle
from .download_sink import FileDownloadSink
from .download_task import DownloadTask
from .download_listener import DownloadListenerBase
from .download_metadata import DownloadMetadata
from .invariant import invariant, required_value
from .error_info import ErrorInfo
from .future import Future

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Tuple, List, Protocol
from pathlib import Path
from queue import Queue
import traceback
import shutil
import queue
import logging
import enum
import threading
import os

logger = logging.getLogger("manager")


class _DownloadStatus(enum.Enum):
    PENDING = enum.auto()
    ACTIVE = enum.auto()
    PAUSED = enum.auto()
    COMPLETE = enum.auto()
    STOPPED = enum.auto()
    ERROR = enum.auto()


@dataclass
class _DownloadState:
    metadata: Optional[DownloadMetadata] = None
    downloaded_bytes: Optional[int] = None
    current_rate: Optional[float] = None
    status: _DownloadStatus = _DownloadStatus.PENDING
    requested_status: Optional[_DownloadStatus] = None
    last_update_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_info: Optional[ErrorInfo] = None

    @property
    def is_final(self):
        return self.status in {
            _DownloadStatus.STOPPED,
            _DownloadStatus.ERROR,
            _DownloadStatus.COMPLETE
        }

    @property
    def is_inactive(self):
        return self.is_final or self.status == _DownloadStatus.PAUSED

    @property
    def can_be_resumed(self):
        return (self.status == _DownloadStatus.PAUSED
                and self.requested_status is None
                and self.metadata is not None
                and self.metadata.file_size is not None)

    @property
    def can_be_paused(self):
        return (self.status == _DownloadStatus.ACTIVE
                and self.requested_status is None)

    @property
    def can_be_stopped(self):
        return (self.status in {_DownloadStatus.ACTIVE, _DownloadStatus.PAUSED}
                and self.requested_status is None)

    @property
    def can_be_retried(self):
        return self.status in {_DownloadStatus.STOPPED, _DownloadStatus.ERROR}

    def serialize(self):
        return {
            "metadata": self.metadata.serialize() if self.metadata else None,
            "downloaded_bytes": self.downloaded_bytes,
            "current_rate": self.current_rate,
            "status": self.status.name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_info": self.error_info.serialize() if self.error_info else None,
            "properties": {
                "is_final": self.is_final,
                "is_inactive": self.is_inactive,
                "can_be_resumed": self.can_be_resumed,
                "can_be_paused": self.can_be_paused,
                "can_be_stopped": self.can_be_stopped,
                "can_be_retried": self.can_be_retried
            }
        }


@dataclass
class _Entry:
    handle: DownloadHandle
    user_request: DownloadRequest
    system_request: DownloadRequest
    task: ThreadedDownloadTask
    state: _DownloadState
    error_info: Optional[ErrorInfo] = None

    def serialize(self):
        return {
            "handle": str(self.handle),
            "user_request": self.user_request.serialize(),
            "system_request": self.system_request.serialize(),
            "state": self.state.serialize()
        }


@dataclass
class DownloadManagerSettings:
    temp_download_dir: Path
    default_download_dir: Path
    shutdown_timeout: timedelta

    def serialize(self) -> Dict:
        return {
            "temp_download_dir": str(self.temp_download_dir.absolute()),
            "default_download_dir": str(self.default_download_dir.absolute()),
            "shutdown_timeout": self.shutdown_timeout.total_seconds()
        }

    @staticmethod
    def deserialize(data) -> "DownloadManagerSettings":
        return DownloadManagerSettings(
            temp_download_dir=Path(data["temp_download_dir"]).expanduser(),
            default_download_dir=Path(data["default_download_dir"]).expanduser(),
            shutdown_timeout=timedelta(seconds=data.get("shutdown_timeout", 10))
        )


@dataclass
class _Request:
    handler: Callable
    args: Tuple[Any]
    kwargs: Dict[str, Any]
    future_result: Future


class DownloadManagerError(RuntimeError):
    pass


def _pop_queue(the_queue: Queue, timeout: timedelta):
    try:
        return the_queue.get(block=True, timeout=timeout.total_seconds())
    except queue.Empty:
        return None


def _cleanup_files(files: List[Path]):
    for current_file in files:
        logger.info(f"cleaning up: {current_file}")
        os.remove(str(current_file))


@dataclass
class _GeneralNotification:
    severity: str
    message: str

    def serialize(self):
        return {
            "severity": self.severity,
            "message": self.message
        }


class EventType(enum.Enum):
    DOWNLOAD_STARTED = enum.auto()
    METADATA_ACQUIRED = enum.auto()
    PROGRESS_CHANGED = enum.auto()
    DOWNLOAD_COMPLETE = enum.auto()
    DOWNLOAD_STOPPED = enum.auto()
    DOWNLOAD_PAUSED = enum.auto()
    DOWNLOAD_RESUMED = enum.auto()
    DOWNLOAD_ERRORED = enum.auto()
    GENERAL_NOTIFICATION = enum.auto()


@dataclass
class DownloadManagerEvent:
    event_type: EventType
    payload: Dict

    def serialize(self):
        return {
            "event_type": self.event_type.name,
            "payload": self.payload
        }


class DownloadManagerObserverBase(Protocol):
    def handle_event(self, event: DownloadManagerEvent):
        raise NotImplementedError("must implement 'handle_event'")


class DownloadManager(DownloadListenerBase):
    def __init__(self, settings: DownloadManagerSettings):
        self._settings = settings
        self._entries: Dict[DownloadHandle, _Entry] = dict()
        self._requests = Queue()
        self._stop_flag = threading.Event()
        self._observers: List[DownloadManagerObserverBase] = []

    @property
    def settings(self) -> DownloadManagerSettings:
        return self._settings

    def download_started(self,
                         update_time: datetime,
                         handle: DownloadHandle,
                         metadata: DownloadMetadata):
        return self._queue_request(
            self._handle_download_started,
            args=(update_time, handle, metadata))

    def progress_changed(self,
                         update_time: datetime,
                         handle: DownloadHandle,
                         downloaded_bytes: float,
                         average_rate: float):
        return self._queue_request(
            self._handle_progress_changed,
            args=(update_time, handle, downloaded_bytes, average_rate))

    def download_complete(self,
                          update_time: datetime,
                          handle: DownloadHandle):
        return self._queue_request(
            self._handle_download_complete,
            args=(update_time, handle))

    def download_stopped(self,
                         update_time: datetime,
                         handle: DownloadHandle):
        return self._queue_request(
            self._handle_download_stopped,
            args=(update_time, handle))

    def download_errored(self,
                         update_time: datetime,
                         handle: DownloadHandle,
                         error_info: ErrorInfo):
        return self._queue_request(
            self._handle_download_errored,
            args=(update_time, handle, error_info))

    def start_download(self,
                       request: DownloadRequest,
                       blocking: Optional[bool] = False):
        self._check_takes_requests()
        return self._queue_request(
            self._handle_start_download,
            args=(request, ), blocking=blocking)

    def stop_download(self,
                      handle: DownloadHandle,
                      blocking: Optional[bool] = False):
        self._check_takes_requests()
        return self._queue_request(
            self._handle_stop_download,
            args=(handle, ), blocking=blocking)

    def pause_download(self,
                       handle: DownloadHandle,
                       blocking: Optional[bool] = False):
        self._check_takes_requests()
        return self._queue_request(
            self._handle_pause_download,
            args=(handle, ), blocking=blocking)

    def resume_download(self,
                        handle: DownloadHandle,
                        blocking: Optional[bool] = False):
        self._check_takes_requests()
        return self._queue_request(
            self._handle_resume_download,
            args=(handle, ), blocking=blocking)

    def remove_download(self,
                        handle: DownloadHandle,
                        blocking: Optional[bool] = False):
        self._check_takes_requests()
        return self._queue_request(
            self._handle_remove_download,
            args=(handle, ), blocking=blocking)

    def get_download(self,
                     handle: DownloadHandle,
                     blocking: Optional[bool] = False):
        self._check_takes_requests()
        return self._queue_request(
            self._handle_get_download,
            args=(handle, ), blocking=blocking)

    def get_downloads(self,
                      blocking: Optional[bool] = False):
        self._check_takes_requests()
        return self._queue_request(
            self._handle_get_downloads,
            blocking=blocking)

    def retry_download(self,
                       handle: DownloadHandle,
                       blocking: Optional[bool] = False):
        self._check_takes_requests()
        return self._queue_request(
            self._handle_retry_download,
            args=(handle, ), blocking=blocking)

    def add_observer(self, observer: DownloadManagerObserverBase):
        self._check_takes_requests()
        self._observers.append(observer)

    def _handle_start_download(self, request: DownloadRequest) -> DownloadHandle:
        handle = DownloadHandle.make()
        invariant(handle not in self._entries)
        system_request = DownloadRequest(
            request.remote_file_url,
            self._settings.temp_download_dir,
            f"{handle}.captain",
            request.auth)
        tmp_file_path = system_request.local_dir / system_request.local_file_name
        invariant(not tmp_file_path.exists())
        sink = FileDownloadSink(tmp_file_path, open_mode="wb")
        task = ThreadedDownloadTask(DownloadTask(handle, system_request, sink, listener=self))
        entry = _Entry(handle, request, system_request, task, _DownloadState())
        self._entries[handle] = entry
        entry.task.start()
        return handle

    def _handle_retry_download(self, handle: DownloadHandle):
        if handle not in self._entries:
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        entry = self._entries[handle]
        if not entry.state.can_be_retried:
            raise DownloadManagerError(f"cannot retry download")
        entry.state = _DownloadState()
        system_request = entry.system_request
        tmp_file_path = system_request.local_dir / system_request.local_file_name
        sink = FileDownloadSink(tmp_file_path, open_mode="wb")
        entry.task = ThreadedDownloadTask(DownloadTask(handle, system_request, sink, listener=self))
        entry.task.start()

    def _handle_stop_download(self, handle: DownloadHandle) -> None:
        if handle not in self._entries:
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        entry = self._entries[handle]
        if not entry.state.can_be_stopped:
            raise DownloadManagerError("cannot stop task")
        entry.state.last_update_time = datetime.now()
        if entry.task is None:
            invariant(entry.state.status == _DownloadStatus.PAUSED)
            entry.state.requested_status = _DownloadStatus.STOPPED
            return self._handle_download_stopped(datetime.now(), handle)
        entry.task.stop()
        entry.state.requested_status = _DownloadStatus.STOPPED

    def _handle_pause_download(self, handle: DownloadHandle):
        if handle not in self._entries:
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        entry = self._entries[handle]
        if not entry.state.can_be_paused:
            raise DownloadManagerError("cannot pause task")
        entry.task.stop()
        entry.state.requested_status = _DownloadStatus.PAUSED
        entry.state.last_update_time = datetime.now()

    def _handle_resume_download(self, handle: DownloadHandle):
        if handle not in self._entries:
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        entry = self._entries[handle]
        if not entry.state.can_be_resumed:
            raise DownloadManagerError("cannot resume task")
        entry.state.requested_status = _DownloadStatus.ACTIVE
        system_request = entry.system_request
        tmp_file_path = system_request.local_dir / system_request.local_file_name
        invariant(tmp_file_path.is_file())
        entry.state.downloaded_bytes = tmp_file_path.stat().st_size
        sink = FileDownloadSink(tmp_file_path, open_mode="ab")
        system_request.data_range = DataRange(entry.state.downloaded_bytes)
        entry.task = ThreadedDownloadTask(DownloadTask(handle, system_request, sink, listener=self))
        entry.task.start()
        logger.info(f"resuming task {handle} from byte {entry.state.downloaded_bytes}")

    def _handle_remove_download(self, handle: DownloadHandle):
        if handle not in self._entries:
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        del self._entries[handle]
        logger.debug(f"removed task: {handle}")

    def _handle_get_download(self, handle: DownloadHandle) -> Dict:
        if handle not in self._entries:
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        entry = self._entries[handle]
        return entry.serialize()

    def _handle_get_downloads(self) -> List[Dict]:
        return [entry.serialize() for entry in self._entries.values()]

    def _handle_download_started(self,
                                 update_time: datetime,
                                 handle: DownloadHandle,
                                 metadata: DownloadMetadata) -> None:
        invariant(handle in self._entries)
        entry = self._entries[handle]
        invariant(entry.state.metadata is None or entry.state.status == _DownloadStatus.PAUSED)
        invariant(entry.state.start_time is None or entry.state.status == _DownloadStatus.PAUSED)
        invariant(entry.state.status in {_DownloadStatus.PENDING, _DownloadStatus.PAUSED})
        if entry.state.status == _DownloadStatus.PENDING:
            logger.debug(f"task status is pending, setting metadata: {metadata}")
            entry.state.metadata = metadata
            entry.state.start_time = datetime.now()
        entry.state.last_update_time = update_time
        entry.state.status = _DownloadStatus.ACTIVE
        entry.state.requested_status = None
        self._notify_observers(EventType.DOWNLOAD_STARTED, entry.serialize())
        logger.debug(f"download {handle} started: {metadata.serialize()}")

    def _handle_download_errored(self,
                                 update_time: datetime,
                                 handle: DownloadHandle,
                                 error_info: ErrorInfo) -> None:
        invariant(handle in self._entries)
        entry = self._entries[handle]
        entry.state.status = _DownloadStatus.ERROR
        entry.state.end_time = datetime.now()
        entry.state.last_update_time = update_time
        entry.state.error_info = error_info
        self._notify_observers(EventType.DOWNLOAD_ERRORED, entry.serialize())
        logger.debug(f"download {handle} errored: {error_info.serialize()}")

    def _handle_download_complete(self,
                                  update_time: datetime,
                                  handle: DownloadHandle) -> None:
        invariant(handle in self._entries)
        entry = self._entries[handle]
        entry.task.join()
        entry.task = None
        invariant(entry.state.downloaded_bytes == entry.state.metadata.file_size)
        local_dir = Path(entry.user_request.local_dir or os.getcwd())
        local_file_name = entry.user_request.local_file_name or entry.state.metadata.remote_file_name
        temp_file_path = entry.system_request.local_dir / entry.system_request.local_file_name
        dest_file_path = local_dir / local_file_name
        logger.info(f"moving temporary file {temp_file_path} to {dest_file_path}")
        shutil.move(str(temp_file_path), str(dest_file_path))
        entry.state.status = _DownloadStatus.COMPLETE
        entry.state.end_time = datetime.now()
        entry.state.last_update_time = update_time
        self._notify_observers(EventType.DOWNLOAD_COMPLETE, entry.serialize())
        logger.info(f"task {handle} complete")

    def _handle_download_stopped(self,
                                 update_time: datetime,
                                 handle: DownloadHandle) -> None:
        invariant(handle in self._entries)
        entry = self._entries[handle]
        invariant(entry.task is not None or entry.state.status == _DownloadStatus.PAUSED)
        if entry.task is not None:
            entry.task.join()
            entry.task = None
        requested_status = entry.state.requested_status
        invariant(requested_status is not None)
        invariant(requested_status in {_DownloadStatus.STOPPED, _DownloadStatus.PAUSED})
        entry.state.last_update_time = update_time
        entry.state.status = requested_status
        entry.state.requested_status = None
        entry.state.end_time = update_time
        if requested_status == _DownloadStatus.STOPPED:
            files = [entry.system_request.local_dir / entry.system_request.local_file_name]
            self._queue_request(_cleanup_files, args=(files, ))
        self._notify_observers(required_value(requested_status), entry.serialize())

    def _handle_progress_changed(self,
                                 update_time: datetime,
                                 handle: DownloadHandle,
                                 downloaded_bytes: int,
                                 average_rate: float) -> None:
        invariant(handle in self._entries)
        invariant(isinstance(downloaded_bytes, int))
        entry = self._entries[handle]
        entry.state.current_rate = average_rate
        if entry.state.downloaded_bytes is None:
            entry.state.downloaded_bytes = 0
        entry.state.downloaded_bytes += downloaded_bytes
        entry.state.last_update_time = update_time
        self._notify_observers(EventType.PROGRESS_CHANGED, entry.serialize())
        logger.debug(f"progress for task {handle} changed: {downloaded_bytes} bytes")

    def _queue_request(self,
                       handler: Callable,
                       args: Optional[Tuple] = None,
                       kwargs: Optional[Dict[str, Any]] = None,
                       blocking: Optional[bool] = False):
        args = args or ()
        kwargs = kwargs or {}
        request = _Request(handler, args, kwargs, Future())
        logger.debug(f"queuing request: {request}")
        self._requests.put(request)
        if blocking:
            return request.future_result.get()
        return request.future_result

    def _stop_outstanding_tasks(self):
        for entry in self._entries.values():
            if entry.state.can_be_paused:
                logger.info(f"pausing task {entry.handle}")
                self._queue_request(self._handle_pause_download, args=(entry.handle, ))
            elif entry.state.can_be_stopped:
                logger.info(f"stopping task {entry.handle}")
                self._queue_request(self._handle_stop_download, args=(entry.handle, ))
            else:
                invariant(entry.state.is_final)

    def _check_takes_requests(self):
        if self._stop_flag.is_set():
            raise DownloadManagerError("download manager is stopping,"
                                       " public interface is disabled")

    def _request_loop(self):
        shutdown_at: Optional[datetime] = None
        while True:
            if self._stop_flag.is_set() and shutdown_at is None:
                logger.info("shutdown requested, stopping all outstanding tasks")
                self._stop_outstanding_tasks()
                shutdown_at = datetime.now() + self._settings.shutdown_timeout
                logger.info(f"will force shutdown at {shutdown_at}")
            elif self._stop_flag.is_set() and shutdown_at is not None:
                all_inactive = all(entry.state.is_inactive for entry in self._entries.values())
                if all_inactive:
                    logger.info("all tasks inactive, leaving request loop")
                    return
                if datetime.now() >= shutdown_at:
                    logger.info("shutdown timeout expired, leaving forcefully")
                    return
            request: Optional[_Request] = _pop_queue(self._requests, timedelta(milliseconds=500))
            if request is None:
                continue
            try:
                logger.debug(f"request start: {request}")
                result = request.handler(*request.args, **request.kwargs)
                request.future_result.set_result(result)
                logger.debug(f"request end [success]: {result}")
            except Exception as e:
                logger.error(f"failure while executing request {request}: {e}\n{traceback.format_exc()}")
                notification = _GeneralNotification("error", str(e))
                self._notify_observers(EventType.GENERAL_NOTIFICATION, notification.serialize())
                request.future_result.set_error(e)
                logger.debug(f"request end [failure]: {e}")

    def _notify_observers(self, *args, **kwargs):
        for observer in self._observers:
            observer.handle_event(DownloadManagerEvent(*args, **kwargs))

    def stop(self):
        logger.info("stopping download manager")
        self._stop_flag.set()

    def run(self):
        self._request_loop()
