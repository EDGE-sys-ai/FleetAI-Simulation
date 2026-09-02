from config import WAREHOUSE_CONFIGS
from models.warehouse import Warehouse
from simulation.engine import SimulationEngine
import time

warehouses = {config.id: Warehouse.from_config(config) for config in WAREHOUSE_CONFIGS}
engine = SimulationEngine(warehouses, headless=True)
engine.start()
engine.set_speed(10.0)

print('Starting simulation...')
for i in range(10):
    engine.update(1.0/60.0 * 10.0)
    stats = engine.get_stats()
    print(f'  Tick {i}: time={stats["simulation_time"]:.1f}, products={stats["total_products"]}, stored={stats["stored_products"]}, robots_active={stats["active_robots"]}, events={stats["events_logged"]}')
    time.sleep(0.1)

print('Done')