"""crewai-kya — KYA (Know Your Agent) identity verification for CrewAI agents.

Provides tools, decorators, and helpers to bring cryptographic agent identity
to CrewAI workflows. No blockchain, no cloud dependency — just Ed25519 signatures.

Usage:
    from crewai_kya import KYAIdentityTool, TrustGateTool, create_agent_card, attach_card
"""

__version__ = "0.1.0"

from crewai_kya.card import create_agent_card, attach_card, get_card
from crewai_kya.identity import KYAIdentityTool
from crewai_kya.trust_gate import TrustGateTool
from crewai_kya.middleware import kya_verified

__all__ = [
    "KYAIdentityTool",
    "TrustGateTool",
    "kya_verified",
    "create_agent_card",
    "attach_card",
    "get_card",
]
