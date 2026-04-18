"""
LLM tool definitions + dispatch for the voice agent.

Two tools are exposed to the LLM (Groq by default; shape is OpenAI-compatible
so the same JSON works for Ollama and OpenAI):
    - check_availability(duration_minutes?, after_iso?)
    - create_booking(customer_name, customer_phone, starts_at_iso,
                      duration_minutes?, service_type?, address?, notes?)

Tool handlers are pure functions against the service layer — no network,
so they're safe to run synchronously inside the async WS loop.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import AppException
from app.features.voice import availability as availability_mod
from app.features.voice import service as voice_service


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "List the next available appointment slots for the business. "
                "Call this before offering a time to the caller."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Override the default appointment duration.",
                    },
                    "after_iso": {
                        "type": "string",
                        "description": (
                            "Only return slots at or after this ISO-8601 UTC timestamp. "
                            "Leave blank for 'as soon as possible'."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "How many slots to return (default 5).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_booking",
            "description": (
                "Book an appointment once the caller has confirmed name, phone, and a "
                "slot returned by check_availability."
            ),
            "parameters": {
                "type": "object",
                "required": ["customer_name", "customer_phone", "starts_at_iso"],
                "properties": {
                    "customer_name": {"type": "string"},
                    "customer_phone": {"type": "string"},
                    "starts_at_iso": {
                        "type": "string",
                        "description": "ISO-8601 UTC start time of the chosen slot.",
                    },
                    "duration_minutes": {"type": "integer"},
                    "service_type": {
                        "type": "string",
                        "description": "e.g. 'leaky faucet', 'water heater replacement'.",
                    },
                    "address": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        },
    },
]


def _parse_iso_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppException(f"Invalid ISO timestamp: {value}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def run_tool(
    *,
    company_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
    default_duration_minutes: int,
    call_id: Optional[str] = None,
    caller_phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a tool call and return a JSON-serializable result."""
    if tool_name == "check_availability":
        duration = int(arguments.get("duration_minutes") or default_duration_minutes)
        after = _parse_iso_utc(arguments.get("after_iso"))
        max_results = int(arguments.get("max_results") or 5)
        slots = availability_mod.next_available_slots(
            company_id,
            duration_minutes=duration,
            after=after,
            max_results=max_results,
        )
        return {"slots": slots, "duration_minutes": duration}

    if tool_name == "create_booking":
        starts_at = _parse_iso_utc(arguments.get("starts_at_iso"))
        if starts_at is None:
            return {"ok": False, "error": "starts_at_iso is required"}
        duration = int(arguments.get("duration_minutes") or default_duration_minutes)
        try:
            booking = voice_service.create_booking_internal(
                company_id,
                customer_name=arguments.get("customer_name", "").strip(),
                customer_phone=(arguments.get("customer_phone") or caller_phone or "").strip(),
                starts_at_utc=starts_at,
                duration_minutes=duration,
                service_type=arguments.get("service_type"),
                address=arguments.get("address"),
                notes=arguments.get("notes"),
                call_id=call_id,
            )
        except AppException as exc:
            return {"ok": False, "error": exc.message}
        return {"ok": True, "booking_id": booking["booking_id"], "starts_at": booking["starts_at"]}

    return {"ok": False, "error": f"unknown tool {tool_name}"}
