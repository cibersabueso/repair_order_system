from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..value_objects.money import Money
from ..enums import OrderStatus, ErrorCode
from ..events.domain_event import DomainEvent
from ..exceptions.domain_exceptions import (
    DomainError,
    OrderCancelledException,
    SequenceErrorException,
    NotAllowedAfterAuthorizationException,
    NoServicesException,
    RequiresReauthException,
    InvalidOperationException
)
from .service import Service
from .authorization import Authorization


@dataclass
class RepairOrder:
    order_id: str
    customer: str
    vehicle: str
    status: OrderStatus = OrderStatus.CREATED
    services: list[Service] = field(default_factory=list)
    authorization: Optional[Authorization] = None
    events: list[DomainEvent] = field(default_factory=list)
    cancel_reason: Optional[str] = None

    VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = field(
        default_factory=lambda: {
            OrderStatus.CREATED: {OrderStatus.DIAGNOSED, OrderStatus.CANCELLED},
            OrderStatus.DIAGNOSED: {OrderStatus.AUTHORIZED, OrderStatus.CANCELLED},
            OrderStatus.AUTHORIZED: {OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED},
            OrderStatus.IN_PROGRESS: {
                OrderStatus.COMPLETED,
                OrderStatus.WAITING_FOR_APPROVAL,
                OrderStatus.CANCELLED
            },
            OrderStatus.WAITING_FOR_APPROVAL: {OrderStatus.AUTHORIZED, OrderStatus.CANCELLED},
            OrderStatus.COMPLETED: {OrderStatus.DELIVERED, OrderStatus.CANCELLED},
            OrderStatus.DELIVERED: set(),
            OrderStatus.CANCELLED: set()
        }
    )

    @classmethod
    def create(cls, order_id: str, customer: str, vehicle: str, timestamp: datetime) -> 'RepairOrder':
        order = cls(order_id=order_id, customer=customer, vehicle=vehicle)
        order._record_event("CREATED", timestamp)
        return order

    def _record_event(self, event_type: str, timestamp: datetime, metadata: dict = None) -> None:
        event = DomainEvent(
            order_id=self.order_id,
            event_type=event_type,
            timestamp=timestamp,
            metadata=metadata or {}
        )
        self.events.append(event)

    def _validate_not_cancelled(self, operation: str) -> None:
        if self.status == OrderStatus.CANCELLED:
            raise OrderCancelledException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.ORDER_CANCELLED,
                message=f"La orden {self.order_id} está cancelada."
            ))

    def _validate_transition(self, target: OrderStatus, operation: str) -> None:
        if target not in self.VALID_TRANSITIONS.get(self.status, set()):
            raise SequenceErrorException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.SEQUENCE_ERROR,
                message=f"Transición inválida de {self.status.value} a {target.value}."
            ))

    def _can_modify_services(self) -> bool:
        return self.status in {OrderStatus.CREATED, OrderStatus.DIAGNOSED}

    def add_service(self, service: Service, operation: str, timestamp: datetime) -> None:
        self._validate_not_cancelled(operation)
        if not self._can_modify_services():
            raise NotAllowedAfterAuthorizationException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.NOT_ALLOWED_AFTER_AUTHORIZATION,
                message="No se pueden modificar servicios después de la autorización."
            ))
        self.services.append(service)

    def set_diagnosed(self, operation: str, timestamp: datetime) -> None:
        self._validate_not_cancelled(operation)
        self._validate_transition(OrderStatus.DIAGNOSED, operation)
        self.status = OrderStatus.DIAGNOSED
        self._record_event("DIAGNOSED", timestamp)

    def authorize(self, operation: str, timestamp: datetime) -> None:
        self._validate_not_cancelled(operation)
        self._validate_transition(OrderStatus.AUTHORIZED, operation)
        
        if not self.services:
            raise NoServicesException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.NO_SERVICES,
                message="No existen servicios válidos para autorizar."
            ))
        
        subtotal = self.get_subtotal_estimated()
        self.authorization = Authorization.create_initial(subtotal, timestamp)
        self.status = OrderStatus.AUTHORIZED
        self._record_event("AUTHORIZED", timestamp, {
            "subtotal": str(subtotal),
            "authorized_amount": str(self.authorization.authorized_amount)
        })

    def set_in_progress(self, operation: str, timestamp: datetime) -> None:
        self._validate_not_cancelled(operation)
        
        if self.status != OrderStatus.AUTHORIZED:
            raise SequenceErrorException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.SEQUENCE_ERROR,
                message="La orden debe estar autorizada para iniciar el trabajo."
            ))
        
        self._validate_transition(OrderStatus.IN_PROGRESS, operation)
        self.status = OrderStatus.IN_PROGRESS
        self._record_event("IN_PROGRESS", timestamp)

    def set_real_cost(
        self,
        service_index: int,
        real_cost: Money,
        completed: bool,
        operation: str,
        timestamp: datetime,
        component_index: Optional[int] = None
    ) -> None:
        self._validate_not_cancelled(operation)
        
        if self.status != OrderStatus.IN_PROGRESS:
            raise SequenceErrorException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.SEQUENCE_ERROR,
                message="Solo se pueden registrar costos reales cuando la orden está en progreso."
            ))
        
        if service_index < 1 or service_index > len(self.services):
            raise InvalidOperationException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.INVALID_OPERATION,
                message=f"Índice de servicio inválido: {service_index}"
            ))
        
        service = self.services[service_index - 1]
        
        if component_index is not None:
            service.set_component_real_cost(component_index - 1, real_cost)
        else:
            service.set_real_cost(real_cost, completed)
        
        self._check_cost_overrun(timestamp)

    def _check_cost_overrun(self, timestamp: datetime) -> None:
        if self.authorization is None:
            return
        
        real_total = self.get_real_total()
        if self.authorization.exceeds_limit(real_total):
            self.status = OrderStatus.WAITING_FOR_APPROVAL
            self._record_event("WAITING_FOR_APPROVAL", timestamp, {
                "real_total": str(real_total),
                "limit": str(self.authorization.get_limit())
            })

    def try_complete(self, operation: str, timestamp: datetime) -> None:
        self._validate_not_cancelled(operation)
        
        if self.status == OrderStatus.WAITING_FOR_APPROVAL:
            raise RequiresReauthException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.REQUIRES_REAUTH,
                message=(
                    f"El costo real ({self.get_real_total()}) excede el 110% del monto autorizado "
                    f"({self.authorization.authorized_amount}). "
                    f"Límite: {self.authorization.get_limit()}."
                )
            ))
        
        if self.status != OrderStatus.IN_PROGRESS:
            raise SequenceErrorException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.SEQUENCE_ERROR,
                message="La orden debe estar en progreso para completarla."
            ))
        
        real_total = self.get_real_total()
        if self.authorization and self.authorization.exceeds_limit(real_total):
            self.status = OrderStatus.WAITING_FOR_APPROVAL
            self._record_event("WAITING_FOR_APPROVAL", timestamp, {
                "real_total": str(real_total),
                "limit": str(self.authorization.get_limit())
            })
            raise RequiresReauthException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.REQUIRES_REAUTH,
                message=(
                    f"El costo real ({real_total}) excede el 110% del monto autorizado "
                    f"({self.authorization.authorized_amount}). "
                    f"Límite: {self.authorization.get_limit()}."
                )
            ))
        
        self.status = OrderStatus.COMPLETED
        self._record_event("COMPLETED", timestamp)

    def reauthorize(self, new_amount: Money, operation: str, timestamp: datetime) -> None:
        self._validate_not_cancelled(operation)
        
        if self.status != OrderStatus.WAITING_FOR_APPROVAL:
            raise SequenceErrorException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.SEQUENCE_ERROR,
                message="Solo se puede re-autorizar cuando la orden está esperando aprobación."
            ))
        
        previous_version = self.authorization.version if self.authorization else 0
        self.authorization = Authorization.create_reauthorization(
            new_amount, timestamp, previous_version
        )
        self.status = OrderStatus.AUTHORIZED
        self._record_event("REAUTHORIZED", timestamp, {
            "new_authorized_amount": str(new_amount),
            "version": self.authorization.version
        })

    def deliver(self, operation: str, timestamp: datetime) -> None:
        self._validate_not_cancelled(operation)
        self._validate_transition(OrderStatus.DELIVERED, operation)
        self.status = OrderStatus.DELIVERED
        self._record_event("DELIVERED", timestamp)

    def cancel(self, reason: str, operation: str, timestamp: datetime) -> None:
        if self.status == OrderStatus.CANCELLED:
            return
        
        if self.status == OrderStatus.DELIVERED:
            raise InvalidOperationException(DomainError(
                operation=operation,
                order_id=self.order_id,
                code=ErrorCode.INVALID_OPERATION,
                message="No se puede cancelar una orden ya entregada."
            ))
        
        self.cancel_reason = reason
        self.status = OrderStatus.CANCELLED
        self._record_event("CANCELLED", timestamp, {"reason": reason})

    def get_subtotal_estimated(self) -> Money:
        total = Money.zero()
        for service in self.services:
            total = total.add(service.get_estimated_total())
        return total

    def get_real_total(self) -> Money:
        total = Money.zero()
        for service in self.services:
            total = total.add(service.get_real_total())
        return total

    def get_authorized_amount(self) -> Optional[Money]:
        return self.authorization.authorized_amount if self.authorization else None

    def to_dict(self) -> dict:
        result = {
            "order_id": self.order_id,
            "status": self.status.value,
            "customer": self.customer,
            "vehicle": self.vehicle,
            "subtotal_estimated": str(self.get_subtotal_estimated())
        }
        
        if self.authorization:
            result["authorized_amount"] = str(self.authorization.authorized_amount)
        
        real_total = self.get_real_total()
        if real_total.amount > 0:
            result["real_total"] = str(real_total)
        
        return result
