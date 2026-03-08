# crewai-kya

**KYA (Know Your Agent) identity verification for CrewAI agents.**

Cryptographic agent identity, trust gates, and verification middleware for [CrewAI](https://crewai.com) workflows. No blockchain, no cloud dependency — just Ed25519 signatures and a clean Python API.

## Install

```bash
pip install crewai-kya
```

For signature verification:
```bash
pip install crewai-kya[signing]
```

## Quick Start

```python
from crewai import Agent
from crewai_kya import create_agent_card, attach_card, KYAIdentityTool

# Create your CrewAI agent
researcher = Agent(
    role="Researcher",
    goal="Find and summarize relevant papers",
    backstory="Expert research analyst",
    tools=[KYAIdentityTool()],  # Agent can verify other agents
)

# Give it a cryptographic identity card
card = create_agent_card(
    researcher,
    owner_name="Acme Corp",
    owner_contact="security@acme.com",
)
attach_card(researcher, card)
```

That's it. Your agent now has a verifiable identity.

## Trust Gates

Block actions when agents don't meet trust requirements:

```python
from crewai_kya import TrustGateTool

# Add to any agent's toolkit
agent = Agent(
    role="Gatekeeper",
    goal="Verify agent identities before granting access",
    tools=[TrustGateTool()],
)
```

The TrustGateTool checks:
- **Completeness score** — is the identity card filled out? (0-100)
- **Signature** — is the card cryptographically signed?
- **Capabilities** — does the agent declare the required capabilities?

## Decorator: `@kya_verified`

Gate any function on KYA identity:

```python
from crewai_kya import kya_verified

@kya_verified(min_score=60, require_signature=True)
def sensitive_operation(agent, data):
    # Only runs if agent has a valid, signed KYA card with score >= 60
    return process(data)

# Fails with KYAVerificationError if agent doesn't meet requirements
sensitive_operation(my_agent, sensitive_data)
```

Failure modes:
- `on_fail="raise"` — raise `KYAVerificationError` (default)
- `on_fail="skip"` — return `None` silently
- `on_fail="log"` — print warning, continue execution

## Why KYA over alternatives?

| Feature | crewai-kya | AgentFolio |
|---------|-----------|------------|
| **Self-hosted** | Yes | No |
| **Works offline** | Yes | No |
| **Cryptographic signing** | Ed25519 | None |
| **Blockchain dependency** | None | Required |
| **PyPI package** | `crewai-kya` | Not published |
| **Zero external deps** | Yes (signing optional) | No |
| **Open standard** | KYA v0.1 schema | Proprietary |

## API Reference

### `create_agent_card(agent, **kwargs) -> dict`

Create a KYA identity card from a CrewAI Agent. Auto-extracts role, goal, backstory, and tool capabilities.

**Parameters:**
- `agent` — CrewAI Agent instance
- `owner_name` — Organization name
- `owner_contact` — Contact email
- `agent_id_prefix` — ID prefix (default: "crewai")
- `capabilities` — Override auto-detected capabilities
- `version` — Agent version (default: "0.1.0")
- `risk_classification` — EU AI Act level (default: "minimal")
- `human_oversight` — Oversight level (default: "human-on-the-loop")

### `attach_card(agent, card)`

Attach a KYA card to an agent instance for middleware access.

### `get_card(agent) -> dict | None`

Retrieve the attached KYA card.

### `KYAIdentityTool`

CrewAI Tool that verifies KYA identity cards. Input: card JSON string. Output: verification result.

### `TrustGateTool`

CrewAI Tool that gates actions on trust score. Input: card JSON + thresholds. Output: PASSED/BLOCKED.

### `@kya_verified(min_score, require_signature, required_capabilities, on_fail)`

Decorator for gating function execution on KYA identity.

## Sign Cards

```python
from kya.signer import generate_keypair, sign_card

# One-time: generate Ed25519 keys
generate_keypair("my-org")

# Sign a card
signed_card = sign_card(card, "~/.kya/keys/my-org.key")
```

## License

MIT — LuciferForge
