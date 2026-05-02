"""
Email templates for transactional sends.

Email rendering rules of thumb (email is *not* the modern web):
- Use tables for layout. Flexbox/grid don't render in Outlook.
- Inline every style. <style> tags are stripped or ignored by many clients.
- 600px max width is the de-facto standard.
- Always provide a plain-text alternative — better deliverability + a11y.
"""

from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _escape(s: Optional[str]) -> str:
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_date(date_str: str) -> str:
    """Turn '2026-05-09' into 'Friday, May 9, 2026'."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%A, %B %-d, %Y")
    except (ValueError, TypeError):
        return date_str


def _format_time(time_str: str) -> str:
    """Turn '09:00' into '9:00 AM'."""
    try:
        t = datetime.strptime(time_str[:5], "%H:%M")
        return t.strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return time_str


# ---------------------------------------------------------------------------
# Shared layout — single source of truth for header/footer/colors.
# ---------------------------------------------------------------------------

_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_BG = "#f5f5f4"
_CARD = "#ffffff"
_TEXT = "#0f172a"
_MUTED = "#64748b"
_BORDER = "#e2e8f0"
_ACCENT = "#0d9488"  # teal-600 — matches the dashboard


def _layout(*, preheader: str, header_label: str, content_html: str, footer_html: str = "") -> str:
    """Wrap content in the shared shell. `preheader` is the snippet shown in the
    inbox preview pane next to the subject line."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_escape(header_label)}</title>
</head>
<body style="margin:0;padding:0;background:{_BG};font-family:{_FONT};color:{_TEXT};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{_escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_BG};padding:32px 16px;">
<tr><td align="center">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;background:{_CARD};border-radius:12px;overflow:hidden;border:1px solid {_BORDER};">
    <tr><td style="background:{_ACCENT};height:4px;line-height:0;font-size:0;">&nbsp;</td></tr>
    <tr><td style="padding:28px 32px 8px 32px;">
      <div style="font-size:12px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{_MUTED};">{_escape(header_label)}</div>
    </td></tr>
    <tr><td style="padding:8px 32px 28px 32px;">{content_html}</td></tr>
    {f'<tr><td style="padding:0 32px 28px 32px;border-top:1px solid {_BORDER};"><div style="padding-top:20px;font-size:12px;color:{_MUTED};line-height:1.5;">{footer_html}</div></td></tr>' if footer_html else ''}
  </table>
  <div style="margin-top:16px;font-size:11px;color:{_MUTED};">Sent by Wispoke voice agent</div>
</td></tr>
</table>
</body>
</html>"""


def _details_table(rows: list) -> str:
    """Render a list of (label, value) tuples as a clean two-column table.
    Skip rows where value is empty."""
    parts = []
    for label, value in rows:
        if not value:
            continue
        parts.append(
            f'<tr>'
            f'<td style="padding:10px 0;font-size:13px;color:{_MUTED};vertical-align:top;width:110px;">{_escape(label)}</td>'
            f'<td style="padding:10px 0;font-size:14px;color:{_TEXT};vertical-align:top;">{_escape(value)}</td>'
            f'</tr>'
        )
    if not parts:
        return ""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin-top:16px;border-top:1px solid {_BORDER};border-bottom:1px solid {_BORDER};">'
        + "".join(parts) +
        "</table>"
    )


# ---------------------------------------------------------------------------
# Renderers — one per email type. Each returns (subject, html, text).
# ---------------------------------------------------------------------------

def render_caller_confirmation(
    *,
    business_name: str,
    caller_name: str,
    scheduled_date: str,
    start_time: str,
    service_type: Optional[str] = None,
    business_phone: Optional[str] = None,
) -> tuple[str, str, str]:
    """Email to the caller confirming their booking."""
    pretty_date = _format_date(scheduled_date)
    pretty_time = _format_time(start_time)
    first_name = (caller_name or "there").split(" ")[0]

    subject = f"You're booked with {business_name} — {pretty_date}"
    preheader = f"Your appointment is confirmed for {pretty_date} at {pretty_time}."

    content = f"""
<h1 style="margin:8px 0 4px 0;font-size:22px;font-weight:600;color:{_TEXT};line-height:1.3;">You're all set, {_escape(first_name)}.</h1>
<p style="margin:0 0 4px 0;font-size:15px;color:{_MUTED};line-height:1.5;">Your appointment with <b style="color:{_TEXT};">{_escape(business_name)}</b> is confirmed.</p>
{_details_table([
    ("Date", pretty_date),
    ("Time", pretty_time),
    ("Service", service_type),
])}
<p style="margin:24px 0 0 0;font-size:14px;color:{_MUTED};line-height:1.6;">Need to reschedule or cancel? Just call back{f' at {_escape(business_phone)}' if business_phone else ''} — we'll take care of it.</p>
"""
    text = (
        f"You're all set, {first_name}.\n\n"
        f"Your appointment with {business_name} is confirmed.\n\n"
        f"Date: {pretty_date}\n"
        f"Time: {pretty_time}\n"
        + (f"Service: {service_type}\n" if service_type else "")
        + f"\nNeed to reschedule? Just call back"
        + (f" at {business_phone}" if business_phone else "")
        + ".\n"
    )
    return subject, _layout(preheader=preheader, header_label="Appointment confirmed", content_html=content), text


def render_owner_notification(
    *,
    business_name: str,
    caller_name: str,
    caller_phone: Optional[str],
    caller_email: Optional[str],
    scheduled_date: str,
    start_time: str,
    service_type: Optional[str] = None,
    notes: Optional[str] = None,
) -> tuple[str, str, str]:
    """Email to the business owner: a new booking just came in."""
    pretty_date = _format_date(scheduled_date)
    pretty_time = _format_time(start_time)

    subject = f"New booking: {caller_name} — {pretty_date} {pretty_time}"
    preheader = f"{caller_name} booked {pretty_time} on {pretty_date}."

    content = f"""
<h1 style="margin:8px 0 4px 0;font-size:22px;font-weight:600;color:{_TEXT};line-height:1.3;">New booking from your voice agent</h1>
<p style="margin:0;font-size:15px;color:{_MUTED};line-height:1.5;"><b style="color:{_TEXT};">{_escape(caller_name)}</b> just booked <b style="color:{_TEXT};">{pretty_time}</b> on <b style="color:{_TEXT};">{pretty_date}</b>.</p>
{_details_table([
    ("Name", caller_name),
    ("Phone", caller_phone),
    ("Email", caller_email),
    ("Service", service_type),
    ("Notes", notes),
])}
"""
    footer = f"Reply to this email to reach {_escape(caller_name)}." if caller_email else ""
    text = (
        f"New booking from your voice agent\n\n"
        f"{caller_name} just booked {pretty_time} on {pretty_date}.\n\n"
        f"Name: {caller_name}\n"
        + (f"Phone: {caller_phone}\n" if caller_phone else "")
        + (f"Email: {caller_email}\n" if caller_email else "")
        + (f"Service: {service_type}\n" if service_type else "")
        + (f"Notes: {notes}\n" if notes else "")
    )
    return (
        subject,
        _layout(preheader=preheader, header_label=f"New booking · {business_name}", content_html=content, footer_html=footer),
        text,
    )
