import pytest
from datetime import datetime
from decimal import Decimal

from src.domain import (
    RepairOrder,
    Service,
    Component,
    Money,
    OrderStatus,
    ErrorCode
)
from src.domain.exceptions import (
    DomainException,
    SequenceErrorException,
    NotAllowedAfterAuthorizationException,
    NoServicesException,
    RequiresReauthException
)
from src.application import CommandHandler, CommandRequest
from src.infrastructure.adapters import InMemoryRepairOrderRepository


class TestMoney:
    def test_half_even_rounding(self):
        assert str(Money(Decimal("10.005"))) == "10.00"
        assert str(Money(Decimal("10.015"))) == "10.02"
        assert str(Money(Decimal("10.025"))) == "10.02"
        assert str(Money(Decimal("10.035"))) == "10.04"

    def test_arithmetic_operations(self):
        m1 = Money.from_string("100.00")
        m2 = Money.from_string("50.00")
        
        assert str(m1.add(m2)) == "150.00"
        assert str(m1.multiply("1.16")) == "116.00"

    def test_comparison(self):
        m1 = Money.from_string("100.00")
        m2 = Money.from_string("99.99")
        
        assert m1.is_greater_than(m2)
        assert m2.is_less_than_or_equal(m1)


class TestRepairOrder:
    def _create_base_order(self) -> RepairOrder:
        return RepairOrder.create(
            order_id="R001",
            customer="ACME",
            vehicle="ABC-123",
            timestamp=datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        )

    def _add_service_to_order(self, order: RepairOrder) -> None:
        service = Service.create(
            description="Engine repair",
            labor_estimated_cost="10000.00",
            components_data=[{"description": "Oil pump", "estimated_cost": "1500.00"}]
        )
        order.add_service(
            service,
            "ADD_SERVICE",
            datetime.fromisoformat("2025-03-01T09:05:00+00:00")
        )

    def test_order_starts_in_created_status(self):
        order = self._create_base_order()
        assert order.status == OrderStatus.CREATED

    def test_case_1_complete_flow_delivered(self):
        order = self._create_base_order()
        ts = datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        
        self._add_service_to_order(order)
        order.set_diagnosed("SET_STATE_DIAGNOSED", ts)
        order.authorize("AUTHORIZE", ts)
        order.set_in_progress("SET_STATE_IN_PROGRESS", ts)
        
        order.set_real_cost(
            service_index=1,
            real_cost=Money.from_string("11500.00"),
            completed=True,
            operation="SET_REAL_COST",
            timestamp=ts
        )
        
        order.try_complete("TRY_COMPLETE", ts)
        order.deliver("DELIVER", ts)
        
        assert order.status == OrderStatus.DELIVERED

    def test_case_2_exceeds_110_percent(self):
        order = self._create_base_order()
        ts = datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        
        self._add_service_to_order(order)
        order.set_diagnosed("SET_STATE_DIAGNOSED", ts)
        order.authorize("AUTHORIZE", ts)
        order.set_in_progress("SET_STATE_IN_PROGRESS", ts)
        
        order.set_real_cost(
            service_index=1,
            real_cost=Money.from_string("15000.00"),
            completed=True,
            operation="SET_REAL_COST",
            timestamp=ts
        )
        
        assert order.status == OrderStatus.WAITING_FOR_APPROVAL
        
        with pytest.raises(RequiresReauthException) as exc_info:
            order.try_complete("TRY_COMPLETE", ts)
        
        assert exc_info.value.error.code == ErrorCode.REQUIRES_REAUTH

    def test_case_3_exactly_110_percent(self):
        order = self._create_base_order()
        ts = datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        
        self._add_service_to_order(order)
        order.set_diagnosed("SET_STATE_DIAGNOSED", ts)
        order.authorize("AUTHORIZE", ts)
        order.set_in_progress("SET_STATE_IN_PROGRESS", ts)
        
        order.set_real_cost(
            service_index=1,
            real_cost=Money.from_string("14674.00"),
            completed=True,
            operation="SET_REAL_COST",
            timestamp=ts
        )
        
        order.try_complete("TRY_COMPLETE", ts)
        assert order.status == OrderStatus.COMPLETED

    def test_case_4_reauthorization(self):
        order = self._create_base_order()
        ts = datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        
        self._add_service_to_order(order)
        order.set_diagnosed("SET_STATE_DIAGNOSED", ts)
        order.authorize("AUTHORIZE", ts)
        order.set_in_progress("SET_STATE_IN_PROGRESS", ts)
        
        order.set_real_cost(
            service_index=1,
            real_cost=Money.from_string("15000.00"),
            completed=True,
            operation="SET_REAL_COST",
            timestamp=ts
        )
        
        assert order.status == OrderStatus.WAITING_FOR_APPROVAL
        
        order.reauthorize(Money.from_string("20000.00"), "REAUTHORIZE", ts)
        assert order.status == OrderStatus.AUTHORIZED
        
        order.set_in_progress("SET_STATE_IN_PROGRESS", ts)
        order.try_complete("TRY_COMPLETE", ts)
        
        assert order.status == OrderStatus.COMPLETED

    def test_case_5_start_without_authorization(self):
        order = self._create_base_order()
        ts = datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        
        self._add_service_to_order(order)
        order.set_diagnosed("SET_STATE_DIAGNOSED", ts)
        
        with pytest.raises(SequenceErrorException) as exc_info:
            order.set_in_progress("SET_STATE_IN_PROGRESS", ts)
        
        assert exc_info.value.error.code == ErrorCode.SEQUENCE_ERROR

    def test_case_6_modify_after_authorization(self):
        order = self._create_base_order()
        ts = datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        
        self._add_service_to_order(order)
        order.set_diagnosed("SET_STATE_DIAGNOSED", ts)
        order.authorize("AUTHORIZE", ts)
        
        new_service = Service.create(
            description="Brake repair",
            labor_estimated_cost="500.00",
            components_data=[]
        )
        
        with pytest.raises(NotAllowedAfterAuthorizationException) as exc_info:
            order.add_service(new_service, "ADD_SERVICE", ts)
        
        assert exc_info.value.error.code == ErrorCode.NOT_ALLOWED_AFTER_AUTHORIZATION

    def test_case_7_cancel_order(self):
        order = self._create_base_order()
        ts = datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        
        self._add_service_to_order(order)
        order.set_diagnosed("SET_STATE_DIAGNOSED", ts)
        order.authorize("AUTHORIZE", ts)
        
        order.cancel("Cliente solicitó cancelación", "CANCEL", ts)
        
        assert order.status == OrderStatus.CANCELLED
        assert order.cancel_reason == "Cliente solicitó cancelación"

    def test_case_8_authorize_without_services(self):
        order = self._create_base_order()
        ts = datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        
        order.set_diagnosed("SET_STATE_DIAGNOSED", ts)
        
        with pytest.raises(NoServicesException) as exc_info:
            order.authorize("AUTHORIZE", ts)
        
        assert exc_info.value.error.code == ErrorCode.NO_SERVICES

    def test_case_9_rounding_precision(self):
        order = self._create_base_order()
        ts = datetime.fromisoformat("2025-03-01T09:00:00+00:00")
        
        service = Service.create(
            description="Engine repair",
            labor_estimated_cost="10000.00",
            components_data=[{"description": "Oil pump", "estimated_cost": "1500.00"}]
        )
        order.add_service(service, "ADD_SERVICE", ts)
        
        assert str(order.get_subtotal_estimated()) == "11500.00"
        
        order.set_diagnosed("SET_STATE_DIAGNOSED", ts)
        order.authorize("AUTHORIZE", ts)
        
        assert str(order.get_authorized_amount()) == "13340.00"
        
        limit = order.authorization.get_limit()
        assert str(limit) == "14674.00"


