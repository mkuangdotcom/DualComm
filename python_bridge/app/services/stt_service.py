"""Speech-to-Text service using the Groq Whisper API.

Provides two operations that can run **in parallel** on the same audio:
  * ``transcribe()`` → original-language text + detected language
  * ``translate()``  → English translation of the audio
  * ``transcribe_and_translate()`` → runs both concurrently
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class STTService:
    """
    Dual-path audio processing via Groq Whisper.

    ``transcribe()`` uses ``/audio/transcriptions`` to get the spoken text
    in its *original language* plus the detected language code.

    ``translate()`` uses ``/audio/translations`` to get an English
    translation of the audio in a single API call.

    ``transcribe_and_translate()`` fires both in parallel and returns a
    combined result dict.
    """

    DEFAULT_MODEL = "whisper-large-v3"

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or self.DEFAULT_MODEL
        self._client: Optional[Any] = None
        self._init_error: Optional[str] = None

        try:
            from groq import Groq  # type: ignore[import-untyped]

            kwargs: dict[str, Any] = {}
            if api_key:
                kwargs["api_key"] = api_key
            self._client = Groq(**kwargs)
        except ImportError:
            self._init_error = (
                "The 'groq' package is not installed. "
                "Install it with: pip install groq"
            )
            logger.warning(self._init_error)
        except Exception as exc:
            self._init_error = f"Failed to initialise Groq client: {exc}"
            logger.warning(self._init_error)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def transcribe(self, file_path: str) -> Dict[str, Any]:
        """Transcribe audio in the original spoken language.

        Returns ``{text, language, status, error}``.
        ``language`` is the Whisper-detected language name (e.g. "english").
        """
        if self._client is None:
            return self._error_result(self._init_error or "Groq client not available")

        resolved = Path(file_path).resolve()
        if not resolved.is_file():
            return self._error_result(f"Audio file not found: {resolved}")

        try:
            return await asyncio.to_thread(self._sync_transcribe, str(resolved))
        except Exception as exc:
            logger.exception("STT transcription failed for %s", resolved)
            return self._error_result(self._build_error_message(exc))

    async def translate(self, file_path: str) -> Dict[str, Any]:
        """Translate audio to English in a single API call.

        Returns ``{text, language, status, error}``.
        ``language`` is always ``"english"`` (output language).
        """
        if self._client is None:
            return self._error_result(self._init_error or "Groq client not available")

        resolved = Path(file_path).resolve()
        if not resolved.is_file():
            return self._error_result(f"Audio file not found: {resolved}")

        try:
            return await asyncio.to_thread(self._sync_translate, str(resolved))
        except Exception as exc:
            logger.exception("STT translation failed for %s", resolved)
            return self._error_result(self._build_error_message(exc))

    async def transcribe_and_translate(self, file_path: str) -> Dict[str, Any]:
        """Run transcription and translation **in parallel**.

        Returns a combined dict::

            {
                "transcription": {text, language, status, error},
                "translation":   {text, language, status, error},
                "status": "ok" | "partial" | "error",
            }
        """
        transcription_task = asyncio.create_task(self.transcribe(file_path))
        translation_task = asyncio.create_task(self.translate(file_path))

        transcription, translation = await asyncio.gather(
            transcription_task, translation_task
        )

        # Overall status
        t_ok = transcription.get("status") == "ok"
        r_ok = translation.get("status") == "ok"
        if t_ok and r_ok:
            overall = "ok"
        elif t_ok or r_ok:
            overall = "partial"
        else:
            overall = "error"

        logger.info(
            "STT parallel complete: transcribe=%s (lang=%s), translate=%s, overall=%s",
            transcription.get("status"),
            transcription.get("language"),
            translation.get("status"),
            overall,
        )

        return {
            "transcription": transcription,
            "translation": translation,
            "status": overall,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sync_transcribe(self, file_path: str) -> Dict[str, Any]:
        """Blocking call → /audio/transcriptions (original language)."""
        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        result = self._client.audio.transcriptions.create(
            file=(os.path.basename(file_path), audio_bytes),
            model=self.model,
            temperature=0,
            response_format="verbose_json",
        )

        text = getattr(result, "text", "") or ""
        detected_language = getattr(result, "language", "") or ""

        logger.info(
            "STT transcribe OK: lang=%s, chars=%d, file=%s",
            detected_language, len(text), file_path,
        )

        return {
            "text": text.strip(),
            "language": detected_language,
            "status": "ok",
            "error": None,
        }

    def _sync_translate(self, file_path: str) -> Dict[str, Any]:
        """Blocking call → /audio/translations (always English output)."""
        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        result = self._client.audio.translations.create(
            file=(os.path.basename(file_path), audio_bytes),
            model=self.model,
            temperature=0,
            response_format="verbose_json",
        )

        text = getattr(result, "text", "") or ""

        logger.info(
            "STT translate OK: chars=%d, file=%s",
            len(text), file_path,
        )

        return {
            "text": text.strip(),
            "language": "english",
            "status": "ok",
            "error": None,
        }

    @staticmethod
    def _error_result(message: str) -> Dict[str, Any]:
        logger.warning("STT error: %s", message)
        return {
            "text": "",
            "language": "",
            "status": "error",
            "error": message,
        }

    @staticmethod
    def _build_error_message(exc: Exception) -> str:
        chain_messages = [
            str(item).strip()
            for item in STTService._iter_exception_chain(exc)
            if str(item).strip()
        ]
        if not chain_messages:
            return "Unknown STT error"

        primary = chain_messages[0]
        chain_text = " | ".join(chain_messages).lower()

        if (
            "winerror 10013" in chain_text
            or "forbidden by its access permissions" in chain_text
        ):
            return (
                f"{primary} (Network access denied: allow outbound HTTPS to "
                "api.groq.com:443 for the Python runtime. Root cause includes WinError 10013.)"
            )

        return primary

    @staticmethod
    def _iter_exception_chain(exc: Exception):
        visited: set[int] = set()
        current: Optional[BaseException] = exc

        while current is not None and id(current) not in visited:
            visited.add(id(current))
            yield current
            current = current.__cause__ or current.__context__
