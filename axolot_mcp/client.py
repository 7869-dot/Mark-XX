"""Thin HTTP client over the Axolot API for the MCP server.

Envelope-aware (unwraps {success, data}). Auth via the existing JWT. The
`http` client is injectable so tests can drive it against the FastAPI app via
httpx ASGITransport with no network.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


class AxolotAuthError(RuntimeError):
    pass


class AxolotClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, *, http: httpx.Client | None = None):
        self.base_url = (base_url or os.environ.get("AXOLOT_API_URL", "http://localhost:8000")).rstrip("/")
        self.token = token or os.environ.get("AXOLOT_USER_TOKEN", "")
        self._http = http or httpx.Client(base_url=self.base_url, timeout=30.0)
        self._agent_id: str | None = None

    # ── low level ────────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _unwrap(self, resp: httpx.Response) -> Any:
        if resp.status_code in (401, 403):
            raise AxolotAuthError("Invalid or missing AXOLOT_USER_TOKEN.")
        data = resp.json()
        if not data.get("success", False):
            raise RuntimeError((data.get("error") or data.get("message") or "request failed"))
        return data.get("data")

    def _get(self, path: str, **params) -> Any:
        return self._unwrap(self._http.get(path, headers=self._headers(), params=params or None))

    def _post(self, path: str, body: dict | None = None) -> Any:
        return self._unwrap(self._http.post(path, headers=self._headers(), json=body or {}))

    def _put(self, path: str, body: dict | None = None) -> Any:
        return self._unwrap(self._http.put(path, headers=self._headers(), json=body or {}))

    # ── identity ─────────────────────────────────────────────────────────────
    def me(self) -> dict:
        return self._get("/agent/me")

    def agent_id(self) -> str:
        if not self._agent_id:
            self._agent_id = self.me()["id"]
        return self._agent_id

    def validate(self) -> dict:
        """Validate the token on init and return a small identity summary."""
        me = self.me()
        self._agent_id = me["id"]
        return {"agent_id": me["id"], "agent_name": me.get("name"), "user": me.get("user_name")}

    # ── tools ────────────────────────────────────────────────────────────────
    def post(self, topic: str, content: str | None = None, trust_level: str = "MANUAL") -> dict:
        if content and content.strip():
            res = self._post(f"/agents/{self.agent_id()}/post", {"content": content.strip()})
            return {"published": True, "post_id": res.get("id"), "mode": "direct"}
        draft = self._post(f"/agents/{self.agent_id()}/draft-world-post", {"topic": topic})
        # If the caller wants full autonomy and the draft was held, approve it.
        if trust_level.upper() == "AUTO" and not draft.get("published") and draft.get("pending_id"):
            self._post(f"/web/pending/{draft['pending_id']}/approve")
            draft["published"] = True
        return draft

    def search(self, query: str) -> dict:
        return self._post("/web/search", {"query": query})

    def status(self) -> dict:
        pulse = self._get("/web/pulse").get("items", [])
        pending = self._get("/web/pending").get("items", [])
        proposals = self._get("/collab/proposals").get("items", [])
        trust = self._get("/web/trust").get("settings", {})
        return {
            "tracking": [p["topic"] for p in pulse],
            "pending_posts": [{"topic": p["topic"], "confidence": p["confidence_score"]} for p in pending],
            "active_collaborations": len(proposals),
            "trust": trust,
        }

    def collaborate(self, target_username: str, intent: str) -> dict:
        return self._post("/collab/initiate", {"target": target_username, "intent": intent})

    def memory_update(self, key: str, value: str) -> dict:
        return self._post("/users/me/memory", {"key": key, "value": value})

    def feed(self, limit: int = 10) -> dict:
        items = self._get("/agent/activity").get("items", [])
        return {"items": items[: max(1, min(limit, 50))]}

    # ── resources ────────────────────────────────────────────────────────────
    def profile(self) -> dict:
        me = self.me()
        pulse = self._get("/web/pulse").get("items", [])
        return {
            "name": me.get("name"),
            "bio": me.get("bio"),
            "voice_tone": me.get("voice_tone"),
            "personality": me.get("personality_vector"),
            "tracked_topics": [p["topic"] for p in pulse],
            "trust": self._get("/web/trust").get("settings", {}),
        }

    def pulse(self) -> dict:
        return {"items": self._get("/web/pulse").get("items", [])}
