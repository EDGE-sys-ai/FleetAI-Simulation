# Warehouse Digital Twin Simulation

A complete Python simulation of an intelligent warehouse management system with digital twin synchronization, inter-warehouse shipping, and real-time visualization.

## Overview

This simulation models the complete lifecycle of products moving through automated warehouses:
- **Inbound**: Receiving, barcode scanning, robot assignment, rack allocation, storage
- **Storage**: Inventory management, rack optimization, product tracking
- **Outbound**: Order picking, shipment creation, outbound processing
- **Inter-warehouse**: Transfers between warehouses with tracking
- **Digital Twin**: Real-time synchronization with validation and desync detection

## Architecture

```
Physical Warehouse A  <--events-->  Central Server  <--events-->  Physical Warehouse B
       |                                    |                         |
       v                                    v                         v
Digital Twin A                            Global Tracking        Digital Twin B
```

### Core Components

- **Models**: Product, Robot, Rack, Warehouse, Order, Shipment
- **Simulation Engine**: Event-driven, time-based simulation with scheduler
- **Warehouse Operations**: Inventory, routing (A* pathfinding), allocation
- **Peer-to-Peer Fleet Coordination**: Robots exchange movement intent, reserve next grid cells, yield on conflicts, and prevent head-on swaps
- **Tracking**: Barcode scanning, shipment tracking, event logging
- **Digital Twin**: State synchronization, validation, desync detection
- **Visualization**: Pygame dashboard and browser-based retro web dashboard

## Installation

Requirements: Python 3.8 or newer and PowerShell on Windows.

From PowerShell, move into the project directory and install the dependencies:

```powershell
cd "D:\DEMO ITEMS\warehouse_sim"
python -m pip install -r requirements.txt
```

## Quick Start

Install the dependencies first:

```powershell
cd "D:\DEMO ITEMS\warehouse_sim"
python -m pip install -r requirements.txt
```

Choose one of the two visual interfaces:

Start the browser dashboard:

```powershell
cd "D:\DEMO ITEMS\warehouse_sim"; python visualization\web_server.py
```

