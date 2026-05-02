"""
Voice Agent — HTTP and WebSocket endpoints.

Both browser and Twilio paths run through the same Pipecat pipeline
(`pipeline.py`). The browser uses SmallWebRTC (WebRTC peer connection,
SDP offer/answer); Twilio uses its WebSocket media stream.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from app.core.security import get_current_user_info
from app.features.auth.dependencies import get_current_company, UserContext
from app.features.auth.repository import get_company_by_id
from app.features.billing.service import is_plan_active
from app.features.voice_agent import service
from app.features.voice_agent.call_log_repository import list_call_logs
from app.features.voice_agent.repository import get_settings as get_va_settings
from app.features.voice_agent.schemas import VoiceAgentSettingsRequest

# Pipecat imports (aiortc, opencv, silero/torch) are deferred to call-handler
# bodies so they don't run on app startup. Loading them eagerly at module
# import slows boot by 20–30s on Railway and bloats memory for every tenant
# regardless of whether they ever touch voice.

logger = logging.getLogger("wispoke.voice")

router = APIRouter(prefix="/voice-agent", tags=["voice-agent"])


# ---------------------------------------------------------------------------
# Settings CRUD
# ---------------------------------------------------------------------------

@router.get("/settings")
async def get_settings(current_user: UserContext = Depends(get_current_company)):
    return service.get_settings(current_user.company_id)


@router.put("/settings")
async def update_settings(
    body: VoiceAgentSettingsRequest,
    current_user: UserContext = Depends(get_current_company),
):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    return service.update_settings(current_user.company_id, data)


# ---------------------------------------------------------------------------
# Call logs (transcripts + linked bookings)
# ---------------------------------------------------------------------------

@router.get("/call-logs")
async def get_call_logs(
    limit: int = 25,
    offset: int = 0,
    current_user: UserContext = Depends(get_current_company),
):
    page = list_call_logs(current_user.company_id, limit=limit, offset=offset)
    return {
        "call_logs": page["items"],
        "total": page["total"],
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(page["items"]) < page["total"],
    }


# ---------------------------------------------------------------------------
# Browser test call — Pipecat SmallWebRTC SDP offer/answer
# ---------------------------------------------------------------------------

@router.post("/offer")
async def voice_agent_offer(payload: Dict[str, Any], token: str = ""):
    """Browser POSTs an SDP offer here; we return an SDP answer.

    Auth: JWT in `?token=...` query param (the Pipecat client SDK can attach
    arbitrary query params to its connection URL).
    """
    user_info = get_current_user_info(token) if token else None
    if not user_info or user_info.get("user_type") != "company":
        raise HTTPException(status_code=401, detail="Unauthorized")

    company_id = user_info.get("company_id")
    company = get_company_by_id(company_id)
    if not company or not is_plan_active(company):
        raise HTTPException(status_code=403, detail="Voice agent requires a Pro plan.")

    va_settings = get_va_settings(company_id) or {}

    from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequest
    from app.features.voice_agent.pipeline import handle_browser_offer

    request = SmallWebRTCRequest(
        sdp=payload["sdp"],
        type=payload["type"],
        pc_id=payload.get("pc_id"),
        restart_pc=payload.get("restart_pc"),
    )

    answer = await handle_browser_offer(request, company_id, va_settings)
    if answer is None:
        raise HTTPException(status_code=500, detail="Failed to negotiate WebRTC connection")
    return answer


@router.patch("/offer")
async def voice_agent_offer_patch(payload: Dict[str, Any], token: str = ""):
    """Browser PATCHes ICE candidates for an in-flight peer connection.

    Pipecat's PATCH payload is `{pc_id, candidates: [{candidate, sdp_mid,
    sdp_mline_index}]}` — different shape than POST (no `sdp`/`type`).
    """
    user_info = get_current_user_info(token) if token else None
    if not user_info or user_info.get("user_type") != "company":
        raise HTTPException(status_code=401, detail="Unauthorized")

    company = get_company_by_id(user_info.get("company_id"))
    if not company or not is_plan_active(company):
        raise HTTPException(status_code=403, detail="Voice agent requires a Pro plan.")

    from pipecat.transports.smallwebrtc.request_handler import (
        IceCandidate,
        SmallWebRTCPatchRequest,
    )
    from app.features.voice_agent.pipeline import handle_browser_patch

    candidates = [
        IceCandidate(
            candidate=c.get("candidate", ""),
            sdp_mid=c.get("sdp_mid") or c.get("sdpMid") or "",
            sdp_mline_index=c.get("sdp_mline_index") if c.get("sdp_mline_index") is not None else c.get("sdpMLineIndex", 0),
        )
        for c in payload.get("candidates", [])
    ]
    patch = SmallWebRTCPatchRequest(pc_id=payload["pc_id"], candidates=candidates)

    await handle_browser_patch(patch)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Twilio incoming call (public)
# ---------------------------------------------------------------------------

@router.post("/twilio/incoming")
async def twilio_incoming_call(request: Request):
    """Twilio hits this URL on incoming calls; we return TwiML that points
    Twilio's <Stream> at our WebSocket media endpoint."""
    form = await request.form()
    called_number = form.get("Called", "")
    call_sid = form.get("CallSid", "")
    logger.info(f"Incoming call to {called_number}, CallSid: {call_sid}")

    settings = service.get_settings_for_call(called_number)
    if not settings:
        twiml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<Response>\n"
            "    <Say>Sorry, this number is not configured for automated scheduling. Goodbye.</Say>\n"
            "    <Hangup/>\n"
            "</Response>"
        )
        return Response(content=twiml, media_type="application/xml")

    company = get_company_by_id(settings["company_id"])
    if not company or not is_plan_active(company):
        logger.warning("Twilio call rejected — no active Pro plan for company %s", settings["company_id"])
        twiml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<Response>\n"
            "    <Say>This number's subscription is not active. Goodbye.</Say>\n"
            "    <Hangup/>\n"
            "</Response>"
        )
        return Response(content=twiml, media_type="application/xml")

    base_url = str(request.base_url).rstrip("/")
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = f"{ws_url}/voice-agent/media-stream/{settings['company_id']}"

    twiml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Response>\n"
        "    <Connect>\n"
        f"        <Stream url=\"{ws_url}\">\n"
        f"            <Parameter name=\"company_id\" value=\"{settings['company_id']}\" />\n"
        "        </Stream>\n"
        "    </Connect>\n"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@router.websocket("/media-stream/{company_id}")
async def media_stream(websocket: WebSocket, company_id: str):
    """Twilio connects here to stream call audio."""
    await websocket.accept()
    logger.info(f"Media stream connected for company: {company_id}")

    va_settings = get_va_settings(company_id)
    if not va_settings or not va_settings.get("is_enabled"):
        logger.warning(f"Voice agent not enabled for company: {company_id}")
        await websocket.close()
        return

    company = get_company_by_id(company_id)
    if not company or not is_plan_active(company):
        logger.warning(f"Voice agent denied — no active Pro plan for company: {company_id}")
        await websocket.close()
        return

    from app.features.voice_agent.pipeline import run_twilio_call

    try:
        await run_twilio_call(websocket, company_id, va_settings)
    except WebSocketDisconnect:
        logger.info(f"Media stream disconnected for company: {company_id}")
    except Exception:
        logger.exception("Media stream error")
