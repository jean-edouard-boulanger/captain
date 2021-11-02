from typing import Dict, Any, Optional, Callable, Tuple, List, Union, Protocol
from datetime import datetime, timedelta
from functools import partial, wraps
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
import threading
import traceback
import shutil
import queue
import uuid
import os

from send2trash import send2trash
import pytz

from .serialization import serialize
from .logging import get_logger
from .client_view import DownloadEntry as ExternalDownloadEntry
from .persistence_factory import get_persistence
from .download_manager_settings import DownloadManagerSettings
from .download_listener import DownloadListenerBase, ThreadedDownloadListenerBridge
from .download_process import DownloadProcessWrapper, create_download_process
from .scheduler import Scheduler, ThreadedScheduler
from .errors import CaptainError
from .fs import empty_directory, remove_directory
from .domain import (
    DownloadState,
    DownloadStatus,
    DownloadMetadata,
    DownloadRequest,
    DownloadEntry,
    DownloadHandle,
    ErrorInfo,
    NotificationSeverity,
    GeneralNotification,
    EventType,
    DownloadManagerEvent,
)
from .invariant import invariant, required_value
from .future import Future


logger = get_logger()


def _make_error_reference_code() -> str:
    return f"{uuid.uuid4()}"


@dataclass
class _Request:
    handler: Callable
    args: Tuple[Any]
    kwargs: Dict[str, Any]
    future_result: Future


class DownloadManagerError(CaptainError):
    def __init__(self, error_message: str):
        super().__init__(error_message)


def _pop_queue(the_queue: Queue, timeout: timedelta):
    try:
        return the_queue.get(block=True, timeout=timeout.total_seconds())
    except queue.Empty:
        return None


def _send_file_to_trash(path: Union[Path, str]):
    if not Path(path).is_file():
        raise RuntimeError(f"{path} does not exist or is not a file")
    send2trash(str(path))


def _cleanup_files(files: List[Union[Path, str]], permanent: bool):
    assert isinstance(files, list)
    cleanup_strategy = os.remove if permanent else _send_file_to_trash
    for current_file in files:
        logger.info(
            f"cleaning up file_path={current_file} strategy={cleanup_strategy.__name__}"
        )
        try:
            cleanup_strategy(str(current_file))
        except Exception as e:
            logger.warning(
                f"failed to clean up file={str(current_file)} "
                f"with strategy={cleanup_strategy.__name__}: {e}"
            )


class DownloadManagerObserverBase(Protocol):
    def handle_event(self, event: DownloadManagerEvent):
        raise NotImplementedError("must implement 'handle_event'")


def public_endpoint(func):
    @wraps(func)
    def impl(manager_self: "DownloadManager", *args, **kwargs):
        if not manager_self.public_api_enabled:
            raise DownloadManagerError("download manager public api is disabled")
        return func(manager_self, *args, **kwargs)

    return impl


