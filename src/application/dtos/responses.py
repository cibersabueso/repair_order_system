from pydantic import BaseModel
from typing import Any


class OrderResponse(BaseModel):
    order_id: str
    status: str
    customer: str
    vehicle: str
    subtotal_estimated: str
    authorized_amount: str | None = None
    real_total: str | None = None


class EventResponse(BaseModel):
    order_id: str
    type: str


class ErrorResponse(BaseModel):
    op: str
    order_id: str
    code: str
    message: str


class CommandResponse(BaseModel):
    orders: list[dict[str, Any]]
    events: list[dict[str, str]]
    errors: list[dict[str, Any]]
