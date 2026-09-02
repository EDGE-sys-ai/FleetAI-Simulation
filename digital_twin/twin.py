from typing import Dict, List, Optional
from models.product import Product, ProductStatus
from models.robot import Robot, RobotStatus
from models.rack import Rack
from models.order import Order, OrderStatus
from models.shipment import Shipment, ShipmentStatus
from models.warehouse import Warehouse
from simulation.events import Event, EventType


class TwinState:
    def __init__(self):
        self.products: Dict[str, Dict] = {}
        self.robots: Dict[str, Dict] = {}
        self.racks: Dict[str, Dict] = {}
        self.orders: Dict[str, Dict] = {}
        self.shipments: Dict[str, Dict] = {}
        self.inventory: Dict[str, str] = {}
        self.last_sync_time: float = 0.0
        self.sync_status: str = "SYNCHRONIZED"


class DigitalTwin:
    def __init__(self, warehouse_id: str, physical_warehouse: Warehouse):
        self.warehouse_id = warehouse_id
        self.state = TwinState()
        self._initialize_from_physical(physical_warehouse)

    def _initialize_from_physical(self, warehouse: Warehouse) -> None:
        for product in warehouse.products.values():
            self.state.products[product.id] = self._product_to_dict(product)

        for robot in warehouse.robots.values():
            self.state.robots[robot.id] = self._robot_to_dict(robot)

        for rack in warehouse.racks.values():
            self.state.racks[rack.id] = rack.to_dict()

        for order in warehouse.orders.values():
            self.state.orders[order.id] = order.to_dict()

        for shipment in warehouse.shipments.values():
            self.state.shipments[shipment.id] = shipment.to_dict()

        self.state.inventory = dict(warehouse.inventory)
        self.state.sync_status = "SYNCHRONIZED"

    def _product_to_dict(self, product: Product) -> Dict:
        return {
            "id": product.id,
            "barcode": product.barcode,
            "sku": product.sku,
            "name": product.name,
            "category": product.category.value,
            "warehouse_id": product.warehouse_id,
            "location": product.location,
            "status": product.status.value,
            "shelf": product.shelf,
            "weight": product.weight,
        }

    def _robot_to_dict(self, robot: Robot) -> Dict:
        return {
            "id": robot.id,
            "x": robot.x,
            "y": robot.y,
            "status": robot.status.value,
            "carrying_product_id": robot.carrying_product_id,
            "battery": robot.battery,
            "destination": robot.destination,
        }

    def update_product(self, product: Product) -> None:
        self.state.products[product.id] = self._product_to_dict(product)
        if product.id in self.state.inventory:
            self.state.inventory[product.id] = product.location

    def update_robot(self, robot: Robot) -> None:
        self.state.robots[robot.id] = self._robot_to_dict(robot)

    def update_rack(self, rack: Rack) -> None:
        self.state.racks[rack.id] = rack.to_dict()

    def update_order(self, order: Order) -> None:
        self.state.orders[order.id] = order.to_dict()

    def update_shipment(self, shipment: Shipment) -> None:
        self.state.shipments[shipment.id] = shipment.to_dict()

    def remove_product(self, product_id: str) -> None:
        self.state.products.pop(product_id, None)
        self.state.inventory.pop(product_id, None)

    def process_event(self, event: Event) -> None:
        if event.event_type == EventType.PRODUCT_SCANNED:
            self.state.products[event.product_id]["status"] = "SCANNED"
        elif event.event_type == EventType.DESTINATION_ASSIGNED:
            self.state.products[event.product_id]["location"] = event.new_state
        elif event.event_type == EventType.PRODUCT_DELIVERED:
            self.state.products[event.product_id]["status"] = "STORED"
            self.state.products[event.product_id]["location"] = event.metadata.get("location", "")
            self.state.inventory[event.product_id] = event.metadata.get("location", "")
        elif event.event_type == EventType.ORDER_PICKED:
            self.state.products[event.product_id]["status"] = "PICKED"
        elif event.event_type == EventType.SHIPMENT_CREATED:
            self.state.shipments[event.shipment_id] = {
                "id": event.shipment_id,
                "tracking_id": event.metadata.get("tracking_id", ""),
                "status": "CREATED",
            }
        elif event.event_type == EventType.SHIPMENT_RECEIVED:
            self.state.products[event.product_id]["status"] = "RECEIVED"
            self.state.products[event.product_id]["warehouse_id"] = self.warehouse_id
        elif event.event_type in (EventType.ROBOT_DISPATCHED, EventType.ROBOT_ARRIVED, EventType.ROBOT_CHARGING, EventType.ROBOT_IDLE):
            # Robot position will be synced via update_robot call
            pass

    def update_robot(self, robot: Robot) -> None:
        self.state.robots[robot.id] = self._robot_to_dict(robot)
        self.state.last_sync_time = robot.updated_at.timestamp() if hasattr(robot, 'updated_at') else __import__('datetime').datetime.now().timestamp()
        self.state.sync_status = "SYNCHRONIZED"

    def synchronize(self) -> None:
        self.state.sync_status = "SYNCHRONIZED"

    def get_state_summary(self) -> Dict:
        return {
            "warehouse_id": self.warehouse_id,
            "products_count": len(self.state.products),
            "robots_count": len(self.state.robots),
            "racks_count": len(self.state.racks),
            "orders_count": len(self.state.orders),
            "shipments_count": len(self.state.shipments),
            "inventory_count": len(self.state.inventory),
            "sync_status": self.state.sync_status,
            "last_sync": self.state.last_sync_time,
        }

    def get_product(self, product_id: str) -> Optional[Dict]:
        return self.state.products.get(product_id)

    def get_robot(self, robot_id: str) -> Optional[Dict]:
        return self.state.robots.get(robot_id)

    def get_all_products(self) -> List[Dict]:
        return list(self.state.products.values())

    def get_all_robots(self) -> List[Dict]:
        return list(self.state.robots.values())