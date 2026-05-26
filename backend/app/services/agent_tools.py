"""Gmail + Calendar tools the chat agent can call autonomously.

Each tool is a plain Python callable bound to exactly one (db, user) pair via a
closure. Gemini's automatic function-calling introspects the name, docstring and
type hints to build the function declarations — so the model decides *which*
tool to call from the user's message, and the SDK runs the call loop.

Security: OAuth tokens never leave the server. Tools call gmail_service /
calendar_service, which load Fernet-encrypted tokens from the DB internally —
the model only ever sees the human-readable tool result string.
"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import User
from app.services import calendar_service, gmail_service, google_auth

logger = get_logger("axolot.agent_tools")


def gmail_available(user: User) -> bool:
    """Gmail tools are offered when the user has granted Gmail, or in stub mode."""
    return bool(user.gmail_connected) or google_auth.is_stub()


def calendar_available(user: User) -> bool:
    """Calendar tools are offered when the user has granted Calendar, or in stub mode."""
    return bool(user.calendar_connected) or google_auth.is_stub()


def build_agent_tools(db: Session, user: User) -> list:
    """Return the Gemini-callable tools bound to this user.

    Only tools for connected integrations are included (all are included in
    stub mode so the feature is demoable offline). An empty list means the
    caller should fall back to plain text generation.
    """
    tools: list = []

    # ── Gmail ──────────────────────────────────────────────────────────────
    def list_emails(max_results: int = 10) -> str:
        """List the user's most recent emails. Call this when the user asks to
        check their inbox, see recent mail, or asks if they have new email.

        Args:
            max_results: how many emails to return (1-25).
        """
        log_event(logger, "tool_call", tool="list_emails", user_id=user.id)
        emails = gmail_service.list_emails(
            db, user.id, max_results=max(1, min(int(max_results), 25))
        )
        if not emails:
            return "The inbox is empty."
        return "\n".join(
            f"[{i + 1}] id={e['id']} | {e['subject']} — from {e['sender']} "
            f"({e.get('date', '')}) — {e['snippet'][:140]}"
            for i, e in enumerate(emails)
        )

    def read_email(message_id: str) -> str:
        """Read the full body of one email by its id. Get the id from
        list_emails or search_emails first. Use when the user wants the details
        of a specific email.

        Args:
            message_id: the email id returned by list_emails / search_emails.
        """
        log_event(logger, "tool_call", tool="read_email", user_id=user.id)
        e = gmail_service.get_email(db, user.id, message_id)
        return (
            f"Subject: {e['subject']}\n"
            f"From: {e['sender']} <{e['sender_email']}>\n"
            f"Date: {e.get('date', '')}\n\n"
            f"{(e.get('body_plain') or '').strip()[:3000]}"
        )

    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email on the user's behalf. Only call this once the user has
        clearly confirmed the recipient, subject and body in the conversation.

        Args:
            to: recipient email address.
            subject: email subject line.
            body: plain-text email body.
        """
        log_event(logger, "tool_call", tool="send_email", user_id=user.id)
        message_id = gmail_service.send_email(db, user.id, to, subject, body)
        return f"Email sent to {to} (id={message_id})."

    def search_emails(query: str) -> str:
        """Search the user's mailbox using Gmail search syntax, e.g.
        'from:dana newer_than:7d' or 'subject:invoice'. Returns matching emails.

        Args:
            query: a Gmail search query.
        """
        log_event(logger, "tool_call", tool="search_emails", user_id=user.id)
        emails = gmail_service.search_emails(db, user.id, query)
        if not emails:
            return f"No emails matched '{query}'."
        return "\n".join(
            f"[{i + 1}] id={e['id']} | {e['subject']} — from {e['sender']} "
            f"— {e['snippet'][:120]}"
            for i, e in enumerate(emails)
        )

    # ── Calendar ───────────────────────────────────────────────────────────
    def list_events(days_ahead: int = 7) -> str:
        """List the user's upcoming calendar events. Call this when the user
        asks about their schedule, agenda, or upcoming meetings.

        Args:
            days_ahead: how many days ahead to look (1-60).
        """
        log_event(logger, "tool_call", tool="list_events", user_id=user.id)
        events = calendar_service.list_events(
            db, user.id, days_ahead=max(1, min(int(days_ahead), 60))
        )
        if not events:
            return f"No events in the next {days_ahead} days."
        return "\n".join(
            f"[{i + 1}] id={ev['id']} | {ev['summary']} — {ev['start']} to {ev['end']}"
            + (f" @ {ev['location']}" if ev.get("location") else "")
            for i, ev in enumerate(events)
        )

    def create_event(
        title: str, start_time: str, end_time: str, description: str = ""
    ) -> str:
        """Create a calendar event. Confirm the details with the user first.

        Args:
            title: event title.
            start_time: ISO 8601 datetime, e.g. '2026-06-01T15:00:00'.
            end_time: ISO 8601 datetime, e.g. '2026-06-01T15:30:00'.
            description: optional event description.
        """
        log_event(logger, "tool_call", tool="create_event", user_id=user.id)
        result = calendar_service.create_event(
            db, user.id, title, start_time, end_time, description or None
        )
        return (
            f"Event '{title}' created (id={result['id']}) "
            f"from {start_time} to {end_time}."
        )

    def check_availability(date: str) -> str:
        """Check the user's free time on a date. Returns open slots within
        working hours.

        Args:
            date: the date to check, formatted YYYY-MM-DD.
        """
        log_event(logger, "tool_call", tool="check_availability", user_id=user.id)
        slots = calendar_service.find_free_slots(db, user.id, date)
        if not slots:
            return f"No free slots on {date}."
        return f"Free slots on {date}:\n" + "\n".join(
            f"- {s['start']} to {s['end']}" for s in slots
        )

    if gmail_available(user):
        tools += [list_emails, read_email, send_email, search_emails]
    if calendar_available(user):
        tools += [list_events, create_event, check_availability]
    return tools


