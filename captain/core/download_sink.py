from typing import Protocol, Optional
from io import BytesIO
from pathlib import Path


class DownloadSinkBase(Protocol):
    def write(self, data: bytes):
        pass

    def __enter__(self) -> "DownloadSinkBase":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class FileDownloadSink(DownloadSinkBase):
    def __init__(self, file_path: Path, open_mode=None):
        self._file_path = file_path
        self._open_mode = open_mode
        self._handle = None

    def write(self, data: bytes):
        self._handle.write(data)

    def __enter__(self):
        self._handle = self._file_path.open(self._open_mode or "wb")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._handle.close()


class InMemoryDownloadSink(DownloadSinkBase):
    def __init__(self, buffer: Optional[BytesIO] = None):
        self._buffer = buffer or BytesIO()

    def write(self, data: bytes):
        self._buffer.write(data)


class NoOpDownloadSink(DownloadSinkBase):
    def write(self, data: bytes):
        pass
