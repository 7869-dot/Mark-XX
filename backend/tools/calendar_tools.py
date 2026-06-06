"""Google Calendar API helpers — all synchronous (called via run_in_executor).

Access tokens are passed in; never stored here.
Calendar creates happen only from the proposed_actions approve endpoint.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

import httpx

logger = logging.getLogger(__name__)

_CAL = "https://www.googleapis.com/calendar/v3"
_TIMEOUT = 15


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def get_today_schedule(access_token: str) -> list[dict]:
    """Return today's calendar events (UTC day boundaries)."""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    day_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return get_events_in_range(access_token, day_start, day_end)


def get_imminent_events(access_token: str, within_minutes: int = 30) -> list[dict]:
    """Return events starting within the next `within_minutes` minutes."""
    now = datetime.now(timezone.utc)
    return get_events_in_range(access_token, now, now + timedelta(minutes=within_minutes))


def get_events_in_range(
    access_token: str,
    time_min: datetime,
    time_max: datetime,
) -> list[dict]:
    """Return calendar events between two UTC datetimes."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        r = client.get(
            f"{_CAL}/calendars/primary/events",
            headers=_headers(access_token),
            params={
                "timeMin":      time_min.isoformat(),
                "timeMax":      time_max.isoformat(),
                "singleEvents": "true",
                "orderBy":      "startTime",
                "maxResults":   20,
            },
        )
        r.raise_for_status()
        return [_format_event(e) for e in r.json().get("items", [])]


def create_calendar_event(
    access_token: str,
    title: str,
    start: str,
    end: str,
    description: str = "",
    attendees: list[str] | None = None,
) -> dict:
    """Create a calendar event.  Called ONLY from the approve endpoint."""
    body: dict = {
        "summary":     title,
        "description": description,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end":   {"dateTime": end,   "timeZone": "UTC"},
    }
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]

    with httpx.Client(timeout=_TIMEOUT) as client:
        r = client.post(
            f"{_CAL}/calendars/primary/events",
            headers=_headers(access_token),
            json=body,
        )
        r.raise_for_status()
        return _format_event(r.json())


def _format_event(e: dict) -> dict:
    start = e.get("start", {})
    end   = e.get("end",   {})
    return {
        "id":          e.get("id", ""),
        "summary":     e.get("summary", "(no title)"),
        "start":       start.get("dateTime", start.get("date", "")),
        "end":         end.get("dateTime",   end.get("date",   "")),
        "description": e.get("description", ""),
        "attendees":   [a.get("email", "") for a in e.get("attendees", [])],
        "html_link":   e.get("htmlLink", ""),
    }
