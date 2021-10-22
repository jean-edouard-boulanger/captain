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
        pass

    def run(self) -> None:
        while True:
            try:
                message = self._message_queue.get(timeout=0.1)
                if isinstance(message, self._Stop):
                    break
                self.consume_message(message)
            except queue.Empty:
                pass

    def stop(self):
        self._message_queue.put(self._Stop())
