"""
Transactional email — Resend wrapper.

`send_email` is best-effort: errors are logged but never raised, since email
failure must not block the booking flow. If RESEND_API_KEY is unset, the
function is a no-op (so dev/test envs run without the key).
"""

import logging
from typing import Optional

import resend

from app.core.config import settings

logger = logging.getLogger("wispoke.email")

if settings.resend_api_key:
    resend.api_key = settings.resend_api_key


def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> Optional[str]:
    """Send an email. Returns the Resend message id on success, None otherwise.

    Always pass a plain-text alternative when possible — clients without HTML
    rendering (some screen readers, terminal mail) get the fallback, and spam
    filters trust multipart messages more than HTML-only."""
    if not settings.resend_api_key:
        logger.info("Email skipped (RESEND_API_KEY not set): to=%s subject=%s", to, subject)
        return None
    if not to:
        return None
    try:
        params: dict = {
            "from": settings.email_from,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if text:
            params["text"] = text
        if reply_to:
            params["reply_to"] = reply_to
        result = resend.Emails.send(params)
        msg_id = result.get("id") if isinstance(result, dict) else None
        logger.info("Email sent id=%s to=%s", msg_id, to)
        return msg_id
    except Exception:
        logger.exception("Email send failed to=%s subject=%s", to, subject)
        return None
