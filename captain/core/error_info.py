from typing import Dict
from dataclasses import dataclass


@dataclass
class ErrorInfo:
    message: str
    stack: str

    def serialize(self) -> Dict:
        return {
            "message": self.message,
            "stack": self.stack
        }
