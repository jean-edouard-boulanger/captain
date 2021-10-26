from typing import Any, Optional
from urllib.parse import unquote
from datetime import datetime
from pathlib import Path
import uuid
import enum
import os

from pydantic import BaseModel


class DownloadHandle(BaseModel):
    handle: uuid.UUID

    def __str__(self):
        return str(self.handle)

    def __hash__(self):
        return hash(self.handle)

    def __eq__(self, other: "DownloadHandle"):
        return self.handle == other.handle

    @staticmethod
    def make() -> "DownloadHandle":
        return DownloadHandle(handle=uuid.uuid4())


class DataRange(BaseModel):
    first_byte: Optional[int] = None
    last_byte: Optional[int] = None


class DownloadRequest(BaseModel):
    remote_file_url: str
    download_dir: Optional[Path] = None
    local_file_name: Optional[str] = None
    start_at: Optional[datetime] = None
    auth_payload: Optional[Any] = None
    data_range: Optional[DataRange] = None

    @property
    def remote_file_name(self):
        return unquote(os.path.basename(self.remote_file_url))


class ErrorInfo(BaseModel):
    message: str
    stack: str


class DownloadStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class DownloadMetadata(BaseModel):
    remote_url: str
    remote_file_name: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    accept_ranges: Optional[bool] = None


class DownloadState(BaseModel):
    status: DownloadStatus
    metadata: Optional[DownloadMetadata] = None
    schedule_handle: Optional[int] = None
    downloaded_bytes: Optional[int] = None
    current_rate: Optional[float] = None
    file_location: Optional[Path] = None
    requested_status: Optional[DownloadStatus] = None
    last_update_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_info: Optional[ErrorInfo] = None

    @property
    def is_final(self):
        return self.status in {
            DownloadStatus.STOPPED,
            DownloadStatus.ERROR,
            DownloadStatus.COMPLETE,
        }

    @property
    def is_active(self) -> bool:
        return self.status == DownloadStatus.ACTIVE

    @property
    def can_be_resumed(self) -> bool:
        return (
            self.status == DownloadStatus.PAUSED
            and self.requested_status is None
            and self.metadata is not None
            and self.metadata.file_size is not None
        )

    @property
    def can_be_paused(self) -> bool:
        return (
            self.status == DownloadStatus.ACTIVE
            and self.requested_status is None
            and self.metadata is not None
            and self.metadata.accept_ranges
        )

    @property
    def can_be_stopped(self) -> bool:
        return (
            self.status
            in {DownloadStatus.ACTIVE, DownloadStatus.PAUSED, DownloadStatus.SCHEDULED}
            and self.requested_status is None
        )

    @property
    def can_be_retried(self) -> bool:
        return self.status in {DownloadStatus.STOPPED, DownloadStatus.ERROR}

    @property
    def can_be_rescheduled(self) -> bool:
        return self.status == DownloadStatus.SCHEDULED

    @property
    def can_be_downloaded(self) -> bool:
        return self.status == DownloadStatus.COMPLETE and self.file_location is not None


class DownloadEntry(BaseModel):
    handle: DownloadHandle
    user_request: DownloadRequest
    system_request: Optional[DownloadRequest]
    state: DownloadState


class NotificationSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class GeneralNotification(BaseModel):
    severity: NotificationSeverity
    message: str


class EventType(str, enum.Enum):
    DOWNLOAD_SCHEDULED = "DOWNLOAD_SCHEDULED"
    DOWNLOAD_STARTED = "DOWNLOAD_STARTED"
    PROGRESS_CHANGED = "PROGRESS_CHANGED"
    DOWNLOAD_COMPLETE = "DOWNLOAD_COMPLETE"
    DOWNLOAD_STOPPED = "DOWNLOAD_STOPPED"
    DOWNLOAD_PAUSED = "DOWNLOAD_PAUSED"
    DOWNLOAD_RESUMED = "DOWNLOAD_RESUMED"
    DOWNLOAD_ERRORED = "DOWNLOAD_ERRORED"
    GENERAL_NOTIFICATION = "GENERAL_NOTIFICATION"


class DownloadManagerEvent(BaseModel):
    event_type: EventType
    payload: Any
