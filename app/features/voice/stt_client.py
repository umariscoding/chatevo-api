"""
Whisper STT sidecar client.

Expected sidecar contract:
    POST {WHISPER_STT_URL}/transcribe
    Body: raw PCM16 little-endian mono at 16000 Hz, Content-Type: application/octet-stream
    Query: ?sample_rate=16000
    Response JSON: {"text": "..."}

A faster-whisper HTTP wrapper (or similar) satisfies this. We keep the contract
narrow on purpose so the sidecar is swappable.
"""

import os
from typing import Optional

import httpx


class STTError(RuntimeError):
    pass


def _base_url() -> Optional[str]:
    return os.getenv("WHISPER_STT_URL") or None


async def transcribe_pcm16(pcm16_mono_16k: bytes, *, language: Optional[str] = "en") -> str:
    base = _base_url()
    if not base:
        raise STTError("WHISPER_STT_URL is not configured")
    if not pcm16_mono_16k:
        return ""
    params = {"sample_rate": "16000"}
    if language:
        params["language"] = language
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base.rstrip('/')}/transcribe",
            params=params,
            content=pcm16_mono_16k,
            headers={"Content-Type": "application/octet-stream"},
        )
        if resp.status_code >= 400:
            raise STTError(f"STT failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        return (data.get("text") or "").strip()
