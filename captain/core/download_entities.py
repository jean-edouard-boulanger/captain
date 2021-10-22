from captain.core.serialization import serializer

from typing import Any, Optional, Dict, Union
from dateutil.parser import parse as parse_date
from dataclasses import dataclass
from urllib.parse import unquote
from datetime import datetime
from pathlib import Path
import enum
import uuid
import os


class DownloadHandle(object):
    def __init__(self, handle: Union[uuid.UUID, str]):
        if isinstance(handle, uuid.UUID):
            self._handle = handle
        if isinstance(handle, str):
            self._handle = uuid.UUID(handle)

    def __str__(self):
        return str(self.handle)

    def __repr__(self):
        return f"DownloadHandle({self.handle})"

    def __hash__(self):
        return hash(self.handle)

    def __eq__(self, other: "DownloadHandle"):
        return self.handle == other.handle

    @property
    def handle(self) -> uuid.UUID:
        return self._handle

    @staticmethod
    def make() -> "DownloadHandle":
        return DownloadHandle(uuid.uuid4())


@dataclass
class DataRange:
    first_byte: Optional[int] = None
    last_byte: Optional[int] = None

    def serialize(self) -> Dict:
        return {"first_byte": self.first_byte, "last_byte": self.last_byte}

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["DataRange"]:
        if not data:
            return None
        return DataRange(
            first_byte=data.get("first_byte"), last_byte=data.get("last_byte")
        )


@dataclass
class DownloadRequest:
    remote_file_url: str
    local_dir: Optional[Path] = None
    local_file_name: Optional[str] = None
    start_at: Optional[datetime] = None
    auth_payload: Optional[Any] = None
    data_range: Optional[DataRange] = None

    @property
    def remote_file_name(self):
        return unquote(os.path.basename(self.remote_file_url))

    @serializer
    def serialize(self) -> Dict:
        return {
            "remote_file_url": self.remote_file_url,
            "local_dir": self.local_dir,
            "local_file_name": self.local_file_name,
            "start_at": self.start_at,
            "auth_payload": self.auth_payload,
            "has_auth": self.auth_payload is not None,
            "range": self.data_range,
            "properties": {"remote_file_name": self.remote_file_name},
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["DownloadRequest"]:
        if data is None:
            return None
        return DownloadRequest(
            remote_file_url=data["remote_file_url"],
            local_dir=Path(data.get("local_dir")) if data.get("local_dir") else None,
            local_file_name=data.get("local_file_name"),
            start_at=parse_date(data.get("start_at")) if data.get("start_at") else None,
            auth_payload=data.get("auth_payload"),
            data_range=DataRange.deserialize(data.get("range")),
        )


@dataclass
class ErrorInfo:
    message: str
    stack: str

    @serializer
    def serialize(self) -> Dict:
        return {"message": self.message, "stack": self.stack}

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["ErrorInfo"]:
        if data is None:
            return None
        return ErrorInfo(message=data["message"], stack=data["stack"])


class DownloadStatus(enum.Enum):
    SCHEDULED = enum.auto()
    PENDING = enum.auto()
    ACTIVE = enum.auto()
    PAUSED = enum.auto()
    COMPLETE = enum.auto()
    STOPPED = enum.auto()
    ERROR = enum.auto()


@dataclass
class DownloadMetadata:
    remote_url: str
    remote_file_name: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    accept_ranges: Optional[bool] = None

    @serializer
    def serialize(self):
        return {
            "remote_url": self.remote_url,
            "remote_file_name": self.remote_file_name,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "accept_ranges": self.accept_ranges,
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["DownloadMetadata"]:
        if data is None:
            return None
        return DownloadMetadata(
            remote_url=data["remote_url"],
            remote_file_name=data["remote_file_name"],
            file_size=int(data["file_size"]),
            file_type=data["file_type"],
            accept_ranges=data["accept_ranges"],
        )


@dataclass
class DownloadState:
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

    @serializer
    def serialize(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata,
            "downloaded_bytes": self.downloaded_bytes,
            "current_rate": self.current_rate,
            "status": self.status.name,
            "file_location": self.file_location,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error_info": self.error_info,
            "properties": {
                "is_final": self.is_final,
                "can_be_resumed": self.can_be_resumed,
                "can_be_paused": self.can_be_paused,
                "can_be_stopped": self.can_be_stopped,
                "can_be_retried": self.can_be_retried,
                "can_be_rescheduled": self.can_be_rescheduled,
                "can_be_downloaded": self.can_be_downloaded,
            },
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["DownloadState"]:
        if data is None:
            return None
        return DownloadState(
            metadata=DownloadMetadata.deserialize(data["metadata"]),
            downloaded_bytes=data["downloaded_bytes"],
            current_rate=data["current_rate"],
            file_location=data.get("file_location"),
            status=DownloadStatus[data["status"]],
            start_time=parse_date(data["start_time"]) if data["start_time"] else None,
            end_time=parse_date(data["end_time"]) if data["end_time"] else None,
            error_info=ErrorInfo.deserialize(data["error_info"]),
        )


@dataclass
class DownloadEntry:
    handle: DownloadHandle
    user_request: DownloadRequest
    system_request: Optional[DownloadRequest]
    state: DownloadState

    @serializer
    def serialize(self):
        return {
            "handle": str(self.handle),
            "user_request": self.user_request,
            "system_request": self.system_request,
            "state": self.state,
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["DownloadEntry"]:
        if data is None:
            return None
        return DownloadEntry(
            handle=DownloadHandle(data["handle"]),
            user_request=DownloadRequest.deserialize(data["user_request"]),
            system_request=DownloadRequest.deserialize(data["system_request"]),
            state=DownloadState.deserialize(data["state"]),
        )
