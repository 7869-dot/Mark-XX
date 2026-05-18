"""Gmail operations. Live via Gmail API; stub-fallback when not connected.

Email content is NEVER persisted — always fetched on demand here.
"""
import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app.models import User
from app.services.google_auth import get_google_credentials, is_stub
from app.core.logging import get_logger

logger = get_logger("axolot.gmail")


# ── Stub corpus ────────────────────────────────────────────────────────────
def _stub_inbox() -> list[dict]:
    now = datetime.utcnow()
    return [
        {
            "id": "stub-msg-1", "thread_id": "stub-thr-1",
            "subject": "Re: Series A timeline — quick question",
            "sender": "Dana Whitfield", "sender_email": "dana@northstar.vc",
            "snippet": "Loved the deck. One thing on the projections before we move forward —",
            "date": (now - timedelta(hours=2)).isoformat(), "is_read": False,
            "has_attachments": False, "labels": ["INBOX", "UNREAD", "IMPORTANT"],
        },
        {
            "id": "stub-msg-2", "thread_id": "stub-thr-2",
            "subject": "Contract for review (due Fri)",
            "sender": "Legal — Marcus", "sender_email": "marcus@harborlaw.com",
            "snippet": "Attached is the redlined MSA. Please confirm sections 4 and 7 by Friday.",
            "date": (now - timedelta(hours=5)).isoformat(), "is_read": False,
            "has_attachments": True, "labels": ["INBOX", "UNREAD"],
        },
        {
            "id": "stub-msg-3", "thread_id": "stub-thr-3",
            "subject": "Weekly product newsletter",
            "sender": "ProductHunt Daily", "sender_email": "digest@producthunt.com",
            "snippet": "The top launches this week, plus a deep dive on agentic UX.",
            "date": (now - timedelta(hours=9)).isoformat(), "is_read": False,
            "has_attachments": False, "labels": ["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        },
        {
            "id": "stub-msg-4", "thread_id": "stub-thr-4",
            "subject": "Coffee next week?",
            "sender": "Priya Menon", "sender_email": "priya@dataplane.io",
            "snippet": "It's been too long — want to grab 30 min Tue or Wed?",
            "date": (now - timedelta(days=1)).isoformat(), "is_read": True,
            "has_attachments": False, "labels": ["INBOX"],
        },
    ]


def _stub_email(message_id: str) -> dict:
    base = next((m for m in _stub_inbox() if m["id"] == message_id), _stub_inbox()[0])
    return {
        **base,
        "to": "you@axolot.dev",
        "cc": "",
        "body_plain": (
            f"{base['snippet']}\n\nThis is stub email body content for {message_id}. "
            "Configure Google OAuth + USE_STUBS=false to read real mail.\n\nBest,\n"
            f"{base['sender']}"
        ),
        "body_html": f"<p>{base['snippet']}</p>",
        "attachments": (
            [{"filename": "MSA_redline.pdf", "mime_type": "application/pdf", "size": 184320}]
            if base["has_attachments"] else []
        ),
    }


def _gmail(db: Session, user_id: str):
    """Return (user, gmail_api_or_None). None => use stub path."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None, None
    if is_stub():
        return user, None
    creds = get_google_credentials(db, user)
    if not creds:
        return user, None
    from googleapiclient.discovery import build  # lazy

    return user, build("gmail", "v1", credentials=creds, cache_discovery=False)


def _header(payload, name, default=""):
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", default)
    return default


def _split_sender(raw: str):
    if "<" in raw and ">" in raw:
        name = raw.split("<")[0].strip().strip('"')
        email = raw.split("<")[1].split(">")[0].strip()
        return name or email, email
    return raw, raw


# ── Public API ─────────────────────────────────────────────────────────────
def list_emails(db, user_id, max_results=20, label="INBOX", unread_only=False):
    user, gm = _gmail(db, user_id)
    if gm is None:
        items = _stub_inbox()
        if unread_only:
            items = [m for m in items if not m["is_read"]]
        return items[:max_results]

    q = "is:unread" if unread_only else None
    resp = gm.users().messages().list(
        userId="me", labelIds=[label], maxResults=max_results, q=q
    ).execute()
    out = []
    for ref in resp.get("messages", []):
        m = gm.users().messages().get(
            userId="me", id=ref["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ).execute()
        p = m.get("payload", {})
        sender_name, sender_email = _split_sender(_header(p, "From"))
        out.append({
            "id": m["id"], "thread_id": m["threadId"],
            "subject": _header(p, "Subject", "(no subject)"),
            "sender": sender_name, "sender_email": sender_email,
            "snippet": m.get("snippet", ""), "date": _header(p, "Date"),
            "is_read": "UNREAD" not in m.get("labelIds", []),
            "has_attachments": any(
                part.get("filename") for part in p.get("parts", [])
            ),
            "labels": m.get("labelIds", []),
        })
    return out


def get_email(db, user_id, message_id):
    user, gm = _gmail(db, user_id)
    if gm is None:
        return _stub_email(message_id)
    m = gm.users().messages().get(userId="me", id=message_id, format="full").execute()
    p = m.get("payload", {})
    sender_name, sender_email = _split_sender(_header(p, "From"))

    def _walk(part):
        plain = html = ""
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            plain = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "ignore")
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "ignore")
        for sub in part.get("parts", []):
            sp, sh = _walk(sub)
            plain += sp
            html += sh
        return plain, html

    body_plain, body_html = _walk(p)
    attachments = [
        {"filename": pt["filename"],
         "mime_type": pt.get("mimeType", ""),
         "size": pt.get("body", {}).get("size", 0)}
        for pt in p.get("parts", []) if pt.get("filename")
    ]
    return {
        "id": m["id"], "thread_id": m["threadId"],
        "subject": _header(p, "Subject", "(no subject)"),
        "sender": sender_name, "sender_email": sender_email,
        "to": _header(p, "To"), "cc": _header(p, "Cc"),
        "body_plain": body_plain, "body_html": body_html,
        "date": _header(p, "Date"), "labels": m.get("labelIds", []),
        "attachments": attachments,
    }


def _raw(to, subject, body, cc=None):
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    if cc:
        msg["cc"] = cc
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send_email(db, user_id, to, subject, body, cc=None, reply_to_thread_id=None):
    user, gm = _gmail(db, user_id)
    if gm is None:
        logger.info("stub send_email to=%s", to)
        return f"stub-sent-{datetime.utcnow().timestamp():.0f}"
    payload = {"raw": _raw(to, subject, body, cc)}
    if reply_to_thread_id:
        payload["threadId"] = reply_to_thread_id
    sent = gm.users().messages().send(userId="me", body=payload).execute()
    return sent["id"]


def draft_email(db, user_id, to, subject, body, cc=None):
    user, gm = _gmail(db, user_id)
    if gm is None:
        return f"stub-draft-{datetime.utcnow().timestamp():.0f}"
    d = gm.users().drafts().create(
        userId="me", body={"message": {"raw": _raw(to, subject, body, cc)}}
    ).execute()
    return d["id"]


def mark_read(db, user_id, message_id):
    user, gm = _gmail(db, user_id)
    if gm is None:
        return True
    gm.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()
    return True


def archive_email(db, user_id, message_id):
    user, gm = _gmail(db, user_id)
    if gm is None:
        return True
    gm.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}
    ).execute()
    return True


def get_thread(db, user_id, thread_id):
    user, gm = _gmail(db, user_id)
    if gm is None:
        e = _stub_email("stub-msg-1")
        return {"id": thread_id, "subject": e["subject"],
                "messages": [e, {**_stub_email("stub-msg-4"),
                                 "subject": "Re: " + e["subject"]}]}
    t = gm.users().threads().get(userId="me", id=thread_id, format="full").execute()
    msgs = []
    for m in t.get("messages", []):
        p = m.get("payload", {})
        sn, se = _split_sender(_header(p, "From"))
        msgs.append({
            "id": m["id"], "subject": _header(p, "Subject"),
            "sender": sn, "sender_email": se,
            "snippet": m.get("snippet", ""), "date": _header(p, "Date"),
        })
    return {"id": thread_id,
            "subject": msgs[0]["subject"] if msgs else "",
            "messages": msgs}


def search_emails(db, user_id, query: str, max_results=10):
    user, gm = _gmail(db, user_id)
    if gm is None:
        ql = query.lower()
        return [m for m in _stub_inbox()
                if ql in (m["subject"] + m["sender"] + m["snippet"]).lower()][:max_results]
    resp = gm.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    out = []
    for ref in resp.get("messages", []):
        m = gm.users().messages().get(
            userId="me", id=ref["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ).execute()
        p = m.get("payload", {})
        sn, se = _split_sender(_header(p, "From"))
        out.append({
            "id": m["id"], "thread_id": m["threadId"],
            "subject": _header(p, "Subject"), "sender": sn, "sender_email": se,
            "snippet": m.get("snippet", ""), "date": _header(p, "Date"),
        })
    return out


def latest_message_id(db, user_id, thread_id) -> str | None:
    t = get_thread(db, user_id, thread_id)
    msgs = t.get("messages", [])
    return msgs[-1]["id"] if msgs else None