class TestCommandHandler:
    def setup_method(self):
        self.repository = InMemoryRepairOrderRepository()
        self.handler = CommandHandler(self.repository)

    def _create_command(self, op: str, ts: str, data: dict) -> dict:
        return {"op": op, "ts": ts, "data": data}

    def test_full_workflow_from_json(self):
        commands = [
            self._create_command(
                "CREATE_ORDER",
                "2025-03-01T09:00:00Z",
                {"order_id": "R001", "customer": "ACME", "vehicle": "ABC-123"}
            ),
            self._create_command(
                "ADD_SERVICE",
                "2025-03-01T09:05:00Z",
                {
                    "order_id": "R001",
                    "service": {
                        "description": "Engine repair",
                        "labor_estimated_cost": "10000.00",
                        "components": [
                            {"description": "Oil pump", "estimated_cost": "1500.00"}
                        ]
                    }
                }
            ),
            self._create_command(
                "SET_STATE_DIAGNOSED",
                "2025-03-01T09:10:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "AUTHORIZE",
                "2025-03-01T09:11:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "SET_STATE_IN_PROGRESS",
                "2025-03-01T09:15:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "SET_REAL_COST",
                "2025-03-01T09:20:00Z",
                {
                    "order_id": "R001",
                    "service_index": 1,
                    "real_cost": "15000.00",
                    "completed": True
                }
            ),
            self._create_command(
                "TRY_COMPLETE",
                "2025-03-01T09:25:00Z",
                {"order_id": "R001"}
            )
        ]

        request = CommandRequest(commands=commands)
        response = self.handler.execute(request.commands)

        assert len(response.orders) == 1
        order = response.orders[0]
        assert order["order_id"] == "R001"
        assert order["status"] == "WAITING_FOR_APPROVAL"
        assert order["subtotal_estimated"] == "11500.00"
        assert order["authorized_amount"] == "13340.00"
        assert order["real_total"] == "15000.00"

        assert len(response.errors) == 1
        error = response.errors[0]
        assert error["code"] == "REQUIRES_REAUTH"
        assert error["op"] == "TRY_COMPLETE"

    def test_multiple_orders(self):
        commands = [
            self._create_command(
                "CREATE_ORDER",
                "2025-03-01T09:00:00Z",
                {"order_id": "R001", "customer": "ACME", "vehicle": "ABC-123"}
            ),
            self._create_command(
                "CREATE_ORDER",
                "2025-03-01T09:00:00Z",
                {"order_id": "R002", "customer": "BETA", "vehicle": "XYZ-789"}
            )
        ]

        request = CommandRequest(commands=commands)
        response = self.handler.execute(request.commands)

        assert len(response.orders) == 2

    def test_event_tracking(self):
        commands = [
            self._create_command(
                "CREATE_ORDER",
                "2025-03-01T09:00:00Z",
                {"order_id": "R001", "customer": "ACME", "vehicle": "ABC-123"}
            ),
            self._create_command(
                "ADD_SERVICE",
                "2025-03-01T09:05:00Z",
                {
                    "order_id": "R001",
                    "service": {
                        "description": "Oil change",
                        "labor_estimated_cost": "100.00",
                        "components": []
                    }
                }
            ),
            self._create_command(
                "SET_STATE_DIAGNOSED",
                "2025-03-01T09:10:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "AUTHORIZE",
                "2025-03-01T09:11:00Z",
                {"order_id": "R001"}
            )
        ]

        request = CommandRequest(commands=commands)
        response = self.handler.execute(request.commands)

        event_types = [e["type"] for e in response.events]
        assert "CREATED" in event_types
        assert "DIAGNOSED" in event_types
        assert "AUTHORIZED" in event_types


