from __future__ import annotations

import importlib
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from app.services.utils import (
    as_str,
    build_prompt_input,
    derive_sender_name,
    placeholder_response,
)


class LlamaIndexRuntime:
    """
    LlamaIndex-ready runtime adapter scaffold for the messaging Python bridge.

    This class mirrors the LangChain scaffold but keeps the integration points
    tailored to a future LlamaIndex pipeline (indexes, retrievers, and agents).
    """

    def __init__(
        self,
        *,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        documents_dir: Optional[str] = None,
    ) -> None:
        self.model_name = model_name or "unset"
        self.system_prompt = system_prompt or (
            "You are a helpful assistant connected to WhatsApp."
        )
        self.documents_dir = Path(documents_dir or "./docs/rag/malay")
        self._documents_cache: Optional[List[str]] = None
        self._init_error: Optional[str] = None

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
            top_k=3,
        )

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
                "llamaindex_error": retrieval.get("error") or self._init_error,
            },
        }

    async def retrieve_context(self, query_text: str, top_k: int = 3) -> Dict[str, Any]:
        docs = self._load_documents()

        if not docs:
            return {
                "status": "no_documents",
                "chunks": [],
                "error": self._init_error,
            }

        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return {
                "status": "empty_query",
                "chunks": [],
                "error": None,
            }

        scored: List[tuple[int, str]] = []
        for chunk in docs:
            chunk_tokens = self._tokenize(chunk)
            overlap = len(query_tokens.intersection(chunk_tokens))
            if overlap > 0:
                scored.append((overlap, chunk))

        if not scored:
            return {
                "status": "no_match",
                "chunks": [],
                "error": None,
            }

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [self._shorten(text) for _, text in scored[: max(top_k, 1)]]
        return {
            "status": "ok",
            "chunks": selected,
            "error": None,
        }

    def _load_documents(self) -> List[str]:
        if self._documents_cache is not None:
            return self._documents_cache

        if not self.documents_dir.exists():
            self._documents_cache = []
            self._init_error = f"LlamaIndex docs directory not found: {self.documents_dir}"
            return self._documents_cache

        # Prefer LlamaIndex loader when available so this runtime stays aligned
        # with the intended retrieval stack.
        try:
            core_module = importlib.import_module("llama_index.core")
            reader_cls = getattr(core_module, "SimpleDirectoryReader")
            documents = reader_cls(
                input_dir=str(self.documents_dir),
                recursive=True,
            ).load_data()

            self._documents_cache = [
                (getattr(doc, "text", "") or "").strip()
                for doc in documents
                if (getattr(doc, "text", "") or "").strip()
            ]
            return self._documents_cache
        except Exception as exc:
            self._init_error = str(exc)

        # Fallback file loader keeps retrieval alive when llama_index is missing
        # or cannot parse a specific file format.
        loaded: List[str] = []
        for file_path in self.documents_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in {".txt", ".md"}:
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    loaded.append(text)
            except OSError:
                continue

        self._documents_cache = loaded
        return self._documents_cache

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        tokens = re.findall(r"[A-Za-z0-9_]+", (text or "").lower())
        return set(tokens)

    @staticmethod
    def _shorten(text: str, limit: int = 500) -> str:
        if len(text) <= limit:
            return text
        return f"{text[:limit].rstrip()}..."


