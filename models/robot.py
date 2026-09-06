from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple
import uuid


class RobotStatus(str, Enum):
    IDLE = "IDLE"
    MOVING = "MOVING"
    SCANNING = "SCANNING"
    LOADING = "LOADING"
    UNLOADING = "UNLOADING"
    CHARGING = "CHARGING"
    WAITING = "WAITING"
    ERROR = "ERROR"


@dataclass
class PathStep:
    x: int
    y: int
    timestamp: float = 0.0


@dataclass
class Robot:
    id: str
    x: float
    y: float
    warehouse_id: str
    status: RobotStatus = RobotStatus.IDLE
    carrying_product_id: Optional[str] = None
    battery: float = 100.0
    destination: Optional[Tuple[int, int]] = None
    path: List[PathStep] = field(default_factory=list)
    path_index: int = 0
    target_rack_id: Optional[str] = None
    assigned_task: Optional[str] = None
    last_scan_time: float = 0.0
    scan_duration: float = 0.5
    load_unload_duration: float = 1.0
    task_timer: float = 0.0
    speed: float = 5.0
    peer_intent: Optional[Tuple[int, int]] = None
    peer_status: str = "CLEAR"
    peer_message: str = ""

    @classmethod
    def create(cls, warehouse_id: str, x: int, y: int, robot_num: int) -> "Robot":
        return cls(
            id=f"ROBOT-{warehouse_id[-1]}-{robot_num:02d}",
            x=x,
            y=y,
            warehouse_id=warehouse_id,
        )

    def set_destination(self, x: int, y: int, path: List[Tuple[int, int]], rack_id: Optional[str] = None, task: Optional[str] = None) -> None:
        self.destination = (x, y)
        self.path = [PathStep(px, py) for px, py in path]
        self.path_index = 0
        self.target_rack_id = rack_id
        self.assigned_task = task
        self.status = RobotStatus.MOVING

    def update_position(self, dt: float) -> bool:
        """Update robot position along path. Uses floating-point coordinates for smooth movement."""
        if self.status != RobotStatus.MOVING or not self.path or self.path_index >= len(self.path):
            return False

        target = self.path[self.path_index]
        dx = target.x - self.x
        dy = target.y - self.y
        distance = max(abs(dx), abs(dy))

        travel = self.speed * dt
        if distance <= travel:
            # Reached target waypoint
            self.x = float(target.x)
            self.y = float(target.y)
            self.path_index += 1
            if self.path_index >= len(self.path):
                # Path complete
                self.destination = None
                self.status = RobotStatus.WAITING
                return True
        else:
            # Move towards target with smooth floating-point interpolation
            if dx != 0 and dy != 0:
                # Diagonal movement - normalize to avoid moving faster diagonally
                magnitude = (dx**2 + dy**2)**0.5
                self.x += (dx / magnitude) * travel
                self.y += (dy / magnitude) * travel
            elif dx != 0:
                # Horizontal movement
                self.x += travel if dx > 0 else -travel
            else:
                # Vertical movement
                self.y += travel if dy > 0 else -travel

        self.battery = max(0, self.battery - 0.01 * dt)
        return False

    def start_scan(self) -> None:
        self.status = RobotStatus.SCANNING
        self.task_timer = self.scan_duration

    def start_load_unload(self) -> None:
        self.status = RobotStatus.LOADING if self.carrying_product_id is None else RobotStatus.UNLOADING
        self.task_timer = self.load_unload_duration

    def update_task(self, dt: float) -> bool:
        if self.task_timer > 0:
            self.task_timer -= dt
            if self.task_timer <= 0:
                if self.status == RobotStatus.SCANNING:
                    self.status = RobotStatus.WAITING
                elif self.status in (RobotStatus.LOADING, RobotStatus.UNLOADING):
                    self.status = RobotStatus.WAITING
                return True
        return False

    def assign_product(self, product_id: str) -> None:
        self.carrying_product_id = product_id
        self.status = RobotStatus.MOVING

    def release_product(self) -> Optional[str]:
        product_id = self.carrying_product_id
        self.carrying_product_id = None
        return product_id

    def needs_charge(self) -> bool:
        return self.battery < 20.0

    def charge(self, dt: float) -> None:
        self.battery = min(100.0, self.battery + 10.0 * dt)
        if self.battery >= 100.0:
            self.status = RobotStatus.IDLE

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "warehouse_id": self.warehouse_id,
            "status": self.status.value,
            "carrying_product_id": self.carrying_product_id,
            "battery": round(self.battery, 1),
            "destination": self.destination,
            "path_index": self.path_index,
            "path_length": len(self.path),
            "target_rack_id": self.target_rack_id,
            "assigned_task": self.assigned_task,
        }