from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class WarehouseConfig:
    id: str
    name: str
    width: int
    height: int
    inbound_zone: Tuple[int, int, int, int]
    outbound_zone: Tuple[int, int, int, int]
    rack_positions: List[Tuple[int, int]]
    robot_count: int
    rack_capacity: int
    rack_shelves: int


@dataclass
class SimulationConfig:
    tick_rate: float = 1.0
    max_products: int = 100
    initial_products: int = 50
    product_arrival_interval: float = 5.0
    order_creation_interval: float = 10.0
    transfer_creation_interval: float = 15.0
    robot_speed: float = 1.0
    scan_time: float = 0.5
    load_unload_time: float = 1.0
    failure_rate: float = 0.05
    network_delay_range: Tuple[float, float] = (0.1, 0.5)
    enable_failures: bool = True
    enable_network_delays: bool = True


@dataclass
class VisualizationConfig:
    cell_size: int = 40
    margin: int = 20
    panel_width: int = 350
    fps: int = 60
    colors: Dict[str, Tuple[int, int, int]] = None

    def __post_init__(self):
        if self.colors is None:
            self.colors = {
                "background": (30, 30, 40),
                "grid": (60, 60, 80),
                "rack_empty": (100, 100, 120),
                "rack_partial": (100, 180, 100),
                "rack_full": (60, 140, 60),
                "inbound": (100, 100, 200),
                "outbound": (200, 100, 100),
                "robot_idle": (100, 200, 255),
                "robot_moving": (255, 200, 50),
                "robot_carrying": (255, 150, 50),
                "robot_charging": (150, 100, 255),
                "product": (255, 255, 100),
                "path": (80, 80, 120),
                "text": (220, 220, 230),
                "text_dim": (150, 150, 170),
                "panel_bg": (25, 25, 35),
                "panel_border": (80, 80, 100),
                "sync_ok": (80, 200, 80),
                "sync_warning": (255, 200, 50),
                "sync_error": (255, 80, 80),
            }


WAREHOUSE_CONFIGS = [
    WarehouseConfig(
        id="WH-A",
        name="Warehouse Alpha",
        width=20,
        height=15,
        inbound_zone=(0, 0, 20, 2),
        outbound_zone=(0, 13, 20, 15),
        rack_positions=[
            (2, 3), (5, 3), (8, 3), (11, 3), (14, 3), (17, 3),
            (2, 6), (5, 6), (8, 6), (11, 6), (14, 6), (17, 6),
            (2, 9), (5, 9), (8, 9), (11, 9), (14, 9), (17, 9),
        ],
        robot_count=8,
        rack_capacity=20,
        rack_shelves=4,
    ),
    WarehouseConfig(
        id="WH-B",
        name="Warehouse Beta",
        width=18,
        height=14,
        inbound_zone=(0, 0, 18, 2),
        outbound_zone=(0, 12, 18, 14),
        rack_positions=[
            (2, 3), (5, 3), (8, 3), (11, 3), (14, 3),
            (2, 6), (5, 6), (8, 6), (11, 6), (14, 6),
            (2, 9), (5, 9), (8, 9), (11, 9), (14, 9),
        ],
        robot_count=6,
        rack_capacity=18,
        rack_shelves=3,
    ),
]

SIMULATION_CONFIG = SimulationConfig()
VISUALIZATION_CONFIG = VisualizationConfig()

PRODUCT_CATEGORIES = {
    "ELEC": "Electronics",
    "FOOD": "Food & Beverage",
    "CLOTH": "Clothing",
    "HOME": "Home & Garden",
    "TOOL": "Tools & Hardware",
}

CATEGORY_RACK_PREFERENCE = {
    "ELEC": ["top", "middle"],
    "FOOD": ["bottom", "middle"],
    "CLOTH": ["middle", "top"],
    "HOME": ["bottom", "middle"],
    "TOOL": ["bottom", "top"],
}