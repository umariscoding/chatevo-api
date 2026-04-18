"""
Smoke tests for the voice agent feature.

These don't hit real Twilio / Groq / Whisper / Piper. They exercise audio
conversion, encryption round-trip, the availability slot generator, and
basic schema validation — the parts we can test without external services.
"""

import os
from datetime import date, datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

def test_encryption_round_trip(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("VOICE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    # Clear lru_cache so the new key is picked up.
    from app.core import encryption

    encryption._fernet.cache_clear()

    ciphertext = encryption.encrypt_secret("super-secret-token")
    assert ciphertext
    assert ciphertext != "super-secret-token"
    assert encryption.decrypt_secret(ciphertext) == "super-secret-token"


def test_encryption_handles_empty(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("VOICE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.core import encryption

    encryption._fernet.cache_clear()

    assert encryption.encrypt_secret(None) is None
    assert encryption.encrypt_secret("") is None
    assert encryption.decrypt_secret(None) is None


# ---------------------------------------------------------------------------
# Audio conversion
# ---------------------------------------------------------------------------

def test_mulaw_roundtrip_preserves_length_ratio():
    from app.features.voice import audio_utils

    # 160 bytes of μ-law = 20 ms @ 8kHz → roughly 640 bytes PCM16 @ 16kHz.
    # audioop.ratecv keeps filter history across calls, so the first call
    # can produce a couple fewer samples than the ideal ratio.
    mulaw = b"\x7f" * 160
    pcm16 = audio_utils.mulaw8k_to_pcm16_16k(mulaw)
    assert 620 <= len(pcm16) <= 660
    assert len(pcm16) % 2 == 0  # PCM16 is 2 bytes per sample


def test_chunk_mulaw_splits_into_20ms_frames():
    from app.features.voice import audio_utils

    data = b"\xff" * 500
    chunks = audio_utils.chunk_mulaw(data, chunk_size=160)
    assert len(chunks) == 4
    assert len(chunks[0]) == 160
    assert len(chunks[-1]) == 20


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_voice_config_update_rejects_bad_phone():
    from pydantic import ValidationError
    from app.features.voice.schemas import VoiceConfigUpdate

    with pytest.raises(ValidationError):
        VoiceConfigUpdate(twilio_phone_number="415-555-1212")


def test_voice_config_update_accepts_e164():
    from app.features.voice.schemas import VoiceConfigUpdate

    model = VoiceConfigUpdate(twilio_phone_number="+14155551212")
    assert model.twilio_phone_number == "+14155551212"


def test_day_hours_rejects_bad_time():
    from pydantic import ValidationError
    from app.features.voice.schemas import DayHours

    with pytest.raises(ValidationError):
        DayHours(open="25:00", close="26:00")


# ---------------------------------------------------------------------------
# Availability slot generation (pure function — no DB)
# ---------------------------------------------------------------------------

def test_generate_slots_single_day_basic():
    from app.features.voice.availability import generate_slots

    availability = {
        "weekly_hours": {
            "mon": {"open": "09:00", "close": "11:00", "enabled": True},
        },
        "slot_granularity_minutes": 30,
        "buffer_minutes": 0,
        "daily_cap": 10,
    }
    # Pick a known Monday.
    day = date(2026, 4, 20)
    slots = generate_slots(
        availability, "UTC", day, duration_minutes=60, existing_bookings=[]
    )
    # 9-10, 9:30-10:30, 10-11 → 3 slots.
    assert len(slots) == 3
    assert slots[0][0].isoformat().startswith("2026-04-20T09:00")


def test_generate_slots_honors_bookings_and_buffer():
    from app.features.voice.availability import generate_slots

    availability = {
        "weekly_hours": {
            "mon": {"open": "09:00", "close": "12:00", "enabled": True},
        },
        "slot_granularity_minutes": 30,
        "buffer_minutes": 15,
        "daily_cap": 10,
    }
    day = date(2026, 4, 20)
    booked_start = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    booking = {
        "starts_at": booked_start.isoformat(),
        "ends_at": (booked_start + timedelta(minutes=60)).isoformat(),
        "status": "scheduled",
    }
    slots = generate_slots(
        availability, "UTC", day, duration_minutes=30, existing_bookings=[booking]
    )
    # Anything that would overlap 09:45-11:15 (booking ± 15 min buffer) is gone.
    for s, e in slots:
        assert e <= datetime(2026, 4, 20, 9, 45, tzinfo=timezone.utc) or s >= datetime(
            2026, 4, 20, 11, 15, tzinfo=timezone.utc
        )


def test_generate_slots_returns_empty_when_day_disabled():
    from app.features.voice.availability import generate_slots

    availability = {
        "weekly_hours": {
            "mon": {"open": "09:00", "close": "17:00", "enabled": False},
        },
        "slot_granularity_minutes": 30,
        "buffer_minutes": 0,
        "daily_cap": 10,
    }
    slots = generate_slots(availability, "UTC", date(2026, 4, 20), 60, [])
    assert slots == []


# ---------------------------------------------------------------------------
# TwiML
# ---------------------------------------------------------------------------

def test_build_stream_twiml_has_stream_and_params():
    from app.features.voice.twilio_utils import build_stream_twiml

    xml = build_stream_twiml(
        "wss://api.example.com/voice/twilio/stream",
        greeting="Hi & welcome",
        custom_params={"company_id": "abc", "call_id": "123"},
    )
    assert "<Stream" in xml
    assert "wss://api.example.com/voice/twilio/stream" in xml
    assert '<Parameter name="company_id" value="abc"' in xml
    assert '<Parameter name="call_id" value="123"' in xml
    # Greeting ampersand is escaped.
    assert "Hi &amp; welcome" in xml
