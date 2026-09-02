#!/usr/bin/env python3
"""
Web-based Warehouse Visualization Server
Retro 1990s game theme - runs on server, viewable in browser
"""

import eventlet
eventlet.monkey_patch()

# Must import after monkey_patch
from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO, emit
import time
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import WAREHOUSE_CONFIGS, SIMULATION_CONFIG, VisualizationConfig
from models.warehouse import Warehouse
from simulation.engine import SimulationEngine


app = Flask(__name__)
app.config['SECRET_KEY'] = 'warehouse-digital-twin-retro'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')


class WebSimulationServer:
    def __init__(self):
        self.warehouses = {config.id: Warehouse.from_config(config) for config in WAREHOUSE_CONFIGS}
        self.engine = SimulationEngine(self.warehouses, headless=True)
        self.running = False
        self.speed = 1.0
        self.bg_task = None
        
    def start(self):
        if not self.running:
            self.running = True
            self.engine.start()
            self.engine.set_speed(self.speed)
            self.bg_task = socketio.start_background_task(self._simulation_loop)
            print("Simulation started")
    
    def stop(self):
        self.running = False
        self.engine.stop()
        print("Simulation stopped")
    
    def set_speed(self, speed):
        self.speed = max(0.1, min(50.0, speed))
        self.engine.set_speed(self.speed)
    
    def _simulation_loop(self):
        dt = 1.0 / 60.0
        last_emit = 0
        emit_interval = 0.1
        tick = 0
        
        print("Simulation loop started")
        while self.running:
            if not self.engine.paused:
                self.engine.update(dt)
                
            current_time = time.time()
            if current_time - last_emit >= emit_interval:
                state = self.get_state()
                print(f"Emitting state: time={state['simulation_time']}, robots_active={state['stats']['active_robots']}, products={state['stats']['total_products']}")
                socketio.emit('state_update', state)
                last_emit = current_time
                
            tick += 1
            if tick % 600 == 0:  # every 10 seconds
                print(f"  Heartbeat: running={self.running}, paused={self.engine.paused}")
            socketio.sleep(dt)
    
    def get_state(self):
        return {
            'simulation_time': round(self.engine.current_time, 1),
            'speed': self.engine.speed,
            'paused': self.engine.paused,
            'running': self.running,
            'warehouses': self._get_warehouses_data(),
            'stats': self.engine.get_stats(),
            'recent_events': self._get_recent_events(20),
        }
    
    def _get_warehouses_data(self):
        result = {}
        for wh_id, warehouse in self.warehouses.items():
            result[wh_id] = {
                'id': wh_id,
                'name': warehouse.name,
                'width': warehouse.width,
                'height': warehouse.height,
                'inbound_zone': warehouse.inbound_zone,
                'outbound_zone': warehouse.outbound_zone,
                'racks': [self._rack_to_dict(r) for r in warehouse.racks.values()],
                'robots': [self._robot_to_dict(r) for r in warehouse.robots.values()],
                'products': [self._product_to_dict(p) for p in warehouse.products.values()],
                'inbound_queue': len(warehouse.inbound_queue),
                'outbound_queue': len(warehouse.outbound_queue),
            }
        return result
    
    def _rack_to_dict(self, rack):
        return {
            'id': rack.id,
            'x': rack.x,
            'y': rack.y,
            'capacity': rack.capacity,
            'shelves': rack.shelves,
            'zone': rack.zone,
            'products': rack.get_products(),
            'product_count': rack.get_product_count(),
            'utilization': rack.utilization(),
        }
    
    def _robot_to_dict(self, robot):
        return {
            'id': robot.id,
            'x': robot.x,
            'y': robot.y,
            'status': robot.status.value,
            'carrying_product_id': robot.carrying_product_id,
            'battery': round(robot.battery, 1),
            'destination': robot.destination,
            'path': [{'x': s.x, 'y': s.y} for s in robot.path[robot.path_index:]] if robot.path else [],
            'peer_intent': robot.peer_intent,
            'peer_status': robot.peer_status,
            'peer_message': robot.peer_message,
        }
    
    def _product_to_dict(self, product):
        return {
            'id': product.id,
            'barcode': product.barcode,
            'sku': product.sku,
            'category': product.category.value,
            'status': product.status.value,
            'warehouse_id': product.warehouse_id,
            'location': product.location,
            'current_robot_id': product.current_robot_id,
            'shelf': product.shelf,
        }
    
    def _get_recent_events(self, count):
        events = self.engine.event_log.get_recent(count)
        return [{
            'timestamp': e.timestamp.strftime('%H:%M:%S.%f')[:-3],
            'type': e.event_type.value,
            'product_id': e.product_id,
            'robot_id': e.robot_id,
            'warehouse_id': e.warehouse_id,
            'old_state': e.old_state,
            'new_state': e.new_state,
        } for e in events]
    
    def trigger_action(self, action):
        if action == 'spawn_product':
            self.engine._spawn_product_arrival()
        elif action == 'spawn_order':
            self.engine._spawn_customer_order()
        elif action == 'spawn_transfer':
            self.engine._spawn_transfer()
        elif action == 'toggle_pause':
            if self.engine.paused:
                self.engine.resume()
            else:
                self.engine.pause()


