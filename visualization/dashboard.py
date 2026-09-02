import pygame
from typing import Dict, List, Optional
from simulation.engine import SimulationEngine
from simulation.events import Event, EventType
from digital_twin.twin import DigitalTwin
from config import VisualizationConfig


class Dashboard:
    def __init__(self, config: VisualizationConfig, engine: SimulationEngine):
        self.config = config
        self.engine = engine
        self.font = None
        self.small_font = None
        self.title_font = None
        self._init_fonts()
        self.selected_product_id: Optional[str] = None
        self.show_digital_twin = True
        self.show_event_log = True
        self.show_stats = True
        self.event_log_scroll = 0

    def _init_fonts(self) -> None:
        try:
            self.font = pygame.font.SysFont("consolas", 14)
            self.small_font = pygame.font.SysFont("consolas", 11)
            self.title_font = pygame.font.SysFont("consolas", 16, bold=True)
        except:
            self.font = pygame.font.Font(None, 16)
            self.small_font = pygame.font.Font(None, 14)
            self.title_font = pygame.font.Font(None, 18)

    def draw(self, surface: pygame.Surface, x: int, y: int, width: int, height: int) -> None:
        panel_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(surface, self.config.colors["panel_bg"], panel_rect)
        pygame.draw.rect(surface, self.config.colors["panel_border"], panel_rect, 2)

        current_y = y + 10
        current_y = self._draw_header(surface, x + 10, current_y, width - 20)
        current_y = self._draw_simulation_stats(surface, x + 10, current_y, width - 20)
        current_y = self._draw_warehouse_stats(surface, x + 10, current_y, width - 20)

        if self.show_digital_twin:
            current_y = self._draw_digital_twin_status(surface, x + 10, current_y, width - 20)

        if self.show_event_log:
            current_y = self._draw_event_log(surface, x + 10, current_y, width - 20, height - (current_y - y) - 10)

        if self.show_stats and self.selected_product_id:
            self._draw_product_tracking(surface, x + 10, current_y, width - 20)

    def _draw_header(self, surface: pygame.Surface, x: int, y: int, width: int) -> int:
        title = self.title_font.render("WAREHOUSE DIGITAL TWIN SIMULATION", True, self.config.colors["text"])
        surface.blit(title, (x, y))
        return y + 25

    def _draw_simulation_stats(self, surface: pygame.Surface, x: int, y: int, width: int) -> int:
        stats = self.engine.get_stats()
        lines = [
            f"Time: {stats['simulation_time']:.1f}s  |  Speed: {stats['speed']:.1f}x  |  {'PAUSED' if stats['paused'] else 'RUNNING'}",
            f"Products: {stats['total_products']}  |  Stored: {stats['stored_products']}  |  Robots: {stats['active_robots']}/{stats['total_robots']} active",
            f"Robot Utilization: {stats['robot_utilization']*100:.0f}%  |  Twin Sync: {stats['digital_twin_sync_rate']*100:.1f}%",
        ]

        for line in lines:
            text = self.font.render(line, True, self.config.colors["text"])
            surface.blit(text, (x, y))
            y += 20
        return y + 5

    def _draw_warehouse_stats(self, surface: pygame.Surface, x: int, y: int, width: int) -> int:
        title = self.font.render("WAREHOUSES", True, (200, 200, 100))
        surface.blit(title, (x, y))
        y += 20

        for wh_id, warehouse in self.engine.warehouses.items():
            stats = warehouse.get_stats()
            line = f"  {wh_id} ({stats['name']}): {stats['stored_products']}/{stats['capacity']} ({stats['utilization']*100:.0f}%)  Robots: {stats['robots_active']}/{stats['robots_total']}  In: {stats['inbound_queue']}  Out: {stats['outbound_queue']}"
            color = self.config.colors["text"] if wh_id == self.engine.warehouses.get(self.engine.warehouses, {}).get(wh_id, {}).get('id') else self.config.colors["text_dim"]
            text = self.small_font.render(line, True, self.config.colors["text"])
            surface.blit(text, (x, y))
            y += 18
        return y + 5

    def _draw_digital_twin_status(self, surface: pygame.Surface, x: int, y: int, width: int) -> int:
        title = self.font.render("DIGITAL TWINS", True, (100, 200, 255))
        surface.blit(title, (x, y))
        y += 20

        for wh_id, twin in self.engine.digital_twins.items():
            summary = twin.get_state_summary()
            status_color = self.config.colors["sync_ok"] if summary["sync_status"] == "SYNCHRONIZED" else self.config.colors["sync_warning"]
            line = f"  {wh_id}: {summary['products_count']} products, {summary['robots_count']} robots, {summary['inventory_count']} in inventory"
            text = self.small_font.render(line, True, self.config.colors["text"])
            surface.blit(text, (x, y))

            status_text = self.small_font.render(f"  Status: {summary['sync_status']}", True, status_color)
            surface.blit(status_text, (x + 150, y))
            y += 18
        return y + 5

    def _draw_event_log(self, surface: pygame.Surface, x: int, y: int, width: int, max_height: int) -> int:
        title = self.font.render("EVENT LOG", True, (255, 200, 100))
        surface.blit(title, (x, y))
        y += 20

        events = self.engine.event_log.get_recent(50)
        max_lines = max(1, max_height // 16)
        start_idx = max(0, len(events) - max_lines + self.event_log_scroll)
        display_events = events[start_idx:start_idx + max_lines]

        for event in display_events:
            time_str = event.timestamp.strftime("%H:%M:%S")
            type_str = event.event_type.value[:20].ljust(20)
            prod_str = event.product_id[-8:] if event.product_id else "".ljust(8)
            robot_str = event.robot_id[-6:] if event.robot_id else "".ljust(6)

            line = f"  {time_str}  {type_str}  {prod_str}  {robot_str}"
            color = self._get_event_color(event.event_type)
            text = self.small_font.render(line, True, color)
            surface.blit(text, (x, y))
            y += 16

        return y

    def _get_event_color(self, event_type: EventType) -> Tuple[int, int, int]:
        if "ERROR" in event_type.value or "FAILED" in event_type.value or "DESYNC" in event_type.value:
            return self.config.colors["sync_error"]
        elif "WARNING" in event_type.value:
            return self.config.colors["sync_warning"]
        elif "SYNC" in event_type.value:
            return self.config.colors["sync_ok"]
        else:
            return self.config.colors["text_dim"]

    def _draw_product_tracking(self, surface: pygame.Surface, x: int, y: int, width: int) -> None:
        if not self.selected_product_id:
            return

        for warehouse in self.engine.warehouses.values():
            product = warehouse.products.get(self.selected_product_id)
            if product:
                title = self.font.render(f"PRODUCT TRACKING: {product.id}", True, (255, 255, 100))
                surface.blit(title, (x, y))
                y += 22

                lines = [
                    f"  Barcode: {product.barcode}",
                    f"  SKU: {product.sku}",
                    f"  Category: {product.category.value}",
                    f"  Status: {product.status.value}",
                    f"  Warehouse: {product.warehouse_id}",
                    f"  Location: {product.location}",
                    f"  Robot: {product.current_robot_id or 'None'}",
                    "",
                    "  Movement History:",
                ]
                for line in lines:
                    text = self.small_font.render(line, True, self.config.colors["text"])
                    surface.blit(text, (x, y))
                    y += 16

                for movement in product.movement_history[-5:]:
                    time_str = movement.timestamp.strftime("%H:%M:%S")
                    line = f"    {time_str}  {movement.event_type}  @ {movement.location}"
                    text = self.small_font.render(line, True, self.config.colors["text_dim"])
                    surface.blit(text, (x, y))
                    y += 14
                break

    def handle_click(self, pos: Tuple[int, int], x: int, y: int, width: int, height: int) -> bool:
        if x <= pos[0] <= x + width and y <= pos[1] <= y + height:
            return True
        return False

    def toggle_digital_twin(self) -> None:
        self.show_digital_twin = not self.show_digital_twin

    def toggle_event_log(self) -> None:
        self.show_event_log = not self.show_event_log

    def toggle_stats(self) -> None:
        self.show_stats = not self.show_stats

    def select_product(self, product_id: str) -> None:
        self.selected_product_id = product_id

    def scroll_event_log(self, direction: int) -> None:
        self.event_log_scroll += direction