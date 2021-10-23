class CaptainError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class NotSupportedError(CaptainError):
    def __init__(self, message: str):
        super().__init__(message)
