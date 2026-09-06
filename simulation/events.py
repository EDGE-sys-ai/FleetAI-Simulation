from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import uuid


class EventType(str, Enum):
    PRODUCT_ARRIVED = "PRODUCT_ARRIVED"
    PRODUCT_LOADED = "PRODUCT_LOADED"
    PRODUCT_SCANNED = "PRODUCT_SCANNED"
    DESTINATION_ASSIGNED = "DESTINATION_ASSIGNED"
    ROBOT_DISPATCHED = "ROBOT_DISPATCHED"
    ROBOT_MOVING = "ROBOT_MOVING"
    ROBOT_ARRIVED = "ROBOT_ARRIVED"
    PRODUCT_DELIVERED = "PRODUCT_DELIVERED"
    INVENTORY_UPDATED = "INVENTORY_UPDATED"
    SHIPMENT_CREATED = "SHIPMENT_CREATED"
    SHIPMENT_DISPATCHED = "SHIPMENT_DISPATCHED"
    SHIPMENT_IN_TRANSIT = "SHIPMENT_IN_TRANSIT"
    SHIPMENT_RECEIVED = "SHIPMENT_RECEIVED"
    PRODUCT_RESCANNED = "PRODUCT_RESCANNED"
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_PICKED = "ORDER_PICKED"
    ORDER_COMPLETED = "ORDER_COMPLETED"
    ROBOT_CHARGING = "ROBOT_CHARGING"
    ROBOT_IDLE = "ROBOT_IDLE"
    DIGITAL_TWIN_SYNC = "DIGITAL_TWIN_SYNC"
    DIGITAL_TWIN_DESYNC = "DIGITAL_TWIN_DESYNC"
    SCAN_FAILED = "SCAN_FAILED"
    ROBOT_ERROR = "ROBOT_ERROR"
    NETWORK_DELAY = "NETWORK_DELAY"


@dataclass
class Event:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type: EventType = EventType.PRODUCT_ARRIVED
    timestamp: datetime = field(default_factory=datetime.now)
    warehouse_id: str = ""
    product_id: str = ""
    robot_id: str = ""
    order_id: str = ""
    shipment_id: str = ""
    old_state: str = ""
    new_state: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "warehouse_id": self.warehouse_id,
            "product_id": self.product_id,
            "robot_id": self.robot_id,
            "order_id": self.order_id,
            "shipment_id": self.shipment_id,
            "old_state": self.old_state,
            "new_state": self.new_state,
            "metadata": self.metadata,
        }

    @classmethod
    def create(
        cls,
        event_type: EventType,
        warehouse_id: str = "",
        product_id: str = "",
        robot_id: str = "",
        order_id: str = "",
        shipment_id: str = "",
        old_state: str = "",
        new_state: str = "",
        **metadata,
    ) -> "Event":
        return cls(
            event_type=event_type,
            warehouse_id=warehouse_id,
            product_id=product_id,
            robot_id=robot_id,
            order_id=order_id,
            shipment_id=shipment_id,
            old_state=old_state,
            new_state=new_state,
            metadata=metadata,
        )


class EventLog:
    def __init__(self, max_size: int = 10000):
        self.events: list[Event] = []
        self.max_size = max_size
        self.subscribers: List[Callable] = []

    def add(self, event: Event) -> None:
        self.events.append(event)
        if len(self.events) > self.max_size:
            self.events = self.events[-self.max_size:]
        for subscriber in self.subscribers:
            try:
                subscriber(event)
            except Exception:
                pass

    def subscribe(self, callback: Callable) -> None:
        self.subscribers.append(callback)

    def get_recent(self, count: int = 100) -> list[Event]:
        return self.events[-count:]

    def get_by_product(self, product_id: str) -> list[Event]:
        return [e for e in self.events if e.product_id == product_id]

    def get_by_warehouse(self, warehouse_id: str) -> list[Event]:
        return [e for e in self.events if e.warehouse_id == warehouse_id]

    def get_by_type(self, event_type: EventType) -> list[Event]:
        return [e for e in self.events if e.event_type == event_type]

    def clear(self) -> None:
        self.events.clear()

    def to_json(self) -> list[dict]:
        return [e.to_dict() for e in self.events]