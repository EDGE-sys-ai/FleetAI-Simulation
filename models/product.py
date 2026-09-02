from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid
import random


class ProductStatus(str, Enum):
    RECEIVED = "RECEIVED"
    SCANNED = "SCANNED"
    ALLOCATED = "ALLOCATED"
    IN_STORAGE_TRANSIT = "IN_STORAGE_TRANSIT"
    STORED = "STORED"
    PICK_REQUESTED = "PICK_REQUESTED"
    PICKED = "PICKED"
    OUTBOUND = "OUTBOUND"
    SHIPPED = "SHIPPED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"


class ProductCategory(str, Enum):
    ELEC = "ELEC"
    FOOD = "FOOD"
    CLOTH = "CLOTH"
    HOME = "HOME"
    TOOL = "TOOL"


@dataclass
class MovementRecord:
    timestamp: datetime
    location: str
    event_type: str
    details: str = ""


@dataclass
class Product:
    id: str
    barcode: str
    sku: str
    name: str
    category: ProductCategory
    weight: float
    warehouse_id: str
    location: str = ""
    status: ProductStatus = ProductStatus.RECEIVED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    movement_history: List[MovementRecord] = field(default_factory=list)
    current_robot_id: Optional[str] = None
    shelf: int = 0

    @classmethod
    def generate(cls, category: ProductCategory, warehouse_id: str) -> "Product":
        product_id = f"P-{uuid.uuid4().hex[:6].upper()}"
        sku_prefix = category.value
        sku_number = random.randint(100, 999)
        sku = f"{sku_prefix}-{sku_number}"
        barcode = f"{random.randint(1000000000000, 9999999999999)}"
        name = f"{category.value} Product {sku_number}"
        weight = round(random.uniform(0.5, 50.0), 2)
        return cls(
            id=product_id,
            barcode=barcode,
            sku=sku,
            name=name,
            category=category,
            weight=weight,
            warehouse_id=warehouse_id,
            location="INBOUND",
        )

    def add_movement(self, location: str, event_type: str, details: str = "") -> None:
        self.movement_history.append(
            MovementRecord(
                timestamp=datetime.now(),
                location=location,
                event_type=event_type,
                details=details,
            )
        )
        self.updated_at = datetime.now()

    def update_status(self, new_status: ProductStatus, location: str = "", details: str = "") -> None:
        self.status = new_status
        if location:
            self.location = location
        self.add_movement(location or self.location, new_status.value, details)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "barcode": self.barcode,
            "sku": self.sku,
            "name": self.name,
            "category": self.category.value,
            "weight": self.weight,
            "warehouse_id": self.warehouse_id,
            "location": self.location,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "shelf": self.shelf,
            "movement_history": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "location": m.location,
                    "event_type": m.event_type,
                    "details": m.details,
                }
                for m in self.movement_history
            ],
        }