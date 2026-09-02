import random
from typing import Optional
from models.product import Product
from models.robot import Robot
from simulation.events import Event, EventType, EventLog
from config import SIMULATION_CONFIG


class BarcodeScanner:
    def __init__(self):
        self.scan_duration = 0.5
        self.failure_rate = SIMULATION_CONFIG.failure_rate

    def scan(self, robot: Robot, product: Product, event_log: EventLog) -> bool:
        if random.random() < self.failure_rate and SIMULATION_CONFIG.enable_failures:
            event_log.add(Event.create(
                EventType.SCAN_FAILED,
                warehouse_id=robot.warehouse_id,
                robot_id=robot.id,
                product_id=product.id,
                new_state="SCAN_FAILED",
                barcode=product.barcode,
            ))
            return False

        event_log.add(Event.create(
            EventType.PRODUCT_SCANNED,
            warehouse_id=robot.warehouse_id,
            robot_id=robot.id,
            product_id=product.id,
            new_state="SCANNED",
            barcode=product.barcode,
            sku=product.sku,
            category=product.category.value,
            weight=product.weight,
        ))

        product.update_status(product.status, product.location, f"Scanned by {robot.id}")
        return True

    def simulate_scan_delay(self) -> float:
        return self.scan_duration + random.uniform(0, 0.2)

    def validate_barcode(self, barcode: str) -> bool:
        return len(barcode) == 13 and barcode.isdigit()