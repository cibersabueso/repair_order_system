from decimal import Decimal, ROUND_HALF_EVEN
from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    amount: Decimal

    def __post_init__(self):
        object.__setattr__(self, 'amount', self._normalize(self.amount))

    @staticmethod
    def _normalize(value: Decimal | str | float) -> Decimal:
        if isinstance(value, str):
            value = Decimal(value)
        elif isinstance(value, float):
            value = Decimal(str(value))
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

    @classmethod
    def zero(cls) -> 'Money':
        return cls(Decimal('0.00'))

    @classmethod
    def from_string(cls, value: str) -> 'Money':
        return cls(Decimal(value))

    def add(self, other: 'Money') -> 'Money':
        return Money(self.amount + other.amount)

    def multiply(self, factor: Decimal | str | float) -> 'Money':
        if isinstance(factor, (str, float)):
            factor = Decimal(str(factor))
        return Money(self.amount * factor)

    def is_greater_than(self, other: 'Money') -> bool:
        return self.amount > other.amount

    def is_less_than_or_equal(self, other: 'Money') -> bool:
        return self.amount <= other.amount

    def __str__(self) -> str:
        return f"{self.amount:.2f}"

    def __repr__(self) -> str:
        return f"Money({self.amount:.2f})"
