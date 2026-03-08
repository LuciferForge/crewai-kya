"""TrustGateTool — Gate agent actions on trust score thresholds.

A CrewAI tool that checks whether an agent's KYA identity card meets
a minimum completeness/trust score before allowing an action to proceed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type

try:
    from crewai.tools import BaseTool as _CrewAIBaseTool

    _HAS_CREWAI = True
except ImportError:
    _HAS_CREWAI = False

try:
    from pydantic import BaseModel, Field
except ImportError:

    class BaseModel:  # type: ignore[no-redef]
        pass

    def Field(**kwargs):  # type: ignore[no-redef]
        return kwargs.get("default")


class TrustGateInput(BaseModel):
    """Input schema for TrustGateTool."""

    card_json: str = Field(  # type: ignore[call-overload]
        ...,
        description="JSON string of a KYA agent identity card.",
    )
    min_score: int = Field(  # type: ignore[call-overload]
        default=50,
        description="Minimum completeness score (0-100) required to pass the gate.",
    )
    require_signature: bool = Field(  # type: ignore[call-overload]
        default=False,
        description="If true, the card must have a valid Ed25519 signature.",
    )
    required_capabilities: Optional[str] = Field(  # type: ignore[call-overload]
        default=None,
        description="Comma-separated list of capability names the agent must declare.",
    )


def evaluate_trust(
    card_json: str,
    min_score: int = 50,
    require_signature: bool = False,
    required_capabilities: Optional[str] = None,
) -> str:
    """Evaluate whether a KYA card meets trust requirements.

    Returns a human-readable PASS/FAIL result with reasons.
    """
    try:
        card = json.loads(card_json)
    except json.JSONDecodeError as e:
        return f"BLOCKED: Invalid JSON — {e}"

    from kya.validator import compute_completeness_score

    score = compute_completeness_score(card)
    reasons: list[str] = []
    passed = True

    # Score check
    if score < min_score:
        passed = False
        reasons.append(f"Score {score}/100 below threshold {min_score}")

    # Signature check
    if require_signature:
        sig = card.get("_signature")
        if not sig:
            passed = False
            reasons.append("No signature — card is unsigned")
        else:
            try:
                from kya.signer import verify_card

                result = verify_card(card)
                if not result.get("valid"):
                    passed = False
                    reasons.append(f"Invalid signature: {result.get('error', 'unknown')}")
            except ImportError:
                passed = False
                reasons.append("Cannot verify signature — install kya-agent[signing]")

    # Capabilities check
    if required_capabilities:
        required = {c.strip().lower() for c in required_capabilities.split(",")}
        declared = {
            c.get("name", "").lower()
            for c in card.get("capabilities", {}).get("declared", [])
        }
        missing = required - declared
        if missing:
            passed = False
            reasons.append(f"Missing capabilities: {', '.join(sorted(missing))}")

    # Build result
    agent_name = card.get("name", "unknown")
    agent_id = card.get("agent_id", "unknown")

    lines = []
    if passed:
        lines.append(f"PASSED: {agent_name} ({agent_id})")
        lines.append(f"Score: {score}/100")
        lines.append("Action permitted.")
    else:
        lines.append(f"BLOCKED: {agent_name} ({agent_id})")
        lines.append(f"Score: {score}/100")
        for r in reasons:
            lines.append(f"Reason: {r}")
        lines.append("Action denied.")

    return "\n".join(lines)


if _HAS_CREWAI:

    class TrustGateTool(_CrewAIBaseTool):
        """Gate an action on an agent's KYA trust score.

        Checks whether the agent's KYA card meets minimum completeness,
        signature, and capability requirements before allowing an action.
        """

        name: str = "kya_trust_gate"
        description: str = (
            "Check if an AI agent meets trust requirements before performing an action. "
            "Input is a KYA card JSON, minimum score threshold, and optional requirements "
            "(signature, capabilities). Returns PASSED or BLOCKED with reasons."
        )
        args_schema: Type[BaseModel] = TrustGateInput

        def _run(
            self,
            card_json: str,
            min_score: int = 50,
            require_signature: bool = False,
            required_capabilities: Optional[str] = None,
        ) -> str:
            return evaluate_trust(card_json, min_score, require_signature, required_capabilities)

else:

    class TrustGateTool:  # type: ignore[no-redef]
        """Trust gate tool (crewai not installed — standalone mode)."""

        name = "kya_trust_gate"
        description = "Check if an AI agent meets trust requirements before performing an action."

        def run(
            self,
            card_json: str,
            min_score: int = 50,
            require_signature: bool = False,
            required_capabilities: Optional[str] = None,
        ) -> str:
            return evaluate_trust(card_json, min_score, require_signature, required_capabilities)

        _run = run
