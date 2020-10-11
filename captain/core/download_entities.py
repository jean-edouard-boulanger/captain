from requests.auth import HTTPBasicAuth, HTTPProxyAuth, HTTPDigestAuth
from dateutil.parser import parse as parse_date
from typing import Optional, Dict, Union
from dataclasses import dataclass
from urllib.parse import unquote
from datetime import datetime
from pathlib import Path
import enum
import uuid
import os


Auth = Union[HTTPBasicAuth, HTTPProxyAuth, HTTPDigestAuth]


def _deserialize_auth(data) -> Optional[Auth]:
    if data is None:
        return None
    if "basic" in data:
        data = data["basic"]
        return HTTPBasicAuth(data["username"], data["password"])
    if "proxy" in data:
        data = data["proxy"]
        return HTTPProxyAuth(data["username"], data["password"])
    if "digest" in data:
        data = data["digest"]
        return HTTPDigestAuth(data["username"], data["password"])
    raise ValueError(f"'{list(data.keys())[0]}' is not a supported authentication strategy")


class DownloadHandle(object):
    def __init__(self, handle: Union[uuid.UUID, str]):
        if isinstance(handle, uuid.UUID):
            self.handle = handle
        if isinstance(handle, str):
            self.handle = uuid.UUID(handle)

    def __str__(self):
        return str(self.handle)

    def __repr__(self):
        return f"DownloadHandle({self.handle})"

    def __hash__(self):
        return hash(self.handle)

    def __eq__(self, other: 'DownloadHandle'):
        return self.handle == other.handle

    @staticmethod
    def make() -> 'DownloadHandle':
        return DownloadHandle(uuid.uuid4())


@dataclass
class DataRange:
    first_byte: Optional[int] = None
    last_byte: Optional[int] = None

    def serialize(self) -> Dict:
        return {
            "first_byte": self.first_byte,
            "last_byte": self.last_byte
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["DataRange"]:
        if not data:
            return None
        return DataRange(
            first_byte=data.get("first_byte"),
            last_byte=data.get("last_byte"))


@dataclass
class DownloadRequest:
    remote_file_url: str
    local_dir: Optional[Path] = None
    local_file_name: Optional[str] = None
    start_at: Optional[datetime] = None
    auth: Optional[Auth] = None
    data_range: Optional[DataRange] = None

    @property
    def remote_file_name(self):
        return unquote(os.path.basename(self.remote_file_url))

    def serialize(self) -> Dict:
        return {
            "remote_file_url": self.remote_file_url,
            "local_dir": str(self.local_dir) if self.local_dir else None,
            "local_file_name": str(self.local_file_name) if self.local_file_name else None,
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "has_auth": self.auth is not None,
            "range": self.data_range.serialize() if self.data_range else None,
            "properties": {
                "remote_file_name": self.remote_file_name
            }
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional['DownloadRequest']:
        if data is None:
            return None
        return DownloadRequest(
            remote_file_url=data["remote_file_url"],
            local_dir=Path(data.get("local_dir")) if data.get("local_dir") else None,
            local_file_name=data.get("local_file_name"),
            start_at=parse_date(data.get("start_at")) if data.get("start_at") else None,
            auth=_deserialize_auth(data.get("auth")),
            data_range=DataRange.deserialize(data)
        )


@dataclass
class ErrorInfo:
    message: str
    stack: str

    def serialize(self) -> Dict:
        return {
            "message": self.message,
            "stack": self.stack
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional['ErrorInfo']:
        if data is None:
            return None
        return ErrorInfo(
            message=data["message"],
            stack=data["stack"])


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

    def serialize(self):
        return {
            "remote_url": self.remote_url,
            "remote_file_name": self.remote_file_name,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "accept_ranges": self.accept_ranges
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
            accept_ranges=data["accept_ranges"])


@dataclass
class DownloadState:
    status: DownloadStatus
    metadata: Optional[DownloadMetadata] = None
    schedule_handle: Optional[int] = None
    downloaded_bytes: Optional[int] = None
    current_rate: Optional[float] = None
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
            DownloadStatus.COMPLETE
        }

    @property
    def is_active(self):
        return self.status == DownloadStatus.ACTIVE

    @property
    def can_be_resumed(self):
        return (self.status == DownloadStatus.PAUSED
                and self.requested_status is None
                and self.metadata is not None
                and self.metadata.file_size is not None)

    @property
    def can_be_paused(self):
        return (self.status == DownloadStatus.ACTIVE
                and self.requested_status is None
                and self.metadata is not None
                and self.metadata.accept_ranges)

    @property
    def can_be_stopped(self):
        return (self.status in {DownloadStatus.ACTIVE, DownloadStatus.PAUSED, DownloadStatus.SCHEDULED}
                and self.requested_status is None)

    @property
    def can_be_retried(self):
        return self.status in {DownloadStatus.STOPPED, DownloadStatus.ERROR}

    @property
    def can_be_rescheduled(self):
        return self.status == DownloadStatus.SCHEDULED

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
                "can_be_resumed": self.can_be_resumed,
                "can_be_paused": self.can_be_paused,
                "can_be_stopped": self.can_be_stopped,
                "can_be_retried": self.can_be_retried,
                "can_be_rescheduled": self.can_be_rescheduled
            }
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["DownloadState"]:
        if data is None:
            return None
        return DownloadState(
            metadata=DownloadMetadata.deserialize(data["metadata"]),
            downloaded_bytes=data["downloaded_bytes"],
            current_rate=data["current_rate"],
            status=DownloadStatus[data["status"]],
            start_time=parse_date(data["start_time"]) if data["start_time"] else None,
            end_time=parse_date(data["end_time"]) if data["end_time"] else None,
            error_info=ErrorInfo.deserialize(data["error_info"])
        )


@dataclass
class DownloadEntry:
    handle: DownloadHandle
    user_request: DownloadRequest
    system_request: Optional[DownloadRequest]
    state: DownloadState

    def serialize(self):
        return {
            "handle": str(self.handle),
            "user_request": self.user_request.serialize(),
            "system_request": self.system_request.serialize() if self.system_request else None,
            "state": self.state.serialize()
        }

    @staticmethod
    def deserialize(data: Optional[Dict]) -> Optional["DownloadEntry"]:
        if data is None:
            return None
        return DownloadEntry(
            handle=DownloadHandle(data["handle"]),
            user_request=DownloadRequest.deserialize(data["user_request"]),
            system_request=DownloadRequest.deserialize(data["system_request"]),
            state=DownloadState.deserialize(data["state"]))
