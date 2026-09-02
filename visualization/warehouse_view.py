import pygame
from typing import Dict, List, Optional, Tuple
from models.warehouse import Warehouse
from models.robot import Robot, RobotStatus
from models.rack import Rack
from config import VisualizationConfig


class WarehouseView:
    def __init__(self, config: VisualizationConfig, warehouse: Warehouse):
        self.config = config
        self.warehouse = warehouse
        self.font = None
        self.small_font = None
        self._init_fonts()

    def _init_fonts(self) -> None:
        try:
            self.font = pygame.font.SysFont("consolas", 14)
            self.small_font = pygame.font.SysFont("consolas", 10)
        except:
            self.font = pygame.font.Font(None, 16)
            self.small_font = pygame.font.Font(None, 12)

    def draw(self, surface: pygame.Surface, offset_x: int, offset_y: int, show_paths: bool = True) -> None:
        self._draw_grid(surface, offset_x, offset_y)
        self._draw_zones(surface, offset_x, offset_y)
        self._draw_racks(surface, offset_x, offset_y)
        self._draw_robots(surface, offset_x, offset_y, show_paths)
        self._draw_legend(surface, offset_x, offset_y)

    def _draw_grid(self, surface: pygame.Surface, offset_x: int, offset_y: int) -> None:
        cell_size = self.config.cell_size
        for x in range(self.warehouse.width + 1):
            pygame.draw.line(
                surface,
                self.config.colors["grid"],
                (offset_x + x * cell_size, offset_y),
                (offset_x + x * cell_size, offset_y + self.warehouse.height * cell_size),
            )
        for y in range(self.warehouse.height + 1):
            pygame.draw.line(
                surface,
                self.config.colors["grid"],
                (offset_x, offset_y + y * cell_size),
                (offset_x + self.warehouse.width * cell_size, offset_y + y * cell_size),
            )

    def _draw_zones(self, surface: pygame.Surface, offset_x: int, offset_y: int) -> None:
        cell_size = self.config.cell_size

        ix1, iy1, ix2, iy2 = self.warehouse.inbound_zone
        inbound_rect = pygame.Rect(
            offset_x + ix1 * cell_size,
            offset_y + iy1 * cell_size,
            (ix2 - ix1) * cell_size,
            (iy2 - iy1) * cell_size,
        )
        pygame.draw.rect(surface, self.config.colors["inbound"], inbound_rect)
        label = self.font.render("INBOUND", True, (255, 255, 255))
        surface.blit(label, (inbound_rect.x + 5, inbound_rect.y + 5))

        ox1, oy1, ox2, oy2 = self.warehouse.outbound_zone
        outbound_rect = pygame.Rect(
            offset_x + ox1 * cell_size,
            offset_y + oy1 * cell_size,
            (ox2 - ox1) * cell_size,
            (oy2 - oy1) * cell_size,
        )
        pygame.draw.rect(surface, self.config.colors["outbound"], outbound_rect)
        label = self.font.render("OUTBOUND", True, (255, 255, 255))
        surface.blit(label, (outbound_rect.x + 5, outbound_rect.y + 5))

    def _draw_racks(self, surface: pygame.Surface, offset_x: int, offset_y: int) -> None:
        cell_size = self.config.cell_size
        for rack in self.warehouse.racks.values():
            rx = offset_x + rack.x * cell_size
            ry = offset_y + rack.y * cell_size

            util = rack.utilization()
            if util == 0:
                color = self.config.colors["rack_empty"]
            elif util < 0.7:
                color = self.config.colors["rack_partial"]
            else:
                color = self.config.colors["rack_full"]

            pygame.draw.rect(surface, color, (rx, ry, cell_size, cell_size))
            pygame.draw.rect(surface, (200, 200, 200), (rx, ry, cell_size, cell_size), 2)

            label = self.small_font.render(rack.id, True, (255, 255, 255))
            surface.blit(label, (rx + 2, ry + 2))

            count_label = self.small_font.render(f"{rack.get_product_count()}/{rack.capacity}", True, (200, 200, 200))
            surface.blit(count_label, (rx + 2, ry + cell_size - 14))

    def _draw_robots(self, surface: pygame.Surface, offset_x: int, offset_y: int, show_paths: bool) -> None:
        cell_size = self.config.cell_size
        radius = cell_size // 2 - 2

        for robot in self.warehouse.robots.values():
            rx = offset_x + robot.x * cell_size + cell_size // 2
            ry = offset_y + robot.y * cell_size + cell_size // 2

            if robot.status == RobotStatus.IDLE:
                color = self.config.colors["robot_idle"]
            elif robot.status == RobotStatus.MOVING:
                color = self.config.colors["robot_moving"]
            elif robot.status in (RobotStatus.LOADING, RobotStatus.UNLOADING, RobotStatus.WAITING):
                color = self.config.colors["robot_carrying"]
            elif robot.status == RobotStatus.CHARGING:
                color = self.config.colors["robot_charging"]
            else:
                color = self.config.colors["robot_idle"]

            pygame.draw.circle(surface, color, (rx, ry), radius)
            pygame.draw.circle(surface, (255, 255, 255), (rx, ry), radius, 2)

            if robot.carrying_product_id:
                pygame.draw.circle(surface, (255, 255, 100), (rx, ry), radius // 2)

            label = self.small_font.render(robot.id[-5:], True, (255, 255, 255))
            surface.blit(label, (rx - 15, ry - 20))

            battery_color = (0, 255, 0) if robot.battery > 50 else (255, 255, 0) if robot.battery > 20 else (255, 0, 0)
            pygame.draw.rect(surface, battery_color, (rx - 10, ry + 15, int(20 * robot.battery / 100), 3))

            if show_paths and robot.path and robot.path_index < len(robot.path):
                path_points = []
                for step in robot.path[robot.path_index:]:
                    px = offset_x + step.x * cell_size + cell_size // 2
                    py = offset_y + step.y * cell_size + cell_size // 2
                    path_points.append((px, py))
                if len(path_points) > 1:
                    pygame.draw.lines(surface, self.config.colors["path"], False, path_points, 1)

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
            self.views[self.active_warehouse].draw(surface, x, y, show_paths)

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