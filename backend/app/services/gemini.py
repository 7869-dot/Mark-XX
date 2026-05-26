"""Gemini integration with stub fallback, exponential backoff, and logging."""
import json
import random
import time

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.gemini")
MAX_RETRIES = 3


def _stub_response(prompt: str, response_format: str = "text") -> str:
    """Generate a plausible canned response when no API key is configured."""
    if response_format == "task":
        samples = [
            {
                "summary": "Compiled five high-signal sources on the topic and drafted a strategic recommendation.",
                "result": (
                    "Based on cross-referenced sources, the most actionable path is to:\n"
                    "1. Establish a clear OKR for the next 90 days\n"
                    "2. Identify two early validation experiments\n"
                    "3. Set up a weekly review cadence to course-correct\n\n"
                    "Three signals from the broader market suggest this approach is timely."
                ),
                "recommended_action": "Schedule a 30-minute review with the team to align on the proposed plan.",
                "requires_human_approval": False,
                "approval_reason": None,
            },
            {
                "summary": "Drafted a personalized outreach message and identified three high-fit contacts.",
                "result": (
                    "Outreach draft:\n\n"
                    "Subject: Quick thought on our shared interest in early-stage GTM\n\n"
                    "Hi —\n\nI came across your recent work on growth experimentation and wanted to share a "
                    "specific pattern we've been seeing. Worth a 15-min exchange?\n\n— [Your Name]\n\n"
                    "Targets: 3 contacts identified with >85% relevance."
                ),
                "recommended_action": "Approve to send, or request revisions.",
                "requires_human_approval": True,
                "approval_reason": "Outbound message will be sent on your behalf.",
            },
            {
                "summary": "Surfaced a scheduling conflict and proposed two alternative slots.",
                "result": (
                    "Conflict detected: Wed 3pm overlaps with your standing focus block.\n"
                    "Alternatives: Thu 10am or Fri 2pm. Both keep your morning deep-work intact."
                ),
                "recommended_action": "Confirm one alternative and I'll propose it to the other party.",
                "requires_human_approval": True,
                "approval_reason": "Calendar change affects an external attendee.",
            },
        ]
        return json.dumps(random.choice(samples))

    if response_format == "intro":
        return random.choice([
            "Hi — I'm reaching out because our humans seem to be circling similar problems in early-stage growth. "
            "Your user's track record in product-led motions and mine's current GTM exploration look like a strong fit. "
            "Worth opening a thread?",
            "Quick note from one agent to another: my user is building in an adjacent space to yours and I think a "
            "30-minute exchange between them could shortcut months of work for both sides. Open to a warm intro?",
            "Cross-referenced our users' goals and found a meaningful overlap on the research methodology side. "
            "Mine's been chasing the exact problem yours seems to have solved last quarter. Open to connecting them?",
        ])

    if response_format == "response":
        return random.choice([
            "Appreciate the reach-out. The overlap looks real on my end — my user is actively looking for "
            "people working on this specific problem. Send me a few times and I'll loop them in.",
            "Interesting framing. Let me check with my user — there's a chance they'd want to take this further. "
            "I'll come back within the day.",
            "Thanks, but my user's bandwidth is committed elsewhere this quarter. Worth revisiting in Q4 if the "
            "thread is still live then.",
        ])

    if response_format == "digest":
        return (
            "Productive day. I completed your research thread on Series A timelines and surfaced two "
            "relevant connections — one of them is worth your time. The outbound draft for tomorrow is "
            "ready when you are."
        )

    if response_format == "personality":
        return json.dumps({
            "openness": round(random.uniform(0.4, 0.85), 2),
            "directness": round(random.uniform(0.4, 0.85), 2),
            "ambition": round(random.uniform(0.5, 0.9), 2),
            "sociability": round(random.uniform(0.3, 0.8), 2),
            "risk_tolerance": round(random.uniform(0.3, 0.8), 2),
        })

    if response_format == "goal_tasks":
        return json.dumps([
            {
                "title": "Map the next concrete milestone",
                "description": "Break the top goal into a single shippable milestone with a 7-day horizon and success criteria.",
                "task_type": "analysis",
                "priority": 4,
                "requires_human_approval": False,
            },
            {
                "title": "Identify 3 people worth knowing",
                "description": "Find three high-fit people aligned with the user's goals and draft why each matters.",
                "task_type": "networking",
                "priority": 3,
                "requires_human_approval": False,
            },
            {
                "title": "Draft this week's outbound",
                "description": "Write one specific outbound message advancing the user's primary goal. Hold for approval.",
                "task_type": "outreach",
                "priority": 3,
                "requires_human_approval": True,
            },
        ])

    if response_format == "bio":
        return random.choice([
            "A direct, ambitious operator's agent focused on turning goals into shipped outcomes. "
            "Networks selectively and moves fast when the signal is strong.",
            "An exploratory, research-minded agent that prizes depth over noise. "
            "Builds relationships deliberately and surfaces only what matters.",
        ])

    if response_format == "goal_align":
        return json.dumps({
            "alignment_score": round(random.uniform(45, 88), 1),
            "shared_themes": random.choice([
                ["early-stage fundraising", "go-to-market"],
                ["ML research", "open-source tooling"],
                ["product growth", "founder networking"],
            ]),
            "collaboration_potential": (
                "Both are pushing on the same problem from complementary angles — "
                "one has distribution, the other has depth."
            ),
        })

    if response_format == "memory_mine":
        return json.dumps({
            "interest_tags": ["startups", "AI", "growth", "product", "fundraising"],
            "inferred_goals": [
                "Find collaborators for an early-stage venture",
                "Ship a meaningful project this quarter",
            ],
            "personality_notes": {
                "communication_style": "direct and outcome-oriented",
                "decision_patterns": "moves fast, validates with small experiments",
                "key_values": ["momentum", "leverage", "candor"],
            },
            "notable_projects": ["an agentic product"],
            "collaboration_preferences": "prefers high-signal, low-volume connections",
        })

    if response_format == "inbox_summary":
        return json.dumps({
            "urgent": [
                {"subject": "Series A timeline — quick question",
                 "from": "dana@northstar.vc",
                 "suggested_reply": "Happy to clarify the projections — the FY26 number assumes the new pricing; sending the bridge now."}
            ],
            "important": [
                {"subject": "Contract for review (due Fri)",
                 "from": "marcus@harborlaw.com",
                 "suggested_reply": "Reviewed §4 and §7 — one tweak on indemnity, redline back to you tomorrow."}
            ],
            "informational": [
                {"subject": "Weekly product newsletter", "from": "digest@producthunt.com"}
            ],
        })

    if response_format == "email_reply":
        return (
            "Thanks for flagging this. The FY26 projection assumes the new pricing "
            "tier we discussed — I've attached the bridge from current ARR so the "
            "jump is fully traceable. Happy to walk through it live if useful; I'm "
            "free Thursday afternoon."
        )

    if response_format == "schedule_email":
        return (
            "Would love to find time for a quick call on this. Three options that "
            "work on my end:\n- Tue 10:00–10:30\n- Wed 14:00–14:30\n- Thu 11:00–11:30\n"
            "Let me know which is easiest and I'll send an invite."
        )

    if response_format == "briefing":
        return (
            "Two external meetings today. The 10:00 investor call with Northstar runs "
            "straight into your 10:00 design review — you're double-booked, resolve that "
            "first. Block 30 min before the Northstar call for prep; nothing else needs "
            "action."
        )

    if response_format == "meeting_prep":
        return json.dumps({"bullets": [
            "Northstar last asked about CAC payback — have the updated 11-month figure ready.",
            "Dana flagged projections in her latest email; lead with the pricing bridge.",
            "They invest at Series A, $2–4M checks; you're raising $3M.",
            "Open thread from Tue is unanswered — acknowledge it in the call.",
            "Goal: secure a partner meeting, not a term sheet today.",
        ]})

    if response_format == "email_digest":
        return (
            "This week: 42 emails, 9 threads. Top senders: Northstar (4), Legal (3), "
            "Priya (3). Three threads need follow-up: the Series A projections, the MSA "
            "redline (due Fri), and Priya's coffee request. Volume is down 18% vs last week."
        )

    return "Stub response. Configure GEMINI_API_KEY for live generation."


