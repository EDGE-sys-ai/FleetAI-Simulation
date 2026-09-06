#!/usr/bin/env python3
"""
Automated Warehouse Digital Twin Simulation

A complete simulation of an intelligent warehouse management system
with digital twin synchronization, inter-warehouse shipping, and
real-time visualization.
"""

import sys
import argparse
import time
import json
from datetime import datetime
from typing import Dict

from config import WAREHOUSE_CONFIGS, SIMULATION_CONFIG, VisualizationConfig
from models.warehouse import Warehouse
from simulation.engine import SimulationEngine


def create_warehouses() -> Dict[str, Warehouse]:
    warehouses = {}
    for config in WAREHOUSE_CONFIGS:
        warehouses[config.id] = Warehouse.from_config(config)
    return warehouses


def run_headless(engine: SimulationEngine, duration: float = 60.0, tick_rate: float = 1.0) -> None:
    print("=" * 60)
    print("WAREHOUSE DIGITAL TWIN SIMULATION - HEADLESS MODE")
    print("=" * 60)
    print(f"Running for {duration} seconds at {tick_rate}x speed...")
    print()

    engine.start()
    start_time = time.time()
    last_print: float = 0.0
    print_interval = 5.0

    try:
        while engine.running and (time.time() - start_time) < duration:
            dt = 1.0 / 60.0
            engine.update(dt * tick_rate)

            current_time = time.time() - start_time
            if current_time - last_print >= print_interval:
                stats = engine.get_stats()
                print(f"[{current_time:.1f}s] Products: {stats['total_products']} | "
                      f"Stored: {stats['stored_products']} | "
                      f"Robots Active: {stats['active_robots']}/{stats['total_robots']} | "
                      f"Sync: {stats['digital_twin_sync_rate']*100:.1f}% | "
                      f"Events: {stats['events_logged']}")
                last_print = current_time

            time.sleep(1.0 / 60.0)

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    print()
    print("=" * 60)
    print("FINAL STATISTICS")
    print("=" * 60)
    stats = engine.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print()
    print("Event Log Summary:")
    print(f"  Total Events: {len(engine.event_log.events)}")
    for event in engine.event_log.get_recent(20):
        print(f"  [{event.timestamp.strftime('%H:%M:%S')}] {event.event_type.value} "
              f"P:{event.product_id[-8:] if event.product_id else 'N/A'} "
              f"R:{event.robot_id[-6:] if event.robot_id else 'N/A'}")


def run_demo(engine: SimulationEngine) -> None:
    print("=" * 60)
    print("WAREHOUSE DIGITAL TWIN SIMULATION - DEMO MODE")
    print("=" * 60)
    print("Running deterministic demonstration scenario...")
    print()

    engine.start()

    demo_steps = [
        (2.0, "Product P-DEMO01 arrives at Warehouse A"),
        (4.0, "Worker loads product onto Robot-A-01"),
        (5.0, "Robot-A-01 scans barcode"),
        (6.0, "Warehouse assigns Rack-A-05"),
        (8.0, "Robot-A-01 travels to Rack-A-05"),
        (12.0, "Product stored successfully"),
        (13.0, "Server receives delivery event"),
        (13.5, "Digital Twin A updates"),
        (15.0, "Customer places order for P-DEMO01"),
        (16.0, "Robot-A-02 retrieves P-DEMO01"),
        (17.0, "Product scanned for outbound"),
        (18.0, "Shipment TRK-DEMO001 created"),
        (19.0, "Product leaves Warehouse A"),
        (25.0, "Shipment travels to Warehouse B"),
        (26.0, "Warehouse B receives and scans P-DEMO01"),
        (27.0, "Robot-B-01 stores P-DEMO01"),
        (28.0, "Digital Twin B updates"),
        (30.0, "Global tracking displays complete journey"),
    ]

    for delay, description in demo_steps:
        print(f"  [{delay:.1f}s] {description}")
        target_time = engine.current_time + delay
        while engine.current_time < target_time and engine.running:
            engine.update(1.0 / 60.0)
            time.sleep(1.0 / 60.0)

    print()
    print("=" * 60)
    print("DEMO COMPLETE - Final State")
    print("=" * 60)

    for wh_id, warehouse in engine.warehouses.items():
        print(f"\n{wh_id} ({warehouse.name}):")
        for product in warehouse.products.values():
            print(f"  {product.id}: {product.status.value} @ {product.location}")

    for wh_id, twin in engine.digital_twins.items():
        summary = twin.get_state_summary()
        print(f"\nDigital Twin {wh_id}: {summary['sync_status']} | "
              f"{summary['products_count']} products | {summary['inventory_count']} in inventory")


