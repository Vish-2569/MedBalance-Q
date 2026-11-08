from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResult:
    output: Any
    model: str
    confidence: float
    tokens_in: int
    tokens_out: int
    tool_calls: list[dict[str, Any]] | None = None
    raw: Any = None


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: float = 20.0,
    ) -> LLMResult: ...

    @abstractmethod
    def name(self) -> str: ...


def _openai_tools_to_gemini(tools: list[dict[str, Any]], types: Any) -> list[Any]:
    declarations = []
    for tool in tools:
        fn = tool.get("function", tool)
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        declarations.append(types.FunctionDeclaration(
            name=name,
            description=desc,
            parameters=params if params else None,
        ))
    if not declarations:
        return []
    return [types.Tool(function_declarations=declarations)]


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        from google import genai
        self._client = genai.Client(api_key=api_key)

    def name(self) -> str:
        return "gemini"

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: float = 20.0,
    ) -> LLMResult:
        from google.genai import types

        system_msg = None
        contents = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            elif m["role"] == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=m["content"])]))
            elif m["role"] == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part(text=m["content"])]))

        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system_msg:
            config_kwargs["system_instruction"] = system_msg
        if schema and not tools:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_json_schema"] = schema

        if tools:
            gemini_tools = _openai_tools_to_gemini(tools, types)
            if gemini_tools:
                config_kwargs["tools"] = gemini_tools

        config = types.GenerateContentConfig(**config_kwargs)

        resp = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        tool_calls_out: list[dict[str, Any]] = []
        text_parts: list[str] = []
        if resp.candidates and resp.candidates[0].content:
            for part in resp.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    tool_calls_out.append({
                        "name": fc.name,
                        "args": dict(fc.args) if fc.args else {},
                    })
                elif part.text:
                    text_parts.append(part.text)

        text = "".join(text_parts)
        try:
            output = json.loads(text) if text else {"text": ""}
        except (json.JSONDecodeError, ValueError):
            output = {"text": text}

        tokens_in = resp.usage_metadata.prompt_token_count if resp.usage_metadata else 0
        tokens_out = resp.usage_metadata.candidates_token_count if resp.usage_metadata else 0

        return LLMResult(
            output=output,
            model=model,
            confidence=1.0,
            tokens_in=tokens_in or 0,
            tokens_out=tokens_out or 0,
            tool_calls=tool_calls_out or None,
        )


class FakeProvider(LLMProvider):
    """For testing. Returns canned responses or echoes input."""

    def __init__(self, responses: list[dict[str, Any]] | None = None):
        self._responses = list(responses) if responses else []
        self._call_count = 0
        self.calls: list[dict[str, Any]] = []

    def name(self) -> str:
        return "fake"

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: float = 20.0,
    ) -> LLMResult:
        self.calls.append({
            "messages": messages,
            "schema": schema,
            "model": model,
            "temperature": temperature,
        })

        if self._responses:
            output = self._responses[self._call_count % len(self._responses)]
        else:
            output = {"reply": "fake response"}

        self._call_count += 1
        return LLMResult(
            output=output,
            model=model,
            confidence=0.99,
            tokens_in=10,
            tokens_out=5,
        )
