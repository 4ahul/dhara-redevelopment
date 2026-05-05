"""
LLM Client Abstraction Layer
Supports multiple backends: Ollama, OpenAI-compatible, Anthropic (production), Mock (testing)
"""

import json
import logging
import os
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Base class for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> dict:
        """Send a chat request and return the response."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model name."""


class OllamaClient(LLMClient):
    """Ollama local LLM client."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        if not self.base_url:
            raise ValueError("OLLAMA_BASE_URL must be set to use OllamaClient")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2:latest")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": max_tokens,
            },
            "stream": False,
        }

        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

    def get_model_name(self) -> str:
        return self.model


class OpenAICompatibleClient(LLMClient):
    """OpenAI-compatible API client (works with vLLM, LM Studio, etc.)."""

    def __init__(
        self, base_url: str | None = None, api_key: str | None = None, model: str | None = None
    ):
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        if not self.base_url:
            raise ValueError("OPENAI_BASE_URL must be set to use OpenAICompatibleClient")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set to use OpenAICompatibleClient")
        self.model = model or os.getenv("OPENAI_MODEL", "llama-3.1-8b-instruct")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.7),
        }

        if tools:
            # Wrap in OpenAI-standard format: {"type": "function", "function": {...}}
            wrapped = []
            for t in tools:
                if "type" in t and "function" in t:
                    wrapped.append(t)  # already wrapped
                else:
                    wrapped.append(
                        {
                            "type": "function",
                            "function": {
                                "name": t["name"],
                                "description": t.get("description", ""),
                                "parameters": t.get("parameters", t.get("input_schema", {})),
                            },
                        }
                    )
            payload["tools"] = wrapped

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return response.json()

    def get_model_name(self) -> str:
        return self.model


class AnthropicClient(LLMClient):
    """Anthropic Claude client for production."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        import anthropic

        self.client = anthropic.AsyncAnthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> dict:
        system = None
        anthropic_messages = []

        for msg in messages:
            role = msg["role"]

            if role == "system":
                system = msg["content"]
                continue

            if role == "tool":
                # Convert to Anthropic tool_result (must be user role)
                block = {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", msg.get("id", "unknown")),
                    "content": msg.get("content", ""),
                }
                # Merge consecutive tool results into a single user message
                if (
                    anthropic_messages
                    and anthropic_messages[-1]["role"] == "user"
                    and isinstance(anthropic_messages[-1]["content"], list)
                    and any(
                        b.get("type") == "tool_result" for b in anthropic_messages[-1]["content"]
                    )
                ):
                    anthropic_messages[-1]["content"].append(block)
                else:
                    anthropic_messages.append({"role": "user", "content": [block]})
                continue

            if role == "assistant":
                parts = []
                raw = msg.get("content", "")
                if isinstance(raw, list):
                    for p in raw:
                        if p.get("type") == "text" and p.get("text", "").strip():
                            parts.append({"type": "text", "text": p["text"]})
                elif isinstance(raw, str) and raw.strip():
                    parts.append({"type": "text", "text": raw})

                for tc in msg.get("tool_calls", []):
                    fn = tc.get("function", {})
                    args = fn.get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    parts.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", f"tu_{os.urandom(4).hex()}"),
                            "name": fn.get("name", ""),
                            "input": args,
                        }
                    )

                if not parts:
                    parts.append({"type": "text", "text": ""})
                anthropic_messages.append({"role": "assistant", "content": parts})
                continue

            # user role
            anthropic_messages.append({"role": "user", "content": msg.get("content", "")})

        # Convert tools: runner uses `parameters` key, Anthropic needs `input_schema`
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t.get(
                        "input_schema",
                        t.get("parameters", {"type": "object", "properties": {}}),
                    ),
                }
                for t in tools
            ]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=anthropic_messages,
            tools=anthropic_tools or [],
        )

        # Convert to standard OpenAI-compatible format
        tool_calls_out = []
        text_parts = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls_out.append(
                    {
                        "id": block.id,
                        "type": "tool_use",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    }
                )
            elif hasattr(block, "text") and block.text:
                text_parts.append({"type": "text", "text": block.text})

        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": text_parts,
                        "tool_calls": tool_calls_out,
                    },
                    "finish_reason": "tool_use"
                    if tool_calls_out
                    else (response.stop_reason or "end_turn"),
                }
            ]
        }

    def get_model_name(self) -> str:
        return self.model


