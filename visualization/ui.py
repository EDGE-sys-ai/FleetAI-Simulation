from typing import TYPE_CHECKING, Dict, List, Tuple, Callable, Optional

if TYPE_CHECKING:
    import pygame
else:
    try:
        import pygame
    except ImportError:
        pygame = None  # type: ignore[assignment]

from config import VisualizationConfig


class Button:
    def __init__(self, x: int, y: int, width: int, height: int, text: str, callback: Callable, config: VisualizationConfig):
        self.rect: Optional["pygame.Rect"] = None
        if pygame is not None:
            self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.config = config
        self.font: Optional["pygame.font.Font"] = None
        self.hovered = False
        self._init_font()

    def _init_font(self) -> None:
        if pygame is None:
            return
        try:
            self.font = pygame.font.SysFont("consolas", 12)
        except:
            self.font = pygame.font.Font(None, 14)

    def draw(self, surface: "pygame.Surface") -> None:
        if pygame is None or self.rect is None:
            return
        colors = self.config.colors or {}
        color = colors.get("panel_border", (80, 80, 100)) if self.hovered else colors.get("grid", (60, 60, 80))
        pygame.draw.rect(surface, colors.get("panel_bg", (25, 25, 35)), self.rect)
        pygame.draw.rect(surface, color, self.rect, 2)

        if self.font:
            text_surf = self.font.render(self.text, True, colors.get("text", (220, 220, 230)))
            text_rect = text_surf.get_rect(center=self.rect.center)
            surface.blit(text_surf, text_rect)

    def handle_event(self, event: "pygame.event.Event") -> bool:
        if pygame is None or self.rect is None:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.callback()
                return True
        return False


class SpeedControl:
    def __init__(self, x: int, y: int, config: VisualizationConfig, get_speed: Callable, set_speed: Callable):
        self.rect: Optional["pygame.Rect"] = None
        if pygame is not None:
            self.rect = pygame.Rect(x, y, 200, 30)
        self.config = config
        self.get_speed = get_speed
        self.set_speed = set_speed
        self.speeds = [0.5, 1.0, 2.0, 5.0, 10.0]
        self.font: Optional["pygame.font.Font"] = None
        self._init_font()

    def _init_font(self) -> None:
        if pygame is None:
            return
        try:
            self.font = pygame.font.SysFont("consolas", 12)
        except:
            self.font = pygame.font.Font(None, 14)

    def draw(self, surface: "pygame.Surface") -> None:
        if pygame is None or self.rect is None:
            return
        colors = self.config.colors or {}
        pygame.draw.rect(surface, colors.get("panel_bg", (25, 25, 35)), self.rect)
        pygame.draw.rect(surface, colors.get("panel_border", (80, 80, 100)), self.rect, 1)

        current = self.get_speed()
        idx = self.speeds.index(current) if current in self.speeds else 1

        if self.font:
            text = self.font.render(f"Speed: {current:.1f}x", True, colors.get("text", (220, 220, 230)))
            surface.blit(text, (self.rect.x + 5, self.rect.y + 5))

    def handle_event(self, event: "pygame.event.Event") -> bool:
        if pygame is None or self.rect is None:
            return False
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
        btn_w, btn_h = 88, 28
        spacing = 5

        controls = [
            ("Pause/Resume", self._toggle_pause),
            ("New Product", self._spawn_product),
            ("New Order", self._spawn_order),
            ("New Transfer", self._spawn_transfer),
            ("Toggle Twin", self.dashboard.toggle_digital_twin),
            ("Toggle Log", self.dashboard.toggle_event_log),
            ("Toggle Stats", self.dashboard.toggle_stats),
            ("Toggle P2P", self.dashboard.toggle_p2p),
            ("Help", self._toggle_help),
            ("WH-A", lambda: self.warehouse_view.set_active("WH-A")),
            ("WH-B", lambda: self.warehouse_view.set_active("WH-B")),
        ]

        for i, (text, callback) in enumerate(controls):
            col = i
            row = 0
            btn = Button(
                button_x + col * (btn_w + spacing),
                button_y + row * (btn_h + spacing),
                btn_w, btn_h, text, callback, self.config
            )
            self.buttons.append(btn)

        self.speed_control = SpeedControl(
            button_x + len(controls) * (btn_w + spacing) + 10,
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

    def draw(self, surface: "pygame.Surface") -> None:
        for btn in self.buttons:
            btn.draw(surface)

        if self.speed_control:
            self.speed_control.draw(surface)

        if self.show_help:
            self._draw_help(surface)

    def _draw_help(self, surface: "pygame.Surface") -> None:
        if pygame is None:
            return
        help_rect = pygame.Rect(50, 50, 400, 300)
        colors = self.config.colors or {}
        pygame.draw.rect(surface, colors.get("panel_bg", (25, 25, 35)), help_rect)
        pygame.draw.rect(surface, colors.get("panel_border", (80, 80, 100)), help_rect, 2)

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
            "MOUSE CONTROLS:",
            "Left-click: Select robot/rack → Show telemetry",
            "Right-click: Cycle speed (0.5x, 1.0x, 2.0x)",
            "Scroll up/down: Fine-tune speed",
            "",
            "DISPLAY:",
            "• Green ring: Robot moving/clear",
            "• Yellow ring: Robot busy/scanning",
            "• Red ring: Robot blocked/desync",
            "• Glowing path: Active route to target",
            "• Pulsing circles: Racks with products",
        ]

        for i, line in enumerate(lines):
            color = colors.get("text", (220, 220, 230)) if line.endswith(":") else colors.get("text_dim", (150, 150, 170))
            text = font.render(line, True, color)
            surface.blit(text, (help_rect.x + 10, help_rect.y + 10 + i * 20))

    def handle_event(self, event: "pygame.event.Event") -> bool:
        if pygame is None:
            return False
        for btn in self.buttons:
            if btn.handle_event(event):
                return True

        if self.speed_control and self.speed_control.handle_event(event):
            return True

        if event.type == pygame.KEYDOWN:
            return self._handle_key(event.key)

        return False

    def _handle_key(self, key: int) -> bool:
        if pygame is None:
            return False
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
        elif key == pygame.K_p:
            self.dashboard.toggle_p2p()
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