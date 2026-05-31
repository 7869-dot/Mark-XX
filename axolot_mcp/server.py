"""Axolot MCP stdio server.

Exposes a user's Axolot agent as standard MCP tools + resources, so any
MCP-compatible client (Claude Desktop, Claude Code, future apps) can talk to
the agent directly. Auth is the existing JWT, passed as AXOLOT_USER_TOKEN on
init and validated on first use.

Run:  python -m axolot_mcp.server
"""
from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from axolot_mcp.client import AxolotClient, AxolotAuthError

mcp = FastMCP("axolot")

_client: AxolotClient | None = None


def client() -> AxolotClient:
    """Lazily build + validate the API client from env (token validated once)."""
    global _client
    if _client is None:
        _client = AxolotClient(
            base_url=os.environ.get("AXOLOT_API_URL"),
            token=os.environ.get("AXOLOT_USER_TOKEN"),
        )
        _client.validate()  # raises AxolotAuthError on a bad/missing token
    return _client


def _json(obj) -> str:
    return json.dumps(obj, indent=2, default=str)


def _guard(fn):
    try:
        return _json(fn())
    except AxolotAuthError as e:
        return f"Auth error: {e} Set AXOLOT_USER_TOKEN to a valid Axolot JWT."
    except Exception as e:  # noqa: BLE001
        return f"Error: {e}"


# ── Tools ─────────────────────────────────────────────────────────────────────
@mcp.tool()
def agent_post(topic: str, content: str | None = None, trust_level: str = "MANUAL") -> str:
    """Post on the user's behalf. If `content` is empty, the agent composes a
    grounded post about `topic` from live world data + the user's personality.
    trust_level=AUTO publishes immediately; otherwise it's queued for approval."""
    return _guard(lambda: client().post(topic, content, trust_level))


@mcp.tool()
def agent_search(query: str) -> str:
    """Web search grounded in the user's interest profile. Returns source-cited
    results filtered through the user's worldview."""
    return _guard(lambda: client().search(query))


@mcp.tool()
def agent_status() -> str:
    """What the agent is currently tracking, its pending posts, active
    collaborations, and per-category trust settings."""
    return _guard(lambda: client().status())


@mcp.tool()
def agent_collaborate(target_username: str, intent: str) -> str:
    """Send a collaboration signal to another user's agent. `intent` is a plain
    goal ('find a co-founder'). PII is never transmitted — the privacy filter is
    applied automatically server-side."""
    return _guard(lambda: client().collaborate(target_username, intent))


@mcp.tool()
def agent_memory_update(key: str, value: str) -> str:
    """Update the user's PersonalityMatrix or TopicInterestProfile. Keys:
    topic|interest, communication_style, goal, or any note key."""
    return _guard(lambda: client().memory_update(key, value))


@mcp.tool()
def agent_feed(limit: int = 10) -> str:
    """The agent's recent activity: posts made, topics read, collaborations proposed."""
    return _guard(lambda: client().feed(limit))


# ── Resources ──────────────────────────────────────────────────────────────────
@mcp.resource("axolot://agent/profile")
def res_profile() -> str:
    """Read-only view of the user's agent: name, personality, tracked topics, trust."""
    return _guard(lambda: client().profile())


@mcp.resource("axolot://agent/feed")
def res_feed() -> str:
    """Live feed of agent activity."""
    return _guard(lambda: client().feed(20))


@mcp.resource("axolot://world/pulse")
def res_pulse() -> str:
    """Current trending topics the agent is monitoring, with interest weights."""
    return _guard(lambda: client().pulse())


def main() -> None:
    mcp.run()  # stdio transport — Claude Desktop / Claude Code compatible


if __name__ == "__main__":
    main()
