"""Tests for crewai-kya integration.

Tests work without crewai installed by using a mock Agent class.
"""

import json
import pytest
from unittest.mock import MagicMock
from typing import Any

from crewai_kya.card import create_agent_card, attach_card, get_card
from crewai_kya.identity import verify_identity, _verify_card_data
from crewai_kya.trust_gate import evaluate_trust
from crewai_kya.middleware import kya_verified, KYAVerificationError


class MockAgent:
    """Mimics crewai.Agent for testing."""

    def __init__(self, role: str, goal: str = "", backstory: str = "", tools: list = None):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []


class MockTool:
    """Mimics a CrewAI tool."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description


# ── Card creation ──


class TestCreateAgentCard:
    def test_basic_card(self):
        agent = MockAgent(role="Researcher", goal="Find relevant papers")
        card = create_agent_card(agent, owner_name="TestOrg", owner_contact="test@test.com")

        assert card["kya_version"] == "0.1"
        assert card["agent_id"] == "crewai/researcher"
        assert card["name"] == "Researcher"
        assert "Find relevant papers" in card["purpose"]
        assert card["owner"]["name"] == "TestOrg"
        assert card["owner"]["contact"] == "test@test.com"

    def test_card_with_tools(self):
        tools = [MockTool("web_search", "Search the web"), MockTool("file_read", "Read files")]
        agent = MockAgent(role="Analyst", goal="Analyze data", tools=tools)
        card = create_agent_card(agent, owner_name="Org")

        declared = card["capabilities"]["declared"]
        assert len(declared) == 2
        assert declared[0]["name"] == "web_search"
        assert declared[1]["name"] == "file_read"

    def test_card_custom_prefix(self):
        agent = MockAgent(role="Writer")
        card = create_agent_card(agent, agent_id_prefix="myorg")
        assert card["agent_id"] == "myorg/writer"

    def test_card_slug_sanitization(self):
        agent = MockAgent(role="Senior Data Analyst!!!")
        card = create_agent_card(agent)
        assert "/" not in card["agent_id"].split("/")[1]
        assert "!" not in card["agent_id"]

    def test_purpose_minimum_length(self):
        agent = MockAgent(role="X", goal="Do")
        card = create_agent_card(agent)
        assert len(card["purpose"]) >= 10

    def test_card_has_metadata_timestamps(self):
        agent = MockAgent(role="Bot")
        card = create_agent_card(agent)
        assert card["metadata"]["created_at"] != ""
        assert card["metadata"]["updated_at"] != ""


# ── Card attachment ──


class TestAttachCard:
    def test_attach_and_get(self):
        agent = MockAgent(role="Test")
        card = {"kya_version": "0.1", "agent_id": "test/test"}
        attach_card(agent, card)
        assert get_card(agent) == card

    def test_get_card_none_when_not_attached(self):
        agent = MockAgent(role="Test")
        assert get_card(agent) is None


# ── Identity verification ──


VALID_CARD = {
    "kya_version": "0.1",
    "agent_id": "crewai/researcher",
    "name": "Researcher",
    "version": "0.1.0",
    "purpose": "A CrewAI agent that researches topics and summarizes findings.",
    "agent_type": "autonomous",
    "owner": {"name": "TestOrg", "contact": "test@test.com"},
    "capabilities": {
        "declared": [
            {"name": "web_search", "risk_level": "medium"},
            {"name": "summarize", "risk_level": "low"},
        ],
        "denied": [],
    },
}

MINIMAL_CARD = {
    "kya_version": "0.1",
    "agent_id": "crewai/minimal",
    "name": "Minimal",
    "version": "0.1.0",
    "purpose": "A minimal test agent for validation.",
    "owner": {"name": "Test", "contact": "test@test.com"},
    "capabilities": {"declared": [{"name": "test", "risk_level": "low"}]},
}

INVALID_CARD = {
    "kya_version": "0.1",
    "name": "Broken",
    # Missing agent_id, purpose, capabilities, owner
}


class TestIdentityVerification:
    def test_valid_card(self):
        result = verify_identity(json.dumps(VALID_CARD))
        assert "VERIFIED" in result
        assert "Researcher" in result

    def test_invalid_card(self):
        result = verify_identity(json.dumps(INVALID_CARD))
        assert "FAILED" in result

    def test_invalid_json(self):
        result = verify_identity("not json")
        assert "FAILED" in result
        assert "Invalid JSON" in result

    def test_verify_data_returns_capabilities(self):
        result = _verify_card_data(VALID_CARD)
        assert "web_search" in result["capabilities"]
        assert "summarize" in result["capabilities"]

    def test_verify_data_score(self):
        result = _verify_card_data(VALID_CARD)
        assert result["completeness_score"] > 0


# ── Trust gate ──


class TestTrustGate:
    def test_passes_valid_card(self):
        result = evaluate_trust(json.dumps(VALID_CARD), min_score=0)
        assert "PASSED" in result

    def test_blocks_low_score(self):
        result = evaluate_trust(json.dumps(MINIMAL_CARD), min_score=100)
        assert "BLOCKED" in result
        assert "below threshold" in result

    def test_blocks_missing_capabilities(self):
        result = evaluate_trust(
            json.dumps(VALID_CARD),
            min_score=0,
            required_capabilities="web_search,secret_power",
        )
        assert "BLOCKED" in result
        assert "secret_power" in result

    def test_blocks_unsigned_when_signature_required(self):
        result = evaluate_trust(
            json.dumps(VALID_CARD),
            min_score=0,
            require_signature=True,
        )
        assert "BLOCKED" in result
        assert "unsigned" in result.lower()

    def test_invalid_json(self):
        result = evaluate_trust("bad json")
        assert "BLOCKED" in result


# ── Middleware decorator ──


class TestKYAVerified:
    def test_passes_with_valid_card(self):
        agent = MockAgent(role="Good Agent", goal="Do good things reliably and well")
        card = create_agent_card(agent, owner_name="Test", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=0)
        def task(agent):
            return "executed"

        assert task(agent) == "executed"

    def test_raises_without_card(self):
        agent = MockAgent(role="Naked Agent")

        @kya_verified()
        def task(agent):
            return "executed"

        with pytest.raises(KYAVerificationError, match="No KYA card"):
            task(agent)

    def test_raises_on_low_score(self):
        agent = MockAgent(role="Weak Agent")
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=100)
        def task(agent):
            return "executed"

        with pytest.raises(KYAVerificationError, match="below required"):
            task(agent)

    def test_skip_on_fail(self):
        agent = MockAgent(role="Skippable")

        @kya_verified(on_fail="skip")
        def task(agent):
            return "executed"

        assert task(agent) is None

    def test_log_on_fail(self, capsys):
        agent = MockAgent(role="Logged Agent")

        @kya_verified(on_fail="log")
        def task(agent):
            return "executed"

        result = task(agent)
        assert result == "executed"
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_agent_as_kwarg(self):
        agent = MockAgent(role="Kwarg Agent", goal="Test keyword argument passing")
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=0)
        def task(data, agent=None):
            return f"processed {data}"

        assert task("stuff", agent=agent) == "processed stuff"

    def test_required_capabilities(self):
        agent = MockAgent(
            role="Limited Agent",
            goal="Has limited capabilities for testing",
            tools=[MockTool("reading")],
        )
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(required_capabilities=["reading"])
        def task(agent):
            return "executed"

        assert task(agent) == "executed"

    def test_missing_required_capabilities(self):
        agent = MockAgent(role="No Tools Agent", goal="Has no tools at all")
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(required_capabilities=["admin_access"])
        def task(agent):
            return "executed"

        with pytest.raises(KYAVerificationError, match="Missing capabilities"):
            task(agent)
