import random
import time
from typing import Dict, List, Optional, Callable, Any, Tuple
from simulation.events import Event, EventType, EventLog
from simulation.scheduler import Scheduler
from simulation.generator import SimulationGenerator
from models.warehouse import Warehouse
from models.product import Product, ProductStatus
from models.robot import Robot, RobotStatus
from models.order import Order, OrderStatus
from models.shipment import Shipment, ShipmentStatus
from warehouse.routing import PathFinder
from warehouse.operations import WarehouseOperations
from tracking.tracking import TrackingSystem
from tracking.barcode import BarcodeScanner
from digital_twin.twin import DigitalTwin
from digital_twin.synchronization import SynchronizationValidator
from config import SIMULATION_CONFIG


class SimulationEngine:
    def __init__(self, warehouses: Dict[str, Warehouse], headless: bool = False):
        self.warehouses = warehouses
        self.headless = headless
        self.running = False
        self.paused = False
        self.speed = 1.0
        self.current_time = 0.0

        self.event_log = EventLog()
        self.scheduler = Scheduler()
        self.generator = SimulationGenerator(warehouses)
        self.pathfinder = PathFinder()
        self.digital_twins: Dict[str, DigitalTwin] = {}
        self.sync_validator = SynchronizationValidator(self.event_log)
        self.scanner = BarcodeScanner()
        self.tracking = TrackingSystem(self.event_log)
        self.operations = WarehouseOperations(
            event_log=self.event_log,
            digital_twins=self.digital_twins,
            tracking_system=self.tracking
        )
        self.operations.set_warehouses(warehouses)

        self._callbacks: Dict[str, List[Callable]] = {}
        self._init_digital_twins()
        self._setup_recurring_events()

    def _init_digital_twins(self) -> None:
        for wh_id, warehouse in self.warehouses.items():
            self.digital_twins[wh_id] = DigitalTwin(wh_id, warehouse)

    def _setup_recurring_events(self) -> None:
        self.scheduler.schedule_recurring(
            SIMULATION_CONFIG.product_arrival_interval,
            self._spawn_product_arrival
        )
        self.scheduler.schedule_recurring(
            SIMULATION_CONFIG.order_creation_interval,
            self._spawn_customer_order
        )
        self.scheduler.schedule_recurring(
            SIMULATION_CONFIG.transfer_creation_interval,
            self._spawn_transfer
        )
        self.scheduler.schedule_recurring(5.0, self._sync_digital_twins)
        self.scheduler.schedule_recurring(10.0, self._validate_sync)

    def _spawn_product_arrival(self) -> None:
        product = self.generator.generate_product_arrival()
        if product is None:
            self._recycle_completed_product()
            product = self.generator.generate_product_arrival()
        if product:
            warehouse = self.warehouses[product.warehouse_id]
            warehouse.add_product(product)
            self.event_log.add(Event.create(
                EventType.PRODUCT_ARRIVED,
                warehouse_id=product.warehouse_id,
                product_id=product.id,
                new_state="RECEIVED",
                barcode=product.barcode,
            ))
            self.operations.process_inbound(product)
            # Sync to digital twin
            if product.warehouse_id in self.digital_twins:
                self.digital_twins[product.warehouse_id].update_product(product)

    def _recycle_completed_product(self) -> None:
        active_product_ids = {
            task.get("product_id")
            for task in self.operations._robot_tasks.values()
            if task.get("product_id")
        }
        active_order_products = {
            item.product_id
            for warehouse in self.warehouses.values()
            for order in warehouse.orders.values()
            if order.status not in (OrderStatus.COMPLETED, OrderStatus.CANCELLED)
            for item in order.items
        }
        for warehouse in self.warehouses.values():
            for product in list(warehouse.products.values()):
                is_orphaned = (product.status == ProductStatus.RECEIVED
                           and product.id not in active_product_ids
                           and product not in warehouse.inbound_queue)
                is_finished = product.status in (ProductStatus.STORED, ProductStatus.SHIPPED,
                                 ProductStatus.DELIVERED)
                if ((is_orphaned or is_finished)
                    and product.id not in active_order_products
                    and product.current_robot_id is None):
                    warehouse.remove_product(product.id)
                    return

    def _spawn_customer_order(self) -> None:
        order = self.generator.generate_customer_order()
        if order:
            warehouse = self.warehouses[order.warehouse_id]
            warehouse.orders[order.id] = order
            self.event_log.add(Event.create(
                EventType.ORDER_CREATED,
                warehouse_id=order.warehouse_id,
                order_id=order.id,
                new_state="CREATED",
                items=[item.product_id for item in order.items],
            ))
            self.operations.process_order(order)

    def _spawn_transfer(self) -> None:
        shipment = self.generator.generate_inter_warehouse_transfer()
        if shipment:
            origin_wh = self.warehouses[shipment.origin_warehouse]
            origin_wh.shipments[shipment.id] = shipment
            self.tracking.create_shipment(shipment)
            self.event_log.add(Event.create(
                EventType.SHIPMENT_CREATED,
                warehouse_id=shipment.origin_warehouse,
                shipment_id=shipment.id,
                new_state="CREATED",
                tracking_id=shipment.tracking_id,
                products=shipment.product_ids,
                destination=shipment.destination_warehouse,
            ))
            self.operations.process_shipment(shipment)

    def _sync_digital_twins(self) -> None:
        for twin in self.digital_twins.values():
            twin.synchronize()

    def _validate_sync(self) -> None:
        for wh_id, twin in self.digital_twins.items():
            warehouse = self.warehouses.get(wh_id)
            if not warehouse:
                continue

            # Auto-insert missing products and robots to prevent desync
            for product_id, product in warehouse.products.items():
                if product_id not in twin.state.products:
                    twin.auto_insert_product(product)

            for robot_id, robot in warehouse.robots.items():
                if robot_id not in twin.state.robots:
                    twin.auto_insert_robot(robot)

            # Validate after auto-insertion
            issues = self.sync_validator.validate(wh_id, warehouse, twin)
            
            # Only log issues that persist after auto-insertion
            for issue in issues:
                if issue.get("details", "").startswith("Location mismatch") or \
                   issue.get("details", "").startswith("Status mismatch") or \
                   issue.get("details", "").startswith("Robot position mismatch"):
                    self.event_log.add(Event.create(
                        EventType.DIGITAL_TWIN_DESYNC,
                        warehouse_id=wh_id,
                        product_id=issue.get("product_id", ""),
                        old_state=issue.get("physical", ""),
                        new_state=issue.get("digital", ""),
                        details=issue.get("details", ""),
                    ))

    def start(self) -> None:
        self.running = True
        self._generate_initial_state()

    def _generate_initial_state(self) -> None:
        initial_products = self.generator.generate_initial_products()
        for product in initial_products:
            warehouse = self.warehouses[product.warehouse_id]
            warehouse.add_product(product)
            # Sync to digital twin
            if product.warehouse_id in self.digital_twins:
                self.digital_twins[product.warehouse_id].update_product(product)
            self.operations.process_inbound(product)

    def stop(self) -> None:
        self.running = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.1, min(10.0, speed))

    def update(self, dt: float) -> None:
        if not self.running or self.paused:
            return

        scaled_dt = dt * self.speed
        self.current_time += scaled_dt
        self.scheduler.update(scaled_dt)

        for warehouse in self.warehouses.values():
            self.operations.update_warehouse(warehouse, scaled_dt)
            self._assign_idle_patrols(warehouse)
            self._update_robots(warehouse, scaled_dt)

    def _assign_idle_patrols(self, warehouse: Warehouse) -> None:
        """Keep free AMRs moving while they monitor aisles between real tasks."""
        has_pending_work = bool(warehouse.inbound_queue) or any(
            order.status == OrderStatus.CREATED for order in warehouse.orders.values()
        ) or any(
            shipment.status == ShipmentStatus.CREATED
            for shipment in warehouse.shipments.values()
        )
        if has_pending_work:
            return

        patrol_points = [
            (rack.x - 1, rack.y)
            for rack in warehouse.racks.values()
            if rack.x > 0
        ]
        if not patrol_points:
            return

        for robot in warehouse.robots.values():
            if robot.status != RobotStatus.IDLE or robot.needs_charge():
                continue

            point_index = (int(self.current_time // 3) + int(robot.id[-2:])) % len(patrol_points)
            target = patrol_points[point_index]
            start = (int(round(robot.x)), int(round(robot.y)))
            path = self.pathfinder.find_path(warehouse, start, target, robot.id)
            if path and len(path) > 1:
                robot.set_destination(target[0], target[1], path, task="PATROL")
                self.event_log.add(Event.create(
                    EventType.ROBOT_DISPATCHED,
                    warehouse_id=warehouse.id,
                    robot_id=robot.id,
                    new_state="AUTONOMOUS_PATROL",
                    destination=target,
                ))

    def _update_robots(self, warehouse: Warehouse, dt: float) -> None:
        self._exchange_peer_intents(warehouse)
        for robot in warehouse.robots.values():
            if robot.status == RobotStatus.MOVING:
                if robot.peer_status == "WAITING":
                    continue
                arrived = robot.update_position(dt)
                if arrived:
                    self.operations.handle_robot_arrival(warehouse, robot)

            elif robot.status in (RobotStatus.SCANNING, RobotStatus.LOADING, RobotStatus.UNLOADING, RobotStatus.WAITING):
                completed = robot.update_task(dt)
                if completed:
                    self.operations.handle_task_completion(warehouse, robot)

            elif robot.status == RobotStatus.CHARGING:
                robot.charge(dt)

            elif robot.status == RobotStatus.IDLE and robot.needs_charge():
                robot.status = RobotStatus.CHARGING
                self.event_log.add(Event.create(
                    EventType.ROBOT_CHARGING,
                    warehouse_id=warehouse.id,
                    robot_id=robot.id,
                    new_state="CHARGING",
                    battery=robot.battery,
                ))

            # Sync robot to digital twin
            if warehouse.id in self.digital_twins:
                self.digital_twins[warehouse.id].update_robot(robot)

    def _exchange_peer_intents(self, warehouse: Warehouse) -> None:
        """Reserve next cells through a local peer-to-peer intent exchange."""
        moving = [robot for robot in warehouse.robots.values()
                  if robot.status == RobotStatus.MOVING and robot.path_index < len(robot.path)]
        reservations: Dict[Tuple[int, int], List["Robot"]] = {}
        current_cells: Dict[str, Tuple[int, int]] = {}

        for robot in moving:
            step = robot.path[robot.path_index]
            intent = (step.x, step.y)
            robot.peer_intent = intent
            robot.peer_status = "CLEAR"
            robot.peer_message = f"INTENT {intent[0]},{intent[1]}"
            reservations.setdefault(intent, []).append(robot)
            current_cells[robot.id] = (round(robot.x), round(robot.y))

        for intent, peers in reservations.items():
            if len(peers) > 1:
                peers.sort(key=lambda robot: robot.id)
                for robot in peers[1:]:
                    robot.peer_status = "WAITING"
                    robot.peer_message = f"YIELD TO {peers[0].id}"

        for robot in moving:
            if robot.peer_status == "WAITING":
                continue
            for peer in moving:
                if peer.id == robot.id or peer.peer_status == "WAITING":
                    continue
                if (robot.peer_intent == current_cells.get(peer.id)
                        and peer.peer_intent == current_cells.get(robot.id)
                        and robot.id > peer.id):
                    robot.peer_status = "WAITING"
                    robot.peer_message = f"SWAP BLOCKED BY {peer.id}"
                    break

    def subscribe(self, event_type: str, callback: Callable) -> None:
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def emit(self, event_type: str, data: Any) -> None:
        if event_type in self._callbacks:
            for callback in self._callbacks[event_type]:
                try:
                    callback(data)
                except Exception:
                    pass

    def get_stats(self) -> dict:
        total_products = sum(len(w.products) for w in self.warehouses.values())
        total_stored = sum(w.get_stats()["stored_products"] for w in self.warehouses.values())
        total_robots = sum(len(w.robots) for w in self.warehouses.values())
        active_robots = sum(w.get_stats()["robots_active"] for w in self.warehouses.values())
        sync_rate = self.sync_validator.get_sync_rate()

        return {
            "simulation_time": round(self.current_time, 1),
            "speed": self.speed,
            "paused": self.paused,
            "total_products": total_products,
            "stored_products": total_stored,
            "total_robots": total_robots,
            "active_robots": active_robots,
            "robot_utilization": round(active_robots / total_robots, 2) if total_robots > 0 else 0,
            "digital_twin_sync_rate": sync_rate,
            "events_logged": len(self.event_log.events),
            "generator": self.generator.get_stats(),
        }

    def export_logs(self, filepath: str) -> None:
        import json
        with open(filepath, 'w') as f:
            json.dump(self.event_log.to_json(), f, indent=2)