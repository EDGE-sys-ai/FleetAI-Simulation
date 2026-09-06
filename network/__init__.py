"""
Network package for P2P robot communication and consensus.
"""

from network.p2p_node import P2PNode, PeerInfo, Message
from network.consensus import negotiate_storage_slot, SlotProposal

__all__ = [
    "P2PNode",
    "PeerInfo",
    "Message",
    "negotiate_storage_slot",
    "SlotProposal",
]