import queue
import threading
from typing import Any, Optional, TypeVar

from .helpers import set_thread_name

QueueType = TypeVar("QueueType", bound=queue.Queue)


class Worker(threading.Thread):
    class _Stop(object):
        pass

    def __init__(
        self, message_queue: Optional[QueueType] = None, name: Optional[str] = None
    ):
        super().__init__(name=name)
        self._message_queue = message_queue or queue.Queue

    def consume_message(self, message: Any):
        raise NotImplementedError("workers must implement 'consume_message'")

    def run(self) -> None:
        set_thread_name(self.name)
        while True:
            try:
                message = self._message_queue.get()
                if isinstance(message, self._Stop):
                    break
                self.consume_message(message)
            except queue.Empty:
                pass

    def send(self, message: Any):
        self._message_queue.put(message)

    def stop(self):
        self.send(self._Stop())
