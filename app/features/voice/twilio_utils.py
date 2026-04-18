"""
Twilio-specific helpers: TwiML response, webhook signature validation.
"""

import os
from typing import Dict, Optional
from xml.sax.saxutils import escape

from twilio.request_validator import RequestValidator


def build_stream_twiml(
    stream_url: str,
    greeting: str,
    custom_params: Optional[Dict[str, str]] = None,
) -> str:
    """TwiML that plays the greeting then connects a Media Stream.

    custom_params become <Parameter> children of <Stream>; Twilio forwards
    them in the `start` frame as `customParameters` so the WS handler can
    recover company_id and call_id without parsing the query string.
    """
    params_xml = ""
    for k, v in (custom_params or {}).items():
        params_xml += f'    <Parameter name="{escape(k)}" value="{escape(v)}"/>\n'
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        f"  <Say>{escape(greeting)}</Say>\n"
        "  <Connect>\n"
        f'    <Stream url="{escape(stream_url)}">\n'
        f"{params_xml}"
        "    </Stream>\n"
        "  </Connect>\n"
        "</Response>"
    )


def validate_signature(auth_token: str, url: str, params: Dict[str, str], signature: str) -> bool:
    if os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() == "false":
        return True
    if not auth_token or not signature:
        return False
    validator = RequestValidator(auth_token)
    return validator.validate(url, params, signature)
