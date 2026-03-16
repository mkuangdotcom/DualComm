from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.utils import (
    as_str,
    build_prompt_input,
    derive_sender_name,
    placeholder_response,
)
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
        score_threshold: float = 0.3,
        category: Optional[str] = None,
    ) -> None:
        self.model_name = model_name or "unset"
        self.system_prompt = system_prompt or (
            "You are a helpful assistant connected to WhatsApp."
        )
        self.score_threshold = score_threshold
        self.category = category

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
                "llamaindex_error": retrieval.get("error"),
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
