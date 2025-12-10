from abc import ABC, abstractmethod
from typing import Optional

from ..entities import RepairOrder


class RepairOrderRepository(ABC):
    @abstractmethod
    def save(self, order: RepairOrder) -> None:
        pass

    @abstractmethod
    def find_by_id(self, order_id: str) -> Optional[RepairOrder]:
        pass

    @abstractmethod
    def find_all(self) -> list[RepairOrder]:
        pass

    @abstractmethod
    def exists(self, order_id: str) -> bool:
        pass
