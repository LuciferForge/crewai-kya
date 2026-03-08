"""KYAIdentityTool — A CrewAI-compatible tool for verifying agent identity cards.

Usable as a standalone tool or within a CrewAI agent's tool belt.
Works with or without crewai installed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type

# Try importing CrewAI's BaseTool. If not available, provide a fallback
# so the module can still be imported and tested without crewai.
try:
    from crewai.tools import BaseTool as _CrewAIBaseTool

    _HAS_CREWAI = True
except ImportError:
    _HAS_CREWAI = False

try:
    from pydantic import BaseModel, Field
except ImportError:
    # crewai requires pydantic, but handle the edge case
    from dataclasses import dataclass, field as _field  # type: ignore

    class BaseModel:  # type: ignore[no-redef]
        pass

    def Field(**kwargs):  # type: ignore[no-redef]
        return kwargs.get("default")


class KYAVerifyInput(BaseModel):
    """Input schema for KYAIdentityTool."""

    card_json: str = Field(  # type: ignore[call-overload]
        ...,
        description="JSON string of a KYA agent identity card to verify.",
    )
    public_key_path: Optional[str] = Field(  # type: ignore[call-overload]
        default=None,
        description="Optional path to a PEM public key file for signature verification.",
    )


def _verify_card_data(card: Dict[str, Any], public_key_path: Optional[str] = None) -> Dict[str, Any]:
    """Core verification logic, independent of CrewAI."""
    from kya.validator import (
        validate_required_fields,
        validate_capabilities,
        compute_completeness_score,
        load_schema,
    )

    schema = load_schema()

    errors = validate_required_fields(card, schema)
    errors.extend([
        e for e in validate_capabilities(card)
        if "missing" in e.lower()
    ])

    score = compute_completeness_score(card)

    # Check signature if present
    sig_result: Dict[str, Any] = {"status": "unsigned"}
    if "_signature" in card:
        try:
            from kya.signer import verify_card

            sig_result_raw = verify_card(card, public_key_path=public_key_path)
            if sig_result_raw.get("valid"):
                sig_result = {
                    "status": "verified",
                    "key_id": sig_result_raw["key_id"],
                    "signed_at": sig_result_raw["signed_at"],
                    "algorithm": sig_result_raw["algorithm"],
                }
            else:
                sig_result = {
                    "status": "invalid",
                    "error": sig_result_raw.get("error", "verification failed"),
                }
        except ImportError:
            sig_result = {
                "status": "unverified",
                "note": "Install kya-agent[signing] to verify signatures",
            }

    result = {
        "valid": len(errors) == 0,
        "agent_id": card.get("agent_id", "unknown"),
        "agent_name": card.get("name", "unknown"),
        "completeness_score": score,
        "signature": sig_result,
        "capabilities": [
            c.get("name", "unnamed")
            for c in card.get("capabilities", {}).get("declared", [])
        ],
        "errors": errors,
    }

    return result


def verify_identity(card_json: str, public_key_path: Optional[str] = None) -> str:
    """Verify a KYA card from JSON string. Returns human-readable result."""
    try:
        card = json.loads(card_json)
    except json.JSONDecodeError as e:
        return f"FAILED: Invalid JSON — {e}"

    result = _verify_card_data(card, public_key_path)

    # Format for LLM consumption
    lines = []
    status = "VERIFIED" if result["valid"] else "FAILED"
    lines.append(f"Identity: {status}")
    lines.append(f"Agent: {result['agent_name']} ({result['agent_id']})")
    lines.append(f"Completeness: {result['completeness_score']}/100")
    lines.append(f"Signature: {result['signature']['status']}")

    if result["capabilities"]:
        lines.append(f"Capabilities: {', '.join(result['capabilities'])}")

    if result["errors"]:
        lines.append(f"Errors: {'; '.join(result['errors'])}")

    return "\n".join(lines)


# Build the CrewAI Tool class conditionally
if _HAS_CREWAI:

    class KYAIdentityTool(_CrewAIBaseTool):
        """Verify a KYA (Know Your Agent) identity card.

        Given a KYA card as JSON, validates its structure, checks the
        Ed25519 signature if present, and returns the verification result.
        """

        name: str = "kya_identity_verify"
        description: str = (
            "Verify an AI agent's KYA identity card. Input is a JSON string of the card. "
            "Returns whether the card is valid, the agent's capabilities, completeness score, "
            "and signature verification status."
        )
        args_schema: Type[BaseModel] = KYAVerifyInput

        def _run(self, card_json: str, public_key_path: Optional[str] = None) -> str:
            return verify_identity(card_json, public_key_path)

else:
    # Fallback: plain class with the same interface for non-crewai use
    class KYAIdentityTool:  # type: ignore[no-redef]
        """KYA identity verification tool (crewai not installed — standalone mode)."""

        name = "kya_identity_verify"
        description = (
            "Verify an AI agent's KYA identity card. Input is a JSON string of the card."
        )

        def run(self, card_json: str, public_key_path: Optional[str] = None) -> str:
            return verify_identity(card_json, public_key_path)

        # Alias for consistency
        _run = run
