import enum
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Union
from urllib.parse import unquote

from pydantic import BaseModel, Field, SecretStr


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


class HttpBasicAuthMethod(BaseModel):
    method: Literal["basic"] = "basic"
    username: str
    password: SecretStr


HttpAuthMethodType = Union[HttpBasicAuthMethod]
HttpAuthMethodChoiceType = Annotated[HttpAuthMethodType, Field(discriminator="method")]


class HttpDownloadRequest(BaseModel):
    method: Literal["http"] = "http"
    remote_file_url: str
    auth_method: HttpAuthMethodChoiceType | None = None

    @property
    def remote_file_name(self) -> str:
        return unquote(os.path.basename(self.remote_file_url))

    def strip_credentials(self):
        self.auth_method = None


class YoutubeAuth(BaseModel):
    username: str
    password: SecretStr


class YoutubeDownloadRequest(BaseModel):
    method: Literal["youtube"] = "youtube"
    remote_file_url: str
    auth: YoutubeAuth | None = None

    @property
    def remote_file_name(self) -> str:
        return unquote(os.path.basename(self.remote_file_url))

    def strip_credentials(self):
        self.auth = None


DownloadMethodType = Union[HttpDownloadRequest, YoutubeDownloadRequest]
DownloadMethodChoiceType = Annotated[DownloadMethodType, Field(discriminator="method")]


class DownloadRequest(BaseModel):
    download_dir: Path
    start_at: datetime | None = None
    download_method: DownloadMethodChoiceType

    @property
    def remote_file_name(self) -> str:
        return self.download_method.remote_file_name

    def strip_credentials(self) -> None:
        self.download_method.strip_credentials()


class ErrorInfo(BaseModel):
    message: str
    stack: str


class DownloadStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    SCHEDULED = "SCHEDULED"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class DownloadMetadata(BaseModel):
    downloaded_file_path: Path
    file_size: int | None = None
    file_type: str | None = None
    resumable: bool | None = None


class DownloadState(BaseModel):
    status: DownloadStatus
    work_dir: Path
    metadata: DownloadMetadata | None = None
    schedule_handle: int | None = None
    downloaded_bytes: int | None = None
    current_rate: float | None = None
    file_location: Path | None = None
    requested_status: DownloadStatus | None = None
    last_update_time: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    error_info: ErrorInfo | None = None

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
    def can_be_removed(self) -> bool:
        return self.is_final or self.status == DownloadStatus.QUEUED

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
            and self.metadata.resumable
        )

    @property
    def can_be_stopped(self) -> bool:
        return (
            self.status in {DownloadStatus.ACTIVE, DownloadStatus.PAUSED, DownloadStatus.SCHEDULED}
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
    state: DownloadState


class NotificationSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class GeneralNotification(BaseModel):
    severity: NotificationSeverity
    message: str


class EventType(str, enum.Enum):
    DOWNLOAD_QUEUED = "DOWNLOAD_QUEUED"
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
