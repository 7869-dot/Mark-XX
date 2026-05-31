"""Axolot MCP — exposes a user's Axolot agent over the Model Context Protocol.

Standalone package inside the monorepo: importable on its own, talks to the
Axolot HTTP API (so it works against the deployed backend and scales with it),
and authenticates with the existing JWT. The protocol is the stable surface;
the intelligence behind it can scale up invisibly.
"""

__all__ = ["AxolotClient"]

from axolot_mcp.client import AxolotClient