class GeminiClient(LLMClient):
    """Google Gemini AI client."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        import google.generativeai as genai

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set to use GeminiClient.")

        genai.configure(api_key=self.api_key)
        self.model_name = model or os.getenv("GEMINI_MODEL") or "gemini-3.1-pro-preview"

        try:
            self.client = genai.GenerativeModel(model_name=self.model_name)
        except Exception as e:
            logger.exception("Failed to initialize Gemini model %s: %s", self.model_name, e)
            # Fallback to a very safe model name
            self.client = genai.GenerativeModel(model_name="gemini-3-flash-preview")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> dict:
        # 1. Convert messages to Gemini Content objects
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                continue

            role = "user" if msg["role"] in ("user", "tool") else "model"
            parts = []
            content = msg.get("content", "")

            if msg["role"] == "tool":
                try:
                    res_data = json.loads(content) if isinstance(content, str) else content
                except Exception:
                    res_data = {"raw": content}

                parts.append(
                    {"function_response": {"name": msg.get("name", ""), "response": res_data}}
                )
            elif isinstance(content, list):
                for p in content:
                    if p.get("type") == "text":
                        parts.append({"text": p["text"]})
                    elif p.get("type") == "tool_use":
                        parts.append({"function_call": {"name": p["name"], "args": p["input"]}})
                    elif p.get("type") == "tool_result":
                        parts.append(
                            {
                                "function_response": {
                                    "name": p.get("name", ""),
                                    "response": json.loads(p.get("content", "{}")),
                                }
                            }
                        )
            elif isinstance(content, str) and content:
                parts.append({"text": content})

            # For Gemini 3.x: use raw parts if available (preserves thought_signature)
            if msg.get("_gemini_raw_parts"):
                # Raw protobuf parts from a previous Gemini response — use directly
                # to preserve thought_signature and other metadata
                parts = list(msg["_gemini_raw_parts"])
            elif msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fc_part = {
                        "function_call": {
                            "name": tc["function"]["name"],
                            "args": json.loads(tc["function"]["arguments"]),
                        }
                    }
                    if tc.get("thought_signature"):
                        fc_part["thought_signature"] = tc["thought_signature"]
                    parts.append(fc_part)

            if parts:
                contents.append({"role": role, "parts": parts})

        # 2. Convert tools
        gemini_tools = []
        if tools:
            for tool in tools:
                gemini_tools.append(
                    {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool.get("input_schema", tool.get("parameters", {})),
                    }
                )

        final_tools = [{"function_declarations": gemini_tools}] if gemini_tools else None

        # 3. Sanitize contents — ensure no non-JSON-serializable objects leak through
        #    (e.g. protobuf MapComposite from previous Gemini responses)
        contents = json.loads(json.dumps(contents, default=str))

        # 4. Call generate_content via thread pool (sync SDK)
        try:
            import asyncio as _asyncio
            import functools as _functools

            response = await _asyncio.to_thread(
                _functools.partial(
                    self.client.generate_content,
                    contents,
                    tools=final_tools,
                    generation_config={
                        "max_output_tokens": max_tokens,
                        "temperature": kwargs.get("temperature", 0.7),
                    },
                )
            )
        except Exception as e:
            logger.exception("Gemini API call failed: %s", e)
            raise

        # 4. Parse result
        tool_calls = []
        text_content = ""

        # Also capture raw parts for Gemini 3.x thought_signature support
        raw_parts = []
        if response.candidates:
            for part in response.candidates[0].content.parts:
                raw_parts.append(part)
                if part.text:
                    text_content += part.text
                if part.function_call:
                    fn = part.function_call
                    # Deep-convert protobuf MapComposite/RepeatedComposite to plain Python
                    args_clean = self._proto_to_dict(fn.args)
                    # Capture thought_signature if present (Gemini 3.x requirement)
                    tc_entry = {
                        "id": f"call_{os.urandom(8).hex()}",
                        "type": "function",
                        "function": {"name": fn.name, "arguments": json.dumps(args_clean)},
                    }
                    if hasattr(part, "thought_signature") and part.thought_signature:
                        tc_entry["thought_signature"] = part.thought_signature
                    tool_calls.append(tc_entry)

        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": text_content}] if text_content else [],
                        "tool_calls": tool_calls,
                        "_gemini_raw_parts": raw_parts,  # preserve for thought_signature
                    },
                    "finish_reason": "tool_use" if tool_calls else "stop",
                }
            ]
        }

    @staticmethod
    def _proto_to_dict(obj):
        """Recursively convert protobuf MapComposite / RepeatedComposite to plain Python."""
        if hasattr(obj, "keys"):  # MapComposite or dict-like
            return {k: GeminiClient._proto_to_dict(v) for k, v in obj.items()}
        if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
            return [GeminiClient._proto_to_dict(v) for v in obj]
        return obj

    def get_model_name(self) -> str:
        return self.model_name


def get_llm_client() -> LLMClient:
    """
    Factory function — priority order:
    1. GEMINI_API_KEY  → GeminiClient  (default for testing)
    2. ANTHROPIC_API_KEY → AnthropicClient
    3. OLLAMA_BASE_URL  → OllamaClient
    4. OPENAI_BASE_URL  → OpenAICompatibleClient
    """
    # Use os.getenv directly so tests can clear environment variables effectively
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    ollama_url = os.getenv("OLLAMA_BASE_URL")
    ollama_model = os.getenv("OLLAMA_MODEL")
    openai_url = os.getenv("OPENAI_BASE_URL")
    openai_model = os.getenv("OPENAI_MODEL")

    if gemini_key and not gemini_key.startswith("your_"):
        logger.info("Using GeminiClient")
        return GeminiClient(
            api_key=gemini_key, model=os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
        )

    if anthropic_key and not anthropic_key.startswith("sk-ant-your-"):
        logger.info("Using AnthropicClient")
        return AnthropicClient(api_key=anthropic_key)

    if ollama_url or ollama_model:
        logger.info("Using OllamaClient")
        return OllamaClient()

    if openai_url or openai_model:
        logger.info("Using OpenAICompatibleClient")
        return OpenAICompatibleClient()

    raise RuntimeError(
        "No LLM API key configured. Set GEMINI_API_KEY (or ANTHROPIC_API_KEY) "
        "in your environment or .env file."
    )


# Convenience function for async initialization
async def create_llm_client() -> LLMClient:
    return get_llm_client()
