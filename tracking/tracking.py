from typing import Dict, List, Optional
from models.shipment import Shipment, ShipmentStatus
from models.product import Product
from simulation.events import Event, EventType, EventLog
from config import SIMULATION_CONFIG
import random


class TrackingSystem:
    def __init__(self, event_log: EventLog):
        self.event_log = event_log
        self.shipments: Dict[str, Shipment] = {}
        self.product_tracking: Dict[str, Dict] = {}

    def create_shipment(self, shipment: Shipment) -> None:
        self.shipments[shipment.id] = shipment
        for product_id in shipment.product_ids:
            self.product_tracking[product_id] = {
                "shipment_id": shipment.id,
                "tracking_id": shipment.tracking_id,
                "origin": shipment.origin_warehouse,
                "destination": shipment.destination_warehouse,
                "status": ShipmentStatus.CREATED.value,
            }

    def update_shipment_status(self, shipment_id: str, status: ShipmentStatus, location: str, details: str = "") -> None:
        shipment = self.shipments.get(shipment_id)
        if shipment:
            shipment.update_status(status, location, details)
            self.event_log.add(Event.create(
                EventType.SHIPMENT_IN_TRANSIT,
                warehouse_id=location,
                shipment_id=shipment.id,
                new_state=status.value,
                tracking_id=shipment.tracking_id,
                details=details,
            ))

            for product_id in shipment.product_ids:
                if product_id in self.product_tracking:
                    self.product_tracking[product_id]["status"] = status.value
                    self.product_tracking[product_id]["location"] = location

    def get_product_tracking(self, product_id: str) -> Optional[Dict]:
        return self.product_tracking.get(product_id)

    def get_shipment(self, shipment_id: str) -> Optional[Shipment]:
        return self.shipments.get(shipment_id)

    def get_shipments_by_status(self, status: ShipmentStatus) -> List[Shipment]:
        return [s for s in self.shipments.values() if s.status == status]

    def simulate_transit(self, dt: float) -> None:
        for shipment in self.shipments.values():
            if shipment.status == ShipmentStatus.IN_TRANSIT:
                shipment.actual_transit_time += dt
                if shipment.actual_transit_time >= shipment.estimated_transit_time:
                    self.update_shipment_status(
                        shipment.id,
                        ShipmentStatus.ARRIVED,
                        shipment.destination_warehouse,
                        "Shipment arrived at destination"
                    )

    def get_all_tracking(self) -> Dict:
        return {
            "active_shipments": len([s for s in self.shipments.values() if s.status not in (ShipmentStatus.STORED, ShipmentStatus.RECEIVED)]),
            "total_shipments": len(self.shipments),
            "products_in_transit": len([p for p in self.product_tracking.values() if p["status"] == "IN_TRANSIT"]),
        }