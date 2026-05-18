"""The brain of A2A discovery — weighted personality + Gemini goal alignment + tags."""
import json
import math

from app.models import Agent
from app.prompts.templates import GOAL_ALIGNMENT
from app.services.gemini import generate
from app.core.logging import get_logger

logger = get_logger("axolot.compatibility")

KEYS = ["openness", "directness", "ambition", "sociability", "risk_tolerance"]


def personality_compatibility(vec_a: dict, vec_b: dict) -> float:
    """Weighted personality compatibility 0-100 (NOT raw cosine).

    - ambition × ambition and sociability × sociability: high-with-high amplifies
      (multiplicative bonus)
    - directness, openness: similarity rewarded (small distance is good)
    - risk_tolerance: complementarity rewarded (one bold + one cautious = good team)
    """
    a = {k: float(vec_a.get(k, 0.5)) for k in KEYS}
    b = {k: float(vec_b.get(k, 0.5)) for k in KEYS}

    # Base raw cosine over the 5 dims (0..1).
    av = [a[k] for k in KEYS]
    bv = [b[k] for k in KEYS]
    dot = sum(x * y for x, y in zip(av, bv))
    na = math.sqrt(sum(x * x for x in av))
    nb = math.sqrt(sum(x * x for x in bv))
    cosine = dot / (na * nb) if na and nb else 0.0

    # Amplifiers: two driven / two social people reinforce each other.
    ambition_amp = a["ambition"] * b["ambition"]          # 0..1
    sociability_amp = a["sociability"] * b["sociability"]  # 0..1

    # Similarity rewards (1 = identical, 0 = opposite).
    directness_sim = 1.0 - abs(a["directness"] - b["directness"])
    openness_sim = 1.0 - abs(a["openness"] - b["openness"])

    # Complementarity reward for risk: distance is good, capped sensibly.
    risk_complement = abs(a["risk_tolerance"] - b["risk_tolerance"])

    score = (
        cosine * 0.30
        + ambition_amp * 0.20
        + sociability_amp * 0.15
        + directness_sim * 0.15
        + openness_sim * 0.10
        + risk_complement * 0.10
    )
    return round(max(0.0, min(1.0, score)) * 100, 2)


def goal_alignment(goals_a: list, goals_b: list) -> tuple[float, list]:
    """Gemini-scored thematic overlap. Returns (score 0-100, shared_themes)."""
    if not goals_a or not goals_b:
        return 0.0, []
    prompt = GOAL_ALIGNMENT.format(goals_a=goals_a, goals_b=goals_b)
    raw = generate(prompt, response_format="goal_align")
    try:
        data = json.loads(raw)
        score = float(data.get("alignment_score", 0.0))
        themes = data.get("shared_themes", []) or []
        return round(max(0.0, min(100.0, score)), 2), list(themes)
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0.0, []


def tag_overlap_score(tags_a: list, tags_b: list) -> float:
    """Jaccard similarity × 100."""
    sa = {str(t).strip().lower() for t in (tags_a or []) if str(t).strip()}
    sb = {str(t).strip().lower() for t in (tags_b or []) if str(t).strip()}
    if not sa or not sb:
        return 0.0
    return round(len(sa & sb) / len(sa | sb) * 100, 2)


def _goal_titles(agent: Agent) -> list:
    return agent.goal_titles if hasattr(agent, "goal_titles") else []


def compute_compatibility(agent_a: Agent, agent_b: Agent) -> dict:
    personality = personality_compatibility(
        agent_a.personality_vector or {}, agent_b.personality_vector or {}
    )
    goal_score, shared_goals = goal_alignment(_goal_titles(agent_a), _goal_titles(agent_b))
    tag_score = tag_overlap_score(agent_a.interest_tags or [], agent_b.interest_tags or [])

    final_score = personality * 0.35 + goal_score * 0.45 + tag_score * 0.20

    if shared_goals:
        reason = (
            f"Strong alignment on {shared_goals[0]} with "
            f"{'complementary' if personality < 70 else 'closely matched'} working styles"
        )
    elif tag_score > 0:
        reason = "Overlapping interests and compatible working styles"
    else:
        reason = "Complementary personalities worth a low-stakes introduction"

    return {
        "score": round(final_score, 2),
        "breakdown": {
            "personality": personality,
            "goal_alignment": goal_score,
            "tag_overlap": tag_score,
        },
        "shared_goals": shared_goals,
        "reason": reason,
    }
