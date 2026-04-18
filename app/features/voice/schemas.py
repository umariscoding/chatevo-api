"""
Pydantic schemas for the voice agent feature.

Response shapes are intentionally documented here so the admin UI's
src/types/voiceAgent.ts can be diffed against them.
"""

from datetime import datetime, time
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


DayKey = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_DEFAULT_WEEKLY_HOURS: Dict[str, Dict[str, Any]] = {
    "mon": {"open": "08:00", "close": "17:00", "enabled": True},
    "tue": {"open": "08:00", "close": "17:00", "enabled": True},
    "wed": {"open": "08:00", "close": "17:00", "enabled": True},
    "thu": {"open": "08:00", "close": "17:00", "enabled": True},
    "fri": {"open": "08:00", "close": "17:00", "enabled": True},
    "sat": {"open": "09:00", "close": "13:00", "enabled": False},
    "sun": {"open": "09:00", "close": "13:00", "enabled": False},
}


# ---------------------------------------------------------------------------
# Voice config
# ---------------------------------------------------------------------------

class VoiceConfigResponse(BaseModel):
    enabled: bool
    greeting: str
    system_prompt: str
    llm_provider: str
    llm_model: str
    tts_voice: str
    timezone: str
    default_appointment_duration_minutes: int
    twilio_account_sid: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    # Secrets are never returned. Boolean hints only.
    twilio_auth_token_set: bool = False
    llm_api_key_set: bool = False


class VoiceConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    greeting: Optional[str] = Field(default=None, max_length=500)
    system_prompt: Optional[str] = Field(default=None, max_length=4000)
    llm_provider: Optional[Literal["groq", "ollama", "openai"]] = None
    llm_model: Optional[str] = Field(default=None, max_length=100)
    llm_api_key: Optional[str] = Field(default=None, max_length=500)
    tts_voice: Optional[str] = Field(default=None, max_length=100)
    timezone: Optional[str] = Field(default=None, max_length=64)
    default_appointment_duration_minutes: Optional[int] = Field(default=None, ge=5, le=480)
    twilio_account_sid: Optional[str] = Field(default=None, max_length=100)
    twilio_auth_token: Optional[str] = Field(default=None, max_length=200)
    twilio_phone_number: Optional[str] = Field(default=None, max_length=32)

    @field_validator("twilio_phone_number")
    @classmethod
    def _normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            return None
        if not stripped.startswith("+") or not stripped[1:].isdigit():
            raise ValueError("twilio_phone_number must be E.164 (e.g. +14155551212)")
        return stripped


# ---------------------------------------------------------------------------
# Availability config
# ---------------------------------------------------------------------------

class DayHours(BaseModel):
    open: str = Field(..., description="HH:MM 24h")
    close: str = Field(..., description="HH:MM 24h")
    enabled: bool = True

    @field_validator("open", "close")
    @classmethod
    def _parse_hhmm(cls, v: str) -> str:
        try:
            time.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("must be HH:MM (24h)") from exc
        return v


class AvailabilityResponse(BaseModel):
    weekly_hours: Dict[str, DayHours]
    slot_granularity_minutes: int
    buffer_minutes: int
    daily_cap: int


class AvailabilityUpdate(BaseModel):
    weekly_hours: Optional[Dict[DayKey, DayHours]] = None
    slot_granularity_minutes: Optional[int] = Field(default=None, ge=5, le=240)
    buffer_minutes: Optional[int] = Field(default=None, ge=0, le=240)
    daily_cap: Optional[int] = Field(default=None, ge=1, le=100)


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

class BookingResponse(BaseModel):
    booking_id: str
    company_id: str
    call_id: Optional[str] = None
    customer_name: str
    customer_phone: str
    service_type: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    status: str
    created_at: datetime


class BookingListResponse(BaseModel):
    bookings: List[BookingResponse]
    total: int


# ---------------------------------------------------------------------------
# Call logs
# ---------------------------------------------------------------------------

class TranscriptTurn(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    text: str
    timestamp: Optional[float] = None


class CallLogResponse(BaseModel):
    call_id: str
    company_id: str
    twilio_call_sid: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    direction: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    transcript: List[TranscriptTurn] = Field(default_factory=list)
    booking_id: Optional[str] = None
    recording_url: Optional[str] = None
    error: Optional[str] = None


class CallLogListResponse(BaseModel):
    calls: List[CallLogResponse]
    total: int


DEFAULT_WEEKLY_HOURS = _DEFAULT_WEEKLY_HOURS
