from typing import Optional

from ...domain import RepairOrder, RepairOrderRepository


class InMemoryRepairOrderRepository(RepairOrderRepository):
    def __init__(self):
        self._orders: dict[str, RepairOrder] = {}

    def save(self, order: RepairOrder) -> None:
        self._orders[order.order_id] = order

    def find_by_id(self, order_id: str) -> Optional[RepairOrder]:
        return self._orders.get(order_id)

    def find_all(self) -> list[RepairOrder]:
        return list(self._orders.values())

    def exists(self, order_id: str) -> bool:
        return order_id in self._orders

    def clear(self) -> None:
        self._orders.clear()
