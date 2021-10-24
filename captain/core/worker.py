from typing import Any, TypeVar, Optional
import threading
import queue


QueueType = TypeVar("QueueType", bound=queue.Queue)


class Worker(threading.Thread):
    class _Stop(object):
        pass

    def __init__(self, message_queue: Optional[QueueType] = None):
        super().__init__()
        self._message_queue = message_queue or queue.Queue

    def consume_message(self, message: Any):
        raise NotImplementedError("workers must implement 'consume_message'")

    def run(self) -> None:
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
