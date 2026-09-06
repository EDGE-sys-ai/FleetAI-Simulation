"""
P2P Network Layer for Robot Communication
Each robot runs a P2PNode to exchange location, battery, and intent with nearby peers.
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set

if TYPE_CHECKING:
    from models.robot import Robot
    from models.rack import Rack


@dataclass
class PeerInfo:
    """Information about a peer robot."""
    robot_id: str
    x: float
    y: float
    battery: float
    target_rack_id: Optional[str] = None
    target_shelf: Optional[int] = None
    status: str = "IDLE"
    last_seen: float = field(default_factory=time.time)


@dataclass
class Message:
    """P2P message structure."""
    msg_id: str
    sender_id: str
    msg_type: str
    payload: Dict
    timestamp: float = field(default_factory=time.time)
    ttl: int = 3


class P2PNode:
    """
    Peer-to-peer communication node attached to a Robot.
    Handles broadcast and direct messaging within communication radius.
    """

    def __init__(
        self,
        robot: "Robot",
        comm_radius: float = 5.0,
        max_peers: int = 10,
    ) -> None:
        self.robot = robot
        self.comm_radius = comm_radius
        self.max_peers = max_peers
        self.peers: Dict[str, PeerInfo] = {}
        self.message_log: List[Message] = []
        self.max_log_size = 100
        self._subscribers: Dict[str, List[Callable[[object], None]]] = {}

    def update_peer_info(self) -> None:
        """Update this node's advertised peer info from robot state."""
        self.peers[self.robot.id] = PeerInfo(
            robot_id=self.robot.id,
            x=self.robot.x,
            y=self.robot.y,
            battery=self.robot.battery,
            target_rack_id=self.robot.target_rack_id,
            target_shelf=getattr(self.robot, "target_shelf", None),
            status=self.robot.status.value,
        )

    def receive_peer_info(self, info: PeerInfo) -> None:
        """Process received peer info from another robot."""
        if info.robot_id == self.robot.id:
            return
        self.peers[info.robot_id] = info
        self._notify_subscribers("peer_update", info)

    def get_nearby_peers(self, max_count: Optional[int] = None) -> List[PeerInfo]:
        """Return peers within communication radius, sorted by distance."""
        nearby = []
        for peer in self.peers.values():
            if peer.robot_id == self.robot.id:
                continue
            dx = peer.x - self.robot.x
            dy = peer.y - self.robot.y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= self.comm_radius:
                nearby.append((dist, peer))
        nearby.sort(key=lambda x: x[0])
        limit = max_count or self.max_peers
        return [p for _, p in nearby[:limit]]

    def broadcast(self, msg_type: str, payload: Dict) -> None:
        """Broadcast a message to all nearby peers."""
        msg = Message(
            msg_id=uuid.uuid4().hex[:8],
            sender_id=self.robot.id,
            msg_type=msg_type,
            payload=payload,
        )
        self.message_log.append(msg)
        if len(self.message_log) > self.max_log_size:
            self.message_log = self.message_log[-self.max_log_size:]
        self._notify_subscribers("broadcast", msg)

    def send_direct(self, target_id: str, msg_type: str, payload: Dict) -> bool:
        """Send a direct message to a specific peer if in range."""
        peer = self.peers.get(target_id)
        if not peer:
            return False
        dx = peer.x - self.robot.x
        dy = peer.y - self.robot.y
        if (dx * dx + dy * dy) ** 0.5 > self.comm_radius:
            return False
        msg = Message(
            msg_id=uuid.uuid4().hex[:8],
            sender_id=self.robot.id,
            msg_type=msg_type,
            payload=payload,
        )
        self.message_log.append(msg)
        if len(self.message_log) > self.max_log_size:
            self.message_log = self.message_log[-self.max_log_size:]
        self._notify_subscribers("direct", msg)
        return True

    def subscribe(self, event: str, callback: Callable[[object], None]) -> None:
        """Subscribe to node events: 'peer_update', 'broadcast', 'direct'."""
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(callback)

    def _notify_subscribers(self, event: str, data: object) -> None:
        for cb in self._subscribers.get(event, []):
            try:
                cb(data)
            except Exception:
                pass

    def cleanup_stale_peers(self, max_age: float = 10.0) -> None:
        """Remove peers not seen recently."""
        now = time.time()
        stale = [pid for pid, p in self.peers.items() if now - p.last_seen > max_age]
        for pid in stale:
            del self.peers[pid]

    def get_state_summary(self) -> Dict:
        """Return serializable state for debugging."""
        return {
            "robot_id": self.robot.id,
            "peer_count": len(self.peers),
            "nearby_count": len(self.get_nearby_peers()),
            "messages_sent": len(self.message_log),
        }