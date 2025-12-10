from dataclasses import dataclass, field
from typing import Optional

from ..value_objects.money import Money
from .component import Component


@dataclass
class Service:
    description: str
    labor_estimated_cost: Money
    components: list[Component] = field(default_factory=list)
    real_labor_cost: Optional[Money] = None
    completed: bool = False

    @classmethod
    def create(
        cls,
        description: str,
        labor_estimated_cost: str,
        components_data: list[dict]
    ) -> 'Service':
        components = [
            Component.create(c["description"], c["estimated_cost"])
            for c in components_data
        ]
        return cls(
            description=description,
            labor_estimated_cost=Money.from_string(labor_estimated_cost),
            components=components
        )

    def get_estimated_total(self) -> Money:
        total = self.labor_estimated_cost
        for component in self.components:
            total = total.add(component.get_estimated_cost())
        return total

    def get_real_total(self) -> Money:
        if self.real_labor_cost is None:
            return Money.zero()
        total = self.real_labor_cost
        for component in self.components:
            total = total.add(component.get_real_cost())
        return total

    def set_real_cost(self, cost: Money, is_completed: bool) -> None:
        self.real_labor_cost = cost
        self.completed = is_completed

    def set_component_real_cost(self, index: int, cost: Money) -> None:
        if 0 <= index < len(self.components):
            self.components[index].set_real_cost(cost)

    def is_completed(self) -> bool:
        return self.completed