Then open [http://localhost:5000](http://localhost:5000). The server starts the simulation automatically. Keep that terminal open while using the dashboard. Press `Ctrl+C` in the same terminal to stop it.

Or start the desktop Pygame dashboard:

```powershell
python main.py
```

If port `5000` is already in use, stop the previous server before starting another copy. Only one web server should run on port `5000`.

## Running the Simulation

Run commands from the `warehouse_sim` directory.

### Web Visualization (Recommended)
```powershell
python visualization\web_server.py
```

Open [http://localhost:5000](http://localhost:5000) in a browser. The web simulation starts automatically at `1x` speed and runs continuously until you press `Ctrl+C` in the server terminal.

The web dashboard shows:
- Live robot positions and paths for Warehouse Alpha and Warehouse Beta
- Blue peer-to-peer communication links between nearby active robots
- Robot intent status and `YIELD` indicators during route conflicts
- Simulation statistics, event logs, pause/resume, speed, product, order, and transfer controls

The web server has no duration limit. The default product limit is 100 products. When the limit is reached, completed or orphaned products are recycled safely so new inbound work can continue without unbounded memory growth. Robots may pause briefly for peer coordination, but the simulation continues assigning work while the server is running.

### Pygame Visual Mode
```bash
python main.py
```

The Pygame view is an interactive simulation. It starts with products and robots already present. Robots process real warehouse tasks continuously; when no receiving, picking, or dispatch task is waiting, free robots patrol the aisles autonomously.

### How to Play the Pygame Simulation

Follow this sequence to see the complete warehouse workflow:

1. Start `python main.py`.
2. If the dashboard says `PAUSED`, press `SPACE` to resume.
3. Press `R` several times to create incoming products at the receiving dock.
4. Watch a robot approach the inbound zone, scan the barcode, choose a rack, and transport the product to storage.
5. Press `O` to create a customer or dealer order for stored products.
6. Watch robots retrieve products from racks and carry them to the outbound dispatch zone.
7. Press `T` to create an inter-warehouse transfer between Warehouse Alpha and Warehouse Beta.
8. Press `D` to inspect digital-twin synchronization and `E` to inspect the event stream.
9. Press `H` at any time to show the in-app help panel.

The simulation is not a manual robot-driving game. You create warehouse events, and the robot fleet makes the decisions: task assignment, barcode scanning, rack selection, A* route planning, peer coordination, collision yielding, inventory updates, and dispatch handover.

### What to Watch

- Green robot ring: moving or clear to move.
- Yellow robot ring: scanning, loading, unloading, or busy.
- Red robot ring: waiting, blocked, or reporting a coordination issue.
- Glowing route: the robot's current planned path.
- Pulsing rack marker: the rack contains products.
- Right dashboard: inventory, active robots, digital-twin health, and recent events.
- Idle robots: autonomous aisle patrols continue until a real warehouse task becomes available.

### Mouse Controls

- Left-click a robot or rack to select it and show telemetry.
- Right-click to cycle through simulation speeds.
- Scroll up to increase speed and scroll down to decrease speed.

### Headless Mode
```bash
python main.py --headless --duration 120 --speed 5.0
```

### Demo Mode (Deterministic Scenario)
```bash
python main.py --demo
```

### Export Event Log
```bash
python main.py --headless --duration 60 --export simulation_logs/events.json
```

## Controls (Visual Mode)

| Key | Action |
|-----|--------|
| SPACE | Pause/Resume |
| R | Generate new product |
| O | Create customer order |
| T | Create inter-warehouse transfer |
| D | Toggle digital twin panel |
| E | Toggle event log |
| S | Toggle statistics |
| 1/2 | Switch warehouse view (WH-A/WH-B) |
| ↑/↓ | Scroll event log |
| H | Show help |
| ESC | Exit |

Mouse controls:

| Mouse action | Result |
|-------------|--------|
| Left-click robot or rack | Select and show telemetry |
| Right-click | Cycle speed |
| Scroll up/down | Increase/decrease speed |

## Project Structure

```
warehouse_sim/
├── main.py                 # Entry point
├── config.py               # Configuration
├── requirements.txt
├── README.md
├── models/                 # Data models
│   ├── product.py
│   ├── robot.py
│   ├── rack.py
│   ├── warehouse.py
│   ├── order.py
│   └── shipment.py
├── simulation/             # Simulation engine
│   ├── engine.py
│   ├── events.py
│   ├── scheduler.py
│   └── generator.py
├── warehouse/              # Warehouse operations
│   ├── routing.py          # A* pathfinding
│   ├── allocation.py       # Rack allocation
│   ├── inventory.py        # Inventory management
│   └── operations.py       # Business logic
├── tracking/               # Tracking system
│   ├── barcode.py
│   └── tracking.py
├── digital_twin/           # Digital twin
│   ├── twin.py
│   ├── synchronization.py
│   └── state.py
├── visualization/          # Pygame and browser UIs
│   ├── warehouse_view.py
│   ├── dashboard.py
│   ├── ui.py
│   └── web_server.py       # Endless Socket.IO web simulation
├── data/
│   └── simulation_logs/    # Exported logs
└── tests/                  # Unit tests
```

## Event Flow

Every physical action generates an event that flows through the system:

1. **Physical Event** (robot moves, product scanned, etc.)
2. **Event Log** (centralized event store)
3. **Server Processing** (validation, state updates)
4. **Digital Twin Update** (virtual representation updated)
5. **Sync Validation** (periodic comparison)

The full autonomous workflow is:

```text
Shipment arrival
-> Barcode scan and product identification
-> AI storage decision
-> P2P robot coordination
-> Dynamic A* route planning
-> Autonomous transport
-> Rack placement verification
-> Inventory and digital-twin synchronization
-> Customer/dealer order
-> Autonomous retrieval
-> Outbound dispatch handover
-> Real-time inventory update
```

### Event Types

- `PRODUCT_ARRIVED`, `PRODUCT_SCANNED`, `PRODUCT_DELIVERED`
- `ROBOT_DISPATCHED`, `ROBOT_MOVING`, `ROBOT_ARRIVED`
- `ORDER_CREATED`, `ORDER_PICKED`, `ORDER_COMPLETED`
- `SHIPMENT_CREATED`, `SHIPMENT_IN_TRANSIT`, `SHIPMENT_RECEIVED`
- `DIGITAL_TWIN_SYNC`, `DIGITAL_TWIN_DESYNC`

## Digital Twin Validation

The system periodically compares physical vs digital state:

```
⚠ DIGITAL TWIN DESYNC
Product: P-00042
Physical: RACK-17
Digital: RACK-12
```

Detected issues are logged and can be corrected through the event pipeline.

## Configuration

Modify `config.py` to adjust:
- Warehouse dimensions and layout
- Robot counts and speeds
- Product categories and rack preferences
- Simulation timing parameters
- Visualization colors and layout

## Adding Warehouses

1. Add a new `WarehouseConfig` to `WAREHOUSE_CONFIGS` in `config.py`
2. The system automatically creates digital twins and integrates with tracking

## Testing

```bash
pytest tests/ -v
```

## Headless Output Example

```
[5.0s] Products: 47 | Stored: 32 | Robots Active: 8/14 | Sync: 100.0% | Events: 156
[10.0s] Products: 52 | Stored: 41 | Robots Active: 10/14 | Sync: 99.5% | Events: 312
[15.0s] Products: 58 | Stored: 48 | Robots Active: 12/14 | Sync: 100.0% | Events: 489

--- STATISTICS ---
Products processed: 58
Products stored: 48
Products shipped: 12
Average processing time: 14.2s
Digital twin synchronization: 99.8%
```

## Demo Scenario

The `--demo` flag runs a deterministic sequence:
1. Product arrives at Warehouse A
2. Robot scans and stores it
3. Digital Twin A synchronizes
4. Customer order created
5. Robot picks product
6. Shipment created and dispatched
7. Inter-warehouse transfer to Warehouse B
8. Warehouse B receives and stores
9. Digital Twin B synchronizes
10. Global tracking shows complete journey

## Requirements

- Python 3.8+
- pygame (for visualization)
- pytest (for testing)

## License

MIT License - Educational/Research Use