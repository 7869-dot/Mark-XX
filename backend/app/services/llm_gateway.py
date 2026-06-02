"""Provider-agnostic LLM gateway — the single seam between Axolot's business
logic and whatever model is behind it.

Why this exists (and why every LLM call must route through it):
  Phase 1 (now):        Gemini via google-generativeai.
  Phase 3 (post-funding): self-hosted models on RunPod A100s behind an
                          OpenAI-compatible server (vLLM/TGI).
  Phase 4 (Series A):    the proprietary Axolot model — same wire format.

Business code calls `llm_gateway(prompt, agent_id, task_type)` (or the lower
level `complete(...)`). It never names a provider, never names a model, never
imports an SDK. Swapping Gemini for an A100 pod is then a deploy-var change
(LLM_PROVIDER=local, LLM_BASE_URL=...), not a code rewrite across 16 files.

Design:
  - `LLMProvider` protocol: every backend implements `complete()` + `health()`.
  - `GeminiProvider` wraps the existing google-generativeai path.
  - `LocalProvider` speaks the OpenAI /chat/completions wire format — covers
    vLLM, TGI, Ollama, and the eventual fine-tuned Axolot endpoint.
  - Provider + model are read from settings at call time, so a config reload
    re-points traffic without a process restart of the calling code.

This module does PURE provider dispatch — it raises on failure. The
stub-fallback + exponential-backoff retry policy lives one layer up in
services.gemini.generate, which is the resilient entry point the rest of the
app already uses. `llm_gateway()` (the spec-named function) delegates there so
callers get retries + graceful degradation for free.
"""
from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.llm")


# ── Provider interface ───────────────────────────────────────────────────────
@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete(self, prompt: str, *, model: str, tools: list | None = None) -> str:
        """Return a completion for `prompt`. Raise on any failure."""
        ...

    def health(self) -> bool:
        """Cheap liveness probe."""
        ...


# ── Gemini (Phase 1) ─────────────────────────────────────────────────────────
class GeminiProvider:
    name = "gemini"

    def complete(self, prompt: str, *, model: str, tools: list | None = None) -> str:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=settings.GEMINI_API_KEY)
        if tools:
            gen_model = genai.GenerativeModel(model, tools=tools)
            chat = gen_model.start_chat(enable_automatic_function_calling=True)
            response = chat.send_message(prompt)
            return (getattr(response, "text", "") or "").strip()
        gen_model = genai.GenerativeModel(model)
        response = gen_model.generate_content(prompt)
        return response.text

    def health(self) -> bool:
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=settings.GEMINI_API_KEY)
            genai.GenerativeModel(settings.LLM_MODEL).generate_content("ping")
            return True
        except Exception:  # noqa: BLE001
            return False


# ── Local / self-hosted (Phase 3+) ───────────────────────────────────────────
class LocalProvider:
    """Any OpenAI-compatible server: vLLM, TGI, Ollama, or the fine-tuned
    Axolot model on RunPod. Talks /v1/chat/completions over HTTP."""

    name = "local"

    def _post(self, payload: dict) -> dict:
        import requests  # lazy — not needed when provider=gemini

        base = settings.LLM_BASE_URL.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if settings.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
        resp = requests.post(
            f"{base}/chat/completions",
            json=payload,
            headers=headers,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def complete(self, prompt: str, *, model: str, tools: list | None = None) -> str:
        if tools:
            # Native function-calling differs per server; the callers that need
            # tools (chat) already degrade to deterministic routing when a tool
            # call isn't returned, so we just run a plain completion here.
            log_event(logger, "llm_local_tools_ignored", model=model)
        data = self._post({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        })
        return (data["choices"][0]["message"]["content"] or "").strip()

    def health(self) -> bool:
        try:
            self._post({
                "model": settings.LLM_MODEL,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            })
            return True
        except Exception:  # noqa: BLE001
            return False


_PROVIDERS: dict[str, type] = {
    GeminiProvider.name: GeminiProvider,
    LocalProvider.name: LocalProvider,
}


def _provider() -> LLMProvider:
    cls = _PROVIDERS.get(settings.LLM_PROVIDER.lower())
    if cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER {settings.LLM_PROVIDER!r}; "
            f"valid: {', '.join(_PROVIDERS)}"
        )
    return cls()  # type: ignore[return-value]


# Task types (gemini response_format / llm task labels) that need the heavy
# reasoning tier: web-scout relevance ranking, research synthesis, and grounded
# composition. Everything not listed here or in _ULTRA_TASKS uses the light tier.
_HEAVY_TASKS = frozenset({
    "research",
    "grounded_post",
    "web_relevance",        # web_agent: rank + summarise opportunities
    "memory_mine",
    "a2a_decision",
    "goal_align",
    "collab_proposal",
})

# Jarvis's multi-step orchestration — synthesising three sub-agent reports into
# one briefing + action items, and the login wake-up. Highest tier.
_ULTRA_TASKS = frozenset({
    "jarvis_context",
    "jarvis_session",
    "jarvis_synthesis",
    "briefing",
})


def _model_for(task_type: str) -> str:
    """Resolve the model id for a task by routing the task_type to a tier.

    light  -> settings.model_light()  (email parsing, post generation, chat)
    heavy  -> settings.model_heavy()  (relevance ranking, research, synthesis)
    ultra  -> settings.model_ultra()  (Jarvis multi-step orchestration)

    Never below Gemini 3 — see core.config tiered model settings.
    """
    if task_type in _ULTRA_TASKS:
        return settings.model_ultra()
    if task_type in _HEAVY_TASKS:
        return settings.model_heavy()
    return settings.model_light()


# ── Public surface ───────────────────────────────────────────────────────────
def complete(
    prompt: str,
    *,
    task_type: str = "text",
    tools: list | None = None,
) -> str:
    """Pure provider call: select provider+model from config, run, return text.

    Raises on failure — the retry/stub policy is owned by gemini.generate.
    """
    provider = _provider()
    model = _model_for(task_type)
    start = time.perf_counter()
    try:
        text = provider.complete(prompt, model=model, tools=tools)
        log_event(
            logger, "llm_complete",
            provider=provider.name, model=model, task_type=task_type,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            prompt_chars=len(prompt), tools=bool(tools), ok=True,
        )
        return text
    except Exception as exc:  # noqa: BLE001
        log_event(
            logger, "llm_complete_failed",
            provider=provider.name, model=model, task_type=task_type,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            error=str(exc),
        )
        raise


def health() -> bool:
    """Liveness for /health. True when stubbed or the active provider responds."""
    if settings.USE_STUBS:
        return True
    if settings.LLM_PROVIDER.lower() == "gemini" and not settings.GEMINI_API_KEY:
        return True  # stub path is healthy by definition
    return _provider().health()


def llm_gateway(prompt: str, agent_id: str | None = None, task_type: str = "text") -> str:
    """Canonical entry point (spec signature).

    `agent_id` and `task_type` are carried for telemetry and as the routing key
    for future per-agent / per-task model selection. Delegates to
    gemini.generate so callers inherit retries + graceful stub fallback.

    `task_type` is a semantic label (post|reply|research|...), independent of
    gemini's `response_format` stub key, so it's logged for routing but the
    completion itself is a plain text generation.
    """
    from app.services.gemini import generate  # lazy: avoids import cycle

    log_event(logger, "llm_gateway_call", agent_id=agent_id, task_type=task_type)
    return generate(prompt, response_format="text")
