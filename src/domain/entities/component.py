from dataclasses import dataclass
from typing import Optional

from ..value_objects.money import Money


@dataclass
class Component:
    description: str
    estimated_cost: Money
    real_cost: Optional[Money] = None

    @classmethod
    def create(cls, description: str, estimated_cost: str) -> 'Component':
        return cls(
            description=description,
            estimated_cost=Money.from_string(estimated_cost)
        )

    def set_real_cost(self, cost: Money) -> None:
        self.real_cost = cost

    def get_estimated_cost(self) -> Money:
        return self.estimated_cost

    def get_real_cost(self) -> Money:
        return self.real_cost if self.real_cost else Money.zero()
