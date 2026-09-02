from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from models.rack import Rack
from models.robot import Robot, RobotStatus
from models.product import Product
from models.order import Order
from models.shipment import Shipment
from config import WarehouseConfig, CATEGORY_RACK_PREFERENCE


@dataclass
class Warehouse:
    id: str
    name: str
    width: int
    height: int
    inbound_zone: Tuple[int, int, int, int]
    outbound_zone: Tuple[int, int, int, int]
    racks: Dict[str, Rack] = field(default_factory=dict)
    robots: Dict[str, Robot] = field(default_factory=dict)
    products: Dict[str, Product] = field(default_factory=dict)
    inventory: Dict[str, str] = field(default_factory=dict)
    orders: Dict[str, Order] = field(default_factory=dict)
    shipments: Dict[str, Shipment] = field(default_factory=dict)
    inbound_queue: List[Product] = field(default_factory=list)
    outbound_queue: List[Product] = field(default_factory=list)
    grid_occupancy: Set[Tuple[int, int]] = field(default_factory=set)

    @classmethod
    def from_config(cls, config: WarehouseConfig) -> "Warehouse":
        warehouse = cls(
            id=config.id,
            name=config.name,
            width=config.width,
            height=config.height,
            inbound_zone=config.inbound_zone,
            outbound_zone=config.outbound_zone,
        )

        for i, (rx, ry) in enumerate(config.rack_positions):
            zone = "top" if ry < config.height // 3 else "bottom" if ry > 2 * config.height // 3 else "middle"
            rack_id = f"RACK-{config.id[-1]}{i+1:02d}"
            rack = Rack(
                id=rack_id,
                x=rx,
                y=ry,
                capacity=config.rack_capacity,
                shelves=config.rack_shelves,
                zone=zone,
            )
            warehouse.racks[rack_id] = rack
            warehouse.grid_occupancy.add((rx, ry))

        for i in range(config.robot_count):
            start_x = config.inbound_zone[0] + 1 + (i % 4) * 4
            start_y = config.inbound_zone[1] + 1 + (i // 4)
            robot = Robot.create(config.id, start_x, start_y, i + 1)
            warehouse.robots[robot.id] = robot
            warehouse.grid_occupancy.add((robot.x, robot.y))

        return warehouse

    def get_rack_at(self, x: int, y: int) -> Optional[Rack]:
        for rack in self.racks.values():
            if rack.x == x and rack.y == y:
                return rack
        return None

    def get_robot_at(self, x: int, y: int) -> Optional[Robot]:
        for robot in self.robots.values():
            if robot.x == x and robot.y == y:
                return robot
        return None

    def is_cell_free(self, x: int, y: int, ignore_robot_id: str = None) -> bool:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        if (x, y) in self.grid_occupancy:
            robot = self.get_robot_at(x, y)
            if robot and robot.id != ignore_robot_id:
                return False
            rack = self.get_rack_at(x, y)
            if rack:
                return False
        return True

    def find_best_rack(self, product: Product) -> Optional[Rack]:
        preferred_zones = CATEGORY_RACK_PREFERENCE.get(product.category.value, ["middle"])
        candidates = []

        for rack in self.racks.values():
            if not rack.is_full():
                if rack.zone in preferred_zones:
                    candidates.append((rack.utilization(), rack))

        if not candidates:
            for rack in self.racks.values():
                if not rack.is_full():
                    candidates.append((rack.utilization(), rack))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        return None

    def allocate_product(self, product: Product) -> Optional[str]:
        rack = self.find_best_rack(product)
        if rack:
            shelf = rack.add_product(product.id)
            if shelf is not None:
                product.shelf = shelf
                self.inventory[product.id] = rack.get_location_string(shelf)
                return rack.id
        return None

    def get_available_robot(self, exclude_ids: Set[str] = None) -> Optional[Robot]:
        exclude = exclude_ids or set()
        for robot in self.robots.values():
            if robot.id not in exclude and robot.status == RobotStatus.IDLE and robot.battery > 20:
                return robot
        return None

    def add_product(self, product: Product) -> None:
        self.products[product.id] = product
        self.inbound_queue.append(product)

    def remove_product(self, product_id: str) -> Optional[Product]:
        product = self.products.pop(product_id, None)
        if product:
            self.inventory.pop(product_id, None)
            if product in self.inbound_queue:
                self.inbound_queue.remove(product)
            if product in self.outbound_queue:
                self.outbound_queue.remove(product)
            for rack in self.racks.values():
                rack.remove_product(product_id)
        return product

    def get_stats(self) -> dict:
        total_capacity = sum(r.capacity for r in self.racks.values())
        total_products = sum(r.get_product_count() for r in self.racks.values())
        active_robots = sum(1 for r in self.robots.values() if r.status != RobotStatus.IDLE)
        return {
            "warehouse_id": self.id,
            "name": self.name,
            "total_products": len(self.products),
            "stored_products": total_products,
            "capacity": total_capacity,
            "utilization": round(total_products / total_capacity, 2) if total_capacity > 0 else 0,
            "robots_total": len(self.robots),
            "robots_active": active_robots,
            "inbound_queue": len(self.inbound_queue),
            "outbound_queue": len(self.outbound_queue),
            "orders": len(self.orders),
            "shipments": len(self.shipments),
        }