from .download_persistence import get_persistence, PersistenceType
from .download_task import ThreadedDownloadTask
from .download_sink import FileDownloadSink
from .download_task import DownloadTask
from .download_listener import DownloadListenerBase
from .scheduler import Scheduler, ThreadedScheduler
from .download_entities import (
    DownloadState,
    DownloadStatus,
    DownloadMetadata,
    DownloadRequest,
    DownloadEntry,
    DownloadHandle,
    ErrorInfo,
    DataRange,
)
from .invariant import invariant, required_value
from .future import Future

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Tuple, List, Protocol
from functools import partial
from pathlib import Path
from queue import Queue
import traceback
import shutil
import queue
import logging
import enum
import threading
import pytz
import os

logger = logging.getLogger("manager")


@dataclass
class DownloadDirectory:
    directory: Path
    label: str

    def serialize(self):
        return {
            "directory": str(self.directory),
            "label": self.label
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["DownloadDirectory"]:
        if data is None:
            return None
        return DownloadDirectory(
            directory=Path(data["directory"]).expanduser(),
            label=data["label"]
        )


@dataclass
class DownloadManagerSettings:
    temp_download_dir: Path
    download_directories: List[DownloadDirectory]
    shutdown_timeout: timedelta
    persistence_type: PersistenceType
    persistence_settings: Dict

    def serialize(self) -> Dict:
        return {
            "temp_download_dir": str(self.temp_download_dir.absolute()),
            "download_directories": [dd.serialize() for dd in self.download_directories],
            "shutdown_timeout": self.shutdown_timeout.total_seconds(),
            "persistence_type": str(self.persistence_type),
            "persistence_settings": self.persistence_settings
        }

    @staticmethod
    def deserialize(data) -> "DownloadManagerSettings":
        return DownloadManagerSettings(
            temp_download_dir=Path(data.get("temp_download_dir", "/tmp")).expanduser(),
            download_directories=[DownloadDirectory.deserialize(item) for item in data["download_directories"]],
            shutdown_timeout=timedelta(seconds=data.get("shutdown_timeout", 10)),
            persistence_type=PersistenceType[data.get("persistence_type", "IN_MEMORY")],
            persistence_settings=data.get("persistence_settings", {})
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
    DOWNLOAD_SCHEDULED = enum.auto()
    DOWNLOAD_STARTED = enum.auto()
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
        self._db = get_persistence(settings.persistence_type, **settings.persistence_settings)
        self._tasks: Dict[DownloadHandle, ThreadedDownloadTask] = dict()
        self._requests = Queue()
        self._stop_flag = threading.Event()
        self._observers: List[DownloadManagerObserverBase] = []
        self._scheduler = ThreadedScheduler(Scheduler())
        for entry in self._db.get_all_entries():
            if entry.user_request.start_at is not None and entry.state.status == DownloadStatus.SCHEDULED:
                self._scheduler.schedule_unsafe(
                    at=entry.user_request.start_at,
                    action=partial(
                        self._queue_request,
                        handler=self._handle_start_download,
                        args=(entry.handle, )))

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
        self._check_enabled()
        return self._queue_request(
            self._handle_schedule_download,
            args=(request, ), blocking=blocking)

    def reschedule_download(self,
                            handle: DownloadHandle,
                            start_at: datetime):
        self._check_enabled()
        return self._queue_request(
            self._handle_reschedule_download,
            args=(handle, start_at))

    def stop_download(self,
                      handle: DownloadHandle,
                      blocking: Optional[bool] = False):
        self._check_enabled()
        return self._queue_request(
            self._handle_stop_download,
            args=(handle, ), blocking=blocking)

    def pause_download(self,
                       handle: DownloadHandle,
                       blocking: Optional[bool] = False):
        self._check_enabled()
        return self._queue_request(
            self._handle_pause_download,
            args=(handle, ), blocking=blocking)

    def resume_download(self,
                        handle: DownloadHandle,
                        blocking: Optional[bool] = False):
        self._check_enabled()
        return self._queue_request(
            self._handle_resume_download,
            args=(handle, ), blocking=blocking)

    def remove_download(self,
                        handle: DownloadHandle,
                        blocking: Optional[bool] = False):
        self._check_enabled()
        return self._queue_request(
            self._handle_remove_download,
            args=(handle, ), blocking=blocking)

    def get_download(self,
                     handle: DownloadHandle,
                     blocking: Optional[bool] = False):
        self._check_enabled()
        return self._queue_request(
            self._handle_get_download,
            args=(handle, ), blocking=blocking)

    def get_downloads(self,
                      blocking: Optional[bool] = False):
        self._check_enabled()
        return self._queue_request(
            self._handle_get_downloads,
            blocking=blocking)

    def retry_download(self,
                       handle: DownloadHandle,
                       blocking: Optional[bool] = False):
        self._check_enabled()
        return self._queue_request(
            self._handle_retry_download,
            args=(handle, ), blocking=blocking)

    def add_observer(self, observer: DownloadManagerObserverBase):
        self._check_enabled()
        self._observers.append(observer)

    def _handle_schedule_download(self, request: DownloadRequest) -> DownloadHandle:
        handle = DownloadHandle.make()
        invariant(not self._db.has_entry(handle))
        entry = DownloadEntry(
            handle=handle,
            user_request=request,
            system_request=None,
            state=DownloadState(status=DownloadStatus.SCHEDULED))
        start_at = request.start_at if request.start_at else datetime.now(pytz.utc)
        schedule_handle = self._defer_request(
            start_at,
            self._handle_start_download,
            args=(handle, ))
        logger.debug(f"got handle {schedule_handle} for scheduled event")
        entry.state.schedule_handle = schedule_handle
        self._db.persist_entry(entry)
        self._notify_observers(EventType.DOWNLOAD_SCHEDULED, entry.serialize())
        return handle

    def _handle_reschedule_download(self, handle: DownloadHandle, start_at: datetime):
        if not self._db.has_entry(handle):
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        with self._db.scoped_entry(handle) as entry:
            if not entry.state.can_be_rescheduled:
                raise DownloadManagerError(f"cannot reschedule download")
            invariant(entry.state.schedule_handle is not None)
            self._scheduler.cancel(entry.state.schedule_handle)
            entry.state.schedule_handle = self._defer_request(
                start_at,
                self._handle_start_download,
                args=(handle,))
        self._notify_observers(EventType.DOWNLOAD_SCHEDULED, entry.serialize())

    def _handle_start_download(self, handle: DownloadHandle) -> DownloadHandle:
        invariant(self._db.has_entry(handle))
        invariant(handle not in self._tasks)
        with self._db.scoped_entry(handle) as entry:
            invariant(entry.system_request is None)
            system_request = DownloadRequest(
                remote_file_url=entry.user_request.remote_file_url,
                local_dir=self._settings.temp_download_dir,
                local_file_name=f"{handle}.captain",
                auth=entry.user_request.auth)
            entry.state.schedule_handle = None
            entry.system_request = system_request
            entry.state.status = DownloadStatus.PENDING
            tmp_file_path = system_request.local_dir / system_request.local_file_name
            invariant(not tmp_file_path.exists())
            sink = FileDownloadSink(tmp_file_path, open_mode="wb")
            download_task = DownloadTask(handle, system_request, sink, listener=self)
            self._tasks[handle] = ThreadedDownloadTask(download_task)
            self._tasks[handle].start()
            return handle

    def _handle_retry_download(self, handle: DownloadHandle):
        if not self._db.has_entry(handle):
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        with self._db.scoped_entry(handle) as entry:
            if not entry.state.can_be_retried:
                raise DownloadManagerError(f"cannot retry download")
            entry.state = DownloadState(status=DownloadStatus.PENDING)
            if not entry.system_request:
                entry.system_request = DownloadRequest(
                    remote_file_url=entry.user_request.remote_file_url,
                    local_dir=self._settings.temp_download_dir,
                    local_file_name=f"{handle}.captain",
                    auth=entry.user_request.auth)
            system_request = entry.system_request
            tmp_file_path = system_request.local_dir / system_request.local_file_name
            sink = FileDownloadSink(tmp_file_path, open_mode="wb")
            invariant(handle not in self._tasks)
            self._tasks[handle] = ThreadedDownloadTask(DownloadTask(handle, system_request, sink, listener=self))
            self._tasks[handle].start()

    def _handle_stop_download(self, handle: DownloadHandle) -> None:
        if not self._db.has_entry(handle):
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        with self._db.scoped_entry(handle) as entry:
            if not entry.state.can_be_stopped:
                raise DownloadManagerError("cannot stop task")
            entry.state.last_update_time = datetime.now()
            if entry.state.schedule_handle is not None:
                self._scheduler.cancel(entry.state.schedule_handle)
                entry.state.schedule_handle = None
            task = self._tasks.get(handle)
            if task is None:
                invariant(entry.state.status in {DownloadStatus.PAUSED, DownloadStatus.SCHEDULED})
                entry.state.requested_status = DownloadStatus.STOPPED
                return self._handle_download_stopped(datetime.now(), handle)
            task.stop()
            entry.state.requested_status = DownloadStatus.STOPPED

    def _handle_pause_download(self, handle: DownloadHandle):
        if not self._db.has_entry(handle):
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        with self._db.scoped_entry(handle) as entry:
            if not entry.state.can_be_paused:
                raise DownloadManagerError("cannot pause task")
            invariant(handle in self._tasks)
            task = self._tasks[handle]
            task.stop()
            entry.state.requested_status = DownloadStatus.PAUSED
            entry.state.last_update_time = datetime.now()

    def _handle_resume_download(self, handle: DownloadHandle):
        if not self._db.has_entry(handle):
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        with self._db.scoped_entry(handle) as entry:
            if not entry.state.can_be_resumed:
                raise DownloadManagerError("cannot resume task")
            entry.state.requested_status = DownloadStatus.ACTIVE
            system_request = entry.system_request
            tmp_file_path = system_request.local_dir / system_request.local_file_name
            invariant(tmp_file_path.is_file())
            entry.state.downloaded_bytes = tmp_file_path.stat().st_size
            sink = FileDownloadSink(tmp_file_path, open_mode="ab")
            system_request.data_range = DataRange(entry.state.downloaded_bytes)
            invariant(handle not in self._tasks)
            download_task = DownloadTask(handle, system_request, sink, listener=self)
            self._tasks[handle] = ThreadedDownloadTask(download_task)
            self._tasks[handle].start()
            logger.info(f"resuming task {handle} from byte {entry.state.downloaded_bytes}")

    def _handle_remove_download(self, handle: DownloadHandle):
        if not self._db.has_entry(handle):
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        self._db.remove_entry(handle)
        logger.debug(f"removed task: {handle}")

    def _handle_get_download(self, handle: DownloadHandle) -> Dict:
        if not self._db.has_entry(handle):
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        return self._db.get_entry(handle).serialize()

    def _handle_get_downloads(self) -> List[Dict]:
        return [
            entry.serialize() for entry
            in self._db.get_all_entries()
        ]

    def _handle_download_started(self,
                                 update_time: datetime,
                                 handle: DownloadHandle,
                                 metadata: DownloadMetadata) -> None:
        invariant(self._db.has_entry(handle))
        with self._db.scoped_entry(handle) as entry:
            invariant(entry.state.metadata is None or entry.state.status == DownloadStatus.PAUSED)
            invariant(entry.state.start_time is None or entry.state.status == DownloadStatus.PAUSED)
            invariant(entry.state.status in {DownloadStatus.PENDING, DownloadStatus.PAUSED})
            if entry.state.status == DownloadStatus.PENDING:
                logger.debug(f"task status is pending, setting metadata: {metadata}")
                entry.state.metadata = metadata
                entry.state.start_time = datetime.now()
            entry.state.last_update_time = update_time
            entry.state.status = DownloadStatus.ACTIVE
            entry.state.requested_status = None
            self._notify_observers(EventType.DOWNLOAD_STARTED, entry.serialize())
            logger.debug(f"download {handle} started: {metadata.serialize()}")

    def _handle_download_errored(self,
                                 update_time: datetime,
                                 handle: DownloadHandle,
                                 error_info: ErrorInfo) -> None:
        invariant(self._db.has_entry(handle))
        invariant(handle in self._tasks)
        self._tasks[handle].join()
        del self._tasks[handle]
        with self._db.scoped_entry(handle) as entry:
            entry.state.status = DownloadStatus.ERROR
            entry.state.end_time = datetime.now()
            entry.state.last_update_time = update_time
            entry.state.error_info = error_info
            self._notify_observers(EventType.DOWNLOAD_ERRORED, entry.serialize())
            logger.warning(f"download {handle} errored: {error_info.serialize()}")

    def _handle_download_complete(self,
                                  update_time: datetime,
                                  handle: DownloadHandle) -> None:
        invariant(self._db.has_entry(handle))
        invariant(handle in self._tasks)
        self._tasks[handle].join()
        del self._tasks[handle]
        with self._db.scoped_entry(handle) as entry:
            invariant(entry.state.downloaded_bytes == entry.state.metadata.file_size)
            local_dir = Path(entry.user_request.local_dir or os.getcwd())
            local_file_name = entry.user_request.local_file_name or entry.state.metadata.remote_file_name
            temp_file_path = entry.system_request.local_dir / entry.system_request.local_file_name
            dest_file_path = local_dir / local_file_name
            logger.info(f"moving temporary file {temp_file_path} to {dest_file_path}")
            shutil.move(str(temp_file_path), str(dest_file_path))
            entry.state.status = DownloadStatus.COMPLETE
            entry.state.end_time = datetime.now()
            entry.state.last_update_time = update_time
            self._notify_observers(EventType.DOWNLOAD_COMPLETE, entry.serialize())
            logger.info(f"task {handle} complete")

    def _handle_download_stopped(self,
                                 update_time: datetime,
                                 handle: DownloadHandle) -> None:
        invariant(self._db.has_entry(handle))
        with self._db.scoped_entry(handle) as entry:
            invariant(handle in self._tasks or entry.state.status in {DownloadStatus.PAUSED, DownloadStatus.SCHEDULED})
            if handle in self._tasks is not None:
                self._tasks[handle].join()
                del self._tasks[handle]
            requested_status = entry.state.requested_status
            invariant(requested_status is not None)
            invariant(requested_status in {DownloadStatus.STOPPED, DownloadStatus.PAUSED})
            entry.state.last_update_time = update_time
            entry.state.status = requested_status
            entry.state.requested_status = None
            entry.state.end_time = update_time
            if requested_status == DownloadStatus.STOPPED and entry.system_request is not None:
                files = [entry.system_request.local_dir / entry.system_request.local_file_name]
                self._queue_request(_cleanup_files, args=(files, ))
            self._notify_observers(required_value(requested_status), entry.serialize())

    def _handle_progress_changed(self,
                                 update_time: datetime,
                                 handle: DownloadHandle,
                                 downloaded_bytes: int,
                                 average_rate: float) -> None:
        invariant(self._db.has_entry(handle))
        invariant(isinstance(downloaded_bytes, int))
        with self._db.scoped_entry(handle) as entry:
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

    def _defer_request(self,
                       start_at: datetime,
                       handler: Callable,
                       args: Optional[Tuple] = None,
                       kwargs: Optional[Dict[str, Any]] = None):
        return self._scheduler.schedule(
            at=start_at,
            action=partial(
                self._queue_request,
                handler=handler,
                args=args,
                kwargs=kwargs,
                blocking=False))

    def _stop_outstanding_tasks(self):
        for entry in self._db.get_all_entries():
            if entry.state.can_be_rescheduled:
                self._scheduler.cancel(required_value(entry.state.schedule_handle))
                entry.state.schedule_handle = None
            elif entry.state.can_be_paused:
                logger.info(f"pausing task {entry.handle}")
                self._queue_request(self._handle_pause_download, args=(entry.handle, ))
            elif entry.state.can_be_stopped:
                logger.info(f"stopping task {entry.handle}")
                self._queue_request(self._handle_stop_download, args=(entry.handle, ))

    def _check_enabled(self):
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
                all_inactive = all(not entry.state.is_active
                                   for entry in self._db.get_all_entries())
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
        logger.info("download manager requested to stop")
        self._stop_flag.set()

    def run(self):
        logger.info("download manager requested to run")
        self._scheduler.start()
        self._request_loop()
        self._scheduler.stop()
        self._scheduler.join()
        self._db.flush()
