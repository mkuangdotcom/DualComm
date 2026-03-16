from __future__ import annotations

from copy import deepcopy
import importlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.langchain_runtime import LangChainRuntime
from app.services.llamaindex_runtime import LlamaIndexRuntime
from app.services.stt_service import STTService
from app.services.utils import parse_model_spec
from app.settings import get_settings

logger = logging.getLogger(__name__)

_VOICE_TYPES = {"voice_note", "audio"}


class HybridRuntime:
    """
    Hybrid runtime pipeline (voice-aware):

    **Voice messages** (parallel STT):
      audio ──┬── /transcriptions → original text + detected language
              └── /translations  → English text
        → translate English text → Malay (LLM)
        → RAG (Malay docs)
        → Agent gets: original text + detected lang + Malay context
        → responds in user's language

    **Text messages**:
      user text → translate → Malay → RAG → Agent → respond in same language
    """

    def __init__(
        self,
        *,
        agent_runtime: LangChainRuntime,
        rag_runtime: LlamaIndexRuntime,
        target_language: str = "Malay",
        rag_top_k: int = 3,
    ) -> None:
        self.agent_runtime = agent_runtime
        self.rag_runtime = rag_runtime
        self.target_language = target_language
        self.rag_top_k = max(rag_top_k, 1)
        self.stt_service = STTService(
            api_key=os.getenv("GROQ_API_KEY") or get_settings().groq_api_key
        )

    async def handle_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        source_message = payload.get("message", {}) or {}

        # ── Voice path: parallel transcribe + translate ──────────────
        stt_combined = await self._maybe_transcribe_audio(source_message)

        if stt_combined is not None and stt_combined["status"] in ("ok", "partial"):
            transcription = stt_combined["transcription"]
            translation = stt_combined["translation"]

            # Original text (user's language)
            original_text = transcription.get("text", "")
            user_language = transcription.get("language", "")

            # For RAG query: use Whisper's English translation, then
            # translate to Malay via LLM for better doc matching
            english_text = translation.get("text", "")
            if english_text:
                translated_query, translation_status = await self._translate_to_target_language(
                    english_text
                )
            else:
                # Fallback: translate original text directly
                translated_query, translation_status = await self._translate_to_target_language(
                    original_text
                )

            logger.info(
                "STT parallel done: lang=%s, original=%d chars, english=%d chars, malay=%d chars",
                user_language,
                len(original_text),
                len(english_text),
                len(translated_query),
            )

        # ── Text path: no STT needed ────────────────────────────────
        else:
            original_text = self._extract_user_text(source_message)
            user_language = ""  # unknown for plain text
            translated_query, translation_status = await self._translate_to_target_language(
                original_text
            )

        # ── RAG retrieval (Malay query → Malay docs) ────────────────
        retrieval = await self.rag_runtime.retrieve_context(
            translated_query,
            top_k=self.rag_top_k,
        )
        context_chunks = retrieval.get("chunks", [])

        # ── Compose agent input ─────────────────────────────────────
        augmented_payload = deepcopy(payload)
        augmented_message = augmented_payload.get("message", {}) or {}
        augmented_message["text"] = self._compose_agent_input(
            original_text=original_text,
            translated_query=translated_query,
            retrieved_chunks=context_chunks,
            target_language=self.target_language,
            user_language=user_language,
        )
        augmented_payload["message"] = augmented_message

        result = await self.agent_runtime.handle_message(augmented_payload)

        # ── Metadata ────────────────────────────────────────────────
        metadata = result.get("metadata") or {}
        metadata.update(
            {
                "runtime": "hybrid",
                "pipeline": "parallel_stt→translate_malay→rag→langchain",
                "stt_status": stt_combined["status"] if stt_combined else "skipped",
                "stt_language": user_language or None,
                "user_language": user_language,
                "translation_target": self.target_language,
                "translation_status": translation_status,
                "rag_status": retrieval.get("status", "unknown"),
                "rag_context_count": len(context_chunks),
                "rag_error": retrieval.get("error"),
                "rag_top_k": self.rag_top_k,
                "rag_score_threshold": self.rag_runtime.score_threshold,
                "rag_category": self.rag_runtime.category,
            }
        )
        result["metadata"] = metadata
        return result

    # ------------------------------------------------------------------
    # STT helpers
    # ------------------------------------------------------------------

    async def _maybe_transcribe_audio(
        self, message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """If the message is a voice note / audio, run parallel STT."""
        message_type = (message.get("messageType") or "").lower()
        if message_type not in _VOICE_TYPES:
            return None

        media_list = message.get("media") or []
        if not media_list:
            return {
                "transcription": {"text": "", "language": "", "status": "error", "error": "No media"},
                "translation": {"text": "", "language": "", "status": "error", "error": "No media"},
                "status": "error",
            }

        storage_path = media_list[0].get("storagePath")
        if not storage_path:
            return {
                "transcription": {"text": "", "language": "", "status": "error", "error": "No storagePath"},
                "translation": {"text": "", "language": "", "status": "error", "error": "No storagePath"},
                "status": "error",
            }

        # Resolve path relative to project root (V Hack/)
        resolved = Path(storage_path)
        if not resolved.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            resolved = project_root / storage_path

        return await self.stt_service.transcribe_and_translate(str(resolved))

    @staticmethod
    def _extract_user_text(message: Dict[str, Any]) -> str:
        text_value = message.get("text")
        if isinstance(text_value, str) and text_value.strip():
            return text_value.strip()

        caption_value = message.get("caption")
        if isinstance(caption_value, str) and caption_value.strip():
            return caption_value.strip()

        return ""

    @staticmethod
    def _compose_agent_input(
        *,
        original_text: str,
        translated_query: str,
        retrieved_chunks: list[str],
        target_language: str,
        user_language: str = "",
    ) -> str:
        context_block = "\n\n".join(retrieved_chunks) if retrieved_chunks else "(No relevant context found.)"

        # Determine reply language
        if user_language:
            lang_instruction = (
                f"The user spoke in {user_language}. "
                f"You MUST reply in {user_language}."
            )
        else:
            lang_instruction = (
                "Reply in the same language as the original user message."
            )

        return (
            "Use the following information to answer the user accurately.\n\n"
            f"Original user message:\n{original_text or '(empty)'}\n\n"
            f"Translated query in {target_language} (for context retrieval only):\n{translated_query or '(empty)'}\n\n"
            f"Retrieved {target_language} context:\n{context_block}\n\n"
            "Response rules:\n"
            f"1. {lang_instruction}\n"
            "2. Use retrieved context if relevant and factual.\n"
            "3. If context is insufficient, say what is missing briefly."
        )

    async def _translate_to_target_language(self, text: str) -> tuple[str, str]:
        if not text.strip():
            return ("", "empty_input")

        model = self._build_translation_model()
        if model is None:
            return (text, "fallback_no_model")

        prompt = (
            f"Translate the user text to {self.target_language}. "
            "Return only the translated text with no explanations."
        )

        try:
            response = await model.ainvoke(
                [
                    ("system", prompt),
                    ("human", text),
                ]
            )
        except Exception:
            return (text, "fallback_error")

        content = self._extract_content(response)
        if not content:
            return (text, "fallback_empty")

        return (content, "ok")

    @staticmethod
    def _extract_content(response: Any) -> str:
        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    value = item.get("text")
                    if isinstance(value, str):
                        parts.append(value)
            return " ".join(part for part in parts if part).strip()

        return ""

    def _build_translation_model(self) -> Optional[Any]:
        model_spec = self.agent_runtime.model_name or "groq:qwen/qwen3-32b"
        provider, model = parse_model_spec(
            model_spec,
            default_provider="groq",
            default_model="qwen/qwen3-32b",
        )
        settings = get_settings()

        if provider != "groq":
            return None

        groq_api_key = os.getenv("GROQ_API_KEY") or settings.groq_api_key
        if not groq_api_key:
            return None

        try:
            chat_groq_module = importlib.import_module("langchain_groq")
            chat_groq_cls = getattr(chat_groq_module, "ChatGroq")
        except Exception:
            return None

        return chat_groq_cls(
            model=model,
            temperature=0,
            max_tokens=512,
            top_p=1,
            api_key=groq_api_key,
        )
