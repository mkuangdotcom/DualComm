from __future__ import annotations

import asyncio
import importlib
import os
from typing import Any, Dict, List, Optional

from app.services.utils import (
    as_str,
    build_prompt_input,
    derive_sender_name,
    parse_model_spec,
    placeholder_response,
)
from app.settings import get_settings
from rag.retriever import retrieve as qdrant_retrieve


class LlamaIndexRuntime:
    """
    LlamaIndex runtime adapter that uses the Qdrant RAG retriever
    for context retrieval in the messaging Python bridge.
    """

    def __init__(
        self,
        *,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        timeout_seconds: float = 25.0,
        rag_top_k: int = 3,
        score_threshold: float = 0.3,
        category: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.llamaindex_model or settings.langchain_model
        self.system_prompt = system_prompt or (
            "You are a helpful assistant connected to WhatsApp."
        )
        self.timeout_seconds = max(timeout_seconds, 1.0)
        self.rag_top_k = max(rag_top_k, 1)
        self.score_threshold = score_threshold
        self.category = category

        self._init_error: Optional[str] = None
        self._runtime_error: Optional[str] = None
        self._chain: Optional[Any] = None

        if self.model_name:
            llm = self._build_chat_model(self.model_name)
            if llm is not None:
                self._chain = self._build_chain(llm)
        else:
            self._init_error = "No model configured for LlamaIndex runtime."

    async def handle_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
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

        response_text = placeholder_response(
            sender_name=sender_name,
            message_type=message_type,
            runtime_label="LlamaIndex runtime scaffold",
        )

        retrieval = await self.retrieve_context(
            query_text=text or caption or prompt_input,
            top_k=self.rag_top_k,
        )

        context_chunks = retrieval.get("chunks", [])
        context_block = "\n\n".join(context_chunks) if context_chunks else "(No relevant context found.)"

        if self._chain is None:
            response_text = placeholder_response(
                sender_name=sender_name,
                message_type=message_type,
                runtime_label="LlamaIndex runtime",
            )
            generation_status = "fallback_no_model"
            self._runtime_error = None
        else:
            try:
                response_text = await asyncio.wait_for(
                    self._chain.ainvoke(
                        {
                            "system_prompt": self.system_prompt,
                            "prompt_input": prompt_input,
                            "retrieved_context": context_block,
                        }
                    ),
                    timeout=self.timeout_seconds,
                )
                response_text = self._sanitize_response_text(response_text)
                if not response_text:
                    response_text = placeholder_response(
                        sender_name=sender_name,
                        message_type=message_type,
                        runtime_label="LlamaIndex runtime",
                    )
                    generation_status = "fallback_empty_response"
                else:
                    generation_status = "ok"
                self._runtime_error = None
            except TimeoutError:
                response_text = (
                    "I am taking too long to respond right now. "
                    "Please try again in a moment."
                )
                generation_status = "timeout"
                self._runtime_error = "Request timed out"
            except Exception as exc:
                self._runtime_error = str(exc)
                response_text = placeholder_response(
                    sender_name=sender_name,
                    message_type=message_type,
                    runtime_label="LlamaIndex runtime",
                )
                generation_status = "fallback_error"

        return {
            "actions": [
                {
                    "type": "send_text",
                    "text": response_text,
                }
            ],
            "metadata": {
                "runtime": "llamaindex",
                "model_name": self.model_name,
                "handled_message_type": message_type,
                "llamaindex_status": retrieval.get("status", "no_context"),
                "llamaindex_context_count": len(retrieval.get("chunks", [])),
                "llamaindex_error": retrieval.get("error"),
                "llamaindex_generation_status": generation_status,
                "llamaindex_init_error": self._init_error,
                "llamaindex_runtime_error": self._runtime_error,
            },
        }

    async def retrieve_context(self, query_text: str, top_k: int = 3) -> Dict[str, Any]:
        result = qdrant_retrieve(
            query=query_text,
            top_k=top_k,
            category=self.category,
            score_threshold=self.score_threshold,
        )

        status = result.get("status", "error")
        error = result.get("error")
        raw_chunks: List[dict] = result.get("chunks", [])

        plain_chunks: List[str] = []
        for chunk in raw_chunks:
            text = chunk.get("text", "").strip()
            source = chunk.get("source", "")
            category = chunk.get("category", "")
            score = chunk.get("score", "")

            parts = [text]
            tags = []
            if source:
                tags.append(f"source: {source}")
            if category:
                tags.append(f"category: {category}")
            if score:
                tags.append(f"score: {score}")
            if tags:
                parts.append(f"[{', '.join(tags)}]")

            plain_chunks.append("\n".join(parts))

        return {
            "status": status,
            "chunks": plain_chunks,
            "error": error,
        }

    def _build_chat_model(self, model_spec: str) -> Any:
        provider, model = parse_model_spec(
            model_spec,
            default_provider="groq",
            default_model="qwen/qwen3-32b",
        )
        settings = get_settings()

        if provider == "openai":
            openai_api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
            if not openai_api_key:
                self._init_error = (
                    "OPENAI_API_KEY is not set. "
                    "LlamaIndex runtime is running in fallback mode."
                )
                return None

            try:
                chat_openai_module = importlib.import_module("langchain_openai")
                chat_openai_cls = getattr(chat_openai_module, "ChatOpenAI")
            except Exception:
                self._init_error = (
                    "langchain-openai is not installed. "
                    "Install it to enable LlamaIndex runtime model calls."
                )
                return None

            return chat_openai_cls(model=model, temperature=0, api_key=openai_api_key)

        if provider == "groq":
            groq_api_key = os.getenv("GROQ_API_KEY") or settings.groq_api_key
            if not groq_api_key:
                self._init_error = (
                    "GROQ_API_KEY is not set. "
                    "LlamaIndex runtime is running in fallback mode."
                )
                return None

            try:
                chat_groq_module = importlib.import_module("langchain_groq")
                chat_groq_cls = getattr(chat_groq_module, "ChatGroq")
            except Exception:
                self._init_error = (
                    "langchain-groq is not installed. "
                    "Install it to enable LlamaIndex runtime with Groq models."
                )
                return None

            return chat_groq_cls(
                model=model,
                temperature=0.3,
                max_tokens=2048,
                top_p=0.95,
                api_key=groq_api_key,
            )

        self._init_error = (
            f"Unsupported provider '{provider}' for LlamaIndex runtime. "
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
                "Install it to enable LlamaIndex runtime model calls."
            )
            return None

        prompt = chat_prompt_template.from_messages(
            [
                ("system", "{system_prompt}"),
                (
                    "human",
                    "User message context:\n{prompt_input}\n\n"
                    "Retrieved context:\n{retrieved_context}\n\n"
                    "Provide one concise and helpful response for the user. "
                    "If context is missing, say so briefly.",
                ),
            ]
        )
        return prompt | llm | str_output_parser()

    @staticmethod
    def _sanitize_response_text(value: Any) -> str:
        text = value if isinstance(value, str) else ("" if value is None else str(value))
        return text.strip()
