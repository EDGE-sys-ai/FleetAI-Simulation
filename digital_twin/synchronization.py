from typing import List, Dict, Any
from models.warehouse import Warehouse
from models.product import Product
from models.robot import Robot
from digital_twin.twin import DigitalTwin
from simulation.events import EventLog, Event, EventType


class SynchronizationValidator:
    def __init__(self, event_log: EventLog):
        self.event_log = event_log
        self.desync_count = 0
        self.sync_checks = 0
        self.last_sync_rate = 1.0

    def validate(self, warehouse_id: str, physical: Warehouse, twin: DigitalTwin) -> List[Dict]:
        self.sync_checks += 1
        issues = []

        for product_id, phys_product in physical.products.items():
            twin_product = twin.state.products.get(product_id)
            if not twin_product:
                issues.append({
                    "product_id": product_id,
                    "physical": f"EXISTS (status: {phys_product.status.value})",
                    "digital": "MISSING",
                    "details": "Product exists in physical but not in digital twin",
                })
                continue

            phys_location = phys_product.location
            twin_location = twin_product.get("location", "")
            if phys_location and twin_location and phys_location != twin_location:
                issues.append({
                    "product_id": product_id,
                    "physical": phys_location,
                    "digital": twin_location,
                    "details": f"Location mismatch: physical={phys_location}, digital={twin_location}",
                })

            phys_status = phys_product.status.value
            twin_status = twin_product.get("status", "")
            if phys_status != twin_status:
                issues.append({
                    "product_id": product_id,
                    "physical": phys_status,
                    "digital": twin_status,
                    "details": f"Status mismatch: physical={phys_status}, digital={twin_status}",
                })

        for robot_id, phys_robot in physical.robots.items():
            twin_robot = twin.state.robots.get(robot_id)
            if not twin_robot:
                issues.append({
                    "product_id": robot_id,
                    "physical": f"EXISTS (pos: {phys_robot.x},{phys_robot.y})",
                    "digital": "MISSING",
                    "details": "Robot exists in physical but not in digital twin",
                })
                continue

            if phys_robot.x != twin_robot.get("x") or phys_robot.y != twin_robot.get("y"):
                issues.append({
                    "product_id": robot_id,
                    "physical": f"({phys_robot.x},{phys_robot.y})",
                    "digital": f"({twin_robot.get('x')},{twin_robot.get('y')})",
                    "details": "Robot position mismatch",
                })

        # Calculate sync rate for this check
        total_entities = len(physical.products) + len(physical.robots)
        if total_entities > 0:
            self.last_sync_rate = max(0.0, 1.0 - (len(issues) / total_entities))
        else:
            self.last_sync_rate = 1.0

        return issues

    def get_sync_rate(self) -> float:
        return self.last_sync_rate

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_checks": self.sync_checks,
            "desync_detected": self.desync_count,
            "sync_rate": round(self.get_sync_rate(), 4),
        }