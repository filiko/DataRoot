"""
Single tool-calling runner for DataRoot.

Signature: run(system_prompt, tools, user_input) -> AgentResult.

Harness-agnostic: tools are JSON schemas, not SDK objects.
"""

from dataclasses import dataclass
from typing import Any

from .codex_client import CodexClient, AgentResult


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]


class Runner:
    """Single tool-calling loop for DataRoot."""

    def __init__(self, client: CodexClient | None = None):
        self.client = client or CodexClient()

    def run(
        self,
        system_prompt: str,
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tool_executor: callable | None = None,
        temperature: float = 0.7,
    ) -> AgentResult:
        """
        Run the agent loop.

        Args:
            system_prompt: The system prompt for this role.
            tools: List of JSON schemas for allowed tools.
            messages: Conversation history (user messages already added).
            tool_executor: Optional function(tool_name, tool_args) -> result.
                           If None, the runner returns after collecting tool calls.
            temperature: Model temperature.

        Returns:
            AgentResult with messages, final_output, tool_calls, error.
        """
        result = self.client.run(system_prompt, messages, tools, temperature)

        # If there are tool calls and we have an executor, run them
        while result.tool_calls and tool_executor:
            for tc in result.tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = tc["function"]["arguments"]
                if isinstance(tool_args, str):
                    import json
                    tool_args = json.loads(tool_args)

                tool_result = tool_executor(tool_name, tool_args)

                result.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tool_name,
                    "content": str(tool_result),
                })

            # Continue with tool results
            result = self.client.run(
                system_prompt,
                result.messages,
                tools,
                temperature,
            )

        return result
