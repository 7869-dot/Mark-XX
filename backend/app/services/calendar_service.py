"""Google Calendar operations. Live via Calendar API; stub-fallback otherwise.

Event content is fetched on demand — never persisted.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import User
from app.services.google_auth import get_google_credentials, is_stub
from app.core.logging import get_logger

logger = get_logger("axolot.calendar")


def _stub_events(days_ahead=7) -> list[dict]:
    base = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    mk = lambda d, h, dur, **kw: {
        "id": f"stub-evt-{d}-{h}",
        "summary": kw.get("summary", "Meeting"),
        "description": kw.get("description", ""),
        "start": (base + timedelta(days=d, hours=h)).isoformat(),
        "end": (base + timedelta(days=d, hours=h, minutes=dur)).isoformat(),
        "attendees": kw.get("attendees", []),
        "location": kw.get("location", ""),
        "meet_link": kw.get("meet_link", ""),
        "is_recurring": kw.get("is_recurring", False),
        "status": "confirmed",
    }
    evs = [
        mk(0, 9, 30, summary="Standup",
           attendees=[{"name": "Team", "email": "team@axolot.dev", "status": "accepted"}],
           is_recurring=True),
        mk(0, 10, 60, summary="Investor call — Northstar",
           attendees=[{"name": "Dana Whitfield", "email": "dana@northstar.vc", "status": "accepted"}],
           meet_link="https://meet.google.com/stub-abc-def"),
        mk(0, 10, 45, summary="Design review",
           attendees=[{"name": "Jordan", "email": "jordan@axolot.dev", "status": "tentative"}]),
        mk(1, 14, 30, summary="1:1 with Priya",
           attendees=[{"name": "Priya Menon", "email": "priya@dataplane.io", "status": "accepted"}]),
        mk(2, 11, 60, summary="Board prep"),
    ]
    return [e for e in evs
            if datetime.fromisoformat(e["start"]) <= base + timedelta(days=days_ahead)]


def _cal(db: Session, user_id: str):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None, None
    if is_stub():
        return user, None
    creds = get_google_credentials(db, user)
    if not creds:
        return user, None
    from googleapiclient.discovery import build  # lazy

    return user, build("calendar", "v3", credentials=creds, cache_discovery=False)


def _norm(ev: dict) -> dict:
    start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
    end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
    return {
        "id": ev.get("id"),
        "summary": ev.get("summary", "(no title)"),
        "description": ev.get("description", ""),
        "start": start, "end": end,
        "attendees": [
            {"name": a.get("displayName", a.get("email", "")),
             "email": a.get("email", ""),
             "status": a.get("responseStatus", "needsAction")}
            for a in ev.get("attendees", [])
        ],
        "location": ev.get("location", ""),
        "meet_link": ev.get("hangoutLink", ""),
        "is_recurring": bool(ev.get("recurringEventId")),
        "status": ev.get("status", "confirmed"),
    }


def list_events(db, user_id, days_ahead=7, max_results=20):
    user, cal = _cal(db, user_id)
    if cal is None:
        return _stub_events(days_ahead)[:max_results]
    now = datetime.utcnow()
    resp = cal.events().list(
        calendarId="primary", timeMin=now.isoformat() + "Z",
        timeMax=(now + timedelta(days=days_ahead)).isoformat() + "Z",
        singleEvents=True, orderBy="startTime", maxResults=max_results,
    ).execute()
    return [_norm(e) for e in resp.get("items", [])]


def get_event(db, user_id, event_id):
    user, cal = _cal(db, user_id)
    if cal is None:
        return next((e for e in _stub_events(30) if e["id"] == event_id),
                    _stub_events(1)[0])
    return _norm(cal.events().get(calendarId="primary", eventId=event_id).execute())


def create_event(db, user_id, summary, start_dt, end_dt, description=None,
                 attendees=None, location=None, add_meet_link=False):
    user, cal = _cal(db, user_id)
    if cal is None:
        return {"id": f"stub-evt-{datetime.utcnow().timestamp():.0f}",
                "meet_link": "https://meet.google.com/stub-new" if add_meet_link else ""}
    body = {
        "summary": summary,
        "description": description or "",
        "start": {"dateTime": start_dt},
        "end": {"dateTime": end_dt},
        "attendees": [{"email": e} for e in (attendees or [])],
    }
    if location:
        body["location"] = location
    kwargs = {"calendarId": "primary", "body": body, "sendUpdates": "all"}
    if add_meet_link:
        body["conferenceData"] = {
            "createRequest": {"requestId": f"axo-{datetime.utcnow().timestamp():.0f}"}
        }
        kwargs["conferenceDataVersion"] = 1
    ev = cal.events().insert(**kwargs).execute()
    return {"id": ev["id"], "meet_link": ev.get("hangoutLink", "")}


def update_event(db, user_id, event_id, **kwargs):
    user, cal = _cal(db, user_id)
    if cal is None:
        return {"id": event_id, "updated": True, "stub": True}
    patch = {k: v for k, v in kwargs.items() if v is not None}
    ev = cal.events().patch(
        calendarId="primary", eventId=event_id, body=patch, sendUpdates="all"
    ).execute()
    return _norm(ev)


def delete_event(db, user_id, event_id, notify_attendees=True):
    user, cal = _cal(db, user_id)
    if cal is None:
        return True
    cal.events().delete(
        calendarId="primary", eventId=event_id,
        sendUpdates="all" if notify_attendees else "none",
    ).execute()
    return True


def find_free_slots(db, user_id, date: str, duration_minutes=30):
    """Open windows on `date` (YYYY-MM-DD) within 09:00–18:00."""
    user, cal = _cal(db, user_id)
    day = datetime.fromisoformat(date)
    work_start = day.replace(hour=9, minute=0, second=0, microsecond=0)
    work_end = day.replace(hour=18, minute=0, second=0, microsecond=0)

    if cal is None:
        busy = [
            (day.replace(hour=10), day.replace(hour=11)),
            (day.replace(hour=14), day.replace(hour=14, minute=30)),
        ]
    else:
        fb = cal.freebusy().query(body={
            "timeMin": work_start.isoformat() + "Z",
            "timeMax": work_end.isoformat() + "Z",
            "items": [{"id": "primary"}],
        }).execute()
        busy = [
            (datetime.fromisoformat(b["start"].replace("Z", "")),
             datetime.fromisoformat(b["end"].replace("Z", "")))
            for b in fb["calendars"]["primary"]["busy"]
        ]

    slots, cursor = [], work_start
    busy.sort()
    for bstart, bend in busy:
        while cursor + timedelta(minutes=duration_minutes) <= bstart:
            slots.append({"start": cursor.isoformat(),
                          "end": (cursor + timedelta(minutes=duration_minutes)).isoformat()})
            cursor += timedelta(minutes=duration_minutes)
        cursor = max(cursor, bend)
    while cursor + timedelta(minutes=duration_minutes) <= work_end:
        slots.append({"start": cursor.isoformat(),
                      "end": (cursor + timedelta(minutes=duration_minutes)).isoformat()})
        cursor += timedelta(minutes=duration_minutes)
    return slots


def get_upcoming_summary(db, user_id, days=3) -> str:
    events = list_events(db, user_id, days_ahead=days, max_results=20)
    if not events:
        return "No events scheduled."
    lines = []
    for e in events[:12]:
        when = e["start"]
        lines.append(f"- {when}: {e['summary']}"
                     + (f" (with {', '.join(a['name'] for a in e['attendees'][:3])})"
                        if e["attendees"] else ""))
    return "\n".join(lines)
