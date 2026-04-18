"""
LLM driver for the voice agent.

Uses the OpenAI-compatible Chat Completions API shape so a single code path
works for Groq (default), Ollama (self-hosted), and OpenAI.

The driver owns a short tool-call loop: if the model responds with a tool
call, we execute the tool, append the result, and re-query until the model
produces a plain assistant message or we hit a safety cap.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx

from app.features.voice import llm_tools


_DEFAULT_ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "ollama": "http://localhost:11434/v1/chat/completions",
}


def _endpoint_for(provider: str) -> str:
    override = os.getenv(f"{provider.upper()}_API_BASE")
    if override:
        return override.rstrip("/") + "/chat/completions"
    return _DEFAULT_ENDPOINTS.get(provider, _DEFAULT_ENDPOINTS["groq"])


class LLMClient:
    """Stateful chat session: system prompt + rolling history."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: Optional[str],
        system_prompt: str,
        company_id: str,
        default_duration_minutes: int,
        call_id: Optional[str] = None,
        caller_phone: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.company_id = company_id
        self.call_id = call_id
        self.caller_phone = caller_phone
        self.default_duration_minutes = default_duration_minutes
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]

    async def say(self, user_text: str, *, max_tool_iterations: int = 4) -> str:
        self.messages.append({"role": "user", "content": user_text})
        return await self._run_until_reply(max_tool_iterations)

    async def _run_until_reply(self, max_tool_iterations: int) -> str:
        for _ in range(max_tool_iterations):
            reply = await self._completion()
            msg = reply["choices"][0]["message"]
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                content = (msg.get("content") or "").strip()
                self.messages.append({"role": "assistant", "content": content})
                return content

            self.messages.append(
                {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )
            for call in tool_calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = llm_tools.run_tool(
                    company_id=self.company_id,
                    tool_name=name,
                    arguments=args,
                    default_duration_minutes=self.default_duration_minutes,
                    call_id=self.call_id,
                    caller_phone=self.caller_phone,
                )
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "name": name,
                        "content": json.dumps(result),
                    }
                )
        # Safety cap: force a plain assistant reply.
        return "Sorry, I'm having trouble completing that. Could you repeat?"

    async def _completion(self) -> Dict[str, Any]:
        endpoint = _endpoint_for(self.provider)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": self.messages,
            "tools": llm_tools.TOOL_SCHEMAS,
            "tool_choice": "auto",
            "temperature": 0.3,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"LLM call failed: {resp.status_code} {resp.text[:200]}")
            return resp.json()
