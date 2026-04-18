"""
Voice agent HTTP router.

Mounts:
    /voice/config          (GET, PUT)   — per-company agent settings
    /voice/availability    (GET, PUT)   — business hours + slot rules
    /voice/bookings        (GET)        — list bookings
    /voice/bookings/{id}/cancel (POST)  — cancel a booking
    /voice/calls           (GET)        — call logs with transcripts
    /voice/twilio/incoming (POST)       — Twilio webhook → TwiML → Media Stream
    /voice/twilio/status   (POST)       — Twilio call status callback
    /voice/twilio/stream   (WS)         — Twilio Media Streams websocket

Admin endpoints use the existing company JWT dependency. Twilio endpoints
identify the company by the dialed number (+ optional signature validation).
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from fastapi.responses import Response

from app.features.auth.dependencies import get_current_company, UserContext
from app.features.voice import repository as repo
from app.features.voice import service
from app.features.voice import twilio_utils
from app.features.voice.schemas import (
    AvailabilityResponse,
    AvailabilityUpdate,
    BookingListResponse,
    BookingResponse,
    CallLogListResponse,
    CallLogResponse,
    VoiceConfigResponse,
    VoiceConfigUpdate,
)
from app.features.voice.ws_handler import handle_media_stream


logger = logging.getLogger("wispoke.voice")

router = APIRouter(prefix="/voice", tags=["voice"])


# ---------------------------------------------------------------------------
# /voice/config
# ---------------------------------------------------------------------------

@router.get("/config", response_model=VoiceConfigResponse)
def get_config(user: UserContext = Depends(get_current_company)) -> VoiceConfigResponse:
    return VoiceConfigResponse(**service.get_config(user.company_id))


@router.put("/config", response_model=VoiceConfigResponse)
def put_config(
    data: VoiceConfigUpdate,
    user: UserContext = Depends(get_current_company),
) -> VoiceConfigResponse:
    payload = data.model_dump(exclude_unset=True)
    return VoiceConfigResponse(**service.update_config(user.company_id, payload))


# ---------------------------------------------------------------------------
# /voice/availability
# ---------------------------------------------------------------------------

@router.get("/availability", response_model=AvailabilityResponse)
def get_availability(user: UserContext = Depends(get_current_company)) -> AvailabilityResponse:
    return AvailabilityResponse(**service.get_availability(user.company_id))


@router.put("/availability", response_model=AvailabilityResponse)
def put_availability(
    data: AvailabilityUpdate,
    user: UserContext = Depends(get_current_company),
) -> AvailabilityResponse:
    payload = data.model_dump(exclude_unset=True)
    return AvailabilityResponse(**service.update_availability(user.company_id, payload))


# ---------------------------------------------------------------------------
# /voice/bookings
# ---------------------------------------------------------------------------

@router.get("/bookings", response_model=BookingListResponse)
def list_bookings(
    status: Optional[str] = None,
    user: UserContext = Depends(get_current_company),
) -> BookingListResponse:
    result = service.list_bookings(user.company_id, status=status)
    return BookingListResponse(
        bookings=[BookingResponse(**b) for b in result["bookings"]],
        total=result["total"],
    )


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: str,
    user: UserContext = Depends(get_current_company),
) -> BookingResponse:
    return BookingResponse(**service.cancel_booking(user.company_id, booking_id))


# ---------------------------------------------------------------------------
# /voice/calls
# ---------------------------------------------------------------------------

@router.get("/calls", response_model=CallLogListResponse)
def list_calls(user: UserContext = Depends(get_current_company)) -> CallLogListResponse:
    result = service.list_calls(user.company_id)
    return CallLogListResponse(
        calls=[CallLogResponse(**c) for c in result["calls"]],
        total=result["total"],
    )


# ---------------------------------------------------------------------------
# Twilio webhooks
# ---------------------------------------------------------------------------

async def _validate_twilio_request(request: Request, form: Dict[str, str]) -> Dict[str, Any]:
    """Resolve company_id by dialed number and validate the Twilio signature."""
    to_number = (form.get("To") or "").strip()
    if not to_number:
        raise HTTPException(status_code=400, detail="Missing 'To' parameter")
    config_row = repo.get_voice_config_by_twilio_number(to_number)
    if not config_row:
        raise HTTPException(status_code=404, detail="No voice agent is configured for this number")
    if not config_row.get("enabled"):
        raise HTTPException(status_code=403, detail="Voice agent is disabled for this company")

    secrets = service.get_decrypted_secrets(config_row["company_id"])
    auth_token = secrets.get("twilio_auth_token") or ""
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if not twilio_utils.validate_signature(auth_token, url, form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    return config_row


@router.post("/twilio/incoming")
async def twilio_incoming(request: Request) -> Response:
    form = dict(await request.form())
    config_row = await _validate_twilio_request(request, form)

    call_sid = form.get("CallSid") or ""
    from_number = form.get("From")
    to_number = form.get("To")
    call_log = service.start_call_log(
        config_row["company_id"],
        twilio_call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
    )

    base_url = os.getenv("PUBLIC_API_BASE_URL", "").rstrip("/")
    if base_url.startswith("https://"):
        ws_base = "wss://" + base_url[len("https://"):]
    elif base_url.startswith("http://"):
        ws_base = "ws://" + base_url[len("http://"):]
    else:
        # Fall back to request host.
        scheme = "wss" if request.url.scheme == "https" else "ws"
        ws_base = f"{scheme}://{request.url.netloc}"

    stream_url = f"{ws_base}/voice/twilio/stream"
    twiml = twilio_utils.build_stream_twiml(
        stream_url,
        config_row.get("greeting") or "Hello.",
        custom_params={
            "company_id": config_row["company_id"],
            "call_id": call_log["call_id"],
            "from_number": from_number or "",
        },
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/twilio/status")
async def twilio_status(request: Request) -> Response:
    form = dict(await request.form())
    await _validate_twilio_request(request, form)
    call_sid = form.get("CallSid") or ""
    call_status = form.get("CallStatus") or "completed"
    duration = form.get("CallDuration")
    duration_seconds = int(duration) if duration and duration.isdigit() else None
    service.finalize_call_log(
        call_sid,
        status=call_status,
        duration_seconds=duration_seconds,
    )
    return Response(status_code=204)


@router.websocket("/twilio/stream")
async def twilio_stream(ws: WebSocket) -> None:
    """Twilio Media Streams endpoint. The company is identified via the
    customParameters Twilio forwards in the `start` frame (set by TwiML
    query string on the <Stream> URL)."""
    # Companion query params make local testing easier; production uses the
    # customParameters from Twilio's start frame, which ws_handler reads.
    await handle_media_stream(ws)
