from requests.auth import HTTPBasicAuth, HTTPProxyAuth, HTTPDigestAuth
from typing import Optional, Union, Dict
from dataclasses import dataclass
from pathlib import Path

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
    def deserialize(data: Optional[Dict]):
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
    auth: Optional[Auth] = None
    data_range: Optional[DataRange] = None

    def serialize(self) -> Dict:
        return {
            "remote_file_url": self.remote_file_url,
            "local_dir": str(self.local_dir) if self.local_dir else None,
            "local_file_name": str(self.local_file_name) if self.local_file_name else None,
            "has_auth": self.auth is not None,
            "range": self.data_range.serialize() if self.data_range else None
        }

    @staticmethod
    def deserialize(data) -> 'DownloadRequest':
        return DownloadRequest(
            remote_file_url=data["remoteFileUrl"],
            local_dir=data.get("localDir"),
            local_file_name=data.get("localFileName"),
            auth=_deserialize_auth(data.get("auth")),
            data_range=DataRange.deserialize(data)
        )
