from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    PICKING = "PICKING"
    PICKED = "PICKED"
    PACKING = "PACKING"
    READY = "READY"
    SHIPPED = "SHIPPED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class OrderItem:
    product_id: str
    quantity: int = 1
    picked: bool = False


@dataclass
class Order:
    id: str
    customer_id: str
    warehouse_id: str
    items: List[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    assigned_robot_id: Optional[str] = None
    shipment_id: Optional[str] = None

    @classmethod
    def create(cls, warehouse_id: str, product_ids: List[str]) -> "Order":
        return cls(
            id=f"ORD-{uuid.uuid4().hex[:8].upper()}",
            customer_id=f"CUST-{uuid.uuid4().hex[:6].upper()}",
            warehouse_id=warehouse_id,
            items=[OrderItem(pid) for pid in product_ids],
        )

    def add_item(self, product_id: str) -> None:
        self.items.append(OrderItem(product_id))
        self.updated_at = datetime.now()

    def mark_picked(self, product_id: str) -> bool:
        for item in self.items:
            if item.product_id == product_id and not item.picked:
                item.picked = True
                self.updated_at = datetime.now()
                return True
        return False

    def is_complete(self) -> bool:
        return all(item.picked for item in self.items)

    def get_unpicked_items(self) -> List[OrderItem]:
        return [item for item in self.items if not item.picked]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "warehouse_id": self.warehouse_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "picked": item.picked,
                }
                for item in self.items
            ],
            "assigned_robot_id": self.assigned_robot_id,
            "shipment_id": self.shipment_id,
        }