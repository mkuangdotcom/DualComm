from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


Channel = Literal["whatsapp", "telegram"]
Direction = Literal["inbound"]

InboundMessageType = Literal[
    "text",
    "image",
    "audio",
    "voice_note",
    "video",
    "document",
    "pdf",
    "sticker",
    "location",
    "contact",
    "reaction",
    "button_reply",
    "list_reply",
    "unknown",
]

MediaKind = Literal[
    "image",
    "audio",
    "voice_note",
    "video",
    "document",
    "pdf",
    "sticker",
    "unknown",
]


class MessageContext(BaseModel):
    quotedMessageId: Optional[str] = None
    quotedParticipant: Optional[str] = None
    quotedText: Optional[str] = None
    replyToMessageType: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MediaAttachment(BaseModel):
    id: str
    kind: MediaKind
    mimeType: Optional[str] = None
    filename: Optional[str] = None
    caption: Optional[str] = None
    sizeBytes: Optional[int] = None
    durationSeconds: Optional[float] = None
    pageCount: Optional[int] = None
    checksumSha256B64: Optional[str] = None
    storagePath: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class InboundMessage(BaseModel):
    instanceId: str
    channel: Channel
    direction: Direction
    messageId: str
    chatId: str
    senderId: str
    senderName: Optional[str] = None
    timestamp: str
    messageType: InboundMessageType
    text: Optional[str] = None
    caption: Optional[str] = None
    media: List[MediaAttachment] = Field(default_factory=list)
    context: Optional[MessageContext] = None
    rawProviderPayload: Optional[Dict[str, Any]] = None


class AgentRequest(BaseModel):
    message: InboundMessage


class SendTextAction(BaseModel):
    type: Literal["send_text"]
    text: str
    replyToMessageId: Optional[str] = None


class SendImageAction(BaseModel):
    type: Literal["send_image"]
    storagePath: str
    caption: Optional[str] = None
    mimeType: Optional[str] = None


class SendAudioAction(BaseModel):
    type: Literal["send_audio"]
    storagePath: str
    mimeType: Optional[str] = None
    ptt: Optional[bool] = None


class SendVideoAction(BaseModel):
    type: Literal["send_video"]
    storagePath: str
    caption: Optional[str] = None
    mimeType: Optional[str] = None


class SendDocumentAction(BaseModel):
    type: Literal["send_document"]
    storagePath: str
    fileName: Optional[str] = None
    caption: Optional[str] = None
    mimeType: Optional[str] = None


class IgnoreAction(BaseModel):
    type: Literal["ignore"]
    reason: Optional[str] = None


OutboundAction = Union[
    SendTextAction,
    SendImageAction,
    SendAudioAction,
    SendVideoAction,
    SendDocumentAction,
    IgnoreAction,
]


class AgentResponse(BaseModel):
    actions: List[OutboundAction] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
