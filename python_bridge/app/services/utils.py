"""Shared utility helpers for runtime adapters.

These functions were previously duplicated across MockRuntime,
LangChainRuntime, LlamaIndexRuntime, and HybridRuntime.  Centralising
them here eliminates copy-paste drift and makes behaviour changes
propagate consistently.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def as_str(value: Any, default: Optional[str] = None) -> Optional[str]:
    """Coerce *value* to ``str``, returning *default* when ``None``."""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def derive_sender_name(sender_id: Optional[str]) -> Optional[str]:
    """Extract a display-friendly name from a provider sender id."""
    if not sender_id:
        return None
    return sender_id.split("@", 1)[0]


def build_prompt_input(
    *,
    message_type: str,
    text: Optional[str],
    caption: Optional[str],
    media: List[Dict[str, Any]],
    sender_name: Optional[str],
) -> str:
    """Build a text representation of the inbound message for LLM prompts.

    This intentionally preserves multimodal context in a text
    representation until dedicated image/audio/document preprocessing
    is added.
    """
    lines: List[str] = []

    if sender_name:
        lines.append(f"Sender: {sender_name}")

    lines.append(f"Message type: {message_type}")

    if text:
        lines.append(f"Text: {text}")

    if caption:
        lines.append(f"Caption: {caption}")

    if media:
        lines.append(f"Media count: {len(media)}")
        lines.append(f"Media metadata: {media}")

    return "\n".join(lines)


def placeholder_response(
    *,
    sender_name: Optional[str],
    message_type: str,
    runtime_label: str = "Runtime",
) -> str:
    """Generate a fallback response when no LLM chain is available."""
    display_name = sender_name or "User"

    if message_type == "text":
        return (
            f"{runtime_label} fallback is active. "
            f"I received your text message, {display_name}."
        )

    return (
        f"{runtime_label} fallback is active. "
        f"I received a {message_type} message from {display_name}. "
        f"Prompt input prepared for future processing."
    )


def parse_model_spec(
    model_spec: str,
    *,
    default_provider: str = "openai",
    default_model: str = "gpt-4o-mini",
) -> tuple[str, str]:
    """Parse a ``provider:model`` specification string.

    Parameters
    ----------
    model_spec:
        A string such as ``"groq:qwen/qwen3-32b"`` or plain ``"gpt-4o-mini"``.
    default_provider:
        Provider to assume when *model_spec* contains no colon.
    default_model:
        Model name to fall back to when the model part is empty.

    Returns
    -------
    tuple[str, str]
        ``(provider, model)`` pair with normalised casing.
    """
    if ":" not in model_spec:
        return (default_provider, model_spec)

    provider, model = model_spec.split(":", 1)
    provider_normalized = provider.strip().lower() or default_provider
    model_name = model.strip() or default_model
    return (provider_normalized, model_name)

