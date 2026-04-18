"""
Voice agent database operations (synchronous, matching Supabase SDK).

Secrets (twilio_auth_token, llm_api_key) live here as encrypted ciphertext.
Decryption happens in the service layer where the plaintext is needed.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import db, generate_id
from app.features.voice.schemas import DEFAULT_WEEKLY_HOURS


# ---------------------------------------------------------------------------
# Voice agent config
# ---------------------------------------------------------------------------

_CONFIG_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "greeting": "Hello, thanks for calling. How can I help you today?",
    "system_prompt": (
        "You are a friendly phone receptionist for a plumbing company. "
        "Help the caller book an appointment. Keep responses short and conversational."
    ),
    "llm_provider": "groq",
    "llm_model": "llama-3.3-70b-versatile",
    "tts_voice": "en_US-amy-medium",
    "timezone": "America/New_York",
    "default_appointment_duration_minutes": 60,
}


def get_voice_config(company_id: str) -> Optional[Dict[str, Any]]:
    res = db.table("voice_agent_config").select("*").eq("company_id", company_id).execute()
    return res.data[0] if res.data else None


def get_or_create_voice_config(company_id: str) -> Dict[str, Any]:
    existing = get_voice_config(company_id)
    if existing:
        return existing
    payload = {"company_id": company_id, **_CONFIG_DEFAULTS}
    res = db.table("voice_agent_config").insert(payload).execute()
    return res.data[0]


def update_voice_config(company_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    if not updates:
        return get_or_create_voice_config(company_id)
    get_or_create_voice_config(company_id)
    updates = {**updates, "updated_at": datetime.now(timezone.utc).isoformat()}
    res = (
        db.table("voice_agent_config")
        .update(updates)
        .eq("company_id", company_id)
        .execute()
    )
    return res.data[0] if res.data else get_voice_config(company_id)  # type: ignore[return-value]


def get_voice_config_by_twilio_number(phone_number: str) -> Optional[Dict[str, Any]]:
    res = (
        db.table("voice_agent_config")
        .select("*")
        .eq("twilio_phone_number", phone_number)
        .execute()
    )
    return res.data[0] if res.data else None


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

_AVAILABILITY_DEFAULTS: Dict[str, Any] = {
    "weekly_hours": DEFAULT_WEEKLY_HOURS,
    "slot_granularity_minutes": 30,
    "buffer_minutes": 15,
    "daily_cap": 8,
}


def get_availability(company_id: str) -> Optional[Dict[str, Any]]:
    res = db.table("availability_config").select("*").eq("company_id", company_id).execute()
    return res.data[0] if res.data else None


def get_or_create_availability(company_id: str) -> Dict[str, Any]:
    existing = get_availability(company_id)
    if existing:
        return existing
    payload = {"company_id": company_id, **_AVAILABILITY_DEFAULTS}
    res = db.table("availability_config").insert(payload).execute()
    return res.data[0]


def update_availability(company_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    if not updates:
        return get_or_create_availability(company_id)
    get_or_create_availability(company_id)
    updates = {**updates, "updated_at": datetime.now(timezone.utc).isoformat()}
    res = (
        db.table("availability_config")
        .update(updates)
        .eq("company_id", company_id)
        .execute()
    )
    return res.data[0] if res.data else get_availability(company_id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

def list_bookings(
    company_id: str,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    q = (
        db.table("bookings")
        .select("*")
        .eq("company_id", company_id)
        .order("starts_at", desc=False)
        .limit(limit)
    )
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


def list_bookings_in_range(
    company_id: str,
    starts_at_gte: datetime,
    starts_at_lt: datetime,
    exclude_statuses: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    q = (
        db.table("bookings")
        .select("*")
        .eq("company_id", company_id)
        .gte("starts_at", starts_at_gte.isoformat())
        .lt("starts_at", starts_at_lt.isoformat())
    )
    res = q.execute().data or []
    if exclude_statuses:
        res = [b for b in res if b.get("status") not in exclude_statuses]
    return res


def get_booking(booking_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    res = (
        db.table("bookings")
        .select("*")
        .eq("booking_id", booking_id)
        .eq("company_id", company_id)
        .execute()
    )
    return res.data[0] if res.data else None


def insert_booking(data: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"booking_id": generate_id(), **data}
    res = db.table("bookings").insert(payload).execute()
    return res.data[0]


def update_booking_status(booking_id: str, company_id: str, status: str) -> Optional[Dict[str, Any]]:
    updates = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
    res = (
        db.table("bookings")
        .update(updates)
        .eq("booking_id", booking_id)
        .eq("company_id", company_id)
        .execute()
    )
    return res.data[0] if res.data else None


# ---------------------------------------------------------------------------
# Call logs
# ---------------------------------------------------------------------------

def insert_call_log(data: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"call_id": generate_id(), **data}
    res = db.table("call_logs").insert(payload).execute()
    return res.data[0]


def get_call_by_sid(twilio_call_sid: str) -> Optional[Dict[str, Any]]:
    res = (
        db.table("call_logs")
        .select("*")
        .eq("twilio_call_sid", twilio_call_sid)
        .execute()
    )
    return res.data[0] if res.data else None


def get_call(call_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    res = (
        db.table("call_logs")
        .select("*")
        .eq("call_id", call_id)
        .eq("company_id", company_id)
        .execute()
    )
    return res.data[0] if res.data else None


def update_call(call_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    res = db.table("call_logs").update(updates).eq("call_id", call_id).execute()
    return res.data[0] if res.data else None


def list_calls(company_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    return (
        db.table("call_logs")
        .select("*")
        .eq("company_id", company_id)
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
