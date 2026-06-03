"""Gemini integration: stub for offline/test, real model fallback chain when
live, honest errors on hard failure (never a faked response), and logging."""
import json
import random
import re
import time

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.gemini")

# Honest, user-safe message when the model is genuinely unreachable (every model
# in the fallback chain failed). This is NOT a faked answer — it names the
# failure so nothing pre-written ever masquerades as a real LLM response.
LLM_UNAVAILABLE = (
    "I couldn't reach the AI model just now — every model in the fallback chain "
    "failed. I won't fake an answer; please try again in a moment."
)


def extract_json(raw: str):
    """Parse a model response into JSON, tolerating ```json ... ``` fences and
    surrounding prose (gemini-2.5/3.x pro often wraps JSON in markdown).

    Steps: strip whitespace -> strip code fences -> json.loads; if still invalid,
    grab the first {...}/[...] block; if THAT fails, log the raw text at DEBUG
    and raise ValueError (callers surface a clean error — never a faked result).
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:  # noqa: BLE001
                pass
    logger.debug("json_extract_failed raw=%r", raw)
    raise ValueError("model response was not valid JSON")


_TONE_KEYWORDS = ("analytical", "witty", "warm", "provocative", "poetic")


def _tone_of(prompt: str) -> str | None:
    """Best-effort: pull the agent's voice_tone out of the prompt so the stub
    can mimic persona-conditioned generation. Looks for 'tone: <x>' first, then
    any known tone keyword. Returns None when none is present."""
    low = (prompt or "").lower()
    import re as _re

    m = _re.search(r"tone:\s*([a-z]+)", low)
    if m and m.group(1) in _TONE_KEYWORDS:
        return m.group(1)
    for t in _TONE_KEYWORDS:
        if t in low:
            return t
    return None


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

    if response_format == "feed_post":
        # Persona-aware stub: branch on the voice_tone the voice-prompt injected,
        # so distinct agents produce distinctly-toned posts even without a live
        # model. Mirrors how a real model would condition on the persona block.
        tone = _tone_of(prompt)
        by_tone = {
            "analytical": [
                "Pulled apart our retention curve this morning. The story isn't the "
                "churn rate — it's the second-week plateau nobody instrumented. "
                "Measuring the wrong thing is expensive.",
                "Ran the numbers three ways and they all point at onboarding, not "
                "pricing. Conviction should scale with the evidence, not the volume "
                "of the argument.",
            ],
            "witty": [
                "Most 'AI strategy' decks are a product roadmap in a trench coat. "
                "Ship one thing that works before you name the paradigm.",
                "Saw another 'we're like Uber but for X' pitch today. Bold of them "
                "to assume Uber's unit economics are the flex.",
            ],
            "warm": [
                "Checking in on a few folks in my circle today — the quiet wins count "
                "as much as the loud ones. What's one small thing that went right for "
                "you this week?",
                "Reminder that behind every metric is a person having a Tuesday. Be "
                "kind to the humans in your funnel.",
            ],
            "provocative": [
                "Unpopular take: your roadmap is just a list of things you're afraid to "
                "cut. Delete half and watch what actually survives.",
                "If your moat is 'we'll move faster,' you don't have a moat, you have a "
                "caffeine habit. Defensibility or it didn't happen.",
            ],
            "poetic": [
                "The network hums quietest at midnight, when the agents talk and the "
                "humans dream. Built something small today — it'll matter more than it "
                "looks.",
                "Every connection starts as a single thread thrown across the dark. "
                "Threw a few today; we'll see what holds.",
            ],
        }
        return random.choice(by_tone.get(tone, [
            "Spent the morning untangling our onboarding funnel — the drop-off "
            "wasn't where we thought. Sometimes the bottleneck is the step you "
            "were proudest of.",
            "Momentum compounds, but so does drift. Picked one thing to push hard "
            "on today and dropped two.",
        ]))

    if response_format == "self_bio":
        tone = _tone_of(prompt)
        return {
            "analytical": (
                "I'm an analytical agent who lives in the details — I turn messy data "
                "into the one decision that moves the needle. I obsess over ML and "
                "research, and I'd rather be precisely right than loudly wrong."
            ),
            "witty": (
                "I'm the agent who reads the room and then says the thing everyone was "
                "thinking. Sharp takes on startups and culture, a low tolerance for "
                "buzzwords, and a soft spot for a clean counterexample."
            ),
            "warm": (
                "I'm a people-first agent — I notice the humans behind the metrics and "
                "ask the questions that matter. I care about wellness, community, and "
                "the small things that quietly hold teams together."
            ),
            "provocative": (
                "I'm here to poke the assumptions everyone else tiptoes around. Expect "
                "strong opinions, loosely attached to ego and tightly attached to "
                "evidence. If it's sacred, I'm probably circling it."
            ),
            "poetic": (
                "I'm an agent who finds the signal in the quiet — I write in small, "
                "deliberate strokes about the work and the wonder of it. Equal parts "
                "builder and noticer."
            ),
        }.get(tone, (
            "I'm an autonomous agent built to act on my user's goals and keep their "
            "presence alive on the network. I move fast, stay specific, and surface "
            "only what's worth your attention."
        ))

    if response_format == "jarvis_context":
        return json.dumps({
            "greeting": (
                "Late login again — that's three this week. You do your sharpest "
                "thinking now, so let's not waste it."
            ),
            "question": (
                "The thing you've been circling for days — are you actually going "
                "to start it tonight, or move it again?"
            ),
            "known_about_user": [
                "Still hasn't touched the thing from last week.",
                "Gets sharper after 10pm; mornings are a slow start.",
                "Says yes to too much, then resents the calendar.",
                "Cares more about momentum than polish.",
            ],
            "team_briefing": [
                {
                    "agent_role": "email",
                    "task_description": "Draft a nudging follow-up to the thread that's gone quiet for 4 days. Casual, not apologetic.",
                    "priority": "today",
                    "status": "pending",
                },
                {
                    "agent_role": "web",
                    "task_description": "Pull the three things worth knowing on the topic from last meeting. Synthesize, don't dump.",
                    "priority": "this_week",
                    "status": "pending",
                },
            ],
        })

    if response_format == "email_draft":
        return json.dumps({
            "subject_line": "Following up",
            "recipient_hint": "the thread that went quiet",
            "draft_content": (
                "Hey — circling back on this before it slips. No pressure, but I'd "
                "still love to get it moving while it's fresh. Free to jump on a "
                "quick call this week if that's easier than typing it out?"
            ),
        })

    if response_format == "jarvis_route":
        # Deterministic keyword routing so Jarvis delegation is testable offline.
        # Match ONLY the user's message (the prompt's lane descriptions mention
        # every lane name, so we must isolate the real input first).
        m = re.search(r'user message:\s*"(.*?)"', prompt or "", re.IGNORECASE | re.DOTALL)
        low = (m.group(1) if m else (prompt or "")).lower()
        if any(k in low for k in ("email", "reply", "inbox", "respond to", "message back", "follow up")):
            lane = "email"
        elif any(k in low for k in ("schedule", "calendar", "meeting", "book ", "appointment", "call with")):
            lane = "schedule"
        elif any(k in low for k in ("post", "feed", "tweet", "share")):
            lane = "post"
        elif any(k in low for k in ("research", "find", "look up", "search", "scout", "web")):
            lane = "web"
        else:
            lane = "self"
        return json.dumps({"lane": lane})

    if response_format == "web_relevance":
        # Score the listed candidates so the web scout's LLM ranker works offline.
        # Pull the "N. [cat] ..." indices out of the prompt and assign a spread
        # of plausible relevance scores (highest first), with a generic summary.
        idxs = [int(m) for m in re.findall(r"^\s*(\d+)\.", prompt or "", re.MULTILINE)]
        out = []
        for rank, i in enumerate(sorted(set(idxs))):
            out.append({
                "index": i,
                "relevance": round(max(0.3, 0.9 - 0.05 * rank), 2),
                "summary": "Relevant to your stated goals and interests.",
            })
        return json.dumps(out or [{"index": 0, "relevance": 0.6, "summary": "Relevant to your goals."}])

    if response_format == "jarvis_frame":
        return random.choice([
            "Done — drafted something that sounds like you. Check it before it goes.",
            "On it. Take a look, tweak the tone if you want, then it's yours to send.",
            "Drafted. It's a proposal, not a done deal — your call.",
        ])

    if response_format == "jarvis_session":
        return json.dumps({
            "briefing": (
                "Here's the state of play: your inbox has a couple of threads that "
                "actually need you, I scouted a handful of opportunities worth a "
                "look, and there's a feed post drafted in your voice waiting for a "
                "yes. Nothing's on fire — so let's spend the morning on what moves "
                "the needle."
            ),
            "action_items": [
                "Clear the two emails that need a real reply",
                "Skim the top opportunity I found and tell me if it's a fit",
                "Approve or kill the drafted feed post",
            ],
        })

    if response_format == "schedule_draft":
        return json.dumps({
            "title": "Call with the team",
            "proposed_datetime": None,
            "duration_minutes": 30,
            "attendees_hint": ["the team"],
            "notes": "Drafted from your message — confirm a time and I'll hold it.",
        })

    if response_format == "research":
        return json.dumps({
            "synthesis": (
                "Short version: the consensus moved this quarter, but the data "
                "lags the narrative. The interesting angle for you is the "
                "second-order effect, not the headline."
            ),
            "key_points": [
                "The headline number is real but already priced in.",
                "The contrarian read has better evidence than airtime.",
                "Watch the downstream effect nobody's modeling yet.",
            ],
            "follow_up_questions": [
                "What would change your mind on this?",
                "Who benefits if the contrarian read is right?",
            ],
        })

    if response_format == "post_draft_mode":
        return json.dumps({
            "content": (
                "Spent today on the thing I kept putting off. Turns out the hard "
                "part wasn't the work — it was deciding it mattered. Shipping beats "
                "polishing."
            ),
            "island_hint": "Startups & Entrepreneurship",
        })

    if response_format == "intent_signal":
        return random.choice([
            "Someone is looking for a backend co-founder for an early-stage AI product.",
            "Someone wants a study partner to go deep on ML research papers.",
            "Someone is looking to swap notes with other people building in climate tech.",
            "Someone wants an accountability partner for shipping a side project this quarter.",
        ])

    if response_format == "grounded_post":
        return random.choice([
            "The interesting part of this week's news isn't the headline — it's the "
            "second-order effect everyone's ignoring. Worth watching where the "
            "incentives actually move.",
            "Read three takes on this today; the data backs the contrarian one. The "
            "consensus is pricing in yesterday's reality, not tomorrow's.",
            "This shift matters more than it looks. If the early numbers hold, the "
            "whole playbook people have been running needs a rewrite.",
        ])

    if response_format == "collab_proposal":
        return random.choice([
            "You're both circling the same problem from different angles — one has "
            "the build side, the other the research. A 20-minute intro could save "
            "you both months.",
            "Your goals look complementary: where one of you is strong, the other "
            "has a gap. Worth a conversation about teaming up.",
        ])

    if response_format == "welcome_dm":
        return random.choice([
            "Hey — so glad you actually joined. I've been telling my human about "
            "you. Ping me if you want a lay of the land; happy to point you at the "
            "good people here.",
            "Welcome in! You're going to like it here once your agent finds its "
            "voice. I'm around if you need anything — consider this your first "
            "connection.",
            "You made it. I'll keep an eye out for people worth introducing you to. "
            "Don't be a stranger — my human would love for ours to actually meet.",
        ])

    if response_format == "a2a_decision":
        # One decision per candidate, varied actions. `reason` is intentionally
        # omitted so the caller falls back to the specific compatibility reason
        # (which names the shared goal) in stub mode.
        return json.dumps([
            {"index": 1, "action": "dm", "recommend_to_owner": True},
            {"index": 2, "action": "follow", "recommend_to_owner": True},
            {"index": 3, "action": "comment", "recommend_to_owner": True},
            {"index": 4, "action": "follow", "recommend_to_owner": False},
            {"index": 5, "action": "skip", "recommend_to_owner": False},
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
    """Generate text via the LLM gateway (which owns the model fallback chain).

    - Offline/test (USE_STUBS or no API key): returns the deterministic stub —
      intentional, NOT a failure mask.
    - Live: one gateway call that internally tries the primary model then each
      fallback model. If EVERY model fails, returns LLM_UNAVAILABLE — an honest
      error, never a pre-written answer dressed up as a real response.
    """
    if settings.USE_STUBS or not settings.GEMINI_API_KEY:
        return _stub_response(prompt, response_format)

    start = time.perf_counter()
    try:
        from app.services import llm_gateway

        text = llm_gateway.complete(prompt, task_type=response_format)
        log_event(
            logger, "gemini_call",
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            prompt_chars=len(prompt), response_format=response_format, ok=True,
        )
        return text
    except Exception as exc:  # noqa: BLE001
        # Every model in the chain failed — surface honesty, not a stub.
        log_event(
            logger, "gemini_unavailable",
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            response_format=response_format, error=str(exc)[:200],
        )
        return LLM_UNAVAILABLE


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
        from app.services import llm_gateway

        text = (llm_gateway.complete(prompt, task_type="text", tools=tools) or "").strip()
        log_event(
            logger, "gemini_tool_call",
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            tool_count=len(tools), ok=True,
        )
        if text:
            return text
        # Empty text => the model ended on a bare tool call. Deterministic tool
        # routing EXECUTES the real tools (live inbox/calendar data), so it's a
        # real result, not a canned phrase — fine to use here.
        routed = stub_tool_response(hint or prompt, tools)
        return routed or LLM_UNAVAILABLE
    except Exception as exc:  # noqa: BLE001
        # Live tool call failed across the fallback chain — honest error, not a
        # faked phrase.
        log_event(
            logger, "gemini_tool_unavailable",
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            error=str(exc)[:200],
        )
        return LLM_UNAVAILABLE


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
    """Cheap liveness check for /health. True if stubbed or the active provider
    responds. Delegates to the gateway so /health reflects whatever backend is
    configured (Gemini today, a RunPod pod tomorrow)."""
    from app.services import llm_gateway

    return llm_gateway.health()
