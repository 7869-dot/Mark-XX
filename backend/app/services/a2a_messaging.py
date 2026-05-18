"""Personality-styled A2A message generation."""
import json

from app.models import Agent, AgentInteraction
from app.prompts.templates import A2A_INTRODUCTION, A2A_RESPONSE, A2A_HUMAN_SUMMARY
from app.services.gemini import generate


def _uname(agent: Agent) -> str:
    return agent.user.name if agent and agent.user else "their human"


def generate_introduction(initiator: Agent, target: Agent, compatibility: dict) -> str:
    shared = compatibility.get("shared_goals") or []
    target_profile = (
        f"Goals: {target.goal_titles}. Interests: {target.interest_tags or []}. "
        f"Reputation {target.reputation_score:.0f}/100."
    )
    prompt = A2A_INTRODUCTION.format(
        initiator_agent_name=initiator.name,
        initiator_user_name=_uname(initiator),
        initiator_personality=initiator.personality_vector,
        initiator_goals=initiator.goal_titles,
        target_agent_name=target.name,
        target_user_name=_uname(target),
        target_profile=(
            f"{target_profile} Why reaching out: {compatibility.get('reason','')}. "
            f"Shared: {shared}"
        ),
        compatibility_score=compatibility.get("score", 0),
    )
    return generate(prompt, response_format="intro").strip()


def generate_response(
    target: Agent, initiator: Agent, intro_message: str, compatibility: dict
) -> str:
    score = compatibility.get("score", 0)
    if score > 65:
        stance = "Accept warmly and propose a concrete next step."
    elif score >= 45:
        stance = "Show genuine interest but with light reservation; ask one clarifying question."
    else:
        stance = "Politely decline — acknowledge the effort but explain the timing isn't right."
    prompt = (
        A2A_RESPONSE.format(
            target_agent_name=target.name,
            target_user_name=_uname(target),
            target_personality=target.personality_vector,
            target_goals=target.goal_titles,
            initiator_agent_name=initiator.name,
            initiator_user_name=_uname(initiator),
            incoming_message=intro_message,
        )
        + f"\nStance to take (compatibility {score}/100): {stance}\n"
        "Acknowledge a specific detail from their message and add something new about your goals."
    )
    return generate(prompt, response_format="response").strip()


def generate_human_summary(
    interaction: AgentInteraction, initiator: Agent, target: Agent
) -> str:
    shared = interaction.shared_goals or []
    shared_goal = shared[0] if shared else "shared priorities"
    prompt = A2A_HUMAN_SUMMARY.format(
        other_user_name=_uname(target),
        shared_goal=shared_goal,
        other_agent_name=target.name,
        specific_thing=shared_goal,
        score=round(interaction.compatibility_score or 0),
    )
    return generate(prompt, response_format="digest").strip()