def stub_tool_response(hint: str, tools: list) -> str:
    """Offline tool routing.

    When no live Gemini key is available we can't do real function-calling, so
    route by keyword on the user's message. This keeps 'check my email' working
    end-to-end against stub data for local dev, tests and demos.
    """
    by_name = {t.__name__: t for t in tools}
    low = (hint or "").lower()

    def _run(name: str, *args) -> str:
        try:
            return by_name[name](*args)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "stub_tool_failed", tool=name, error=str(exc))
            return f"(couldn't run {name})"

    if "search_emails" in by_name and ("search" in low and ("email" in low or "mail" in low)):
        match = re.search(r"(?:search|find).*?(?:for|about)\s+(.+)", low)
        query = match.group(1).strip(" .?!") if match else low
        return "Here's what I found in your mail:\n\n" + _run("search_emails", query)

    if "list_emails" in by_name and any(k in low for k in ("inbox", "email", "mail")):
        return "Here's what's in your inbox right now:\n\n" + _run("list_emails")

    if "check_availability" in by_name and any(
        k in low for k in ("free", "available", "availability", "open slot")
    ):
        match = re.search(r"\d{4}-\d{2}-\d{2}", hint or "")
        date = match.group(0) if match else datetime.utcnow().strftime("%Y-%m-%d")
        return _run("check_availability", date)

    if "list_events" in by_name and any(
        k in low for k in ("schedule", "calendar", "agenda", "meeting", "event", "upcoming")
    ):
        return "Here's your upcoming schedule:\n\n" + _run("list_events")

    # No tool keyword matched. Return empty so the caller falls through to a
    # plain text generate(). The previous hardcoded "try check my inbox"
    # response was firing on every off-topic message in stub mode and being
    # interpreted by users as "the chatbot is broken".
    return ""
