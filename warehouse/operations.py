from typing import Optional, List, Set, TYPE_CHECKING, Dict
from models.warehouse import Warehouse
from models.product import Product, ProductStatus
from models.robot import Robot, RobotStatus
from models.order import Order, OrderStatus
from models.shipment import Shipment, ShipmentStatus
from simulation.events import Event, EventType, EventLog
from warehouse.routing import PathFinder
from warehouse.allocation import RackAllocator
from warehouse.inventory import InventoryManager
from tracking.barcode import BarcodeScanner
import random

if TYPE_CHECKING:
    from digital_twin.twin import DigitalTwin
    from simulation.engine import SimulationEngine


class WarehouseOperations:
    def __init__(
        self,
        event_log: EventLog,
        digital_twins: Dict[str, "DigitalTwin"],
        tracking_system
    ):
        self.event_log = event_log
        self.digital_twins = digital_twins
        self.tracking = tracking_system
        self.pathfinder = PathFinder()
        self.allocator = RackAllocator()
        self.inventory = InventoryManager()
        self.scanner = BarcodeScanner()
        self._robot_tasks: dict = {}

    def process_inbound(self, product: Product) -> None:
        warehouse = self.get_warehouse(product.warehouse_id)
        if not warehouse:
            return
        self.inventory.receive_product(warehouse, product)

        # Sync product to digital twin
        if warehouse.id in self.digital_twins:
            self.digital_twins[warehouse.id].update_product(product)

        robot = warehouse.get_available_robot()
        if robot:
            self._assign_inbound_task(warehouse, robot, product)
        else:
            warehouse.inbound_queue.append(product)

    def get_warehouse(self, warehouse_id: str) -> Optional[Warehouse]:
        # This will be set by the engine
        return getattr(self, '_warehouses', {}).get(warehouse_id)

    def set_warehouses(self, warehouses: Dict[str, Warehouse]) -> None:
        self._warehouses = warehouses

    def _assign_inbound_task(self, warehouse: Warehouse, robot: Robot, product: Product) -> None:
        inbound_x = warehouse.inbound_zone[0] + 1
        inbound_y = warehouse.inbound_zone[1] + 1

        # If robot already at inbound position, start loading immediately
        if robot.x == inbound_x and robot.y == inbound_y:
            robot.start_load_unload()
            self._robot_tasks[robot.id] = {"product_id": product.id, "phase": "LOADING"}
            self.event_log.add(Event.create(
                EventType.ROBOT_DISPATCHED,
                warehouse_id=warehouse.id,
                robot_id=robot.id,
                product_id=product.id,
                new_state="LOADING_AT_INBOUND",
            ))
            return

        path = self.pathfinder.find_path(warehouse, (robot.x, robot.y), (inbound_x, inbound_y), robot.id)
        if path:
            robot.set_destination(inbound_x, inbound_y, path, task="INBOUND_PICKUP")
            robot.assigned_task = "INBOUND_PICKUP"
            self._robot_tasks[robot.id] = {"product_id": product.id, "phase": "PICKUP"}
            self.event_log.add(Event.create(
                EventType.ROBOT_DISPATCHED,
                warehouse_id=warehouse.id,
                robot_id=robot.id,
                product_id=product.id,
                new_state="MOVING_TO_INBOUND",
            ))

    def process_order(self, order: Order) -> None:
        warehouse = self.get_warehouse(order.warehouse_id)
        if not warehouse:
            return
        order.status = OrderStatus.PICKING

        for item in order.get_unpicked_items():
            product = warehouse.products.get(item.product_id)
            if product and product.status == ProductStatus.STORED:
                robot = warehouse.get_available_robot()
                if robot:
                    self._assign_pick_task(warehouse, robot, order, product)
                    break

    def _assign_pick_task(self, warehouse: Warehouse, robot: Robot, order: Order, product: Product) -> None:
        location = warehouse.inventory.get(product.id)
        if not location:
            return

        rack_id = location.split('/')[0]
        rack = warehouse.racks.get(rack_id)
        if not rack:
            return

        path = self.pathfinder.find_path_to_rack(warehouse, robot, rack_id)
        if path:
            robot.set_destination(rack.x, rack.y, path, rack_id=rack_id, task="PICK")
            robot.assigned_task = "PICK"
            self._robot_tasks[robot.id] = {
                "order_id": order.id,
                "product_id": product.id,
                "phase": "PICK",
            }
            order.assigned_robot_id = robot.id
            self.event_log.add(Event.create(
                EventType.ROBOT_DISPATCHED,
                warehouse_id=warehouse.id,
                robot_id=robot.id,
                product_id=product.id,
                order_id=order.id,
                new_state="MOVING_TO_PICK",
            ))

    def process_shipment(self, shipment: Shipment) -> None:
        warehouse = self.get_warehouse(shipment.origin_warehouse)
        if not warehouse:
            return
        shipment.update_status(ShipmentStatus.PICKED_UP, warehouse.id, "Shipment picked up")

        for product_id in shipment.product_ids:
            product = warehouse.products.get(product_id)
            if product and product.status == ProductStatus.STORED:
                robot = warehouse.get_available_robot()
                if robot:
                    self._assign_shipment_pick_task(warehouse, robot, shipment, product)
                    break

    def _assign_shipment_pick_task(self, warehouse: Warehouse, robot: Robot, shipment: Shipment, product: Product) -> None:
        location = warehouse.inventory.get(product.id)
        if not location:
            return

        rack_id = location.split('/')[0]
        rack = warehouse.racks.get(rack_id)
        if not rack:
            return

        path = self.pathfinder.find_path_to_rack(warehouse, robot, rack_id)
        if path:
            robot.set_destination(rack.x, rack.y, path, rack_id=rack_id, task="SHIPMENT_PICK")
            robot.assigned_task = "SHIPMENT_PICK"
            self._robot_tasks[robot.id] = {
                "shipment_id": shipment.id,
                "product_id": product.id,
                "phase": "PICK",
            }
            self.event_log.add(Event.create(
                EventType.ROBOT_DISPATCHED,
                warehouse_id=warehouse.id,
                robot_id=robot.id,
                product_id=product.id,
                shipment_id=shipment.id,
                new_state="MOVING_TO_SHIPMENT_PICK",
            ))

    def handle_robot_arrival(self, warehouse: Warehouse, robot: Robot) -> None:
        task_info = self._robot_tasks.get(robot.id)
        if not task_info:
            robot.status = RobotStatus.IDLE
            return

        phase = task_info.get("phase")
        product_id = task_info.get("product_id")

        if phase == "PICKUP":
            self._handle_inbound_pickup(warehouse, robot, task_info)
        elif phase == "PICK":
            self._handle_pick(warehouse, robot, task_info)
        elif phase == "DELIVER":
            self._handle_deliver(warehouse, robot, task_info)
        elif phase == "SHIPMENT_PICK":
            self._handle_shipment_pick(warehouse, robot, task_info)
        elif phase == "SHIPMENT_DELIVER":
            self._handle_shipment_deliver(warehouse, robot, task_info)

    def _handle_inbound_pickup(self, warehouse: Warehouse, robot: Robot, task_info: dict) -> None:
        product_id = task_info["product_id"]
        product = None
        for p in warehouse.inbound_queue:
            if p.id == product_id:
                product = p
                break

        if product:
            robot.start_load_unload()
            task_info["phase"] = "LOADING"
        else:
            robot.status = RobotStatus.IDLE
            self._robot_tasks.pop(robot.id, None)

    def _handle_pick(self, warehouse: Warehouse, robot: Robot, task_info: dict) -> None:
        order_id = task_info.get("order_id")
        product_id = task_info.get("product_id")
        
        if not order_id or not product_id:
            robot.status = RobotStatus.IDLE
            self._robot_tasks.pop(robot.id, None)
            return
            
        order = warehouse.orders.get(order_id)
        product = warehouse.products.get(product_id)

        if product and order:
            robot.start_scan()
            task_info["phase"] = "SCANNING"
        else:
            robot.status = RobotStatus.IDLE
            self._robot_tasks.pop(robot.id, None)

    def _handle_deliver(self, warehouse: Warehouse, robot: Robot, task_info: dict) -> None:
        product_id = task_info["product_id"]
        product = warehouse.products.get(product_id)

        if product:
            robot.start_load_unload()
            task_info["phase"] = "UNLOADING"
        else:
            robot.status = RobotStatus.IDLE
            self._robot_tasks.pop(robot.id, None)

    def _handle_shipment_pick(self, warehouse: Warehouse, robot: Robot, task_info: dict) -> None:
        product_id = task_info["product_id"]
        product = warehouse.products.get(product_id)

        if product:
            robot.start_scan()
            task_info["phase"] = "SCANNING"
        else:
            robot.status = RobotStatus.IDLE
            self._robot_tasks.pop(robot.id, None)

    def _handle_shipment_deliver(self, warehouse: Warehouse, robot: Robot, task_info: dict) -> None:
        product_id = task_info["product_id"]
        product = warehouse.products.get(product_id)

        if product:
            robot.start_load_unload()
            task_info["phase"] = "UNLOADING"
        else:
            robot.status = RobotStatus.IDLE
            self._robot_tasks.pop(robot.id, None)

    def handle_task_completion(self, warehouse: Warehouse, robot: Robot) -> None:
        task_info = self._robot_tasks.get(robot.id)
        if not task_info:
            robot.status = RobotStatus.IDLE
            return

        phase = task_info.get("phase")
        product_id = task_info.get("product_id")

        if phase == "LOADING":
            self._complete_loading(warehouse, robot, task_info)
        elif phase == "UNLOADING":
            self._complete_unloading(warehouse, robot, task_info)
        elif phase == "SCANNING":
            self._complete_scanning(warehouse, robot, task_info)

    def _complete_loading(self, warehouse: Warehouse, robot: Robot, task_info: dict) -> None:
        product_id = task_info["product_id"]
        product = None

        for p in warehouse.inbound_queue:
            if p.id == product_id:
                product = p
                break

        if product:
            warehouse.inbound_queue.remove(product)
            robot.assign_product(product.id)
            product.current_robot_id = robot.id
            product.update_status(ProductStatus.ALLOCATED, "ROBOT", "Loaded onto robot")

            self.scanner.scan(robot, product, self.event_log)
            rack_id = self.allocator.allocate(warehouse, product)
            if rack_id:
                task_info["phase"] = "DELIVER"
                task_info["rack_id"] = rack_id
                path = self.pathfinder.find_path_to_rack(warehouse, robot, rack_id)
                if path:
                    robot.set_destination(0, 0, path, rack_id=rack_id, task="DELIVER")
                    self.event_log.add(Event.create(
                        EventType.DESTINATION_ASSIGNED,
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                        robot_id=robot.id,
                        new_state=rack_id,
                    ))
            else:
                robot.release_product()
                robot.status = RobotStatus.IDLE
                self._robot_tasks.pop(robot.id, None)
        else:
            robot.status = RobotStatus.IDLE
            self._robot_tasks.pop(robot.id, None)

    def _complete_unloading(self, warehouse: Warehouse, robot: Robot, task_info: dict) -> None:
        product_id = task_info["product_id"]
        product = warehouse.products.get(product_id)

        if product:
            robot.release_product()
            product.current_robot_id = None

            if task_info.get("rack_id"):
                rack_id = task_info["rack_id"]
                rack = warehouse.racks.get(rack_id)
                if rack:
                    shelf = product.shelf
                    self.inventory.store_product(warehouse, product, rack_id, shelf)
                    self.event_log.add(Event.create(
                        EventType.PRODUCT_DELIVERED,
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                        robot_id=robot.id,
                        new_state="STORED",
                        location=rack.get_location_string(shelf),
                    ))
                    if warehouse.id in self.digital_twins:
                        self.digital_twins[warehouse.id].update_product(product)

            elif task_info.get("order_id"):
                order_id = task_info["order_id"]
                order = warehouse.orders.get(order_id)
                if order:
                    order.mark_picked(product_id)
                    product.update_status(ProductStatus.OUTBOUND, "ROBOT", "Picked for order")
                    self.event_log.add(Event.create(
                        EventType.ORDER_PICKED,
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                        order_id=order.id,
                        new_state="PICKED",
                    ))
                    # Sync to digital twin
                    if warehouse.id in self.digital_twins:
                        self.digital_twins[warehouse.id].update_product(product)

                    if order.is_complete():
                        order.status = OrderStatus.PICKED
                        self._create_shipment_for_order(warehouse, order)

                    path = self.pathfinder.find_path_to_zone(warehouse, robot, warehouse.outbound_zone)
                    if path:
                        task_info["phase"] = "SHIPMENT_DELIVER"
                        robot.set_destination(0, 0, path, task="SHIPMENT_DELIVER")

            elif task_info.get("shipment_id"):
                shipment_id = task_info["shipment_id"]
                shipment = warehouse.shipments.get(shipment_id)
                if shipment:
                    product.update_status(ProductStatus.OUTBOUND, "ROBOT", "Picked for shipment")
                    self.event_log.add(Event.create(
                        EventType.SHIPMENT_DISPATCHED,
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                        shipment_id=shipment.id,
                        new_state="PICKED_UP",
                    ))

                    path = self.pathfinder.find_path_to_zone(warehouse, robot, warehouse.outbound_zone)
                    if path:
                        task_info["phase"] = "SHIPMENT_DELIVER"
                        robot.set_destination(0, 0, path, task="SHIPMENT_DELIVER")

        robot.status = RobotStatus.IDLE
        self._robot_tasks.pop(robot.id, None)

    def _complete_scanning(self, warehouse: Warehouse, robot: Robot, task_info: dict) -> None:
        product_id = task_info["product_id"]
        product = warehouse.products.get(product_id)

        if product:
            self.scanner.scan(robot, product, self.event_log)
            robot.start_load_unload()
            task_info["phase"] = "UNLOADING"
        else:
            robot.status = RobotStatus.IDLE
            self._robot_tasks.pop(robot.id, None)

    def _create_shipment_for_order(self, warehouse: Warehouse, order: Order) -> None:
        from models.shipment import Shipment
        shipment = Shipment.create(
            [item.product_id for item in order.items],
            warehouse.id,
            warehouse.id,
        )
        warehouse.shipments[shipment.id] = shipment
        order.shipment_id = shipment.id
        order.status = OrderStatus.READY
        self.tracking.create_shipment(shipment)
        self.event_log.add(Event.create(
            EventType.SHIPMENT_CREATED,
            warehouse_id=warehouse.id,
            shipment_id=shipment.id,
            order_id=order.id,
            new_state="CREATED",
            tracking_id=shipment.tracking_id,
        ))

    def update_warehouse(self, warehouse: Warehouse, dt: float) -> None:
        active_product_ids = {
            task.get("product_id")
            for task in self._robot_tasks.values()
            if task.get("product_id")
        }
        queued_product_ids = {product.id for product in warehouse.inbound_queue}
        for product in warehouse.products.values():
            if (product.status == ProductStatus.RECEIVED
                    and product.id not in active_product_ids
                    and product.id not in queued_product_ids):
                warehouse.inbound_queue.append(product)

        for product in list(warehouse.inbound_queue):
            robot = warehouse.get_available_robot()
            if robot:
                warehouse.inbound_queue.remove(product)
                self._assign_inbound_task(warehouse, robot, product)

        for order in list(warehouse.orders.values()):
            if order.status == OrderStatus.CREATED:
                self.process_order(order)

        for shipment in list(warehouse.shipments.values()):
            if shipment.status == ShipmentStatus.CREATED:
                self.process_shipment(shipment)

    def receive_transfer(self, warehouse: Warehouse, product: Product) -> None:
        self.inventory.receive_transfer(warehouse, product)
        self.event_log.add(Event.create(
            EventType.SHIPMENT_RECEIVED,
            warehouse_id=warehouse.id,
            product_id=product.id,
            new_state="RECEIVED",
        ))
        self.process_inbound(product)