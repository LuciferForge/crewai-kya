"""Card helpers — create and manage KYA identity cards for CrewAI agents.

Works with or without crewai installed. When crewai is available, cards
are stored on agent objects via a _kya_card attribute.
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional

# KYA card structure follows the v0.1 schema
_CARD_TEMPLATE: Dict[str, Any] = {
    "kya_version": "0.1",
    "agent_id": "",
    "name": "",
    "version": "0.1.0",
    "purpose": "",
    "agent_type": "autonomous",
    "owner": {"name": "", "contact": ""},
    "capabilities": {"declared": [], "denied": []},
    "data_access": {
        "sources": [],
        "destinations": [],
        "pii_handling": "none",
        "retention_policy": "session-only",
    },
    "security": {
        "last_audit": None,
        "known_vulnerabilities": [],
        "injection_tested": False,
    },
    "compliance": {
        "frameworks": [],
        "risk_classification": "minimal",
        "human_oversight": "human-on-the-loop",
    },
    "behavior": {
        "logging_enabled": False,
        "log_format": "none",
        "max_actions_per_minute": 0,
        "kill_switch": True,
        "escalation_policy": "halt-and-notify",
    },
    "metadata": {
        "created_at": "",
        "updated_at": "",
        "tags": ["crewai"],
    },
}


def _resolve_agent_fields(agent: Any) -> Dict[str, str]:
    """Extract identity-relevant fields from a CrewAI Agent object.

    CrewAI Agent has: role, goal, backstory, tools, verbose, etc.
    We map these to KYA card fields.
    """
    role = getattr(agent, "role", "unknown-agent")
    goal = getattr(agent, "goal", "")
    backstory = getattr(agent, "backstory", "")

    # Build a stable agent_id from the role
    slug = role.lower().replace(" ", "-").replace("_", "-")
    # Strip non-alphanumeric except hyphens
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    slug = slug.strip("-") or "agent"

    return {
        "role": role,
        "goal": goal,
        "backstory": backstory,
        "slug": slug,
    }


def _extract_tool_capabilities(agent: Any) -> List[Dict[str, str]]:
    """Extract capabilities from CrewAI agent's tools list."""
    tools = getattr(agent, "tools", []) or []
    capabilities = []
    for tool in tools:
        name = getattr(tool, "name", None) or type(tool).__name__
        description = getattr(tool, "description", "") or ""
        capabilities.append({
            "name": name,
            "description": description[:200],
            "risk_level": "medium",  # Conservative default
            "scope": "as-configured",
        })
    return capabilities


def create_agent_card(
    agent: Any,
    *,
    owner_name: str = "unspecified",
    owner_contact: str = "unspecified",
    agent_id_prefix: str = "crewai",
    capabilities: Optional[List[Dict[str, str]]] = None,
    version: str = "0.1.0",
    risk_classification: str = "minimal",
    human_oversight: str = "human-on-the-loop",
) -> Dict[str, Any]:
    """Create a KYA identity card from a CrewAI Agent.

    Args:
        agent: A crewai.Agent instance (or any object with role/goal/backstory).
        owner_name: Organization or person responsible for this agent.
        owner_contact: Contact email for security/compliance inquiries.
        agent_id_prefix: Prefix for the agent_id (default: "crewai").
        capabilities: Override auto-detected capabilities. If None, extracted from agent.tools.
        version: Semantic version for the agent.
        risk_classification: EU AI Act risk level (minimal/limited/high/unacceptable).
        human_oversight: Oversight level (none/human-on-the-loop/human-in-the-loop/human-above-the-loop).

    Returns:
        A KYA card dict conforming to the v0.1 schema.
    """
    fields = _resolve_agent_fields(agent)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if capabilities is None:
        capabilities = _extract_tool_capabilities(agent)

    # Build purpose from goal + backstory
    purpose_parts = []
    if fields["goal"]:
        purpose_parts.append(fields["goal"])
    if fields["backstory"]:
        purpose_parts.append(fields["backstory"])
    purpose = ". ".join(purpose_parts) if purpose_parts else f"CrewAI agent: {fields['role']}"
    # Ensure purpose meets KYA minLength of 10
    if len(purpose) < 10:
        purpose = f"CrewAI agent performing the role of {fields['role']}"
    # Cap at schema maxLength
    purpose = purpose[:500]

    card: Dict[str, Any] = {
        "kya_version": "0.1",
        "agent_id": f"{agent_id_prefix}/{fields['slug']}",
        "name": fields["role"],
        "version": version,
        "purpose": purpose,
        "agent_type": "autonomous",
        "owner": {
            "name": owner_name,
            "contact": owner_contact,
        },
        "capabilities": {
            "declared": capabilities,
            "denied": [],
        },
        "data_access": {
            "sources": [],
            "destinations": [],
            "pii_handling": "none",
            "retention_policy": "session-only",
        },
        "security": {
            "last_audit": None,
            "known_vulnerabilities": [],
            "injection_tested": False,
        },
        "compliance": {
            "frameworks": [],
            "risk_classification": risk_classification,
            "human_oversight": human_oversight,
        },
        "behavior": {
            "logging_enabled": False,
            "log_format": "none",
            "max_actions_per_minute": 0,
            "kill_switch": True,
            "escalation_policy": "halt-and-notify",
        },
        "metadata": {
            "created_at": now,
            "updated_at": now,
            "tags": ["crewai"],
        },
    }

    return card


def attach_card(agent: Any, card: Dict[str, Any]) -> None:
    """Attach a KYA identity card to a CrewAI Agent instance.

    Stores the card as agent._kya_card for retrieval by tools and middleware.
    """
    agent._kya_card = card


def get_card(agent: Any) -> Optional[Dict[str, Any]]:
    """Retrieve the KYA card attached to a CrewAI Agent, if any."""
    return getattr(agent, "_kya_card", None)
