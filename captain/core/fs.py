import os
import shutil
from pathlib import Path

from .errors import CaptainError


class FileSystemError(CaptainError):
    def __init__(self, message: str):
        super().__init__(message)


def empty_directory(path: Path):
    if path == Path("/"):
        raise FileSystemError(f"refusing to run on {path}")
    if not path.is_dir():
        raise FileSystemError(f"not a directory: {path}")
    for entry in path.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            os.remove(entry)


def remove_directory(path: Path):
    if path == Path("/"):
        raise FileSystemError(f"refusing to run on {path}")
    if not path.is_dir():
        raise FileSystemError(f"not a directory: {path}")
    shutil.rmtree(path)