def run_visual(engine: SimulationEngine) -> None:
    try:
        # Load pygame dynamically so the optional dependency does not trigger
        # an import-resolution error when running headless.
        pygame = __import__("pygame")
    except ImportError:
        print("Pygame not installed. Run: pip install pygame")
        print("Falling back to headless mode...")
        run_headless(engine)
        return

    from visualization.warehouse_view import MultiWarehouseView
    from visualization.dashboard import Dashboard
    from visualization.ui import UIManager
    from config import VisualizationConfig

    pygame.init()

    viz_config = VisualizationConfig()
    screen_width = 1400
    screen_height = 900
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
    pygame.display.set_caption("Warehouse Digital Twin Simulation")
    clock = pygame.time.Clock()

    warehouse_view = MultiWarehouseView(viz_config, engine.warehouses)
    dashboard = Dashboard(viz_config, engine)
    ui_manager = UIManager(viz_config, engine, dashboard, warehouse_view)

    view_x = 20
    panel_y = 80
    header_height = 70

    engine.start()
    live_export_path = "data/simulation_logs/live_state.json"
    last_export_time = 0.0

    print("Visualization started. Press H for help, ESC to exit.")

    running = True
    while running and engine.running:
        screen_width, screen_height = screen.get_size()
        view_y = header_height
        active_warehouse = warehouse_view.active_warehouse
        warehouse_width = (
            engine.warehouses[active_warehouse].width * viz_config.cell_size
            if active_warehouse else viz_config.cell_size
        )
        panel_x = view_x + warehouse_width + 20
        panel_width = max(360, screen_width - panel_x - 20)
        dt = clock.tick(viz_config.fps) / 1000.0
        engine.update(dt)
        if engine.current_time - last_export_time >= 1.0:
            engine.export_state(live_export_path)
            last_export_time = engine.current_time

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                else:
                    ui_manager.handle_event(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Toolbar buttons take priority over warehouse selection.
                    handled = ui_manager.handle_event(event)
                    if not handled:
                        clicked = warehouse_view.handle_click(event.pos, view_x, view_y)
                        if clicked:
                            dashboard.select_product(clicked)
                elif event.button == 3:
                    # Right-click: Adjust simulation speed (cycle through speeds)
                    speeds = [0.5, 1.0, 2.0]
                    current_idx = speeds.index(engine.speed) if engine.speed in speeds else 1
                    next_idx = (current_idx + 1) % len(speeds)
                    engine.set_speed(speeds[next_idx])
                elif event.button == 4:
                    # Scroll wheel up: Increase speed
                    engine.set_speed(min(10.0, engine.speed * 1.5))
                elif event.button == 5:
                    # Scroll wheel down: Decrease speed
                    engine.set_speed(max(0.1, engine.speed / 1.5))
            else:
                ui_manager.handle_event(event)

        colors = viz_config.colors or {"background": (30, 30, 40)}
        screen.fill(colors.get("background", (30, 30, 40)))

        warehouse_view.draw(screen, view_x, view_y, show_paths=True)

        dashboard.draw(screen, panel_x, panel_y, panel_width, screen_height - panel_y - 20)

        ui_manager.draw(screen)

        fps_text = pygame.font.SysFont("consolas", 12).render(
            f"FPS: {clock.get_fps():.0f}", True, (150, 150, 170)
        )
        screen.blit(fps_text, (screen_width - 100, 10))

        pygame.display.flip()

    pygame.quit()
    print("Visualization closed.")


def main():
    parser = argparse.ArgumentParser(description="Warehouse Digital Twin Simulation")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no GUI)")
    parser.add_argument("--demo", action="store_true", help="Run deterministic demo scenario")
    parser.add_argument("--duration", type=float, default=60.0, help="Headless run duration (seconds)")
    parser.add_argument("--speed", type=float, default=1.0, help="Simulation speed multiplier")
    parser.add_argument("--export", type=str, help="Export event log to JSON file")
    args = parser.parse_args()

    print("Initializing warehouse simulation...")
    warehouses = create_warehouses()
    engine = SimulationEngine(warehouses, headless=args.headless or args.demo)
    engine.set_speed(args.speed)

    try:
        if args.demo:
            run_demo(engine)
        elif args.headless:
            run_headless(engine, args.duration, args.speed)
        else:
            run_visual(engine)
    finally:
        if args.export:
            engine.export_logs(args.export)
            print(f"Event log exported to {args.export}")


if __name__ == "__main__":
    main()