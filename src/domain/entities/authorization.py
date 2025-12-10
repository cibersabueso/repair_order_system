from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..value_objects.money import Money


@dataclass
class Authorization:
    version: int
    authorized_amount: Money
    timestamp: datetime
    subtotal: Money

    IVA_RATE = Decimal("1.16")
    OVERRUN_LIMIT = Decimal("1.10")

    @classmethod
    def create_initial(cls, subtotal: Money, timestamp: datetime) -> 'Authorization':
        authorized_amount = subtotal.multiply(cls.IVA_RATE)
        return cls(
            version=1,
            authorized_amount=authorized_amount,
            timestamp=timestamp,
            subtotal=subtotal
        )

    @classmethod
    def create_reauthorization(
        cls,
        new_amount: Money,
        timestamp: datetime,
        previous_version: int
    ) -> 'Authorization':
        return cls(
            version=previous_version + 1,
            authorized_amount=new_amount,
            timestamp=timestamp,
            subtotal=Money.zero()
        )

    def get_limit(self) -> Money:
        return self.authorized_amount.multiply(self.OVERRUN_LIMIT)

    def exceeds_limit(self, real_total: Money) -> bool:
        return real_total.is_greater_than(self.get_limit())
