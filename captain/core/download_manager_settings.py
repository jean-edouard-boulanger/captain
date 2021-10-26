from typing import List, Annotated
from datetime import timedelta
from pathlib import Path

from pydantic import BaseModel, Field, validator

from .persistence_factory import PersistenceSettingsType


DEFAULT_LOGGING_FORMAT = (
    "%(asctime)s (%(threadName)s) [%(levelname)s] %(message)s (%(filename)s:%(lineno)d)"
)


def _sanitize_path(path: Path):
    return path.expanduser().absolute()


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = DEFAULT_LOGGING_FORMAT


class DownloadDirectory(BaseModel):
    directory: Path
    label: str

    @validator("directory")
    def sanitize_path(cls, path: Path):
        path = _sanitize_path(path)
        if not path.is_dir():
            raise ValueError(f"{path} does not exist or is not a directory")
        return path


class DownloadManagerSettings(BaseModel):
    listen_host: str = "0.0.0.0"
    listen_port: int = 4001
    temp_download_dir: Path = Path("/tmp")
    download_directories: List[DownloadDirectory] = Field(default_factory=list)
    shutdown_timeout: timedelta = timedelta(seconds=10)
    send_files_to_trash: bool = False
    persistence_settings: Annotated[
        PersistenceSettingsType, Field(discriminator="persistence_type")
    ]
    logging_settings: LoggingSettings = Field(default_factory=LoggingSettings)
