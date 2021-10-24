from typing import Protocol


class DownloadTaskBase(Protocol):
    supports_graceful_stop: bool

    def run(self) -> None:
        raise NotImplementedError("must implement 'run'")

    def stop(self):
        raise NotImplementedError("must implement 'stop'")
