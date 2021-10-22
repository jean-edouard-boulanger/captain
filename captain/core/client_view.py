from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel

from .download_entities import (
    DownloadEntry as InternalDownloadEntry,
    DownloadState as InternalDownloadState,
)


def _get_download_progress_pc(state: InternalDownloadState) -> Optional[float]:
    if (
        state.downloaded_bytes is None
        or state.metadata is None
        or state.metadata.file_size is None
    ):
        return None
    return state.downloaded_bytes / state.metadata.file_size


def _get_valid_actions(state: InternalDownloadState):
    actions = []
    if state.can_be_resumed:
        actions.append("r")
    if state.can_be_paused:
        actions.append("p")
    if state.can_be_stopped:
        actions.append("S")
    if state.can_be_retried:
        actions.append("rt")
    if state.can_be_rescheduled:
        actions.append("rs")
    if state.can_be_downloaded:
        actions.append("d")
    return actions


def _get_error_message(state: InternalDownloadState) -> Optional[str]:
    return None if not state.error_info else state.error_info.message


class DownloadEntry(BaseModel):
    handle: str
    file_name: str
    status: str
    is_final: bool
    progress_pc: Optional[float]
    current_rate: Optional[float]
    start_time: Optional[datetime]
    error_message: Optional[str]
    valid_actions: List[str]

    @staticmethod
    def from_internal(entry: InternalDownloadEntry) -> "DownloadEntry":
        return DownloadEntry(
            handle=str(entry.handle),
            file_name=entry.user_request.remote_file_name,
            status=entry.state.status.name,
            is_final=entry.state.is_final,
            progress_pc=_get_download_progress_pc(entry.state),
            current_rate=entry.state.current_rate,
            start_time=entry.state.start_time,
            error_message=_get_error_message(entry.state),
            valid_actions=_get_valid_actions(entry.state),
        )
