"""
Unit tests for P2P Network and Consensus modules.
"""

import pytest
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, MagicMock

from warehouse_sim.models.robot import Robot
from warehouse_sim.models.rack import Rack
from warehouse_sim.network.p2p_node import P2PNode, PeerInfo, Message
from warehouse_sim.network.consensus import negotiate_storage_slot, SlotProposal


class TestPeerInfo:
    def test_peer_info_creation(self) -> None:
        info = PeerInfo(
            robot_id="ROBOT-A-01",
            x=5,
            y=10,
            battery=85.0,
            target_rack_id="RACK-01",
            target_shelf=2,
            status="MOVING",
        )
        assert info.robot_id == "ROBOT-A-01"
        assert info.x == 5
        assert info.y == 10
        assert info.battery == 85.0
        assert info.target_rack_id == "RACK-01"
        assert info.target_shelf == 2
        assert info.status == "MOVING"

    def test_peer_info_defaults(self) -> None:
        info = PeerInfo(robot_id="ROBOT-B-02", x=0, y=0, battery=50.0)
        assert info.target_rack_id is None
        assert info.target_shelf is None
        assert info.status == "IDLE"
        assert info.last_seen > 0


class TestMessage:
    def test_message_creation(self) -> None:
        msg = Message(
            msg_id="abc123",
            sender_id="ROBOT-A-01",
            msg_type="intent",
            payload={"target": "RACK-01"},
        )
        assert msg.msg_id == "abc123"
        assert msg.sender_id == "ROBOT-A-01"
        assert msg.msg_type == "intent"
        assert msg.payload == {"target": "RACK-01"}
        assert msg.ttl == 3


class TestP2PNode:
    def setup_method(self) -> None:
        self.mock_robot = Mock()
        self.mock_robot.id = "ROBOT-A-01"
        self.mock_robot.x = 5
        self.mock_robot.y = 5
        self.mock_robot.battery = 90.0
        self.mock_robot.target_rack_id = "RACK-01"
        self.mock_robot.target_shelf = 1
        self.mock_robot.status.value = "MOVING"

    def test_node_initialization(self) -> None:
        node = P2PNode(self.mock_robot, comm_radius=5.0)
        assert node.robot == self.mock_robot
        assert node.comm_radius == 5.0
        assert node.max_peers == 10
        assert len(node.peers) == 0

    def test_update_peer_info(self) -> None:
        node = P2PNode(self.mock_robot)
        node.update_peer_info()
        assert self.mock_robot.id in node.peers
        peer = node.peers[self.mock_robot.id]
        assert peer.x == 5
        assert peer.y == 5
        assert peer.battery == 90.0

    def test_receive_peer_info(self) -> None:
        node = P2PNode(self.mock_robot)
        peer_info = PeerInfo(
            robot_id="ROBOT-B-02",
            x=7,
            y=6,
            battery=80.0,
            target_rack_id="RACK-02",
            target_shelf=0,
            status="IDLE",
        )
        node.receive_peer_info(peer_info)
        assert "ROBOT-B-02" in node.peers
        assert node.peers["ROBOT-B-02"].x == 7

    def test_get_nearby_peers_within_radius(self) -> None:
        node = P2PNode(self.mock_robot, comm_radius=5.0)
        # Peer at distance ~2.8 (within radius)
        peer_close = PeerInfo("ROBOT-B-02", 7, 6, 80.0)
        # Peer at distance ~10 (outside radius)
        peer_far = PeerInfo("ROBOT-C-03", 15, 15, 70.0)

        node.receive_peer_info(peer_close)
        node.receive_peer_info(peer_far)

        nearby = node.get_nearby_peers()
        assert len(nearby) == 1
        assert nearby[0].robot_id == "ROBOT-B-02"

    def test_get_nearby_peers_sorted_by_distance(self) -> None:
        node = P2PNode(self.mock_robot, comm_radius=10.0)
        peer1 = PeerInfo("ROBOT-B-02", 10, 5, 80.0)  # dist 5
        peer2 = PeerInfo("ROBOT-C-03", 7, 6, 70.0)   # dist ~2.2
        peer3 = PeerInfo("ROBOT-D-04", 5, 10, 60.0)  # dist 5

        node.receive_peer_info(peer1)
        node.receive_peer_info(peer2)
        node.receive_peer_info(peer3)

        nearby = node.get_nearby_peers()
        assert nearby[0].robot_id == "ROBOT-C-03"
        assert nearby[1].robot_id in ("ROBOT-B-02", "ROBOT-D-04")

    def test_broadcast_message(self) -> None:
        node = P2PNode(self.mock_robot)
        node.broadcast("intent", {"rack": "RACK-01", "shelf": 1})
        assert len(node.message_log) == 1
        msg = node.message_log[0]
        assert msg.msg_type == "intent"
        assert msg.sender_id == "ROBOT-A-01"
        assert msg.payload == {"rack": "RACK-01", "shelf": 1}

    def test_send_direct_success(self) -> None:
        node = P2PNode(self.mock_robot, comm_radius=5.0)
        peer = PeerInfo("ROBOT-B-02", 6, 5, 80.0)  # dist 1
        node.receive_peer_info(peer)

        result = node.send_direct("ROBOT-B-02", "reserve", {"slot": 1})
        assert result is True
        assert len(node.message_log) == 1

    def test_send_direct_fail_out_of_range(self) -> None:
        node = P2PNode(self.mock_robot, comm_radius=2.0)
        peer = PeerInfo("ROBOT-B-02", 10, 10, 80.0)  # dist ~7
        node.receive_peer_info(peer)

        result = node.send_direct("ROBOT-B-02", "reserve", {"slot": 1})
        assert result is False

    def test_send_direct_fail_unknown_peer(self) -> None:
        node = P2PNode(self.mock_robot)
        result = node.send_direct("UNKNOWN", "reserve", {"slot": 1})
        assert result is False

    def test_subscribe_and_notify(self) -> None:
        node = P2PNode(self.mock_robot)
        received = []

        def callback(data: object) -> None:
            received.append(data)

        node.subscribe("peer_update", callback)
        peer_info = PeerInfo("ROBOT-B-02", 7, 6, 80.0)
        node.receive_peer_info(peer_info)

        assert len(received) == 1
        assert received[0].robot_id == "ROBOT-B-02"

    def test_cleanup_stale_peers(self) -> None:
        import time
        node = P2PNode(self.mock_robot)
        peer = PeerInfo("ROBOT-B-02", 7, 6, 80.0)
        peer.last_seen = time.time() - 20  # 20 seconds ago
        node.receive_peer_info(peer)

        node.cleanup_stale_peers(max_age=10.0)
        assert "ROBOT-B-02" not in node.peers

    def test_get_state_summary(self) -> None:
        node = P2PNode(self.mock_robot)
        summary = node.get_state_summary()
        assert summary["robot_id"] == "ROBOT-A-01"
        assert summary["peer_count"] == 0


