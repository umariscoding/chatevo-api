"""
Piper TTS sidecar client.

Expected sidecar contract:
    POST {PIPER_TTS_URL}/tts
    JSON body: {"text": "...", "voice": "en_US-amy-medium"}
    Response: audio/wav, PCM16 mono 22050 Hz (or whatever the voice outputs;
              we re-read the rate from the WAV header and resample downstream).
"""

import os
from typing import Optional

import httpx


class TTSError(RuntimeError):
    pass


def _base_url() -> Optional[str]:
    return os.getenv("PIPER_TTS_URL") or None


async def synthesize(text: str, voice: str) -> bytes:
    if not text.strip():
        return b""
    base = _base_url()
    if not base:
        raise TTSError("PIPER_TTS_URL is not configured")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base.rstrip('/')}/tts",
            json={"text": text, "voice": voice},
        )
        if resp.status_code >= 400:
            raise TTSError(f"TTS failed: {resp.status_code} {resp.text[:200]}")
        return resp.content