sim_server = WebSimulationServer()


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WAREHOUSE DIGITAL TWIN - RETRO TERMINAL</title>
    <link href="https://fonts.googleapis.com/css2?family=VT323&family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: #0a0a0f; 
            color: #00ff41; 
            font-family: 'VT323', monospace; 
            font-size: 18px;
            line-height: 1.4;
            overflow: hidden;
            height: 100vh;
        }
        .scanlines { 
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: repeating-linear-gradient(0deg, rgba(0,0,0,0.15), rgba(0,0,0,0.15) 1px, transparent 1px, transparent 3px);
            pointer-events: none; z-index: 9999; opacity: 0.3;
        }
        .crt-glow { 
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            box-shadow: inset 0 0 100px rgba(0,255,65,0.05), inset 0 0 200px rgba(0,0,0,0.5);
            pointer-events: none; z-index: 9998;
        }
        .container { display: grid; grid-template-columns: 1fr 380px; height: 100vh; gap: 10px; padding: 10px; }
        .panel { 
            border: 2px solid #00ff41; 
            background: rgba(0, 20, 0, 0.9); 
            padding: 10px;
            box-shadow: 0 0 20px rgba(0,255,65,0.2), inset 0 0 20px rgba(0,255,65,0.05);
            display: flex; flex-direction: column;
        }
        .panel-header { 
            color: #00ff41; text-transform: uppercase; letter-spacing: 2px; 
            border-bottom: 1px solid #00ff41; padding-bottom: 5px; margin-bottom: 10px;
            text-shadow: 0 0 10px #00ff41;
        }
        #canvas-container { position: relative; overflow: hidden; }
        #warehouse-canvas { display: block; image-rendering: pixelated; image-rendering: crisp-edges; }
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 14px; }
        .stat-item { display: flex; justify-content: space-between; }
        .stat-label { color: #00aa22; }
        .stat-value { color: #00ff41; font-weight: bold; }
        .stat-value.warning { color: #ffaa00; }
        .stat-value.error { color: #ff3333; }
        .stat-value.sync-ok { color: #00ff41; }
        .stat-value.sync-warn { color: #ffaa00; }
        .stat-value.sync-error { color: #ff3333; }
        .warehouse-tabs { display: flex; gap: 5px; margin-bottom: 10px; }
        .tab { 
            padding: 5px 15px; background: #001100; border: 1px solid #003300; 
            cursor: pointer; transition: all 0.1s; text-transform: uppercase;
        }
        .tab.active { background: #00ff41; color: #000; border-color: #00ff41; box-shadow: 0 0 10px #00ff41; }
        .tab:hover:not(.active) { border-color: #00ff41; }
        .controls { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
        .btn { 
            padding: 8px 16px; background: #001100; border: 1px solid #003300; 
            color: #00ff41; font-family: inherit; font-size: 14px; cursor: pointer;
            text-transform: uppercase; transition: all 0.1s;
        }
        .btn:hover { background: #003300; border-color: #00ff41; box-shadow: 0 0 10px rgba(0,255,65,0.3); }
        .btn:active { background: #00ff41; color: #000; }
        .btn.primary { border-color: #00ff41; }
        .speed-control { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
        .speed-slider { flex: 1; accent-color: #00ff41; }
        .event-log { flex: 1; overflow-y: auto; font-family: 'Share Tech Mono', monospace; font-size: 12px; line-height: 1.6; }
        .event-line { padding: 2px 5px; border-left: 2px solid #003300; transition: all 0.1s; }
        .event-line:hover { background: rgba(0,255,65,0.1); border-left-color: #00ff41; }
        .event-time { color: #008811; }
        .event-type { color: #00ff41; font-weight: bold; }
        .event-type.error { color: #ff3333; }
        .event-type.warn { color: #ffaa00; }
        .event-type.sync { color: #00ff41; }
        .event-ids { color: #008811; font-family: 'VT323', monospace; }
        .legend { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; font-size: 12px; }
        .legend-item { display: flex; align-items: center; gap: 5px; }
        .legend-color { width: 12px; height: 12px; border: 1px solid #00ff41; }
        .status-bar { 
            display: flex; justify-content: space-between; padding: 5px 10px; 
            background: #001100; border-top: 1px solid #003300; font-size: 14px;
        }
        .blink { animation: blink 1s infinite; }
        @keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
        .hidden { display: none !important; }
        @media (max-width: 1200px) { .container { grid-template-columns: 1fr; grid-template-rows: auto 1fr; } }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <div class="crt-glow"></div>
    
    <div class="container">
        <!-- LEFT: WAREHOUSE VIEW -->
        <div class="panel">
            <div class="panel-header">WAREHOUSE VISUALIZATION [GRID MAP]</div>
            <div class="warehouse-tabs">
                <button class="tab active" data-wh="WH-A">WAREHOUSE ALPHA</button>
                <button class="tab" data-wh="WH-B">WAREHOUSE BETA</button>
            </div>
            <div id="canvas-container">
                <canvas id="warehouse-canvas"></canvas>
            </div>
            <div class="legend" id="legend"></div>
        </div>
        
        <!-- RIGHT: DASHBOARD -->
        <div class="panel" style="display: flex; flex-direction: column;">
            <div class="panel-header">SYSTEM STATUS</div>
            <div class="stats-grid" id="stats-grid"></div>
            
            <div class="panel-header" style="margin-top: 15px;">CONTROLS</div>
            <div class="controls">
                <button class="btn primary" id="btn-pause">PAUSE / RESUME</button>
                <button class="btn" id="btn-product">SPAWN PRODUCT</button>
                <button class="btn" id="btn-order">CREATE ORDER</button>
                <button class="btn" id="btn-transfer">INIT TRANSFER</button>
            </div>
            <div class="speed-control">
                <span>SPEED: <span id="speed-display">1.0</span>x</span>
                <input type="range" class="speed-slider" id="speed-slider" min="0.1" max="50" step="0.1" value="1">
            </div>
            
            <div class="panel-header" style="margin-top: 15px;">EVENT LOG</div>
            <div class="event-log" id="event-log"></div>
        </div>
    </div>
    
    <div class="status-bar">
        <span>CONNECTION: <span id="conn-status" class="blink">● ONLINE</span></span>
        <span>FRAME: <span id="frame-count">0</span></span>
        <span>v1.0.0-RETRO</span>
    </div>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script>
        const socket = io();
        let currentWarehouse = 'WH-A';
        let frameCount = 0;
        
        const canvas = document.getElementById('warehouse-canvas');
        const ctx = canvas.getContext('2d');
        const CELL_SIZE = 32;
        const MARGIN = 10;
        
        // Retro color palette
        const COLORS = {
            bg: '#0a0f0a',
            grid: '#002200',
            rackEmpty: '#1a3a1a',
            rackPartial: '#1a5a1a',
            rackFull: '#0a7a0a',
            inbound: '#001a44',
            outbound: '#441a00',
            robotIdle: '#00cc44',
            robotMoving: '#ffaa00',
            robotCarrying: '#ff8800',
            robotCharging: '#aa44ff',
            product: '#ffff00',
            path: '#004411',
            text: '#00ff41',
            textDim: '#006611',
        };
        
        socket.on('connect', () => {
            document.getElementById('conn-status').textContent = '● ONLINE';
            document.getElementById('conn-status').classList.add('blink');
        });
        socket.on('disconnect', () => {
            document.getElementById('conn-status').textContent = '● OFFLINE';
            document.getElementById('conn-status').classList.remove('blink');
        });
        socket.on('state_update', (data) => {
            updateUI(data);
        });
        
        function updateUI(data) {
            updateStats(data.stats);
            updateEventLog(data.recent_events);
            renderWarehouse(data.warehouses[currentWarehouse]);
            document.getElementById('speed-display').textContent = data.speed.toFixed(1);
        }
        
        function updateStats(stats) {
            const grid = document.getElementById('stats-grid');
            const syncClass = stats.digital_twin_sync_rate >= 0.95 ? 'sync-ok' : 
                             stats.digital_twin_sync_rate >= 0.7 ? 'sync-warn' : 'sync-error';
            grid.innerHTML = `
                <div class="stat-item"><span class="stat-label">SIM TIME</span><span class="stat-value">${stats.simulation_time}s</span></div>
                <div class="stat-item"><span class="stat-label">SPEED</span><span class="stat-value">${stats.speed}x</span></div>
                <div class="stat-item"><span class="stat-label">STATUS</span><span class="stat-value ${stats.paused ? 'warning' : ''}">${stats.paused ? 'PAUSED' : 'RUNNING'}</span></div>
                <div class="stat-item"><span class="stat-label">PRODUCTS</span><span class="stat-value">${stats.total_products}</span></div>
                <div class="stat-item"><span class="stat-label">STORED</span><span class="stat-value">${stats.stored_products}</span></div>
                <div class="stat-item"><span class="stat-label">ROBOTS</span><span class="stat-value">${stats.active_robots}/${stats.total_robots}</span></div>
                <div class="stat-item"><span class="stat-label">UTILIZATION</span><span class="stat-value">${(stats.robot_utilization*100).toFixed(0)}%</span></div>
                <div class="stat-item"><span class="stat-label">TWIN SYNC</span><span class="stat-value ${syncClass}">${(stats.digital_twin_sync_rate*100).toFixed(1)}%</span></div>
            `;
        }
        
        function updateEventLog(events) {
            const log = document.getElementById('event-log');
            log.innerHTML = events.map(e => {
                let typeClass = '';
                if (e.type.includes('ERROR') || e.type.includes('FAILED') || e.type.includes('DESYNC')) typeClass = 'error';
                else if (e.type.includes('WARN')) typeClass = 'warn';
                else if (e.type.includes('SYNC')) typeClass = 'sync';
                return `<div class="event-line">
                    <span class="event-time">[${e.timestamp}]</span>
                    <span class="event-type ${typeClass}">${e.type.padEnd(24)}</span>
                    <span class="event-ids">P:${(e.product_id||'----').slice(-6)} R:${(e.robot_id||'----').slice(-4)} W:${e.warehouse_id||'--'}</span>
                </div>`;
            }).join('');
            log.scrollTop = log.scrollHeight;
        }
        
        function renderWarehouse(wh) {
            if (!wh) return;
            const width = wh.width * CELL_SIZE + MARGIN * 2;
            const height = wh.height * CELL_SIZE + MARGIN * 2;
            canvas.width = width;
            canvas.height = height;
            canvas.style.width = width + 'px';
            canvas.style.height = height + 'px';
            
            // Clear
            ctx.fillStyle = COLORS.bg;
            ctx.fillRect(0, 0, width, height);
            
            // Grid
            ctx.strokeStyle = COLORS.grid;
            ctx.lineWidth = 1;
            for (let x = 0; x <= wh.width; x++) {
                const px = MARGIN + x * CELL_SIZE;
                ctx.beginPath(); ctx.moveTo(px, MARGIN); ctx.lineTo(px, MARGIN + wh.height * CELL_SIZE); ctx.stroke();
            }
            for (let y = 0; y <= wh.height; y++) {
                const py = MARGIN + y * CELL_SIZE;
                ctx.beginPath(); ctx.moveTo(MARGIN, py); ctx.lineTo(MARGIN + wh.width * CELL_SIZE, py); ctx.stroke();
            }
            
            // Zones
            drawZone(wh.inbound_zone, COLORS.inbound, 'INBOUND');
            drawZone(wh.outbound_zone, COLORS.outbound, 'OUTBOUND');
            
            // Racks
            wh.racks.forEach(rack => {
                const rx = MARGIN + rack.x * CELL_SIZE;
                const ry = MARGIN + rack.y * CELL_SIZE;
                let color = rack.utilization === 0 ? COLORS.rackEmpty :
                           rack.utilization < 0.7 ? COLORS.rackPartial : COLORS.rackFull;
                ctx.fillStyle = color;
                ctx.fillRect(rx, ry, CELL_SIZE, CELL_SIZE);
                ctx.strokeStyle = '#00ff41';
                ctx.lineWidth = 1;
                ctx.strokeRect(rx, ry, CELL_SIZE, CELL_SIZE);
                
                // Rack label
                ctx.fillStyle = COLORS.text;
                ctx.font = '10px VT323';
                ctx.fillText(rack.id, rx + 2, ry + 12);
                ctx.fillText(`${rack.product_count}/${rack.capacity}`, rx + 2, ry + CELL_SIZE - 4);
            });

            // Peer-to-peer communication links between nearby active robots.
            const activeRobots = wh.robots.filter(robot => robot.status !== 'IDLE');
            ctx.save();
            ctx.setLineDash([5, 4]);
            ctx.lineWidth = 1;
            activeRobots.forEach((robot, index) => {
                activeRobots.slice(index + 1).forEach(peer => {
                    const distance = Math.hypot(robot.x - peer.x, robot.y - peer.y);
                    if (distance > 7) return;
                    const x1 = MARGIN + robot.x * CELL_SIZE + CELL_SIZE / 2;
                    const y1 = MARGIN + robot.y * CELL_SIZE + CELL_SIZE / 2;
                    const x2 = MARGIN + peer.x * CELL_SIZE + CELL_SIZE / 2;
                    const y2 = MARGIN + peer.y * CELL_SIZE + CELL_SIZE / 2;
                    ctx.strokeStyle = '#2080ff';
                    ctx.beginPath();
                    ctx.moveTo(x1, y1);
                    ctx.lineTo(x2, y2);
                    ctx.stroke();
                });
            });
            ctx.restore();
            
            // Robots
            wh.robots.forEach(robot => {
                const rx = MARGIN + robot.x * CELL_SIZE + CELL_SIZE/2;
                const ry = MARGIN + robot.y * CELL_SIZE + CELL_SIZE/2;
                const r = CELL_SIZE/2 - 2;
                
                let color = robot.status === 'IDLE' ? COLORS.robotIdle :
                           robot.status === 'MOVING' ? COLORS.robotMoving :
                           (robot.status === 'LOADING' || robot.status === 'UNLOADING' || robot.status === 'WAITING') ? COLORS.robotCarrying :
                           robot.status === 'CHARGING' ? COLORS.robotCharging : COLORS.robotIdle;
                
                // Path
                if (robot.path && robot.path.length > robot.path_index) {
                    ctx.strokeStyle = COLORS.path;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(rx, ry);
                    robot.path.slice(robot.path_index).forEach(p => {
                        const px = MARGIN + p.x * CELL_SIZE + CELL_SIZE/2;
                        const py = MARGIN + p.y * CELL_SIZE + CELL_SIZE/2;
                        ctx.lineTo(px, py);
                    });
                    ctx.stroke();
                }
                
                // Robot body
                ctx.fillStyle = color;
                ctx.beginPath(); ctx.arc(rx, ry, r, 0, Math.PI*2); ctx.fill();
                ctx.strokeStyle = '#00ff41';
                ctx.lineWidth = 2;
                ctx.stroke();
                
                // Carrying indicator
                if (robot.carrying_product_id) {
                    ctx.fillStyle = COLORS.product;
                    ctx.beginPath(); ctx.arc(rx, ry, r/2, 0, Math.PI*2); ctx.fill();
                }
                
                // Battery bar
                const bw = 20, bh = 3;
                ctx.fillStyle = '#001100';
                ctx.fillRect(rx - bw/2, ry + r + 4, bw, bh);
                ctx.fillStyle = robot.battery > 50 ? '#00ff41' : robot.battery > 20 ? '#ffaa00' : '#ff3333';
                ctx.fillRect(rx - bw/2, ry + r + 4, bw * robot.battery/100, bh);
                
                // Label
                ctx.fillStyle = COLORS.text;
                ctx.font = '9px VT323';
                ctx.fillText(robot.id.slice(-5), rx - 12, ry - r - 4);
                if (robot.peer_status === 'WAITING') {
                    ctx.fillStyle = '#2080ff';
                    ctx.fillText('YIELD', rx - 12, ry + r + 16);
                }
            });
            
            updateLegend(wh);
        }
        
        function drawZone(zone, color, label) {
            const [x1, y1, x2, y2] = zone;
            const rx = MARGIN + x1 * CELL_SIZE;
            const ry = MARGIN + y1 * CELL_SIZE;
            const rw = (x2 - x1) * CELL_SIZE;
            const rh = (y2 - y1) * CELL_SIZE;
            ctx.fillStyle = color;
            ctx.fillRect(rx, ry, rw, rh);
            ctx.fillStyle = COLORS.text;
            ctx.font = '12px VT323';
            ctx.fillText(label, rx + 5, ry + 16);
        }
        
        function updateLegend(wh) {
            const legend = document.getElementById('legend');
            const robot = wh.robots.find(r => r.status !== 'IDLE');
            const activeRobots = wh.robots.filter(r => r.status !== 'IDLE').length;
            legend.innerHTML = `
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.rackEmpty}"></div>RACK EMPTY</div>
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.rackPartial}"></div>RACK PARTIAL</div>
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.rackFull}"></div>RACK FULL</div>
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.inbound}"></div>INBOUND</div>
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.outbound}"></div>OUTBOUND</div>
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.robotIdle}"></div>ROBOT IDLE</div>
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.robotMoving}"></div>ROBOT MOVING</div>
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.robotCarrying}"></div>ROBOT CARRYING</div>
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.robotCharging}"></div>ROBOT CHARGING</div>
                <div class="legend-item"><div class="legend-color" style="background:${COLORS.product}"></div>PRODUCT</div>
            `;
        }
        
        // Controls
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                currentWarehouse = tab.dataset.wh;
            });
        });
        
        document.getElementById('btn-pause').addEventListener('click', () => sendAction('toggle_pause'));
        document.getElementById('btn-product').addEventListener('click', () => sendAction('spawn_product'));
        document.getElementById('btn-order').addEventListener('click', () => sendAction('spawn_order'));
        document.getElementById('btn-transfer').addEventListener('click', () => sendAction('spawn_transfer'));
        
        document.getElementById('speed-slider').addEventListener('input', (e) => {
            fetch('/api/speed', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({speed: parseFloat(e.target.value)})});
        });
        
        function sendAction(action) {
            fetch('/api/action', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action})});
        }
        
        // Initial render
        fetch('/api/state').then(r => r.json()).then(data => updateUI(data));
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/state')
def api_state():
    return jsonify(sim_server.get_state())


@app.route('/api/action', methods=['POST'])
def api_action():
    data = request.get_json()
    sim_server.trigger_action(data.get('action'))
    return jsonify({'ok': True})


@app.route('/api/speed', methods=['POST'])
def api_speed():
    data = request.get_json()
    sim_server.set_speed(data.get('speed', 1.0))
    return jsonify({'ok': True, 'speed': sim_server.speed})


@socketio.on('connect')
def on_connect(auth=None):
    print('Client connected')
    emit('state_update', sim_server.get_state())


@socketio.on('disconnect')
def on_disconnect():
    print('Client disconnected')


if __name__ == '__main__':
    print("=" * 60)
    print("WAREHOUSE DIGITAL TWIN - RETRO WEB VISUALIZATION")
    print("=" * 60)
    print("Starting web server on http://localhost:5000")
    print("Open browser to view simulation")
    print("=" * 60)
    sim_server.start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)