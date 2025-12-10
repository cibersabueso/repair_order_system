from dataclasses import dataclass
from typing import Any

from ..enums import ErrorCode


@dataclass
class DomainError:
    operation: str
    order_id: str
    code: ErrorCode
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.operation,
            "order_id": self.order_id,
            "code": self.code.value,
            "message": self.message
        }


class DomainException(Exception):
    def __init__(self, error: DomainError):
        self.error = error
        super().__init__(error.message)


class OrderCancelledException(DomainException):
    pass


class SequenceErrorException(DomainException):
    pass


class NotAllowedAfterAuthorizationException(DomainException):
    pass


class NoServicesException(DomainException):
    pass


class RequiresReauthException(DomainException):
    pass


class InvalidOperationException(DomainException):
    pass
