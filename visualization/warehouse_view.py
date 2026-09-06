from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
import time
import math

if TYPE_CHECKING:
    import pygame
else:
    try:
        import pygame
    except ImportError:
        pygame = None  # type: ignore[assignment]

from models.warehouse import Warehouse
from models.robot import Robot, RobotStatus
from models.rack import Rack
from config import VisualizationConfig


class WarehouseView:
    def __init__(self, config: VisualizationConfig, warehouse: Warehouse):
        self.config = config
        self.warehouse = warehouse
        self.font: Optional["pygame.font.Font"] = None
        self.small_font: Optional["pygame.font.Font"] = None
        self._rack_label_cache: Dict[str, "pygame.Surface"] = {}
        self._rack_count_cache: Dict[str, Tuple[int, "pygame.Surface"]] = {}
        self._start_time = time.time()
        self._init_fonts()

    def _init_fonts(self) -> None:
        if pygame is None:
            return
        try:
            self.font = pygame.font.SysFont("consolas", 14)
            self.small_font = pygame.font.SysFont("consolas", 10)
        except:
            self.font = pygame.font.Font(None, 16)
            self.small_font = pygame.font.Font(None, 12)

    def draw(self, surface: pygame.Surface, offset_x: int, offset_y: int, show_paths: bool = True) -> None:
        if pygame is None:
            return
        self._draw_grid(surface, offset_x, offset_y)
        self._draw_zones(surface, offset_x, offset_y)
        self._draw_racks(surface, offset_x, offset_y)
        self._draw_robots(surface, offset_x, offset_y, show_paths)
        self._draw_legend(surface, offset_x, offset_y)

    def _draw_grid(self, surface: "pygame.Surface", offset_x: int, offset_y: int) -> None:
        if pygame is None:
            return
        cell_size = self.config.cell_size
        colors = self.config.colors
        if colors is None:
            return
        for x in range(self.warehouse.width + 1):
            pygame.draw.line(
                surface,
                colors["grid"],
                (offset_x + x * cell_size, offset_y),
                (offset_x + x * cell_size, offset_y + self.warehouse.height * cell_size),
            )
        for y in range(self.warehouse.height + 1):
            pygame.draw.line(
                surface,
                colors["grid"],
                (offset_x, offset_y + y * cell_size),
                (offset_x + self.warehouse.width * cell_size, offset_y + y * cell_size),
            )

    def _draw_zones(self, surface: "pygame.Surface", offset_x: int, offset_y: int) -> None:
        if pygame is None:
            return
        cell_size = self.config.cell_size
        colors = self.config.colors or {}

        ix1, iy1, ix2, iy2 = self.warehouse.inbound_zone
        inbound_rect = pygame.Rect(
            offset_x + ix1 * cell_size,
            offset_y + iy1 * cell_size,
            (ix2 - ix1) * cell_size,
            (iy2 - iy1) * cell_size,
        )
        pygame.draw.rect(surface, colors.get("inbound", (100, 100, 200)), inbound_rect)
        if self.font:
            label = self.font.render("INBOUND", True, (255, 255, 255))
            surface.blit(label, (inbound_rect.x + 5, inbound_rect.y + 5))

        ox1, oy1, ox2, oy2 = self.warehouse.outbound_zone
        outbound_rect = pygame.Rect(
            offset_x + ox1 * cell_size,
            offset_y + oy1 * cell_size,
            (ox2 - ox1) * cell_size,
            (oy2 - oy1) * cell_size,
        )
        pygame.draw.rect(surface, colors.get("outbound", (200, 100, 100)), outbound_rect)
        if self.font:
            label = self.font.render("OUTBOUND", True, (255, 255, 255))
            surface.blit(label, (outbound_rect.x + 5, outbound_rect.y + 5))

    def _draw_racks(self, surface: "pygame.Surface", offset_x: int, offset_y: int) -> None:
        if pygame is None:
            return
        cell_size = self.config.cell_size
        colors = self.config.colors or {}
        
        elapsed = time.time() - self._start_time
        pulse_cycle = (math.sin(elapsed * 4) + 1) / 2  # Oscillates 0-1 at 2Hz
        
        for rack in self.warehouse.racks.values():
            rx = offset_x + rack.x * cell_size
            ry = offset_y + rack.y * cell_size

            util = rack.utilization()
            if util == 0:
                color = colors.get("rack_empty", (100, 100, 120))
            elif util < 0.7:
                color = colors.get("rack_partial", (100, 180, 100))
            else:
                color = colors.get("rack_full", (60, 140, 60))

            pygame.draw.rect(surface, color, (rx, ry, cell_size, cell_size))
            pygame.draw.rect(surface, (200, 200, 200), (rx, ry, cell_size, cell_size), 2)

            if self.small_font:
                label = self.small_font.render(rack.id, True, (255, 255, 255))
                surface.blit(label, (rx + 2, ry + 2))

                count_label = self.small_font.render(f"{rack.get_product_count()}/{rack.capacity}", True, (200, 200, 200))
                surface.blit(count_label, (rx + 2, ry + cell_size - 14))

            # Pulsing load indicator for filled racks
            if rack.get_product_count() > 0:
                pulse_radius = int(3 + pulse_cycle * 4)
                pulse_alpha = int(100 + pulse_cycle * 155)
                # Draw pulsing circle at rack center
                pygame.draw.circle(
                    surface,
                    (255, 200, 100),
                    (rx + cell_size // 2, ry + cell_size // 2),
                    pulse_radius,
                    2
                )


    def _draw_robots(self, surface: "pygame.Surface", offset_x: int, offset_y: int, show_paths: bool) -> None:
        if pygame is None:
            return
        cell_size = self.config.cell_size
        colors = self.config.colors or {}
        radius = cell_size // 2 - 2

        for robot in self.warehouse.robots.values():
            rx = offset_x + robot.x * cell_size + cell_size // 2
            ry = offset_y + robot.y * cell_size + cell_size // 2

            # Draw glowing path lines with gradient effect
            if show_paths and robot.path and robot.path_index < len(robot.path):
                path_points = []
                for step in robot.path[robot.path_index:]:
                    px = offset_x + step.x * cell_size + cell_size // 2
                    py = offset_y + step.y * cell_size + cell_size // 2
                    path_points.append((px, py))
                
                # Draw path with glow effect
                if len(path_points) > 1:
                    # Glow layers (outer to inner for glow effect)
                    for glow_width in [4, 2]:
                        glow_color = tuple(min(255, c + 80) for c in colors.get("path", (80, 80, 120)))
                        pygame.draw.lines(surface, glow_color, False, path_points, glow_width)
                    # Draw bright path line
                    pygame.draw.lines(surface, (200, 255, 100), False, path_points, 1)

            # Determine robot status color and ring color
            if robot.status == RobotStatus.IDLE:
                color = colors.get("robot_idle", (100, 200, 255))
                ring_color = (100, 200, 100)  # Green = idle/clear
            elif robot.status == RobotStatus.MOVING:
                color = colors.get("robot_moving", (255, 200, 50))
                ring_color = (100, 200, 100)  # Green = moving/active
            elif robot.status in (RobotStatus.LOADING, RobotStatus.UNLOADING, RobotStatus.SCANNING, RobotStatus.WAITING):
                color = colors.get("robot_carrying", (255, 150, 50))
                ring_color = (255, 255, 0)  # Yellow = busy/occupied
            elif robot.status == RobotStatus.CHARGING:
                color = colors.get("robot_charging", (150, 100, 255))
                ring_color = (100, 200, 100)  # Green = charging
            else:
                color = colors.get("robot_idle", (100, 200, 255))
                ring_color = (200, 100, 100)  # Red = error/unknown

            # Check for desync (peer_status = WAITING means blocked)
            if robot.peer_status == "WAITING":
                ring_color = (255, 100, 100)  # Red = blocked/desync

            # Draw outer status indicator ring
            pygame.draw.circle(surface, ring_color, (int(rx), int(ry)), radius + 4, 2)
            
            # Draw main robot circle
            pygame.draw.circle(surface, color, (int(rx), int(ry)), radius)
            pygame.draw.circle(surface, (255, 255, 255), (int(rx), int(ry)), radius, 2)

            # Draw load indicator (inner circle if carrying product)
            if robot.carrying_product_id:
                pygame.draw.circle(surface, (255, 255, 100), (int(rx), int(ry)), radius // 2)

            # Draw robot ID label
            if self.small_font:
                label = self.small_font.render(robot.id[-5:], True, (255, 255, 255))
                surface.blit(label, (int(rx - 15), int(ry - 20)))

            # Draw battery status indicator
            battery_color = (0, 255, 0) if robot.battery > 50 else (255, 255, 0) if robot.battery > 20 else (255, 0, 0)
            pygame.draw.rect(surface, battery_color, (int(rx - 10), int(ry + 15), int(20 * robot.battery / 100), 3))


    def _draw_legend(self, surface: pygame.Surface, offset_x: int, offset_y: int) -> None:
        pass


class MultiWarehouseView:
    def __init__(self, config: VisualizationConfig, warehouses: Dict[str, Warehouse]):
        self.config = config
        self.warehouses = warehouses
        self.views = {wh_id: WarehouseView(config, wh) for wh_id, wh in warehouses.items()}
        self.active_warehouse = list(warehouses.keys())[0] if warehouses else None

    def set_active(self, warehouse_id: str) -> None:
        if warehouse_id in self.views:
            self.active_warehouse = warehouse_id

    def draw(self, surface: pygame.Surface, x: int, y: int, show_paths: bool = True) -> None:
        if self.active_warehouse and self.active_warehouse in self.views:
            view = self.views[self.active_warehouse]
            if view.font:
                colors = self.config.colors or {}
                label = view.font.render(
                    f"ACTIVE WAREHOUSE: {view.warehouse.name} ({view.warehouse.id})",
                    True,
                    colors.get("text", (220, 220, 230)),
                )
                surface.blit(label, (x, y - 24))
            view.draw(surface, x, y, show_paths)

    def handle_click(self, pos: Tuple[int, int], view_x: int, view_y: int) -> Optional[str]:
        if not self.active_warehouse:
            return None

        cell_size = self.config.cell_size
        rel_x = (pos[0] - view_x) // cell_size
        rel_y = (pos[1] - view_y) // cell_size

        warehouse = self.warehouses[self.active_warehouse]
        if 0 <= rel_x < warehouse.width and 0 <= rel_y < warehouse.height:
            rack = warehouse.get_rack_at(rel_x, rel_y)
            if rack:
                return rack.id
            robot = warehouse.get_robot_at(rel_x, rel_y)
            if robot:
                return robot.id
        return None