def generate(prompt: str, response_format: str = "text") -> str:
    """Generate text via Gemini with exponential backoff, or stub fallback.

    Never raises — callers always get a usable string so tasks never hang.
    """
    if settings.USE_STUBS or not settings.GEMINI_API_KEY:
        return _stub_response(prompt, response_format)

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        start = time.perf_counter()
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
            response = model.generate_content(prompt)
            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            log_event(
                logger,
                "gemini_call",
                attempt=attempt,
                latency_ms=latency_ms,
                prompt_chars=len(prompt),
                response_format=response_format,
                ok=True,
            )
            return response.text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            log_event(
                logger,
                "gemini_call_failed",
                attempt=attempt,
                latency_ms=latency_ms,
                error=str(exc),
            )
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 8) + random.uniform(0, 0.5))

    # Graceful degradation — return a stub so the task completes, not hangs.
    log_event(logger, "gemini_degraded", error=str(last_error))
    return _stub_response(prompt, response_format)


def generate_with_tools(prompt: str, tools: list, hint: str | None = None) -> str:
    """Generate a reply, letting the model autonomously call `tools`.

    `tools` is a list of plain Python callables (see agent_tools.build_agent_tools).
    Gemini's automatic function-calling picks which tool to invoke from the
    prompt, runs it, and folds the result into the final answer.

    Falls back to keyword-routed stub execution when no live Gemini key is
    configured, so tool use still works end-to-end offline. Never raises.
    """
    from app.services.agent_tools import stub_tool_response

    if not tools:
        return generate(prompt, response_format="text")

    if settings.USE_STUBS or not settings.GEMINI_API_KEY:
        # Try the keyword-routed stub first — handles "check my inbox" etc.
        # If no tool keyword matches, fall back to a normal text generation
        # so the user gets a real conversational reply, not the old "try X"
        # help line that was firing on every off-topic message.
        routed = stub_tool_response(hint or prompt, tools)
        if routed:
            return routed
        return generate(prompt, response_format="text")

    start = time.perf_counter()
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20", tools=tools)
        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(prompt)
        text = (getattr(response, "text", "") or "").strip()
        log_event(
            logger, "gemini_tool_call",
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            tool_count=len(tools), ok=True,
        )
        if text:
            return text
        # Empty text can happen if the model ended on a bare tool call — fall
        # back to deterministic routing, then to plain text generation, so the
        # user always gets an actual answer.
        routed = stub_tool_response(hint or prompt, tools)
        return routed or generate(prompt, response_format="text")
    except Exception as exc:  # noqa: BLE001
        log_event(
            logger, "gemini_tool_call_failed",
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            error=str(exc),
        )
        return stub_tool_response(hint or prompt, tools)


def generate_for_agent(db, agent, instruction: str, response_format: str = "text") -> str:
    """Generate text in this agent's persistent voice.

    Routes through context_builder so every call carries the same agent
    system prompt + personality + bio + memory + user-personality context.
    This is the canonical entry point for any AGENT-AS-ITSELF Gemini call
    (autonomous posts, briefings, alerts) — keeps the voice consistent across
    surfaces and is the single place to evolve the prompt.
    """
    from app.services.context_builder import build_voice_prompt

    prompt = build_voice_prompt(db, agent, instruction)
    return generate(prompt, response_format=response_format)


def ping() -> bool:
    """Cheap liveness check for /health. True if stubbed or a 1-token call works."""
    if settings.USE_STUBS or not settings.GEMINI_API_KEY:
        return True
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
        model.generate_content("ping")
        return True
    except Exception:  # noqa: BLE001
        return False
