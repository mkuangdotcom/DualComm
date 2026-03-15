export type Channel = 'whatsapp' | 'telegram';

export type InboundMessageType =
  | 'text'
  | 'image'
  | 'audio'
  | 'voice_note'
  | 'video'
  | 'document'
  | 'pdf'
  | 'sticker'
  | 'location'
  | 'contact'
  | 'reaction'
  | 'button_reply'
  | 'list_reply'
  | 'unknown';

export type MediaKind =
  | 'image'
  | 'audio'
  | 'voice_note'
  | 'video'
  | 'document'
  | 'pdf'
  | 'sticker'
  | 'unknown';

export interface MessageContext {
  quotedMessageId?: string;
  quotedParticipant?: string;
  quotedText?: string;
  replyToMessageType?: string;
  metadata?: Record<string, unknown>;
}

export interface MediaAttachment {
  id: string;
  kind: MediaKind;
  mimeType?: string;
  filename?: string;
  caption?: string;
  sizeBytes?: number;
  durationSeconds?: number;
  pageCount?: number;
  checksumSha256B64?: string;
  storagePath?: string;
  metadata?: Record<string, unknown>;
}

export interface InboundMessage {
  instanceId: string;
  channel: Channel;
  direction: 'inbound';
  messageId: string;
  chatId: string;
  senderId: string;
  senderName?: string;
  timestamp: string;
  messageType: InboundMessageType;
  text?: string;
  caption?: string;
  media: MediaAttachment[];
  context?: MessageContext;
  rawProviderPayload?: unknown;
}
