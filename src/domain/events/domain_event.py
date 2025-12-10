from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DomainEvent:
    order_id: str
    event_type: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "type": self.event_type,
            "ts": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    def to_simple_dict(self) -> dict[str, str]:
        return {
            "order_id": self.order_id,
            "type": self.event_type
        }
