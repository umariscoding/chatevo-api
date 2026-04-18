"""
Audio format helpers for the Twilio Media Streams bridge.

Twilio sends and expects audio as μ-law (G.711) 8 kHz mono, base64-encoded in
JSON frames. Whisper wants PCM16 mono 16 kHz. Piper emits PCM16 mono at the
voice's native rate (usually 22050 Hz) wrapped in WAV. This module bridges
those formats using the stdlib `audioop` and `wave` modules.

Using audioop keeps the runtime dependency-free for audio work.
"""

from __future__ import annotations

import audioop
import io
import wave
from typing import Tuple


def mulaw8k_to_pcm16_16k(mulaw_bytes: bytes) -> bytes:
    """Convert Twilio μ-law 8 kHz → PCM16 16 kHz for Whisper."""
    if not mulaw_bytes:
        return b""
    pcm16_8k = audioop.ulaw2lin(mulaw_bytes, 2)
    pcm16_16k, _ = audioop.ratecv(pcm16_8k, 2, 1, 8000, 16000, None)
    return pcm16_16k


def _wav_to_pcm16(wav_bytes: bytes) -> Tuple[bytes, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        rate = w.getframerate()
        nchannels = w.getnchannels()
        sampwidth = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if sampwidth != 2:
        frames = audioop.lin2lin(frames, sampwidth, 2)
    if nchannels == 2:
        frames = audioop.tomono(frames, 2, 0.5, 0.5)
    return frames, rate


def tts_wav_to_mulaw8k(wav_bytes: bytes) -> bytes:
    """Convert Piper WAV (any rate, mono/stereo) → μ-law 8 kHz for Twilio."""
    if not wav_bytes:
        return b""
    pcm16, rate = _wav_to_pcm16(wav_bytes)
    if rate != 8000:
        pcm16, _ = audioop.ratecv(pcm16, 2, 1, rate, 8000, None)
    return audioop.lin2ulaw(pcm16, 2)


def chunk_mulaw(data: bytes, chunk_size: int = 160) -> list[bytes]:
    """Split μ-law bytes into 20 ms frames (160 samples @ 8kHz = 160 bytes)."""
    return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
