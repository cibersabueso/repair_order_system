from datetime import datetime
from typing import Any

from ...domain import (
    RepairOrder,
    Service,
    Money,
    RepairOrderRepository,
    DomainException,
    DomainError,
    ErrorCode,
    InvalidOperationException
)
from ..dtos import Command, CommandResponse


class CommandHandler:
    def __init__(self, repository: RepairOrderRepository):
        self._repository = repository
        self._errors: list[dict[str, Any]] = []
        self._handlers = {
            "CREATE_ORDER": self._handle_create_order,
            "ADD_SERVICE": self._handle_add_service,
            "SET_STATE_DIAGNOSED": self._handle_set_diagnosed,
            "AUTHORIZE": self._handle_authorize,
            "SET_STATE_IN_PROGRESS": self._handle_set_in_progress,
            "SET_REAL_COST": self._handle_set_real_cost,
            "TRY_COMPLETE": self._handle_try_complete,
            "REAUTHORIZE": self._handle_reauthorize,
            "DELIVER": self._handle_deliver,
            "CANCEL": self._handle_cancel
        }

    def execute(self, commands: list[Command]) -> CommandResponse:
        self._errors = []
        
        for command in commands:
            self._process_command(command)
        
        orders = self._repository.find_all()
        all_events = []
        for order in orders:
            all_events.extend(order.events)
        
        return CommandResponse(
            orders=[order.to_dict() for order in orders],
            events=[event.to_simple_dict() for event in all_events],
            errors=self._errors
        )

    def _process_command(self, command: Command) -> None:
        handler = self._handlers.get(command.op)
        if handler is None:
            self._record_error(
                command.op,
                command.data.order_id or "UNKNOWN",
                ErrorCode.INVALID_OPERATION,
                f"Operación no reconocida: {command.op}"
            )
            return
        
        try:
            handler(command)
        except DomainException as e:
            self._errors.append(e.error.to_dict())

    def _record_error(self, op: str, order_id: str, code: ErrorCode, message: str) -> None:
        error = DomainError(
            operation=op,
            order_id=order_id,
            code=code,
            message=message
        )
        self._errors.append(error.to_dict())

    def _get_order(self, order_id: str, operation: str) -> RepairOrder:
        order = self._repository.find_by_id(order_id)
        if order is None:
            raise InvalidOperationException(DomainError(
                operation=operation,
                order_id=order_id,
                code=ErrorCode.INVALID_OPERATION,
                message=f"Orden no encontrada: {order_id}"
            ))
        return order

    def _handle_create_order(self, command: Command) -> None:
        data = command.data
        order = RepairOrder.create(
            order_id=data.order_id,
            customer=data.customer,
            vehicle=data.vehicle,
            timestamp=command.ts
        )
        self._repository.save(order)

    def _handle_add_service(self, command: Command) -> None:
        data = command.data
        order = self._get_order(data.order_id, command.op)
        
        service_data = data.service
        components = [
            {"description": c.description, "estimated_cost": c.estimated_cost}
            for c in service_data.components
        ]
        
        service = Service.create(
            description=service_data.description,
            labor_estimated_cost=service_data.labor_estimated_cost,
            components_data=components
        )
        
        order.add_service(service, command.op, command.ts)
        self._repository.save(order)

    def _handle_set_diagnosed(self, command: Command) -> None:
        order = self._get_order(command.data.order_id, command.op)
        order.set_diagnosed(command.op, command.ts)
        self._repository.save(order)

    def _handle_authorize(self, command: Command) -> None:
        order = self._get_order(command.data.order_id, command.op)
        order.authorize(command.op, command.ts)
        self._repository.save(order)

    def _handle_set_in_progress(self, command: Command) -> None:
        order = self._get_order(command.data.order_id, command.op)
        order.set_in_progress(command.op, command.ts)
        self._repository.save(order)

    def _handle_set_real_cost(self, command: Command) -> None:
        data = command.data
        order = self._get_order(data.order_id, command.op)
        
        order.set_real_cost(
            service_index=data.service_index,
            real_cost=Money.from_string(data.real_cost),
            completed=data.completed or False,
            operation=command.op,
            timestamp=command.ts,
            component_index=data.component_index
        )
        self._repository.save(order)

    def _handle_try_complete(self, command: Command) -> None:
        order = self._get_order(command.data.order_id, command.op)
        order.try_complete(command.op, command.ts)
        self._repository.save(order)

    def _handle_reauthorize(self, command: Command) -> None:
        data = command.data
        order = self._get_order(data.order_id, command.op)
        
        new_amount = Money.from_string(data.new_authorized_amount)
        order.reauthorize(new_amount, command.op, command.ts)
        self._repository.save(order)

    def _handle_deliver(self, command: Command) -> None:
        order = self._get_order(command.data.order_id, command.op)
        order.deliver(command.op, command.ts)
        self._repository.save(order)

    def _handle_cancel(self, command: Command) -> None:
        data = command.data
        order = self._get_order(data.order_id, command.op)
        order.cancel(data.reason or "", command.op, command.ts)
        self._repository.save(order)
