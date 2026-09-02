from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid


class ShipmentStatus(str, Enum):
    CREATED = "CREATED"
    PICKED_UP = "PICKED_UP"
    DEPARTED = "DEPARTED"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    RECEIVED = "RECEIVED"
    STORED = "STORED"


@dataclass
class TrackingEvent:
    timestamp: datetime
    status: ShipmentStatus
    location: str
    details: str = ""


@dataclass
class Shipment:
    id: str
    tracking_id: str
    product_ids: List[str]
    origin_warehouse: str
    destination_warehouse: str
    status: ShipmentStatus = ShipmentStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    departed_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    tracking_history: List[TrackingEvent] = field(default_factory=list)
    estimated_transit_time: float = 30.0
    actual_transit_time: float = 0.0

    @classmethod
    def create(cls, product_ids: List[str], origin: str, destination: str) -> "Shipment":
        return cls(
            id=f"SHP-{uuid.uuid4().hex[:8].upper()}",
            tracking_id=f"TRK-{uuid.uuid4().hex[:10].upper()}",
            product_ids=product_ids,
            origin_warehouse=origin,
            destination_warehouse=destination,
        )

    def update_status(self, new_status: ShipmentStatus, location: str, details: str = "") -> None:
        self.status = new_status
        self.tracking_history.append(
            TrackingEvent(
                timestamp=datetime.now(),
                status=new_status,
                location=location,
                details=details,
            )
        )
        if new_status == ShipmentStatus.DEPARTED:
            self.departed_at = datetime.now()
        elif new_status == ShipmentStatus.ARRIVED:
            self.arrived_at = datetime.now()
            if self.departed_at:
                self.actual_transit_time = (self.arrived_at - self.departed_at).total_seconds()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tracking_id": self.tracking_id,
            "product_ids": self.product_ids,
            "origin_warehouse": self.origin_warehouse,
            "destination_warehouse": self.destination_warehouse,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "departed_at": self.departed_at.isoformat() if self.departed_at else None,
            "arrived_at": self.arrived_at.isoformat() if self.arrived_at else None,
            "estimated_transit_time": self.estimated_transit_time,
            "actual_transit_time": self.actual_transit_time,
            "tracking_history": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "status": e.status.value,
                    "location": e.location,
                    "details": e.details,
                }
                for e in self.tracking_history
            ],
        }