class MockRack(Rack):
    def __init__(self, rack_id: str, x: int, y: int, capacity: int = 20, shelves: int = 4):
        super().__init__(id=rack_id, x=x, y=y, capacity=capacity, shelves=shelves, zone="test")
        self._products: Dict[int, List[str]] = {i: [] for i in range(shelves)}

    def get_shelf(self, shelf_num: int) -> Any:
        shelf = super().get_shelf(shelf_num)
        if shelf is None:
            class Shelf:
                def __init__(self, products):
                    self.products = products
                def is_full(self):
                    return len(self.products) >= 5
            return Shelf(self._products.get(shelf_num, []))
        return shelf

    def utilization(self) -> float:
        total = sum(len(p) for p in self._products.values())
        return total / (self.capacity * self.shelves) if self.capacity > 0 else 0.0


class MockRobot(Robot):
    def __init__(self, robot_id: str, x: int, y: int, battery: float = 90.0):
        super().__init__(id=robot_id, x=x, y=y, warehouse_id="TEST", battery=battery)
        self.target_rack_id: Optional[str] = None
        self.target_shelf: Optional[int] = None
        self.status = Mock(value="MOVING")


class TestConsensus:
    def setup_method(self) -> None:
        self.racks = {
            "RACK-01": MockRack("RACK-01", 2, 3),
            "RACK-02": MockRack("RACK-02", 5, 3),
            "RACK-03": MockRack("RACK-03", 8, 3),
        }
        self.requesting_robot = MockRobot("ROBOT-A-01", 3, 3, 90.0)
        self.nearby_peers = [
            PeerInfo("ROBOT-B-02", 4, 3, 80.0, target_rack_id="RACK-02", target_shelf=1),
            PeerInfo("ROBOT-C-03", 6, 3, 70.0, target_rack_id="RACK-03", target_shelf=0),
        ]

    def test_negotiate_finds_alternative_slot(self) -> None:
        # RACK-01 shelf 0 is occupied
        result = negotiate_storage_slot(
            self.requesting_robot,
            ("RACK-01", 0),
            self.nearby_peers,
            self.racks,
        )
        assert result is not None
        rack_id, shelf = result
        assert rack_id in self.racks
        assert 0 <= shelf < self.racks[rack_id].shelves
        assert rack_id != "RACK-01" or shelf != 0

    def test_negotiate_returns_none_when_all_full(self) -> None:
        # Fill all racks
        for rack in self.racks.values():
            for i in range(rack.shelves):
                rack._products[i] = ["p1", "p2", "p3", "p4", "p5"]

        result = negotiate_storage_slot(
            self.requesting_robot,
            ("RACK-01", 0),
            self.nearby_peers,
            self.racks,
        )
        assert result is None

    def test_negotiate_prefers_closer_racks(self) -> None:
        # RACK-02 is closer than RACK-03
        self.racks["RACK-02"]._products[1] = []  # shelf 1 empty
        self.racks["RACK-03"]._products[0] = []  # shelf 0 empty

        result = negotiate_storage_slot(
            self.requesting_robot,
            ("RACK-01", 0),
            self.nearby_peers,
            self.racks,
        )
        assert result == ("RACK-02", 1)

    def test_negotiate_respects_peer_priority(self) -> None:
        # Peer B is closer to RACK-02 and targeting it
        self.requesting_robot.battery = 50.0  # Lower battery
        self.nearby_peers[0].battery = 90.0   # Higher battery peer

        result = negotiate_storage_slot(
            self.requesting_robot,
            ("RACK-01", 0),
            self.nearby_peers,
            self.racks,
        )
        # Should avoid RACK-02 shelf 1 since peer B has priority
        if result:
            assert result != ("RACK-02", 1)

    def test_negotiate_with_empty_peers(self) -> None:
        result = negotiate_storage_slot(
            self.requesting_robot,
            ("RACK-01", 0),
            [],
            self.racks,
        )
        assert result is not None
        rack_id, shelf = result
        assert rack_id in self.racks


class TestSlotProposal:
    def test_slot_proposal_creation(self) -> None:
        prop = SlotProposal(
            rack_id="RACK-01",
            shelf=2,
            score=15.5,
            proposer_id="ROBOT-A-01",
            distance=10.0,
            utilization=0.3,
        )
        assert prop.rack_id == "RACK-01"
        assert prop.shelf == 2
        assert prop.score == 15.5
        assert prop.proposer_id == "ROBOT-A-01"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])