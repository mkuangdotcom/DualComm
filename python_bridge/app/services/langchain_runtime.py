from __future__ import annotations

import asyncio
import importlib
import os
import re
from typing import Any, Dict, Optional

from app.services.utils import (
    as_str,
    build_prompt_input,
    derive_sender_name,
    parse_model_spec,
    placeholder_response,
)
from app.settings import get_settings


class LangChainRuntime:
    """
    LangChain runtime adapter for the messaging Python bridge.

    This class is intentionally lightweight for now. Its purpose is to define
    the integration boundary between the normalized inbound bridge payload and a
    future LangChain-based agent workflow.

    Current behavior:
    - accepts normalized inbound payloads from the TypeScript bridge
    - runs a basic prompt through LangChain when a provider is configured
    - falls back to safe scaffold text when model dependencies are unavailable
    - returns contract-compliant outbound actions
    """

    def __init__(
        self,
        *,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        timeout_seconds: float = 25.0,
    ) -> None:
        self.model_name = model_name or "groq:qwen/qwen3-32b"
        self.system_prompt = system_prompt or (
            "You are a helpful assistant connected to Telegram and WhatsApp. "
            "Answer clearly, safely, and concisely."
        )
        self.timeout_seconds = max(timeout_seconds, 1.0)

        self._init_error: Optional[str] = None
        self._runtime_error: Optional[str] = None
        self._chain: Optional[Any] = None

        llm = self._build_chat_model(self.model_name)
        if llm is not None:
            self._chain = self._build_chain(llm)

    async def handle_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a normalized inbound bridge payload and return outbound actions.

        The returned structure must remain compatible with the bridge contract:
        {
            "actions": [...],
            "metadata": {...}
        }
        """
        message = payload.get("message", {}) or {}

        message_type = as_str(message.get("messageType"), default="unknown")
        sender_name = as_str(message.get("senderName")) or derive_sender_name(
            as_str(message.get("senderId"))
        )
        text = as_str(message.get("text"))
        caption = as_str(message.get("caption"))
        media = message.get("media") or []

        prompt_input = build_prompt_input(
            message_type=message_type,
            text=text,
            caption=caption,
            media=media,
            sender_name=sender_name,
        )

        if self._chain is None:
            response_text = placeholder_response(
                sender_name=sender_name,
                message_type=message_type,
                runtime_label="LangChain runtime",
            )
            status = "fallback_no_model"
            self._runtime_error = None
        else:
            try:
                response_text = await asyncio.wait_for(
                    self._chain.ainvoke(
                        {
                            "system_prompt": self.system_prompt,
                            "prompt_input": prompt_input,
                        }
                    ),
                    timeout=self.timeout_seconds,
                )
                response_text = self._sanitize_response_text(response_text)
                if not response_text or not response_text.strip():
                    response_text = placeholder_response(
                        sender_name=sender_name,
                        message_type=message_type,
                        runtime_label="LangChain runtime",
                    )
                    status = "fallback_empty_response"
                else:
                    status = "ok"
                self._runtime_error = None
            except TimeoutError:
                response_text = (
                    "I am taking too long to respond right now. "
                    "Please try again in a moment."
                )
                status = "timeout"
                self._runtime_error = "Request timed out"
            except Exception as exc:
                self._runtime_error = str(exc)
                response_text = placeholder_response(
                    sender_name=sender_name,
                    message_type=message_type,
                    runtime_label="LangChain runtime",
                )
                status = "fallback_error"

        return {
            "actions": [
                {
                    "type": "send_text",
                    "text": response_text,
                }
            ],
            "metadata": {
                "runtime": "langchain",
                "model_name": self.model_name,
                "handled_message_type": message_type,
                "langchain_status": status,
                "langchain_init_error": self._init_error,
                "langchain_runtime_error": self._runtime_error,
            },
        }

    def _build_chat_model(self, model_spec: str) -> Any:
        provider, model = parse_model_spec(model_spec)
        settings = get_settings()

        if provider == "openai":
            openai_api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
            if not openai_api_key:
                self._init_error = (
                    "OPENAI_API_KEY is not set. "
                    "LangChain runtime is running in fallback mode."
                )
                return None

            try:
                chat_openai_module = importlib.import_module("langchain_openai")
                chat_openai_cls = getattr(chat_openai_module, "ChatOpenAI")
            except Exception:
                self._init_error = (
                    "langchain-openai is not installed. "
                    "Install it to enable AGENT_BACKEND=langchain model calls."
                )
                return None

            return chat_openai_cls(model=model, temperature=0, api_key=openai_api_key)

        if provider == "groq":
            groq_api_key = os.getenv("GROQ_API_KEY") or settings.groq_api_key
            if not groq_api_key:
                self._init_error = (
                    "GROQ_API_KEY is not set. "
                    "LangChain runtime is running in fallback mode."
                )
                return None

            try:
                chat_groq_module = importlib.import_module("langchain_groq")
                chat_groq_cls = getattr(chat_groq_module, "ChatGroq")
            except Exception:
                self._init_error = (
                    "langchain-groq is not installed. "
                    "Install it to enable AGENT_BACKEND=langchain with Groq models."
                )
                return None

            return chat_groq_cls(
                model=model,
                temperature=0.6,
                max_tokens=4096,
                top_p=0.95,
                api_key=groq_api_key,
            )

        self._init_error = (
            f"Unsupported LangChain provider '{provider}'. "
            "Supported providers: groq, openai"
        )
        return None

    def _build_chain(self, llm: Any) -> Optional[Any]:
        try:
            prompts_module = importlib.import_module("langchain_core.prompts")
            parsers_module = importlib.import_module("langchain_core.output_parsers")

            chat_prompt_template = getattr(prompts_module, "ChatPromptTemplate")
            str_output_parser = getattr(parsers_module, "StrOutputParser")
        except Exception:
            self._init_error = (
                "langchain-core is not installed. "
                "Install it to enable AGENT_BACKEND=langchain model calls."
            )
            return None

        prompt = chat_prompt_template.from_messages(
            [
                ("system", "{system_prompt}"),
                (
                    "human",
                    "User message context:\n{prompt_input}\n\n"
                    "Generate one helpful reply for the user.",
                ),
            ]
        )
        return prompt | llm | str_output_parser()

    @staticmethod
    def _sanitize_response_text(value: Any) -> str:
        text = value if isinstance(value, str) else ("" if value is None else str(value))
        # Remove hidden reasoning blocks if a model accidentally emits them.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
        return text.strip()
