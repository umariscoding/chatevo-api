"""
Twilio Media Streams bridge.

Protocol (https://www.twilio.com/docs/voice/twiml/stream):
    Twilio sends JSON frames: {"event": "start"|"media"|"stop"|"mark", ...}
    - "start":  {"streamSid": "...", "start": {"callSid": "...", "customParameters": {...}}}
    - "media":  {"streamSid": "...", "media": {"payload": "<base64 mulaw 8k>"}}
    - "stop":   end of stream

We send frames back as:
    {"event": "media", "streamSid": "...", "media": {"payload": "<base64 mulaw 8k>"}}
    {"event": "mark", "streamSid": "...", "mark": {"name": "..."}}
    {"event": "clear", "streamSid": "..."}  (to stop current playback on barge-in)

Speech endpointing is intentionally simple: buffer inbound audio, and after
~1s of relative silence (measured via linear RMS) treat the buffer as a full
utterance, ship it to Whisper, then to the LLM, then to Piper, then back.
"""

from __future__ import annotations

import asyncio
import audioop
import base64
import json
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.features.voice import audio_utils
from app.features.voice import repository as repo
from app.features.voice import service as voice_service
from app.features.voice import stt_client, tts_client
from app.features.voice.llm_client import LLMClient


logger = logging.getLogger("wispoke.voice")

# μ-law frame is 160 bytes = 20 ms @ 8kHz. PCM16 equivalent = 320 bytes.
# Silence threshold is in linear16 RMS units; 500 is a reasonable default for
# a phone line. Tune via WHISPER_VAD_RMS / WHISPER_VAD_SILENCE_MS.
_SILENCE_RMS = 500
_SILENCE_MS = 1000
_MIN_UTTERANCE_MS = 300
_MAX_UTTERANCE_MS = 15000


async def _send_audio_to_twilio(ws: WebSocket, stream_sid: str, pcm_mulaw: bytes) -> None:
    for chunk in audio_utils.chunk_mulaw(pcm_mulaw, chunk_size=160):
        if not chunk:
            continue
        await ws.send_text(
            json.dumps(
                {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": base64.b64encode(chunk).decode("ascii")},
                }
            )
        )
        # Pace output roughly in real time so barge-in stays responsive.
        await asyncio.sleep(0.019)


async def _speak(
    ws: WebSocket,
    stream_sid: str,
    text: str,
    voice: str,
    call_id: Optional[str],
) -> None:
    if not text.strip():
        return
    try:
        wav = await tts_client.synthesize(text, voice)
    except Exception as exc:  # sidecar down / misconfigured
        logger.warning("TTS failure: %s", exc)
        return
    mulaw = audio_utils.tts_wav_to_mulaw8k(wav)
    if call_id:
        voice_service.append_transcript(call_id, "assistant", text)
    await _send_audio_to_twilio(ws, stream_sid, mulaw)


async def handle_media_stream(ws: WebSocket) -> None:
    """Entry point for WS /voice/twilio/stream. Driven entirely by Twilio frames."""
    await ws.accept()
    stream_sid: Optional[str] = None
    company_id: Optional[str] = None
    call_id: Optional[str] = None
    caller_phone: Optional[str] = None
    llm: Optional[LLMClient] = None
    voice: str = "en_US-amy-medium"

    pcm_buffer = bytearray()
    silence_ms = 0.0
    speech_ms = 0.0
    busy = {"value": False}  # mutable flag so inner callbacks can flip it

    def _set_idle() -> None:
        busy["value"] = False

    try:
        while True:
            raw = await ws.receive_text()
            frame = json.loads(raw)
            event = frame.get("event")

            if event == "start":
                stream_sid = frame["streamSid"]
                custom = (frame.get("start") or {}).get("customParameters") or {}
                company_id = custom.get("company_id")
                call_id = custom.get("call_id")
                caller_phone = custom.get("from_number")
                if not company_id:
                    logger.warning("Media stream started without company_id; closing.")
                    await ws.close()
                    return
                config_row = repo.get_or_create_voice_config(company_id)
                secrets = voice_service.get_decrypted_secrets(company_id)
                voice = config_row.get("tts_voice") or voice
                llm = LLMClient(
                    provider=config_row.get("llm_provider") or "groq",
                    model=config_row.get("llm_model") or "llama-3.3-70b-versatile",
                    api_key=secrets.get("llm_api_key"),
                    system_prompt=config_row.get("system_prompt") or "",
                    company_id=company_id,
                    default_duration_minutes=int(
                        config_row.get("default_appointment_duration_minutes") or 60
                    ),
                    call_id=call_id,
                    caller_phone=caller_phone,
                )
                logger.info("voice stream started company=%s call=%s", company_id, call_id)
                continue

            if event == "media" and stream_sid and llm:
                payload_b64 = frame["media"]["payload"]
                mulaw_chunk = base64.b64decode(payload_b64)
                pcm16_16k = audio_utils.mulaw8k_to_pcm16_16k(mulaw_chunk)
                pcm_buffer.extend(pcm16_16k)

                # Each 20 ms μ-law chunk → 640 bytes PCM16@16k (40 ms worth).
                rms = audioop.rms(pcm16_16k, 2) if pcm16_16k else 0
                dur_ms = (len(pcm16_16k) / 2) / 16.0  # samples → ms
                if rms < _SILENCE_RMS:
                    silence_ms += dur_ms
                else:
                    silence_ms = 0.0
                    speech_ms += dur_ms

                ready_to_flush = (
                    not busy["value"]
                    and speech_ms >= _MIN_UTTERANCE_MS
                    and (silence_ms >= _SILENCE_MS or speech_ms >= _MAX_UTTERANCE_MS)
                )
                if ready_to_flush:
                    utterance = bytes(pcm_buffer)
                    pcm_buffer.clear()
                    silence_ms = 0.0
                    speech_ms = 0.0
                    busy["value"] = True
                    asyncio.create_task(
                        _process_utterance(
                            ws,
                            stream_sid=stream_sid,
                            utterance=utterance,
                            llm=llm,
                            voice=voice,
                            call_id=call_id,
                            on_done=_set_idle,
                        )
                    )
                continue

            if event == "stop":
                logger.info("voice stream stopped stream_sid=%s", stream_sid)
                break

            # "mark" / "connected" / anything else — ignore.
    except WebSocketDisconnect:
        logger.info("voice websocket disconnected")
    except Exception:
        logger.exception("voice websocket error")
    finally:
        try:
            await ws.close()
        except Exception:
            pass


async def _process_utterance(
    ws: WebSocket,
    *,
    stream_sid: str,
    utterance: bytes,
    llm: LLMClient,
    voice: str,
    call_id: Optional[str],
    on_done,
) -> None:
    try:
        try:
            text = await stt_client.transcribe_pcm16(utterance, language="en")
        except Exception as exc:
            logger.warning("STT error: %s", exc)
            return
        if not text:
            return
        if call_id:
            voice_service.append_transcript(call_id, "user", text)
        try:
            reply = await llm.say(text)
        except Exception as exc:
            logger.warning("LLM error: %s", exc)
            reply = "Sorry, I'm having trouble right now. Could you say that again?"
        await _speak(ws, stream_sid, reply, voice, call_id)
    finally:
        try:
            on_done()
        except Exception:
            pass
