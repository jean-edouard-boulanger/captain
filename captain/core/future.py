import threading


class _Unset:
    pass


class Future:
    def __init__(self):
        self._flag = threading.Event()
        self._result = _Unset()
        self._error = _Unset()

    def _error_set(self):
        return not isinstance(self._error, _Unset)

    def _result_set(self):
        return not isinstance(self._result, _Unset)

    def set_result(self, result):
        self._result = result
        self._flag.set()

    def set_error(self, error):
        self._error = error
        self._flag.set()

    def get(self):
        self._flag.wait()
        if self._error_set():
            raise self._error
        assert self._result_set()
        return self._result
