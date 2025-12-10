from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ComponentData(BaseModel):
    description: str
    estimated_cost: str


class ServiceData(BaseModel):
    description: str
    labor_estimated_cost: str
    components: list[ComponentData] = Field(default_factory=list)


class CommandData(BaseModel):
    order_id: Optional[str] = None
    customer: Optional[str] = None
    vehicle: Optional[str] = None
    service: Optional[ServiceData] = None
    service_index: Optional[int] = None
    component_index: Optional[int] = None
    real_cost: Optional[str] = None
    completed: Optional[bool] = None
    new_authorized_amount: Optional[str] = None
    reason: Optional[str] = None


class Command(BaseModel):
    op: str
    ts: datetime
    data: CommandData


class CommandRequest(BaseModel):
    commands: list[Command]
