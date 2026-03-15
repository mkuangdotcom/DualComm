from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.utils import as_str, derive_sender_name


class MockRuntime:
    """
    Minimal mock runtime for the messaging Python bridge.

    This adapter accepts the normalized inbound payload from the TypeScript
    bridge and returns stable outbound actions without depending on any
    external LLM framework.
    """

    async def handle_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        message = payload.get("message", {}) or {}

        message_type = as_str(message.get("messageType"), default="unknown")
        chat_id = as_str(message.get("chatId"))
        sender_name = as_str(message.get("senderName")) or derive_sender_name(
            as_str(message.get("senderId"))
        )
        text = as_str(message.get("text"))
        caption = as_str(message.get("caption"))
        media = message.get("media") or []

        if message_type in {"text", "button_reply", "list_reply", "reaction"}:
            reply_text = self._handle_text_like_message(
                text=text,
                sender_name=sender_name,
                chat_id=chat_id,
            )
        elif message_type in {
            "image",
            "audio",
            "voice_note",
            "video",
            "document",
            "pdf",
            "sticker",
        }:
            reply_text = self._handle_media_message(
                message_type=message_type,
                caption=caption,
                media=media,
                sender_name=sender_name,
            )
        elif message_type == "location":
            reply_text = self._handle_location_message(
                text=text,
                sender_name=sender_name,
            )
        elif message_type == "contact":
            reply_text = self._handle_contact_message(
                text=text,
                sender_name=sender_name,
            )
        else:
            reply_text = (
                f"I received a `{message_type}` message. "
                "The mock runtime is connected, but advanced handling is not implemented yet."
            )

        return {
            "actions": [
                {
                    "type": "send_text",
                    "text": reply_text,
                }
            ],
            "metadata": {
                "runtime": "mock",
                "handled_message_type": message_type,
            },
        }

    def _handle_text_like_message(
        self,
        text: Optional[str],
        sender_name: Optional[str],
        chat_id: Optional[str],
    ) -> str:
        normalized = (text or "").strip()

        if not normalized:
            return "I received your message, but it did not contain readable text."

        lowered = normalized.lower()

        if lowered in {"/help", "help"}:
            return (
                "Mock runtime is connected.\n\n"
                "Current capabilities:\n"
                "- receive normalized Telegram/WhatsApp messages\n"
                "- acknowledge media metadata\n"
                "- return outbound actions\n\n"
                "Planned next step:\n"
                "- replace this mock adapter with LangChain or LlamaIndex"
            )

        if lowered in {"/ping", "ping"}:
            return "pong"

        if lowered in {"/whoami", "whoami"}:
            name = sender_name or "unknown sender"
            chat = chat_id or "unknown chat"
            return f"You are {name}. Current chat id: {chat}"

        return f"{sender_name or 'User'} said: {normalized}"

    def _handle_media_message(
        self,
        message_type: str,
        caption: Optional[str],
        media: List[Dict[str, Any]],
        sender_name: Optional[str],
    ) -> str:
        first_media = media[0] if media else {}

        filename = as_str(first_media.get("filename"))
        mime_type = as_str(first_media.get("mimeType"))
        storage_path = as_str(first_media.get("storagePath"))

        details: List[str] = [f"I received your {message_type} message"]

        if sender_name:
            details.append(f"from {sender_name}")

        metadata_bits: List[str] = []

        if filename:
            metadata_bits.append(f"filename={filename}")
        if mime_type:
            metadata_bits.append(f"mime={mime_type}")
        if storage_path:
            metadata_bits.append(f"stored_at={storage_path}")
        if caption:
            metadata_bits.append(f"caption={caption}")

        if metadata_bits:
            details.append(f"({', '.join(metadata_bits)})")

        details.append(
            "The bridge is ready for future multimodal processing, "
            "but this mock runtime currently returns a placeholder response."
        )

        return " ".join(details)

    def _handle_location_message(
        self,
        text: Optional[str],
        sender_name: Optional[str],
    ) -> str:
        if text:
            return f"I received a location from {sender_name or 'the user'}: {text}"
        return "I received a location message."

    def _handle_contact_message(
        self,
        text: Optional[str],
        sender_name: Optional[str],
    ) -> str:
        if text:
            return f"I received a contact from {sender_name or 'the user'}: {text}"
        return "I received a contact message."


