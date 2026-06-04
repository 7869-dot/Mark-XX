"""Gmail + Calendar integration router.

New routes use the spec error envelope { success:false, error:{code,message} }
(consistent with the A2A router decision). Email/event content is fetched on
demand from Google — never persisted.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.core.security import get_current_user, create_access_token, decode_token
from app.models import User
from app.services import google_auth, gmail_service, calendar_service
from app.services import agent_email_tasks, agent_calendar_tasks

logger = get_logger("axolot.integrations")
router = APIRouter(tags=["integrations"])


def _meta(uid):
    return {"timestamp": datetime.utcnow().isoformat(), "agent_id": None, "user_id": uid}


def ok(data, uid=None):
    return {"success": True, "data": data, "meta": _meta(uid)}


def fail(code, message, status=400):
    return JSONResponse(
        status_code=status,
        content={"success": False, "error": {"code": code, "message": message}},
    )


def _agent_id(user: User):
    return user.agent.id if user.agent else None


# ── Connection status & OAuth flow ─────────────────────────────────────────
@router.get("/integrations/status")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    connected = google_auth.is_connected(user)
    reason = None if connected else (user.google_disconnect_reason or None)
    return ok({
        "gmail": bool(user.gmail_connected),
        "calendar": bool(user.calendar_connected),
        # Consolidated Google connection state so the UI can show a
        # "Reconnect Google" prompt when a refresh token expires/revokes (Bug 3).
        "google": {"connected": connected, "reason": reason},
        "stub_mode": google_auth.is_stub(),
        "token_health": google_auth.check_token_health(db, user),
    }, user.id)


def _start_connect(user: User):
    state = create_access_token(user.id, {"scope": "google_connect"})
    return ok({"authorization_url": google_auth.build_authorization_url(state)}, user.id)


@router.post("/integrations/gmail/connect")
def gmail_connect(user: User = Depends(get_current_user)):
    return _start_connect(user)


@router.post("/integrations/calendar/connect")
def calendar_connect(user: User = Depends(get_current_user)):
    return _start_connect(user)


# The Gmail/Calendar offline grant is registered at THREE paths so it works no
# matter which redirect_uri the Google Cloud Console / GMAIL_REDIRECT_URI env
# is set to:
#   /integrations/google/callback          — the canonical path
#   /auth/google/callback/gmail            — what current prod creds whitelist
#   /auth/google/callback/calendar         — calendar variant of the above
# All three run the SAME handler: the user is identified entirely from the
# signed `state` JWT, not the path, so the suffix is cosmetic. See the OAuth
# redirect-URI checklist in README / the deploy notes.
@router.get("/integrations/google/callback")
@router.get("/auth/google/callback/gmail")
@router.get("/auth/google/callback/calendar")
def google_callback(
    request: Request,
    state: str = "",
    code: str = "",
    error: str = "",
    stub: int = 0,
    db: Session = Depends(get_db),
):
    """Google redirects here after the Gmail/Calendar consent screen.

    Flow: validate the signed `state` JWT → resolve the user → exchange the
    auth `code` for access+refresh tokens → store them Fernet-encrypted on the
    user row → bounce back to the integrations settings page.
    """
    err_url = f"{settings.FRONTEND_URL}/app?gmail=error"

    # 0. The user denied consent (or Google errored) — nothing to exchange.
    if error:
        log_event(logger, "google_connect_denied", reason=error)
        return RedirectResponse(url=err_url)

    # 1. Decode + validate the state JWT. It must be one we issued for THIS
    #    flow — `_start_connect` stamps it with scope="google_connect".
    try:
        payload = decode_token(state)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "google_connect_bad_state", error=str(exc))
        return RedirectResponse(url=err_url)
    if payload.get("scope") != "google_connect":
        log_event(logger, "google_connect_wrong_scope", scope=payload.get("scope"))
        return RedirectResponse(url=err_url)
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        log_event(logger, "google_connect_unknown_user", user_id=user_id)
        return RedirectResponse(url=err_url)

    # 2. A live (non-stub) flow with no code can't be exchanged — bail cleanly
    #    instead of feeding "" into Google's token endpoint.
    if not code and not google_auth.is_stub():
        log_event(logger, "google_connect_no_code", user_id=user_id)
        return RedirectResponse(url=err_url)

    # 3. Exchange the code and persist the encrypted tokens against the user.
    try:
        tokens = google_auth.exchange_code(code or f"stub-{user_id}")
        google_auth.store_tokens(
            db, user, tokens["access_token"], tokens["refresh_token"],
            tokens["expiry"], tokens["scopes"],
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log_event(logger, "google_connect_exchange_failed", user_id=user_id, error=str(exc))
        return RedirectResponse(url=err_url)

    log_event(
        logger, "google_connect_ok",
        user_id=user_id, gmail=user.gmail_connected, calendar=user.calendar_connected,
    )
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/app?gmail=connected"
    )


def _disconnect(db, user, gmail=False, calendar=False):
    # Fully revoke if both go; otherwise just flip the relevant flag.
    if gmail and calendar:
        google_auth.revoke_google_access(db, user)
    else:
        if gmail:
            user.gmail_connected = False
        if calendar:
            user.calendar_connected = False
        if not user.gmail_connected and not user.calendar_connected:
            google_auth.revoke_google_access(db, user)
        db.commit()
    return ok({"gmail": bool(user.gmail_connected),
               "calendar": bool(user.calendar_connected)}, user.id)


@router.post("/integrations/gmail/disconnect")
def gmail_disconnect(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _disconnect(db, user, gmail=True)


@router.post("/integrations/calendar/disconnect")
def calendar_disconnect(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _disconnect(db, user, calendar=True)


def _require_gmail(user: User):
    if not user.gmail_connected and not google_auth.is_stub():
        return fail("GMAIL_NOT_CONNECTED", "Connect Gmail first", 409)
    return None


def _require_calendar(user: User):
    if not user.calendar_connected and not google_auth.is_stub():
        return fail("CALENDAR_NOT_CONNECTED", "Connect Calendar first", 409)
    return None


# ── Gmail ──────────────────────────────────────────────────────────────────
@router.get("/gmail/inbox")
def inbox(unread_only: bool = False, max: int = 20,
          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    return ok(gmail_service.list_emails(db, user.id, max_results=max,
                                        unread_only=unread_only), user.id)


@router.get("/gmail/email/{message_id}")
def email(message_id: str, db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    return ok(gmail_service.get_email(db, user.id, message_id), user.id)


@router.get("/gmail/thread/{thread_id}")
def thread(thread_id: str, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    return ok(gmail_service.get_thread(db, user.id, thread_id), user.id)


@router.get("/gmail/search")
def search(q: str, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    return ok(gmail_service.search_emails(db, user.id, q), user.id)


@router.post("/gmail/draft")
def gmail_draft(body: dict, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    did = gmail_service.draft_email(db, user.id, body["to"], body["subject"],
                                    body["body"], body.get("cc"))
    return ok({"draft_id": did}, user.id)


@router.post("/gmail/send")
def gmail_send(body: dict, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    mid = gmail_service.send_email(db, user.id, body["to"], body["subject"],
                                   body["body"], body.get("cc"))
    return ok({"message_id": mid}, user.id)


@router.post("/gmail/reply")
def gmail_reply(body: dict, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    mid = gmail_service.send_email(
        db, user.id, body.get("to", ""), body.get("subject", "Re:"),
        body["body"], reply_to_thread_id=body["thread_id"],
    )
    return ok({"message_id": mid}, user.id)


@router.patch("/gmail/email/{message_id}/read")
def gmail_mark_read(message_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    return ok({"ok": gmail_service.mark_read(db, user.id, message_id)}, user.id)


@router.patch("/gmail/email/{message_id}/archive")
def gmail_archive(message_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    return ok({"ok": gmail_service.archive_email(db, user.id, message_id)}, user.id)


@router.post("/gmail/watch")
def gmail_watch(body: dict, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    if (e := _require_gmail(user)):
        return e
    if not user.agent:
        return fail("AGENT_NOT_FOUND", "No agent", 404)
    return ok(agent_email_tasks.monitor_thread(db, user.agent.id,
                                               body["thread_id"]), user.id)


# ── Calendar ───────────────────────────────────────────────────────────────
@router.get("/calendar/events")
def cal_events(days: int = 7, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if (e := _require_calendar(user)):
        return e
    return ok(calendar_service.list_events(db, user.id, days_ahead=days), user.id)


@router.get("/calendar/event/{event_id}")
def cal_event(event_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    if (e := _require_calendar(user)):
        return e
    return ok(calendar_service.get_event(db, user.id, event_id), user.id)


@router.get("/calendar/free-slots")
def cal_free(date: str, duration: int = 30, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    if (e := _require_calendar(user)):
        return e
    return ok(calendar_service.find_free_slots(db, user.id, date, duration), user.id)


@router.post("/calendar/event")
def cal_create(body: dict, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if (e := _require_calendar(user)):
        return e
    return ok(calendar_service.create_event(
        db, user.id, body["summary"], body["start"], body["end"],
        body.get("description"), body.get("attendees", []),
        body.get("location"), body.get("meet_link", False),
    ), user.id)


@router.patch("/calendar/event/{event_id}")
def cal_update(event_id: str, body: dict, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if (e := _require_calendar(user)):
        return e
    return ok(calendar_service.update_event(db, user.id, event_id, **body), user.id)


@router.delete("/calendar/event/{event_id}")
def cal_delete(event_id: str, notify: bool = True, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if (e := _require_calendar(user)):
        return e
    return ok({"deleted": calendar_service.delete_event(
        db, user.id, event_id, notify)}, user.id)


# ── Agent Gemini-powered task triggers ─────────────────────────────────────
def _need_agent(user):
    return None if user.agent else fail("AGENT_NOT_FOUND", "No agent", 404)


@router.post("/agent/tasks/summarize-inbox")
def t_summarize(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if (e := _need_agent(user)) or (e := _require_gmail(user)):
        return e
    return ok(agent_email_tasks.summarize_inbox(db, user.agent.id), user.id)


@router.post("/agent/tasks/draft-reply")
def t_draft(body: dict, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    if (e := _need_agent(user)) or (e := _require_gmail(user)):
        return e
    return ok(agent_email_tasks.draft_reply(
        db, user.agent.id, body["message_id"], body.get("instruction", "")), user.id)


@router.post("/agent/tasks/schedule-meeting")
def t_schedule(body: dict, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if (e := _need_agent(user)) or (e := _require_gmail(user)):
        return e
    return ok(agent_email_tasks.schedule_meeting(
        db, user.agent.id, body["with_email"], body["purpose"],
        body.get("duration", 30)), user.id)


@router.post("/agent/tasks/prep-meeting")
def t_prep(body: dict, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    if (e := _need_agent(user)) or (e := _require_calendar(user)):
        return e
    return ok(agent_calendar_tasks.prep_for_meeting(
        db, user.agent.id, body["event_id"]), user.id)


@router.post("/agent/tasks/daily-briefing")
def t_brief(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if (e := _need_agent(user)) or (e := _require_calendar(user)):
        return e
    return ok(agent_calendar_tasks.daily_briefing(db, user.agent.id), user.id)
