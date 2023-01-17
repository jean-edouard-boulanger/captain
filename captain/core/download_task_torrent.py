import shutil
import time
import traceback
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from threading import Event

from .domain import DownloadHandle, DownloadMetadata, ErrorInfo, TorrentDownloadRequest
from .download_listener import DownloadListenerBase
from .download_task import DownloadTaskBase
from .fs import create_zip_archive
from .logging import get_logger
from .rtorrent_client import RtorrentClient, Torrent

logger = get_logger()


class State(str, Enum):
    new = "new"
    wait_started = "wait_started"
    wait_metadata = "wait_metadata"
    downloading = "downloading"
    post_process = "post_process"
    done = "done"


def get_final_download_file_path(work_dir: Path, torrent_name: str, is_multi_file: bool):
    if is_multi_file:
        return work_dir / f"{torrent_name}.zip"
    return work_dir / torrent_name


class TorrentDownloadTask(DownloadTaskBase):
    supports_graceful_stop = True

    def __init__(
        self,
        handle: DownloadHandle,
        download_request: TorrentDownloadRequest,
        existing_metadata: DownloadMetadata | None,
        work_dir: Path,
        listener: DownloadListenerBase | None = None,
        progress_report_interval: timedelta | None = None,
    ):
        self._handle = handle
        self._request = download_request
        self._metadata = existing_metadata
        self._work_dir = work_dir
        self._listener = listener
        self._progress_report_interval = progress_report_interval
        self._stopped_flag = Event()
        self._client = RtorrentClient(self._request.rtorrent_rpc_url)
        self._torrent: Torrent | None = None
        self._state = State.new

    @property
    def _should_stop(self):
        return self._stopped_flag.is_set() or self._state == State.done

    @property
    def _download_dir(self) -> Path:
        return self._work_dir / "download"

    def _set_state(self, new_state: State) -> None:
        assert new_state != self._state
        logger.debug(
            f"torrent {self._torrent.info_hash} download task changing state"
            f" old_state={self._state.value} new_state={new_state.value}"
        )
        self._state = new_state

    def _main_loop(self):
        if self._state == State.new:
            self._download_dir.mkdir()
            self._torrent = self._client.start_torrent(self._request.magnet_link)
            self._set_state(State.wait_started)

        torrent = self._torrent
        if self._state == State.wait_started:
            if not torrent.exists():
                return
            self._set_state(State.wait_metadata)

        if self._state == State.wait_metadata:
            if torrent.is_meta:
                return
            self._metadata = DownloadMetadata(
                downloaded_file_path=get_final_download_file_path(
                    work_dir=self._work_dir, torrent_name=torrent.name, is_multi_file=torrent.is_multi_file
                ),
                file_size=torrent.size_bytes,
                file_type=None,
                resumable=False,
            )
            self._listener.download_started(update_time=datetime.now(), handle=self._handle, metadata=self._metadata)
            self._set_state(State.downloading)

        if self._state == State.downloading:
            self._listener.progress_changed(
                datetime.now(),
                self._handle,
                torrent.completed_bytes,
                torrent.download_rate,
            )
            if torrent.is_complete:
                self._set_state(State.post_process)

        if self._state == State.post_process:
            if torrent.is_multi_file:
                create_zip_archive(archive_file_path=self._metadata.downloaded_file_path, source_dir=torrent.base_path)
            else:
                shutil.copyfile(torrent.base_path, self._metadata.downloaded_file_path)
            self._set_state(State.done)

        if self._state == State.done:
            self._listener.download_complete(datetime.now(), self._handle)

    def run(self) -> None:
        try:
            while not self._should_stop:
                self._main_loop()
                if not self._should_stop:
                    time.sleep(self._progress_report_interval.total_seconds())
            # Always cleanup after we're done or we've been requested to stop
            if self._torrent:
                self._torrent.erase()
        except Exception as e:
            logger.error("error while downloading torrent", exc_info=True)
            self._listener.download_errored(
                datetime.now(),
                self._handle,
                ErrorInfo(
                    message=f"Could not download torrent {self._request.magnet_link}: {e}",
                    stack=traceback.format_exc(),
                ),
            )

    def stop(self) -> None:
        logger.info(f"task {self._handle} ({type(self).__name__}) requested to stop")
        self._stopped_flag.set()
