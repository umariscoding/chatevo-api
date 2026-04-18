"""
Voice agent business logic.

The service layer is the only place allowed to encrypt/decrypt secrets and to
translate between API-level payloads and DB rows.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.encryption import encrypt_secret, decrypt_secret
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.features.voice import repository as repo
from app.features.voice import availability as availability_mod


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _config_to_response(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "enabled": bool(row.get("enabled")),
        "greeting": row.get("greeting") or "",
        "system_prompt": row.get("system_prompt") or "",
        "llm_provider": row.get("llm_provider") or "groq",
        "llm_model": row.get("llm_model") or "llama-3.3-70b-versatile",
        "tts_voice": row.get("tts_voice") or "en_US-amy-medium",
        "timezone": row.get("timezone") or "America/New_York",
        "default_appointment_duration_minutes": int(row.get("default_appointment_duration_minutes") or 60),
        "twilio_account_sid": row.get("twilio_account_sid"),
        "twilio_phone_number": row.get("twilio_phone_number"),
        "twilio_auth_token_set": bool(row.get("twilio_auth_token_encrypted")),
        "llm_api_key_set": bool(row.get("llm_api_key_encrypted")),
    }


def get_config(company_id: str) -> Dict[str, Any]:
    row = repo.get_or_create_voice_config(company_id)
    return _config_to_response(row)


def update_config(company_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    updates = {k: v for k, v in updates.items() if v is not None}
    db_updates: Dict[str, Any] = {}

    for key in (
        "enabled",
        "greeting",
        "system_prompt",
        "llm_provider",
        "llm_model",
        "tts_voice",
        "timezone",
        "default_appointment_duration_minutes",
        "twilio_account_sid",
    ):
        if key in updates:
            db_updates[key] = updates[key]

    if "twilio_phone_number" in updates:
        new_number = updates["twilio_phone_number"]
        clash = repo.get_voice_config_by_twilio_number(new_number)
        if clash and clash["company_id"] != company_id:
            raise ConflictError("This Twilio phone number is already attached to another company")
        db_updates["twilio_phone_number"] = new_number

    if "twilio_auth_token" in updates:
        db_updates["twilio_auth_token_encrypted"] = encrypt_secret(updates["twilio_auth_token"])
    if "llm_api_key" in updates:
        db_updates["llm_api_key_encrypted"] = encrypt_secret(updates["llm_api_key"])

    row = repo.update_voice_config(company_id, db_updates)
    return _config_to_response(row)


def get_decrypted_secrets(company_id: str) -> Dict[str, Optional[str]]:
    row = repo.get_or_create_voice_config(company_id)
    return {
        "twilio_auth_token": decrypt_secret(row.get("twilio_auth_token_encrypted")),
        "llm_api_key": decrypt_secret(row.get("llm_api_key_encrypted")),
    }


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def _availability_to_response(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "weekly_hours": row.get("weekly_hours") or {},
        "slot_granularity_minutes": int(row.get("slot_granularity_minutes") or 30),
        "buffer_minutes": int(row.get("buffer_minutes") or 15),
        "daily_cap": int(row.get("daily_cap") or 8),
    }


def get_availability(company_id: str) -> Dict[str, Any]:
    row = repo.get_or_create_availability(company_id)
    return _availability_to_response(row)


def update_availability(company_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    updates = {k: v for k, v in updates.items() if v is not None}
    db_updates: Dict[str, Any] = {}
    if "weekly_hours" in updates:
        weekly = updates["weekly_hours"]
        if hasattr(weekly, "items"):
            db_updates["weekly_hours"] = {
                k: (v.model_dump() if hasattr(v, "model_dump") else v)
                for k, v in weekly.items()
            }
        else:
            db_updates["weekly_hours"] = weekly
    for key in ("slot_granularity_minutes", "buffer_minutes", "daily_cap"):
        if key in updates:
            db_updates[key] = updates[key]
    row = repo.update_availability(company_id, db_updates)
    return _availability_to_response(row)


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

def list_bookings(company_id: str, status: Optional[str] = None) -> Dict[str, Any]:
    rows = repo.list_bookings(company_id, status=status)
    return {"bookings": rows, "total": len(rows)}


def cancel_booking(company_id: str, booking_id: str) -> Dict[str, Any]:
    existing = repo.get_booking(booking_id, company_id)
    if not existing:
        raise NotFoundError("Booking not found")
    if existing["status"] == "cancelled":
        return existing
    updated = repo.update_booking_status(booking_id, company_id, "cancelled")
    return updated or existing


def create_booking_internal(
    company_id: str,
    *,
    customer_name: str,
    customer_phone: str,
    starts_at_utc: datetime,
    duration_minutes: int,
    service_type: Optional[str] = None,
    address: Optional[str] = None,
    notes: Optional[str] = None,
    call_id: Optional[str] = None,
) -> Dict[str, Any]:
    if starts_at_utc.tzinfo is None:
        starts_at_utc = starts_at_utc.replace(tzinfo=timezone.utc)
    ends_at_utc = starts_at_utc + __import__("datetime").timedelta(minutes=duration_minutes)
    if not availability_mod.is_slot_free(company_id, starts_at_utc, ends_at_utc):
        raise ConflictError("Requested time slot is no longer available")
    if not customer_name.strip() or not customer_phone.strip():
        raise ValidationError("customer_name and customer_phone are required")

    return repo.insert_booking(
        {
            "company_id": company_id,
            "call_id": call_id,
            "customer_name": customer_name.strip(),
            "customer_phone": customer_phone.strip(),
            "service_type": service_type,
            "address": address,
            "notes": notes,
            "starts_at": starts_at_utc.isoformat(),
            "ends_at": ends_at_utc.isoformat(),
            "status": "scheduled",
        }
    )


# ---------------------------------------------------------------------------
# Call logs
# ---------------------------------------------------------------------------

def list_calls(company_id: str) -> Dict[str, Any]:
    rows = repo.list_calls(company_id)
    return {"calls": rows, "total": len(rows)}


def start_call_log(
    company_id: str,
    twilio_call_sid: str,
    from_number: Optional[str],
    to_number: Optional[str],
) -> Dict[str, Any]:
    existing = repo.get_call_by_sid(twilio_call_sid)
    if existing:
        return existing
    return repo.insert_call_log(
        {
            "company_id": company_id,
            "twilio_call_sid": twilio_call_sid,
            "from_number": from_number,
            "to_number": to_number,
            "direction": "inbound",
            "status": "in-progress",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "transcript": [],
        }
    )


def append_transcript(call_id: str, role: str, text: str) -> None:
    call = repo.update_call(call_id, {})  # no-op fetch; keeps API cohesive
    if not call:
        return
    transcript: List[Dict[str, Any]] = list(call.get("transcript") or [])
    transcript.append(
        {"role": role, "text": text, "timestamp": datetime.now(timezone.utc).timestamp()}
    )
    repo.update_call(call_id, {"transcript": transcript})


def finalize_call_log(
    twilio_call_sid: str,
    status: str,
    duration_seconds: Optional[int] = None,
    error: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    call = repo.get_call_by_sid(twilio_call_sid)
    if not call:
        return None
    updates: Dict[str, Any] = {
        "status": status,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    if duration_seconds is not None:
        updates["duration_seconds"] = duration_seconds
    if error:
        updates["error"] = error
    return repo.update_call(call["call_id"], updates)