class DownloadManager(DownloadListenerBase):
    def __init__(self, settings: DownloadManagerSettings):
        self._settings = settings
        self._db = get_persistence(settings.persistence_settings)
        self._tasks: Dict[DownloadHandle, DownloadProcessWrapper] = dict()
        self._requests = Queue()
        self._stop_flag = threading.Event()
        self._observers: List[DownloadManagerObserverBase] = []
        self._scheduler = ThreadedScheduler(Scheduler())
        self._listener_bridge = ThreadedDownloadListenerBridge(self)
        for entry in self._db.get_all_entries():
            if (
                entry.user_request.start_at is not None
                and entry.state.status == DownloadStatus.SCHEDULED
            ):
                invariant(entry.state.schedule_handle is None)
                entry.state.schedule_handle = self._scheduler.schedule_unsafe(
                    at=entry.user_request.start_at,
                    action=partial(
                        self._queue_request,
                        handler=self._handle_start_download,
                        args=(entry.handle,),
                    ),
                )

    @property
    def settings(self) -> DownloadManagerSettings:
        return self._settings

    @property
    def public_api_enabled(self):
        return not self._stop_flag.is_set()

    @public_endpoint
    def start_download(
        self, request: DownloadRequest, blocking: Optional[bool] = False
    ):
        return self._queue_request(
            self._handle_schedule_download, args=(request,), blocking=blocking
        )

    @public_endpoint
    def reschedule_download(self, handle: DownloadHandle, start_at: datetime):
        return self._queue_request(
            self._handle_reschedule_download, args=(handle, start_at)
        )

    @public_endpoint
    def stop_download(self, handle: DownloadHandle, blocking: Optional[bool] = False):
        return self._queue_request(
            self._handle_stop_download, args=(handle,), blocking=blocking
        )

    @public_endpoint
    def pause_download(self, handle: DownloadHandle, blocking: Optional[bool] = False):
        return self._queue_request(
            self._handle_pause_download, args=(handle,), blocking=blocking
        )

    @public_endpoint
    def resume_download(self, handle: DownloadHandle, blocking: Optional[bool] = False):
        return self._queue_request(
            self._handle_resume_download, args=(handle,), blocking=blocking
        )

    @public_endpoint
    def remove_download(
        self,
        handle: DownloadHandle,
        delete_file: Optional[bool] = False,
        blocking: Optional[bool] = False,
    ):
        return self._queue_request(
            self._handle_remove_download, args=(handle, delete_file), blocking=blocking
        )

    @public_endpoint
    def get_download(self, handle: DownloadHandle, blocking: Optional[bool] = False):
        return self._queue_request(
            self._handle_get_download, args=(handle,), blocking=blocking
        )

    @public_endpoint
    def get_downloads(self, blocking: Optional[bool] = False):
        return self._queue_request(self._handle_get_downloads, blocking=blocking)

    @public_endpoint
    def retry_download(self, handle: DownloadHandle, blocking: Optional[bool] = False):
        return self._queue_request(
            self._handle_retry_download, args=(handle,), blocking=blocking
        )

    @public_endpoint
    def add_observer(self, observer: DownloadManagerObserverBase):
        self._observers.append(observer)

    def download_started(
        self, update_time: datetime, handle: DownloadHandle, metadata: DownloadMetadata
    ):
        return self._queue_request(
            self._handle_download_started, args=(update_time, handle, metadata)
        )

    def progress_changed(
        self,
        update_time: datetime,
        handle: DownloadHandle,
        downloaded_bytes: float,
        average_rate: float,
    ):
        return self._queue_request(
            self._handle_progress_changed,
            args=(update_time, handle, downloaded_bytes, average_rate),
        )

    def download_complete(self, update_time: datetime, handle: DownloadHandle):
        return self._queue_request(
            self._handle_download_complete, args=(update_time, handle)
        )

    def download_stopped(self, update_time: datetime, handle: DownloadHandle):
        return self._queue_request(
            self._handle_download_stopped, args=(update_time, handle)
        )

    def download_errored(
        self, update_time: datetime, handle: DownloadHandle, error_info: ErrorInfo
    ):
        return self._queue_request(
            self._handle_download_errored, args=(update_time, handle, error_info)
        )

    def _handle_schedule_download(self, request: DownloadRequest) -> DownloadHandle:
        handle = DownloadHandle.make()
        invariant(not self._db.has_entry(handle))
        work_dir = self.settings.temp_download_dir / f"{handle}.captain"
        logger.debug(f"creating work directory {work_dir} for download handle={handle}")
        work_dir.mkdir()
        entry = DownloadEntry(
            handle=handle,
            user_request=request,
            state=DownloadState(status=DownloadStatus.SCHEDULED, work_dir=work_dir),
        )
        start_at = request.start_at if request.start_at else datetime.now(pytz.utc)
        schedule_handle = self._defer_request(
            start_at, self._handle_start_download, args=(handle,)
        )
        logger.debug(f"got handle {schedule_handle} for scheduled event")
        entry.state.schedule_handle = schedule_handle
        self._db.persist_entry(entry)
        self._update_observers(
            EventType.DOWNLOAD_SCHEDULED, ExternalDownloadEntry.from_internal(entry)
        )
        return handle

    def _hard_download_task_cleanup(
        self, handle: DownloadHandle, post_action: Optional[str] = None
    ) -> None:
        task = self._tasks.get(handle)
        if task and task.is_alive():
            logger.info(f"killing download {handle} subprocess")
            task.kill()
            task.join()
            del self._tasks[handle]
        if self._db.has_entry(handle):
            task_work_dir = self._db.get_entry(handle).state.work_dir
            if task_work_dir and task_work_dir.is_dir():
                logger.info(
                    f"emptying download {handle} work directory {task_work_dir}"
                )
                try:
                    empty_directory(task_work_dir)
                except Exception as e:
                    logger.warning(
                        f"failed to empty download {handle} work directory {task_work_dir}: {e}"
                    )
            if post_action == "delete":
                logger.info(f"removing download {handle} from manager")
                self._db.remove_entry(handle)
            else:
                logger.info(f"marking download {handle} as error")
                with self._db.scoped_entry(handle) as entry:
                    entry.state.status = DownloadStatus.ERROR
                    entry.state.error_info = ErrorInfo(
                        message="Internal error", stack=traceback.format_exc()
                    )

    @contextmanager
    def _download_error_handler(
        self, handle: DownloadHandle, post_action: Optional[str] = None
    ) -> None:
        post_action = post_action or "mark_error"
        try:
            yield
        except Exception as e:
            logger.warning(
                f"error caught in error handler, will cleanup download {handle}"
                f" post_action={post_action}: {e}"
            )
            self._hard_download_task_cleanup(handle, post_action)
            if self._db.has_entry(handle):
                entry = self._db.get_entry(handle)
                self._update_observers(
                    EventType.DOWNLOAD_ERRORED,
                    ExternalDownloadEntry.from_internal(entry),
                )
            raise

    def _handle_reschedule_download(self, handle: DownloadHandle, start_at: datetime):
        logger.info(
            f"handling reschedule download request handle={handle} start_at={start_at}"
        )
        with self._download_error_handler(handle):
            if not self._db.has_entry(handle):
                raise DownloadManagerError(f"download entry not found: {handle.handle}")
            with self._db.scoped_entry(handle) as entry:
                if not entry.state.can_be_rescheduled:
                    raise DownloadManagerError(f"cannot reschedule download")
                invariant(entry.state.schedule_handle is not None)
                self._scheduler.cancel(entry.state.schedule_handle)
                entry.user_request.start_at = start_at
                entry.state.schedule_handle = self._defer_request(
                    start_at, self._handle_start_download, args=(handle,)
                )
            self._update_observers(
                EventType.DOWNLOAD_SCHEDULED, ExternalDownloadEntry.from_internal(entry)
            )

    def _handle_start_download(self, handle: DownloadHandle) -> DownloadHandle:
        logger.info(f"handling start download request handle={handle}")
        with self._download_error_handler(handle):
            invariant(self._db.has_entry(handle))
            invariant(handle not in self._tasks)
            with self._db.scoped_entry(handle) as entry:
                entry.state.schedule_handle = None
                entry.state.status = DownloadStatus.PENDING
                self._tasks[handle] = create_download_process(
                    handle=handle,
                    download_request=entry.user_request,
                    existing_metadata=entry.state.metadata,
                    work_dir=entry.state.work_dir,
                    listener=self._listener_bridge.make_listener(),
                )
                self._tasks[handle].start()
                return handle

    def _handle_retry_download(self, handle: DownloadHandle):
        logger.info(f"handling retry download request handle={handle}")
        with self._download_error_handler(handle):
            if not self._db.has_entry(handle):
                raise DownloadManagerError(f"download entry not found: {handle.handle}")
            with self._db.scoped_entry(handle) as entry:
                if not entry.state.can_be_retried:
                    raise DownloadManagerError(f"cannot retry download")
                work_dir = entry.state.work_dir
                invariant(work_dir.exists())
                logger.debug(f"clearing work directory {work_dir}")
                empty_directory(work_dir)
                entry.state = DownloadState(
                    status=DownloadStatus.PENDING, work_dir=work_dir
                )
                invariant(handle not in self._tasks)
                self._tasks[handle] = create_download_process(
                    handle=handle,
                    download_request=entry.user_request,
                    existing_metadata=entry.state.metadata,
                    work_dir=work_dir,
                    listener=self._listener_bridge.make_listener(),
                )
                self._tasks[handle].start()

    def _handle_stop_download(self, handle: DownloadHandle) -> None:
        logger.info(f"handling stop download request handle={handle}")
        with self._download_error_handler(handle):
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
                    invariant(
                        entry.state.status
                        in {DownloadStatus.PAUSED, DownloadStatus.SCHEDULED}
                    )
                    entry.state.requested_status = DownloadStatus.STOPPED
                    self._queue_request(
                        self._handle_download_stopped, args=(datetime.now(), handle)
                    )
                    return
                task.stop()
                entry.state.requested_status = DownloadStatus.STOPPED

    def _handle_pause_download(self, handle: DownloadHandle):
        logger.info(f"handling pause download request handle={handle}")
        with self._download_error_handler(handle):
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
        logger.info(f"handling resume download request handle={handle}")
        with self._download_error_handler(handle):
            if not self._db.has_entry(handle):
                raise DownloadManagerError(f"download entry not found: {handle.handle}")
            with self._db.scoped_entry(handle) as entry:
                if not entry.state.can_be_resumed:
                    raise DownloadManagerError("cannot resume task")
                entry.state.requested_status = DownloadStatus.ACTIVE
                invariant(entry.state.metadata is not None)
                invariant(handle not in self._tasks)
                self._tasks[handle] = create_download_process(
                    handle=handle,
                    download_request=entry.user_request.copy(deep=True),
                    existing_metadata=entry.state.metadata,
                    work_dir=entry.state.work_dir,
                    listener=self._listener_bridge.make_listener(),
                )
                self._tasks[handle].start()

    def _handle_remove_download(self, handle: DownloadHandle, delete_file: bool):
        logger.info(
            f"handling remove download request handle={handle} delete_file={delete_file}"
        )
        with self._download_error_handler(handle, post_action="remove"):
            if not self._db.has_entry(handle):
                raise DownloadManagerError(f"download entry not found: {handle.handle}")
            entry = self._db.get_entry(handle)
            if (
                delete_file
                and entry.state.file_location
                and entry.state.file_location.is_file()
            ):
                logger.info(f"removing downloaded file {entry.state.file_location}")
                self._queue_request(
                    _cleanup_files,
                    args=([entry.state.file_location],),
                    kwargs={"permanent": not self._settings.send_files_to_trash},
                )
            if entry.state.work_dir.is_dir():
                logger.info(f"removing work directory {entry.state.work_dir}")
                remove_directory(entry.state.work_dir)
            self._db.remove_entry(handle)
            self._notify_observers(
                NotificationSeverity.INFO,
                f"Removed '{entry.user_request.remote_file_name}' from the list",
            )
            logger.debug(f"removed task: {handle}")

    def _handle_get_download(self, handle: DownloadHandle) -> Dict[str, Any]:
        logger.info(f"handling get download request handle={handle}")
        if not self._db.has_entry(handle):
            raise DownloadManagerError(f"download entry not found: {handle.handle}")
        return serialize(
            ExternalDownloadEntry.from_internal(self._db.get_entry(handle))
        )

    def _handle_get_downloads(self) -> List[Dict[str, Any]]:
        logger.info(f"handling get downloads request")
        return [
            serialize(ExternalDownloadEntry.from_internal(entry))
            for entry in self._db.get_all_entries()
        ]

    def _handle_download_started(
        self, update_time: datetime, handle: DownloadHandle, metadata: DownloadMetadata
    ) -> None:
        logger.info(
            f"handling download started event handle={handle} update_time={update_time.isoformat()}"
            f" metadata={metadata}"
        )
        with self._download_error_handler(handle):
            invariant(self._db.has_entry(handle))
            with self._db.scoped_entry(handle) as entry:
                invariant(
                    entry.state.metadata is None
                    or entry.state.status == DownloadStatus.PAUSED
                )
                invariant(
                    entry.state.start_time is None
                    or entry.state.status == DownloadStatus.PAUSED
                )
                invariant(
                    entry.state.status
                    in {DownloadStatus.PENDING, DownloadStatus.PAUSED}
                )
                if entry.state.status == DownloadStatus.PENDING:
                    logger.debug(
                        f"task status is pending, setting metadata: {metadata}"
                    )
                    entry.state.metadata = metadata
                    entry.state.start_time = datetime.now()
                entry.state.last_update_time = update_time
                entry.state.status = DownloadStatus.ACTIVE
                entry.state.requested_status = None
                self._update_observers(
                    EventType.DOWNLOAD_STARTED,
                    ExternalDownloadEntry.from_internal(entry),
                )
                logger.debug(f"download {handle} started: {serialize(metadata)}")

    def _handle_download_errored(
        self, update_time: datetime, handle: DownloadHandle, error_info: ErrorInfo
    ) -> None:
        logger.info(
            f"handling download errored event handle={handle} update_time={update_time.isoformat()}"
            f" error={error_info.message}"
        )
        with self._download_error_handler(handle):
            invariant(self._db.has_entry(handle))
            invariant(handle in self._tasks)
            self._tasks[handle].join()
            del self._tasks[handle]
            with self._db.scoped_entry(handle) as entry:
                entry.state.status = DownloadStatus.ERROR
                entry.state.end_time = datetime.now()
                entry.state.last_update_time = update_time
                entry.state.error_info = error_info
                self._update_observers(
                    EventType.DOWNLOAD_ERRORED,
                    ExternalDownloadEntry.from_internal(entry),
                )
                logger.warning(f"download {handle} errored: {serialize(error_info)}")
            empty_directory(entry.state.work_dir)

    def _handle_download_complete(
        self, update_time: datetime, handle: DownloadHandle
    ) -> None:
        logger.info(
            f"handling download complete event handle={handle} update_time={update_time.isoformat()}"
        )
        with self._download_error_handler(handle):
            invariant(self._db.has_entry(handle))
            invariant(handle in self._tasks)
            self._tasks[handle].join()
            del self._tasks[handle]
            with self._db.scoped_entry(handle) as entry:
                file_size = entry.state.metadata.file_size
                invariant(
                    file_size is None or entry.state.downloaded_bytes == file_size
                )
                invariant(entry.state.metadata is not None)
                downloaded_file_path = entry.state.metadata.downloaded_file_path
                invariant(downloaded_file_path.is_file())
                dest_file_path = (
                    entry.user_request.download_dir / downloaded_file_path.name
                )
                logger.info(
                    f"moving temporary file {downloaded_file_path} to {dest_file_path}"
                )
                shutil.move(str(downloaded_file_path), str(dest_file_path))
                entry.state.file_location = dest_file_path
                entry.state.status = DownloadStatus.COMPLETE
                entry.state.end_time = datetime.now()
                entry.state.last_update_time = update_time
                self._update_observers(
                    EventType.DOWNLOAD_COMPLETE,
                    ExternalDownloadEntry.from_internal(entry),
                )
                self._notify_observers(
                    NotificationSeverity.INFO,
                    f"Download '{entry.user_request.remote_file_name}' complete",
                )
                logger.info(f"task {handle} complete")
                remove_directory(entry.state.work_dir)

    def _handle_download_stopped(
        self, update_time: datetime, handle: DownloadHandle
    ) -> None:
        logger.info(
            f"handling download stopped event handle={handle} update_time={update_time.isoformat()}"
        )
        with self._download_error_handler(handle):
            invariant(self._db.has_entry(handle))
            with self._db.scoped_entry(handle) as entry:
                invariant(
                    handle in self._tasks
                    or entry.state.status
                    in {DownloadStatus.PAUSED, DownloadStatus.SCHEDULED}
                )
                if handle in self._tasks:
                    self._tasks[handle].join()
                    del self._tasks[handle]
                requested_status = entry.state.requested_status
                invariant(requested_status is not None)
                invariant(
                    requested_status in {DownloadStatus.STOPPED, DownloadStatus.PAUSED}
                )
                entry.state.last_update_time = update_time
                entry.state.status = requested_status
                entry.state.requested_status = None
                entry.state.end_time = update_time
                if requested_status == DownloadStatus.STOPPED:
                    empty_directory(entry.state.work_dir)
                self._update_observers(
                    EventType.DOWNLOAD_PAUSED
                    if requested_status == DownloadStatus.PAUSED
                    else EventType.DOWNLOAD_STOPPED,
                    ExternalDownloadEntry.from_internal(entry),
                )

    def _handle_progress_changed(
        self,
        update_time: datetime,
        handle: DownloadHandle,
        downloaded_bytes: int,
        average_rate: float,
    ) -> None:
        with self._download_error_handler(handle):
            invariant(self._db.has_entry(handle))
            invariant(isinstance(downloaded_bytes, int))
            invariant(downloaded_bytes >= 0)
            with self._db.scoped_entry(handle) as entry:
                entry.state.current_rate = average_rate
                entry.state.downloaded_bytes = downloaded_bytes
                entry.state.last_update_time = update_time
                self._update_observers(
                    EventType.PROGRESS_CHANGED,
                    ExternalDownloadEntry.from_internal(entry),
                )
                logger.debug(
                    f"progress for task {handle} changed: {downloaded_bytes} bytes"
                )

    def _queue_request(
        self,
        handler: Callable,
        args: Optional[Tuple] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        blocking: Optional[bool] = False,
    ):
        args = args or ()
        kwargs = kwargs or {}
        request = _Request(handler, args, kwargs, Future())
        logger.debug(f"queuing request: {request}")
        self._requests.put(request)
        if blocking:
            return request.future_result.get()
        return request.future_result

    def _defer_request(
        self,
        start_at: datetime,
        handler: Callable,
        args: Optional[Tuple] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ):
        return self._scheduler.schedule(
            at=start_at,
            action=partial(
                self._queue_request,
                handler=handler,
                args=args,
                kwargs=kwargs,
                blocking=False,
            ),
        )

    def _stop_outstanding_tasks(self):
        logger.info(f"stopping all outstanding tasks")
        for entry in self._db.get_all_entries():
            if entry.state.can_be_rescheduled:
                self._scheduler.cancel(required_value(entry.state.schedule_handle))
                entry.state.schedule_handle = None
            elif entry.state.can_be_paused:
                logger.info(f"pausing task {entry.handle}")
                self._queue_request(self._handle_pause_download, args=(entry.handle,))
            elif entry.state.can_be_stopped:
                logger.info(f"stopping task {entry.handle}")
                self._queue_request(self._handle_stop_download, args=(entry.handle,))

    def _check_enabled(self):
        if self._stop_flag.is_set():
            raise DownloadManagerError(
                "download manager is stopping," " interface is disabled"
            )

    def _request_loop(self):
        logger.debug("entering request loop")
        shutdown_at: Optional[datetime] = None
        while True:
            if self._stop_flag.is_set() and shutdown_at is None:
                logger.info("shutdown requested, stopping all outstanding tasks")
                self._stop_outstanding_tasks()
                shutdown_at = datetime.now() + self._settings.shutdown_timeout
                logger.info(f"will force shutdown at {shutdown_at}")
            elif shutdown_at is not None:
                all_inactive = all(
                    not entry.state.is_active for entry in self._db.get_all_entries()
                )
                if all_inactive:
                    logger.info("all tasks inactive, leaving request loop")
                    return
                if datetime.now() >= shutdown_at:
                    logger.info("shutdown timeout expired, leaving forcefully")
                    return
            request: Optional[_Request] = _pop_queue(
                self._requests, timedelta(milliseconds=500)
            )
            if request is None:
                continue
            try:
                logger.debug(f"request start: {request}")
                result = request.handler(*request.args, **request.kwargs)
                request.future_result.set_result(result)
                logger.debug(
                    f"request end [success]" + f": {result}"
                    if result is not None
                    else ""
                )
            except Exception as e:
                ref_code = _make_error_reference_code()
                logger.error(
                    f"failure while executing request={request} ref_code={ref_code}: {e}\n{traceback.format_exc()}"
                )
                self._notify_observers(
                    NotificationSeverity.ERROR,
                    f"Internal error (reference code: {ref_code})",
                )
                request.future_result.set_error(e)
                logger.debug(f"request end [failure]: {e}")

    def _notify_observers(self, severity: NotificationSeverity, message: str):
        notification = GeneralNotification(severity=severity, message=message)
        logger.debug(f"notifying observers: {serialize(notification)}")
        self._update_observers(EventType.GENERAL_NOTIFICATION, serialize(notification))

    def _update_observers(self, event_type: EventType, payload: Any):
        for observer in self._observers:
            observer.handle_event(
                DownloadManagerEvent(event_type=event_type, payload=serialize(payload))
            )

    def stop(self):
        logger.info("download manager requested to stop")
        self._stop_flag.set()

    def run(self):
        logger.info("download manager requested to run")
        self._scheduler.start()
        self._listener_bridge.start()
        self._request_loop()
        logger.info("stopping download listener bridge")
        self._listener_bridge.stop()
        self._listener_bridge.join()
        logger.info("stopping internal scheduler")
        self._scheduler.stop()
        self._scheduler.join()
        logger.info("persisting download manager state")
        self._db.flush()
