from typing import Optional
from dataclasses import dataclass


@dataclass
class DownloadMetadata:
    remote_url: str
    remote_file_name: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None

    def serialize(self):
        return {
            "remote_url": self.remote_url,
            "remote_file_name": self.remote_file_name,
            "file_size": self.file_size,
            "file_type": self.file_type
        }
