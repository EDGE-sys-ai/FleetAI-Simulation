"""
Local Consensus Protocol for Storage Slot Negotiation
Robots collaboratively pick alternative rack slots without central server.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Mapping, Optional, Tuple

if TYPE_CHECKING:
    from models.robot import Robot
    from models.rack import Rack
    from network.p2p_node import P2PNode, PeerInfo


@dataclass
class SlotProposal:
    """A proposed storage slot with scoring metadata."""
    rack_id: str
    shelf: int
    score: float
    proposer_id: str
    distance: float
    utilization: float


def negotiate_storage_slot(
    requesting_robot: "Robot",
    occupied_slot: Tuple[str, int],
    nearby_nodes: List["PeerInfo"],
    racks: Mapping[str, Any],
    max_proposals: int = 3,
) -> Optional[Tuple[str, int]]:
    """
    Negotiate an alternative storage slot when the assigned bin is blocked.

    Args:
        requesting_robot: Robot requesting a slot
        occupied_slot: (rack_id, shelf) that is occupied
        nearby_nodes: List of PeerInfo from nearby robots
        racks: Dictionary of all racks in the warehouse
        max_proposals: Maximum number of proposals to consider

    Returns:
        Tuple of (rack_id, shelf) for the agreed slot, or None if no consensus
    """
    occ_rack_id, occ_shelf = occupied_slot
    candidates: List[SlotProposal] = []

    # Collect proposals from nearby peers
    for peer in nearby_nodes:
        if peer.target_rack_id and peer.target_rack_id != occ_rack_id:
            rack = racks.get(peer.target_rack_id)
            if rack is not None:
                shelf = rack.get_shelf(peer.target_shelf or 0)
                if shelf is not None and not shelf.is_full():
                    dist = _manhattan_distance(requesting_robot.x, requesting_robot.y, rack.x, rack.y)
                    util = rack.utilization()
                    score = _score_slot(dist, util, peer.battery)
                    candidates.append(SlotProposal(
                        rack_id=peer.target_rack_id,
                        shelf=peer.target_shelf or 0,
                        score=score,
                        proposer_id=peer.robot_id,
                        distance=dist,
                        utilization=util,
                    ))

    # Add local proposals for nearby racks
    for rack in racks.values():
        if rack.id == occ_rack_id:
            continue
        for shelf_num in range(rack.shelves):
            shelf = rack.get_shelf(shelf_num)
            if shelf and not shelf.is_full():
                dist = _manhattan_distance(requesting_robot.x, requesting_robot.y, rack.x, rack.y)
                util = rack.utilization()
                score = _score_slot(dist, util, requesting_robot.battery)
                candidates.append(SlotProposal(
                    rack_id=rack.id,
                    shelf=shelf_num,
                    score=score,
                    proposer_id=requesting_robot.id,
                    distance=dist,
                    utilization=util,
                ))

    if not candidates:
        return None

    # Sort by score (lower is better)
    candidates.sort(key=lambda p: p.score)

    # Simple consensus: pick best slot not contested by higher-priority robot
    for proposal in candidates[:max_proposals]:
        if _is_slot_available(proposal, nearby_nodes, requesting_robot.id, racks):
            return (proposal.rack_id, proposal.shelf)

    return None


def _manhattan_distance(x1: float | int, y1: float | int, x2: float | int, y2: float | int) -> float:
    return abs(int(x1) - int(x2)) + abs(int(y1) - int(y2))


def _score_slot(distance: float, utilization: float, battery: float) -> float:
    """
    Score a slot: prefer closer, less utilized racks, and robots with higher battery.
    Lower score = better.
    """
    return distance * 1.0 + utilization * 5.0 + (100.0 - battery) * 0.1


def _is_slot_available(
    proposal: SlotProposal,
    nearby_nodes: List["PeerInfo"],
    requesting_id: str,
    racks: Mapping[str, Any],
) -> bool:
    """Check if no higher-priority robot is targeting the same slot."""
    target_rack = racks.get(proposal.rack_id)
    if target_rack is None:
        return True
    for peer in nearby_nodes:
        if peer.robot_id == requesting_id:
            continue
        if (peer.target_rack_id == proposal.rack_id
                and peer.target_shelf == proposal.shelf):
            # Peer has priority if closer or higher battery
            peer_dist = _manhattan_distance(
                peer.x, peer.y,
                target_rack.x, target_rack.y,
            )
            if peer_dist < proposal.distance or peer.battery > 80:
                return False
    return True