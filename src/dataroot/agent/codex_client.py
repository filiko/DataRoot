"""
Single Codex API client for DataRoot.

Wraps the Codex API (or OpenAI compatible API) for tool-calling.
Owns API key, request/response handling, retry logic.
"""

import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentResult:
    """Result of an agent run."""
    messages: list[dict[str, Any]]
    final_output: str | None
    tool_calls: list[dict[str, Any]]
    error: str | None


_MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"


def _is_minimax(model: str) -> bool:
    return model.startswith("MiniMax")


class CodexClient:
    """Single API wrapper for Codex / OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model or os.environ.get("DATAROOT_MODEL", "gpt-4o")
        if _is_minimax(self.model):
            self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        else:
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url
        self._session = None

    def run(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> AgentResult:
        """
        Run a tool-calling loop with the given system prompt and messages.

        Returns AgentResult with messages, final_output, tool_calls, and error.
        """
        tool_calls = []
        conversation = list(messages)

        for attempt in range(max_retries):
            try:
                api_messages = [{"role": "system", "content": system_prompt}] + conversation
                response = self._call(api_messages, tools, temperature)
                assistant_message = response["message"]
                conversation.append(assistant_message)

                if response.get("finish_reason") == "stop":
                    return AgentResult(
                        messages=conversation,
                        final_output=assistant_message.get("content"),
                        tool_calls=tool_calls,
                        error=None,
                    )

                if assistant_message.get("tool_calls"):
                    for tc in assistant_message["tool_calls"]:
                        tool_calls.append(tc)
                    return AgentResult(
                        messages=conversation,
                        final_output=None,
                        tool_calls=tool_calls,
                        error=None,
                    )
                return AgentResult(
                    messages=conversation,
                    final_output=assistant_message.get("content"),
                    tool_calls=tool_calls,
                    error=None,
                )

            except Exception as e:
                if attempt == max_retries - 1:
                    return AgentResult(
                        messages=conversation,
                        final_output=None,
                        tool_calls=tool_calls,
                        error=str(e),
                    )
                time.sleep(2 ** attempt)

        return AgentResult(
            messages=conversation,
            final_output=None,
            tool_calls=tool_calls,
            error="Max retries exceeded",
        )

    def _call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
    ) -> dict[str, Any]:
        """Make a single API call. Override for different API shapes."""
        if _is_minimax(self.model):
            return self._call_minimax(messages, tools, temperature)
        return self._call_openai(messages, tools, temperature)

    def _call_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
    ) -> dict[str, Any]:
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message.model_dump(exclude_none=True)
        return {
            "message": message,
            "finish_reason": response.choices[0].finish_reason,
        }

    def _call_minimax(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
    ) -> dict[str, Any]:
        import requests

        # MiniMax exposes an Anthropic-compatible endpoint — extract system from messages
        system = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_messages.append(m)

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system:
            payload["system"] = system

        base = (self.base_url or _MINIMAX_BASE_URL).rstrip("/")
        resp = requests.post(
            f"{base}/v1/messages",
            headers={
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        # MiniMax may return thinking blocks before the text block
        text = next((b["text"] for b in data.get("content", []) if b.get("type") == "text"), None)
        stop_reason = data.get("stop_reason")
        return {
            "message": {"role": "assistant", "content": text},
            "finish_reason": "stop" if stop_reason == "end_turn" else stop_reason,
        }
