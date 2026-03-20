from __future__ import annotations

import asyncio
from copy import deepcopy
import importlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.langchain_runtime import LangChainRuntime
from app.services.llamaindex_runtime import LlamaIndexRuntime
from app.services.stt_service import STTService
from app.services.advocacy_service import AdvocacyService
from app.services.utils import parse_model_spec
from app.settings import get_settings
from rag.embedder import process_user_image, process_user_pdf

logger = logging.getLogger(__name__)

_VOICE_TYPES = {"voice_note", "audio"}
_IMAGE_TYPES = {"image"}
_DOCUMENT_TYPES = {"pdf", "document"}
_MEDIA_TYPES = _IMAGE_TYPES | _DOCUMENT_TYPES


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
        self.advocacy_service = AdvocacyService(
            groq_api_key=os.getenv("GROQ_API_KEY") or get_settings().groq_api_key
        )
        self.advocacy_sessions: Dict[str, Any] = {}

    async def handle_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        source_message = payload.get("message", {}) or {}
        message_type = (source_message.get("messageType") or "").lower()

        media_result: Optional[Dict[str, Any]] = None

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

        # ── Media path: image / PDF / document ───────────────────────
        elif message_type in _MEDIA_TYPES:
            media_result = await self._maybe_process_media(source_message)

            # Read TS bridge translation metadata for the caption
            ts_media_meta = (
                (source_message.get("context") or {})
                .get("metadata", {})
                .get("translation", {})
            )
            raw_original_caption = ts_media_meta.get("originalCaption", "")
            ts_media_src_lang = ts_media_meta.get("src_lang", "")

            if raw_original_caption:
                original_text = raw_original_caption.strip()
                user_language = ts_media_src_lang or ""
                translated_query = self._extract_user_text(source_message)
                translation_status = "ts_bridge"
            else:
                original_text = self._extract_user_text(source_message)
                user_language = ""
                translated_query, translation_status = await self._translate_to_target_language(
                    original_text
                )

            logger.info(
                "Media processing done: type=%s, status=%s, chunks=%d, caption=%d chars",
                message_type,
                media_result.get("status", "unknown") if media_result else "none",
                len(media_result.get("chunks", [])) if media_result else 0,
                len(original_text),
            )

        # ── Text path: no STT needed ────────────────────────────────
        else:
            # The TypeScript bridge may have already translated the text to Malay.
            # If so, the ORIGINAL user text is stored in context.metadata.translation.originalText
            ts_translation_meta = (
                (source_message.get("context") or {})
                .get("metadata", {})
                .get("translation", {})
            )
            raw_original = ts_translation_meta.get("originalText", "")
            ts_src_lang = ts_translation_meta.get("src_lang", "")

            if raw_original:
                # TS bridge already translated; use original for advocacy & lang detection
                original_text = raw_original.strip()
                user_language = ts_src_lang or ""
                # The current message.text IS already the Malay translation from TS
                translated_query = self._extract_user_text(source_message)
                translation_status = "ts_bridge"
                logger.info(
                    f"TS bridge pre-translated: original='{original_text}', malay='{translated_query}', src_lang='{user_language}'"
                )
            else:
                # No TS translation happened; do it ourselves
                original_text = self._extract_user_text(source_message)
                user_language = ""  # unknown for plain text
                translated_query, translation_status = await self._translate_to_target_language(
                    original_text
                )
                logger.info(f"Fallback translation done: original='{original_text}', malay='{translated_query}'")

        # ── Advocacy Layer: check for sector triggers ───────────────
        advocacy_response = await self._maybe_handle_advocacy(original_text, payload, user_language)
        if advocacy_response:
            return advocacy_response

        # ── RAG retrieval (Malay query → Malay docs) ────────────────
        if media_result and media_result.get("status") in ("ok", "no_match"):
            context_chunks = self._format_raw_chunks(media_result.get("chunks", []))
            retrieval = {"status": media_result["status"], "error": media_result.get("error")}
        else:
            retrieval = await self.rag_runtime.retrieve_context(
                translated_query,
                top_k=self.rag_top_k,
            )
            context_chunks = retrieval.get("chunks", [])

        # ── Compose agent input ─────────────────────────────────────
        agent_input = self._compose_agent_input(
            original_text=original_text,
            translated_query=translated_query,
            retrieved_chunks=context_chunks,
            target_language=self.target_language,
            user_language=user_language,
        )

        augmented_payload = deepcopy(payload)
        if "message" not in augmented_payload:
            augmented_payload["message"] = {}
        augmented_payload["message"]["text"] = agent_input

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
                "media_processing": media_result["status"] if media_result else "skipped",
                "media_type": message_type if media_result else None,
            }
        )
        result["metadata"] = metadata
        return result

    # ------------------------------------------------------------------
    # Media helpers (image / PDF / document)
    # ------------------------------------------------------------------

    async def _maybe_process_media(
        self, message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """If the message is an image/PDF/document, process via embedder."""
        message_type = (message.get("messageType") or "").lower()
        if message_type not in _MEDIA_TYPES:
            return None

        media_list = message.get("media") or []
        if not media_list:
            return {"status": "error", "chunks": [], "error": "No media"}

        storage_path = media_list[0].get("storagePath")
        if not storage_path:
            return {"status": "error", "chunks": [], "error": "No storagePath"}

        # Resolve path relative to project root
        resolved = Path(storage_path)
        if not resolved.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            resolved = project_root / storage_path

        if not resolved.exists():
            return {"status": "error", "chunks": [], "error": f"File not found: {resolved}"}

        try:
            if message_type in _IMAGE_TYPES:
                result = await asyncio.to_thread(process_user_image, str(resolved))
            else:
                result = await asyncio.to_thread(process_user_pdf, str(resolved))
            return result
        except Exception as exc:
            logger.exception("Media processing failed for %s", resolved)
            return {"status": "error", "chunks": [], "error": str(exc)}

    @staticmethod
    def _format_raw_chunks(raw_chunks: List[dict]) -> List[str]:
        """Convert embedder chunk dicts to formatted strings."""
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
        return plain_chunks

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

        # Reply language should follow the user's original language or dialect
        lang_instruction = "You MUST reply ONLY in the exact language or dialect detected in the original user message. 100% STRICTLY FOLLOW ANSWER IN USER LANGUAGE NO MATTER WHAT."
        if user_language:
            lang_instruction += f" The detected language is '{user_language}'."

        return (
            "You are DualComm, a helpful assistant. Use the following information to answer accurately.\n\n"
            f"Original user message:\n{original_text or '(empty)'}\n\n"
            f"Translated query in {target_language} (for context retrieval only):\n{translated_query or '(empty)'}\n\n"
            f"Retrieved {target_language} context (Source of truth):\n{context_block}\n\n"
            "Response rules:\n"
            f"1. {lang_instruction}\n"
            "2. Use retrieved context if relevant and factual.\n"
            "3. If context is insufficient, explain what is missing in the user's language.\n"
            "4. Follow the system prompt strictly regarding tone, simplification, and output format (3 to 5 bullet points)."
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

    async def _maybe_handle_advocacy(self, text: str, payload: Dict[str, Any], user_lang_context: str = "") -> Optional[Dict[str, Any]]:
        """If the text is an advocacy trigger or a confirmation, handle it."""
        if not text:
            return None

        t = text.lower().strip()
        chat_id = payload.get("message", {}).get("chatId", "default")
        session = self.advocacy_sessions.get(chat_id)

        # 1. Confirmation Step (1 for Yes, 2 for No)
        if session and session.get("status") == "draft_ready":
            saved_lang_context = session.get("user_lang_context", "Malay")
            if t == "1":
                self.advocacy_service.execute_send(session)
                self.advocacy_sessions.pop(chat_id, None)
                base_msg = "✅ *Berjaya!* Aduan anda telah dihantar secara rasmi ke jabatan berkaitan. Terima kasih."
                msg_text = await self.advocacy_service.translate_text(base_msg, saved_lang_context)
                # optionally pop session
                return {
                    "actions": [{"type": "send_text", "text": msg_text}],
                    "metadata": {"source": "advocacy_sent"}
                }
            elif t == "2":
                self.advocacy_sessions.pop(chat_id, None)
                base_cancel = "❌ *Dibatalkan.* Draf aduan telah dipadamkan."
                msg_cancel = await self.advocacy_service.translate_text(base_cancel, saved_lang_context)
                return {
                    "actions": [{"type": "send_text", "text": msg_cancel}],
                    "metadata": {"source": "advocacy_cancelled"}
                }
            # If they type something else, we let it flow to AI or re-prompt if it looks like they are trying to answer.
            # But let's stay in confirmation mode if it's just a short text.
            if len(t) < 3:
                base_reprompt = "Sila taip *1* untuk hantar atau *2* untuk batal."
                msg_reprompt = await self.advocacy_service.translate_text(base_reprompt, saved_lang_context)
                return {
                    "actions": [{"type": "send_text", "text": msg_reprompt}],
                    "metadata": {"source": "advocacy_reprompt"}
                }

        # 2. Strict Menu Trigger
        # Clean text from common punctuation to be robust
        clean_text = t.strip(" .!?？")
        # Remove all spaces and common symbols (including full-width) to compare raw content
        comparable_text = re.sub(r'[\s.,!?？、，。]', '', t)

        # EXACT phrases requested by user to surpass everything blocking it
        exact_bypass_phrases = [
            "點樣可以send email去政府部門呀？需要撳邊度？",
            "pripun carane ngirim email teng kantor pemerintah nggih? kedah mencet napa?"
        ]
        is_exact_bypass = text.strip() in exact_bypass_phrases or t in exact_bypass_phrases
        
        # Specific triggers for Cantonese/Javanese Email questions
        is_cantonese_email = "點樣可以sendemail" in comparable_text or "需要撳邊度" in comparable_text
        is_javanese_email = "pripuncaranengirimemail" in comparable_text or "kedahmencetnapa" in comparable_text
        is_generic_email = clean_text in ["email", "emel"]

        if is_exact_bypass or is_cantonese_email or is_javanese_email or is_generic_email:
            self.advocacy_sessions[chat_id] = {
                "status": "awaiting_sector_selection",
                "user_lang_context": text
            }
            # Pass original text to allow dialect-aware menu translation
            menu = await self.advocacy_service.get_menu(user_language_context=text)
            return {
                "actions": [{"type": "send_text", "text": menu}],
                "metadata": {"source": "advocacy_menu"}
            }

        # 3. Sector Selection (1-4)
        if session and session.get("status") == "awaiting_sector_selection" and t in ["1", "2", "3", "4"]:
            sector_map = {"1": "jtk", "2": "jkm", "3": "kkm", "4": "jpn"}
            sector = sector_map[t]
            
            # Retrieve the saved language context from the previous turn
            saved_lang_context = session.get("user_lang_context", "Malay")
            
            self.advocacy_sessions[chat_id] = {
                "status": "selecting_details", 
                "sector": sector,
                "user_lang_context": saved_lang_context # Keep carrying the context explicitly
            }
            # Pass the saved language context (e.g. Cantonese text) so it knows how to translate
            ask_msg = await self.advocacy_service.get_info_request(user_language_context=saved_lang_context)
            return {
                "actions": [{"type": "send_text", "text": ask_msg}],
                "metadata": {"source": "advocacy_ask_info", "sector": sector}
            }

        # 4. Continuation Logic
        if session:
            sector = session.get("sector", "kkm")
            result = await self.advocacy_service.generate_draft(sector, text)
            
            if result.get("status") == "draft_ready":
                self.advocacy_sessions[chat_id] = result 
                return self._format_advocacy_response(result, sector)
            else:
                return {
                    "actions": [{"type": "send_text", "text": result["text"]}],
                    "metadata": {"source": "advocacy_missing_info", "sector": sector}
                }

        return None

    def _format_advocacy_response(self, result: Dict[str, Any], sector: str) -> Dict[str, Any]:
        actions = [{"type": "send_text", "text": result["text"]}]
        for path in result.get("attachments", []):
            ext = Path(path).suffix.lower()
            mime_type = "application/pdf" if ext == ".pdf" else "text/csv" if ext == ".csv" else "application/octet-stream"
            actions.append({
                "type": "send_document",
                "storagePath": path,
                "fileName": Path(path).name,
                "mimeType": mime_type
            })
        return {
            "actions": actions,
            "metadata": {"source": "advocacy_flow", "sector": sector}
        }