class TestIntegrationScenarios:
    def setup_method(self):
        self.repository = InMemoryRepairOrderRepository()
        self.handler = CommandHandler(self.repository)

    def _create_command(self, op: str, ts: str, data: dict) -> dict:
        return {"op": op, "ts": ts, "data": data}

    def test_complete_delivery_flow(self):
        commands = [
            self._create_command(
                "CREATE_ORDER",
                "2025-03-01T09:00:00Z",
                {"order_id": "R001", "customer": "ACME", "vehicle": "ABC-123"}
            ),
            self._create_command(
                "ADD_SERVICE",
                "2025-03-01T09:05:00Z",
                {
                    "order_id": "R001",
                    "service": {
                        "description": "Oil change",
                        "labor_estimated_cost": "1000.00",
                        "components": []
                    }
                }
            ),
            self._create_command(
                "SET_STATE_DIAGNOSED",
                "2025-03-01T09:10:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "AUTHORIZE",
                "2025-03-01T09:11:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "SET_STATE_IN_PROGRESS",
                "2025-03-01T09:15:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "SET_REAL_COST",
                "2025-03-01T09:20:00Z",
                {
                    "order_id": "R001",
                    "service_index": 1,
                    "real_cost": "1000.00",
                    "completed": True
                }
            ),
            self._create_command(
                "TRY_COMPLETE",
                "2025-03-01T09:25:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "DELIVER",
                "2025-03-01T10:00:00Z",
                {"order_id": "R001"}
            )
        ]

        request = CommandRequest(commands=commands)
        response = self.handler.execute(request.commands)

        assert len(response.errors) == 0
        assert response.orders[0]["status"] == "DELIVERED"

    def test_reauthorization_flow(self):
        commands = [
            self._create_command(
                "CREATE_ORDER",
                "2025-03-01T09:00:00Z",
                {"order_id": "R001", "customer": "ACME", "vehicle": "ABC-123"}
            ),
            self._create_command(
                "ADD_SERVICE",
                "2025-03-01T09:05:00Z",
                {
                    "order_id": "R001",
                    "service": {
                        "description": "Engine repair",
                        "labor_estimated_cost": "10000.00",
                        "components": [
                            {"description": "Oil pump", "estimated_cost": "1500.00"}
                        ]
                    }
                }
            ),
            self._create_command(
                "SET_STATE_DIAGNOSED",
                "2025-03-01T09:10:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "AUTHORIZE",
                "2025-03-01T09:11:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "SET_STATE_IN_PROGRESS",
                "2025-03-01T09:15:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "SET_REAL_COST",
                "2025-03-01T09:20:00Z",
                {
                    "order_id": "R001",
                    "service_index": 1,
                    "real_cost": "20000.00",
                    "completed": True
                }
            ),
            self._create_command(
                "TRY_COMPLETE",
                "2025-03-01T09:25:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "REAUTHORIZE",
                "2025-03-01T09:30:00Z",
                {
                    "order_id": "R001",
                    "new_authorized_amount": "25000.00"
                }
            ),
            self._create_command(
                "SET_STATE_IN_PROGRESS",
                "2025-03-01T09:35:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "TRY_COMPLETE",
                "2025-03-01T09:40:00Z",
                {"order_id": "R001"}
            ),
            self._create_command(
                "DELIVER",
                "2025-03-01T10:00:00Z",
                {"order_id": "R001"}
            )
        ]

        request = CommandRequest(commands=commands)
        response = self.handler.execute(request.commands)

        reauth_errors = [e for e in response.errors if e["code"] == "REQUIRES_REAUTH"]
        assert len(reauth_errors) == 1

        assert response.orders[0]["status"] == "DELIVERED"

    def test_cancellation_flow(self):
        commands = [
            self._create_command(
                "CREATE_ORDER",
                "2025-03-01T09:00:00Z",
                {"order_id": "R001", "customer": "ACME", "vehicle": "ABC-123"}
            ),
            self._create_command(
                "ADD_SERVICE",
                "2025-03-01T09:05:00Z",
                {
                    "order_id": "R001",
                    "service": {
                        "description": "Oil change",
                        "labor_estimated_cost": "100.00",
                        "components": []
                    }
                }
            ),
            self._create_command(
                "CANCEL",
                "2025-03-01T09:10:00Z",
                {
                    "order_id": "R001",
                    "reason": "Customer request"
                }
            )
        ]

        request = CommandRequest(commands=commands)
        response = self.handler.execute(request.commands)

        assert response.orders[0]["status"] == "CANCELLED"
        
        event_types = [e["type"] for e in response.events]
        assert "CANCELLED" in event_types
