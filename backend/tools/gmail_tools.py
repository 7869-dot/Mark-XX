"""Gmail API helpers — all synchronous (called via run_in_executor).

Access tokens are passed in; never stored here.
All calls are read-only or draft-only.  Sending is done only from the
proposed_actions approve endpoint.
"""
from __future__ import annotations

import base64
import email as _email_lib
import logging

import httpx

logger = logging.getLogger(__name__)

_GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
_TIMEOUT = 15


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def list_recent_emails(
    access_token: str,
    max_results: int = 10,
    query: str = "is:unread",
) -> list[dict]:
    """Return a list of recent email summaries (id, from, subject, date, snippet)."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        r = client.get(
            f"{_GMAIL}/messages",
            headers=_headers(access_token),
            params={"maxResults": max_results, "q": query},
        )
        r.raise_for_status()
        messages = r.json().get("messages", [])
        results = []
        for msg in messages:
            try:
                mr = client.get(
                    f"{_GMAIL}/messages/{msg['id']}",
                    headers=_headers(access_token),
                    params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                )
                mr.raise_for_status()
                data = mr.json()
                hdrs = {h["name"].lower(): h["value"] for h in data.get("payload", {}).get("headers", [])}
                results.append({
                    "id":      msg["id"],
                    "from":    hdrs.get("from", ""),
                    "subject": hdrs.get("subject", "(no subject)"),
                    "date":    hdrs.get("date", ""),
                    "snippet": data.get("snippet", ""),
                })
            except Exception as exc:
                logger.warning("Could not fetch email %s: %s", msg["id"], exc)
        return results


def read_email(access_token: str, message_id: str) -> dict:
    """Return full email content (id, from, subject, date, body)."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        r = client.get(
            f"{_GMAIL}/messages/{message_id}",
            headers=_headers(access_token),
            params={"format": "full"},
        )
        r.raise_for_status()
        data = r.json()
        hdrs = {h["name"].lower(): h["value"] for h in data.get("payload", {}).get("headers", [])}
        body = _extract_body(data.get("payload", {}))
        return {
            "id":      message_id,
            "from":    hdrs.get("from", ""),
            "to":      hdrs.get("to", ""),
            "subject": hdrs.get("subject", "(no subject)"),
            "date":    hdrs.get("date", ""),
            "body":    body[:8000],
        }


def send_gmail(
    access_token: str,
    to: str,
    subject: str,
    body: str,
    in_reply_to_id: str | None = None,
) -> str:
    """Send an email via Gmail API.  Called ONLY from the approve endpoint."""
    msg = _email_lib.message.EmailMessage()
    msg["To"]      = to
    msg["Subject"] = subject
    msg.set_content(body)
    if in_reply_to_id:
        msg["In-Reply-To"] = in_reply_to_id
        msg["References"]  = in_reply_to_id

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    with httpx.Client(timeout=_TIMEOUT) as client:
        r = client.post(
            f"{_GMAIL}/messages/send",
            headers=_headers(access_token),
            json={"raw": raw},
        )
        r.raise_for_status()
    return f"Email sent to {to}."


def _extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return ""
