from typing import Protocol


class DownloadProviderBase(Protocol):
    download_type: str
