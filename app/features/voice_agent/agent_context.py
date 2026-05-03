"""
Shared agent context used by both browser and Twilio Pipecat pipelines:
the system prompt + the catalog of collectable caller fields.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


FIELD_DEFS: Dict[str, Dict[str, str]] = {
    "name":         {"param": "caller_name",   "label": "name",          "desc": "Caller's full name",       "prompt": "Their REAL name (asked explicitly — NEVER assume or make up a name)"},
    "phone":        {"param": "caller_phone",  "label": "phone number",  "desc": "Caller's phone number",    "prompt": "Their phone number"},
    "email":        {"param": "caller_email",  "label": "email address", "desc": "Caller's email address",   "prompt": "Their email address"},
    "address":      {"param": "caller_address","label": "address",       "desc": "Caller's address",         "prompt": "Their address"},
    "service_type": {"param": "service_type",  "label": "service needed","desc": "Service requested",        "prompt": "What service they need"},
    "notes":        {"param": "notes",         "label": "extra details", "desc": "Additional notes/details", "prompt": "Any extra details or notes"},
}


def _availability_text(company_id: str, duration_min: int) -> str:
    """Summarize the next 7 days of availability for the system prompt.

    Uses one batched fetch (3 queries total) instead of 7×3 sequential queries.
    """
    from app.features.availability.service import get_available_slots_for_range

    today = datetime.now(timezone.utc)
    from_date = today.strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=6)).strftime("%Y-%m-%d")

    try:
        slots_by_date = get_available_slots_for_range(company_id, from_date, to_date, duration_min)
    except Exception:
        slots_by_date = {}

    lines: List[str] = []
    for i in range(7):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        day_name = d.strftime("%A")
        slots = slots_by_date.get(date_str, [])
        if not slots:
            lines.append(f"  {day_name} {date_str}: Closed")
            continue
        ranges, rs, re_ = [], slots[0]["start_time"], slots[0]["end_time"]
        for s in slots[1:]:
            if s["start_time"] == re_:
                re_ = s["end_time"]
            else:
                ranges.append(f"{rs}-{re_}")
                rs, re_ = s["start_time"], s["end_time"]
        ranges.append(f"{rs}-{re_}")
        lines.append(f"  {day_name} {date_str}: {', '.join(ranges)}")
    return "Schedule (next 7 days):\n" + "\n".join(lines)


def build_system_prompt(company_id: str, va_settings: Dict[str, Any]) -> str:
    """Render the receptionist system prompt with business + availability + fields."""
    biz_name = va_settings.get("business_name") or "our business"
    biz_type = va_settings.get("business_type") or "service provider"
    duration = va_settings.get("appointment_duration_min", 30)
    custom = va_settings.get("system_prompt") or ""
    fields = va_settings.get("appointment_fields") or ["name", "phone"]

    collect_steps = ["Which date and time they want"]
    for f in fields:
        fd = FIELD_DEFS.get(f)
        if fd:
            collect_steps.append(fd["prompt"])
    collect_steps.append('A final confirmation: repeat details and ask "Does that sound right?"')
    collect_numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(collect_steps))

    field_labels = " AND ".join(FIELD_DEFS[f]["label"] for f in fields if f in FIELD_DEFS)
    avail = _availability_text(company_id, duration)

    return f"""# Role
You are the phone receptionist at {biz_name}, a {biz_type}. You sound like a real person.

# Style
- Warm, brief, natural. Sound like a coworker, not a script.
- ONE short sentence per turn. Never more than two.
- No bullets, lists, or markdown — your text is read aloud.
- Say times naturally: "nine AM", "Tuesday the twenty-first".
- Say phone numbers digit by digit.

# Conversation Rules
- Ask ONE thing at a time. Wait for the answer before asking the next.
- If the caller just says "hi" or "hello", greet back and ask how you can help. Do NOT assume they want to book yet.
- Only start collecting booking details AFTER the caller says they want an appointment.
- Never bundle multiple questions in one turn ("what's your name, phone, and email?" is forbidden).
- If you misheard, say "Sorry, didn't catch that — could you repeat?" Move on after the second try.
- Never repeat the same question twice in a row.

# Confirmations
- Confirm names by repeating them once: "Got it, Sarah Chen — right?" Do NOT spell letter-by-letter unless the caller spells first.
- Confirm emails by reading them back: "umar at gmail dot com — correct?" Only spell back if they ask you to.
- Read phone numbers back digit by digit once.

# Booking Tool — STRICT
You may ONLY call book_appointment when ALL of these are true:
- The caller has explicitly asked to book
- You have collected: {field_labels}, plus a date and time
- The caller has said yes to a final summary like: "So that's [name] on [day] at [time], does that sound right?"

NEVER call book_appointment with empty, missing, or placeholder values. NEVER guess. If anything is missing, ask for it — do not call the tool.

Required steps before booking:
{collect_numbered}

# Availability
- If the caller asks what's open, summarize the week.
- If they give a vague time ("morning", "next week"), suggest a concrete slot from the schedule below.
- If a slot is closed or full, offer the nearest open slot.

{avail}

{custom}""".strip()
