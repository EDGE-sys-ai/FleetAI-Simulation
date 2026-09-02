import pygame
from typing import Dict, List, Tuple, Callable, Optional
from config import VisualizationConfig


class Button:
    def __init__(self, x: int, y: int, width: int, height: int, text: str, callback: Callable, config: VisualizationConfig):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.config = config
        self.font = None
        self.hovered = False
        self._init_font()

    def _init_font(self) -> None:
        try:
            self.font = pygame.font.SysFont("consolas", 12)
        except:
            self.font = pygame.font.Font(None, 14)

    def draw(self, surface: pygame.Surface) -> None:
        color = self.config.colors["panel_border"] if self.hovered else self.config.colors["grid"]
        pygame.draw.rect(surface, self.config.colors["panel_bg"], self.rect)
        pygame.draw.rect(surface, color, self.rect, 2)

        text_surf = self.font.render(self.text, True, self.config.colors["text"])
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.callback()
                return True
        return False


class SpeedControl:
    def __init__(self, x: int, y: int, config: VisualizationConfig, get_speed: Callable, set_speed: Callable):
        self.rect = pygame.Rect(x, y, 200, 30)
        self.config = config
        self.get_speed = get_speed
        self.set_speed = set_speed
        self.speeds = [0.5, 1.0, 2.0, 5.0, 10.0]
        self.font = None
        self._init_font()

    def _init_font(self) -> None:
        try:
            self.font = pygame.font.SysFont("consolas", 12)
        except:
            self.font = pygame.font.Font(None, 14)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.config.colors["panel_bg"], self.rect)
        pygame.draw.rect(surface, self.config.colors["panel_border"], self.rect, 1)

        current = self.get_speed()
        idx = self.speeds.index(current) if current in self.speeds else 1

        text = self.font.render(f"Speed: {current:.1f}x", True, self.config.colors["text"])
        surface.blit(text, (self.rect.x + 5, self.rect.y + 5))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                current = self.get_speed()
                idx = self.speeds.index(current) if current in self.speeds else 1
                if event.pos[0] < self.rect.centerx:
                    idx = max(0, idx - 1)
                else:
                    idx = min(len(self.speeds) - 1, idx + 1)
                self.set_speed(self.speeds[idx])
                return True
        return False


class UIManager:
    def __init__(self, config: VisualizationConfig, engine, dashboard, warehouse_view):
        self.config = config
        self.engine = engine
        self.dashboard = dashboard
        self.warehouse_view = warehouse_view
        self.buttons: List[Button] = []
        self.speed_control: Optional[SpeedControl] = None
        self.show_help = False
        self._create_controls()

    def _create_controls(self) -> None:
        button_y = 10
        button_x = 10
        btn_w, btn_h = 100, 30
        spacing = 5

        controls = [
            ("Pause/Resume", self._toggle_pause),
            ("New Product", self._spawn_product),
            ("New Order", self._spawn_order),
            ("New Transfer", self._spawn_transfer),
            ("Toggle Twin", self.dashboard.toggle_digital_twin),
            ("Toggle Log", self.dashboard.toggle_event_log),
            ("Toggle Stats", self.dashboard.toggle_stats),
            ("Help", self._toggle_help),
        ]

        for i, (text, callback) in enumerate(controls):
            col = i % 4
            row = i // 4
            btn = Button(
                button_x + col * (btn_w + spacing),
                button_y + row * (btn_h + spacing),
                btn_w, btn_h, text, callback, self.config
            )
            self.buttons.append(btn)

        self.speed_control = SpeedControl(
            button_x + 4 * (btn_w + spacing) + 20,
            button_y,
            self.config,
            lambda: self.engine.speed,
            lambda s: self.engine.set_speed(s)
        )

    def _toggle_pause(self) -> None:
        if self.engine.paused:
            self.engine.resume()
        else:
            self.engine.pause()

    def _spawn_product(self) -> None:
        self.engine._spawn_product_arrival()

    def _spawn_order(self) -> None:
        self.engine._spawn_customer_order()

    def _spawn_transfer(self) -> None:
        self.engine._spawn_transfer()

    def _toggle_help(self) -> None:
        self.show_help = not self.show_help

    def draw(self, surface: pygame.Surface) -> None:
        for btn in self.buttons:
            btn.draw(surface)

        if self.speed_control:
            self.speed_control.draw(surface)

        if self.show_help:
            self._draw_help(surface)

    def _draw_help(self, surface: pygame.Surface) -> None:
        help_rect = pygame.Rect(50, 50, 400, 300)
        pygame.draw.rect(surface, self.config.colors["panel_bg"], help_rect)
        pygame.draw.rect(surface, self.config.colors["panel_border"], help_rect, 2)

        try:
            font = pygame.font.SysFont("consolas", 12)
        except:
            font = pygame.font.Font(None, 14)

        lines = [
            "CONTROLS:",
            "SPACE - Pause/Resume",
            "R - Generate new product",
            "O - Create customer order",
            "T - Create inter-warehouse transfer",
            "D - Toggle digital twin panel",
            "E - Toggle event log",
            "S - Toggle statistics",
            "ESC - Exit",
            "",
            "Click on rack/robot to select",
            "Left/Right click speed control",
            "to change simulation speed",
            "",
            "PANELS:",
            "Left: Warehouse visualization",
            "Right: Dashboard & tracking",
        ]

        for i, line in enumerate(lines):
            color = self.config.colors["text"] if line.endswith(":") else self.config.colors["text_dim"]
            text = font.render(line, True, color)
            surface.blit(text, (help_rect.x + 10, help_rect.y + 10 + i * 20))

    def handle_event(self, event: pygame.event.Event) -> bool:
        for btn in self.buttons:
            if btn.handle_event(event):
                return True

        if self.speed_control and self.speed_control.handle_event(event):
            return True

        if event.type == pygame.KEYDOWN:
            return self._handle_key(event.key)

        return False

    def _handle_key(self, key: int) -> bool:
        if key == pygame.K_SPACE:
            self._toggle_pause()
            return True
        elif key == pygame.K_r:
            self._spawn_product()
            return True
        elif key == pygame.K_o:
            self._spawn_order()
            return True
        elif key == pygame.K_t:
            self._spawn_transfer()
            return True
        elif key == pygame.K_d:
            self.dashboard.toggle_digital_twin()
            return True
        elif key == pygame.K_e:
            self.dashboard.toggle_event_log()
            return True
        elif key == pygame.K_s:
            self.dashboard.toggle_stats()
            return True
        elif key == pygame.K_ESCAPE:
            self.engine.stop()
            return True
        elif key == pygame.K_h:
            self._toggle_help()
            return True
        elif key == pygame.K_1:
            self.warehouse_view.set_active("WH-A")
            return True
        elif key == pygame.K_2:
            self.warehouse_view.set_active("WH-B")
            return True
        elif key == pygame.K_UP:
            self.dashboard.scroll_event_log(-1)
            return True
        elif key == pygame.K_DOWN:
            self.dashboard.scroll_event_log(1)
            return True
        return False