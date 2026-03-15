import type { WAMessage, proto } from 'baileys';
import {
  assertMediaContent,
  downloadMediaMessage,
  getContentType,
  normalizeMessageContent,
} from 'baileys';

import type {
  InboundMessage,
  InboundMessageType,
  MediaAttachment,
  MediaKind,
  MessageContext,
} from '../../core/messages.js';
import type { MediaStore } from '../media/mediaStore.js';

export interface InboundMessageNormalizerOptions {
  instanceId?: string;
  mediaStore?: MediaStore;
}

const DEFAULT_INSTANCE_ID = 'default';

export class InboundMessageNormalizer {
  private readonly instanceId: string;
  private readonly mediaStore?: MediaStore;

  constructor(options: InboundMessageNormalizerOptions = {}) {
    this.instanceId = options.instanceId ?? DEFAULT_INSTANCE_ID;
    this.mediaStore = options.mediaStore;
  }

  public async normalize(message: WAMessage): Promise<InboundMessage | null> {
    if (!message.message || !message.key.remoteJid || !message.key.id) {
      return null;
    }

    if (message.key.remoteJid === 'status@broadcast') {
      return null;
    }

    if (message.key.fromMe) {
      return null;
    }

    const normalizedContent = normalizeMessageContent(message.message);
    if (!normalizedContent) {
      return null;
    }

    const contentType = getContentType(normalizedContent);
    const messageType = this.resolveMessageType(normalizedContent, contentType);
    const text = this.extractText(normalizedContent, messageType);
    const caption = this.extractCaption(normalizedContent, messageType);
    const context = this.extractContext(normalizedContent);
    const media = await this.extractMedia(message, normalizedContent, messageType);

    if (
      messageType === 'unknown' &&
      !text &&
      !caption &&
      media.length === 0 &&
      !context
    ) {
      return null;
    }

    return {
      instanceId: this.instanceId,
      channel: 'whatsapp',
      direction: 'inbound',
      messageId: message.key.id,
      chatId: message.key.remoteJid,
      senderId:
        message.key.participant ||
        message.participant ||
        message.key.remoteJid,
      senderName: message.pushName || undefined,
      timestamp: this.resolveTimestamp(message.messageTimestamp),
      messageType,
      text: text || undefined,
      caption: caption || undefined,
      media,
      context,
      rawProviderPayload: message,
    };
  }

  private resolveMessageType(
    content: proto.IMessage,
    contentType: keyof proto.IMessage | undefined
  ): InboundMessageType {
    if (content.conversation || content.extendedTextMessage?.text) {
      return 'text';
    }

    if (content.imageMessage) {
      return 'image';
    }

    if (content.audioMessage) {
      return content.audioMessage.ptt ? 'voice_note' : 'audio';
    }

    if (content.videoMessage) {
      return 'video';
    }

    if (content.documentMessage) {
      return content.documentMessage.mimetype === 'application/pdf'
        ? 'pdf'
        : 'document';
    }

    if (content.stickerMessage) {
      return 'sticker';
    }

    if (content.locationMessage || content.liveLocationMessage) {
      return 'location';
    }

    if (content.contactMessage || content.contactsArrayMessage) {
      return 'contact';
    }

    if (content.reactionMessage) {
      return 'reaction';
    }

    if (content.buttonsResponseMessage) {
      return 'button_reply';
    }

    if (content.listResponseMessage) {
      return 'list_reply';
    }

    if (contentType === 'messageContextInfo' || contentType === undefined) {
      return 'unknown';
    }

    return 'unknown';
  }

  private extractText(
    content: proto.IMessage,
    messageType: InboundMessageType
  ): string | null {
    switch (messageType) {
      case 'text':
        return (
          content.conversation ||
          content.extendedTextMessage?.text ||
          null
        );

      case 'button_reply':
        return (
          content.buttonsResponseMessage?.selectedDisplayText ||
          content.buttonsResponseMessage?.selectedButtonId ||
          null
        );

      case 'list_reply':
        return (
          content.listResponseMessage?.title ||
          content.listResponseMessage?.singleSelectReply?.selectedRowId ||
          null
        );

      case 'reaction':
        return content.reactionMessage?.text || null;

      case 'contact':
        return (
          content.contactMessage?.displayName ||
          this.extractFirstContactName(content.contactsArrayMessage) ||
          null
        );

      case 'location':
        return this.formatLocationText(content);

      default:
        return null;
    }
  }

  private extractCaption(
    content: proto.IMessage,
    messageType: InboundMessageType
  ): string | null {
    switch (messageType) {
      case 'image':
        return content.imageMessage?.caption || null;

      case 'video':
        return content.videoMessage?.caption || null;

      case 'document':
      case 'pdf':
        return content.documentMessage?.caption || null;

      default:
        return null;
    }
  }

  private extractContext(content: proto.IMessage): MessageContext | undefined {
    const contextInfo =
      content.extendedTextMessage?.contextInfo ||
      content.imageMessage?.contextInfo ||
      content.videoMessage?.contextInfo ||
      content.documentMessage?.contextInfo ||
      content.audioMessage?.contextInfo ||
      content.buttonsResponseMessage?.contextInfo ||
      content.listResponseMessage?.contextInfo ||
      undefined;

    const quotedText = this.extractQuotedText(contextInfo?.quotedMessage);

    if (
      !contextInfo?.stanzaId &&
      !contextInfo?.participant &&
      !quotedText
    ) {
      return undefined;
    }

    return {
      quotedMessageId: contextInfo?.stanzaId || undefined,
      quotedParticipant: contextInfo?.participant || undefined,
      quotedText: quotedText || undefined,
      replyToMessageType: contextInfo?.quotedMessage
        ? getContentType(
            normalizeMessageContent(contextInfo.quotedMessage) || undefined
          )
        : undefined,
      metadata: {
        forwardingScore: contextInfo?.forwardingScore,
        isForwarded: contextInfo?.isForwarded,
      },
    };
  }

  private async extractMedia(
    message: WAMessage,
    content: proto.IMessage,
    messageType: InboundMessageType
  ): Promise<MediaAttachment[]> {
    const mediaKind = this.resolveMediaKind(messageType);
    if (!mediaKind) {
      return [];
    }

    const mediaContent = this.getTypedMediaContent(content, messageType);
    if (!mediaContent) {
      return [];
    }

    const metadata = this.buildMediaMetadata(mediaContent, messageType);

    if (!this.mediaStore) {
      return [
        {
          id: message.key.id || `${Date.now()}`,
          kind: mediaKind,
          mimeType: this.readMimeType(mediaContent),
          filename: this.readFileName(mediaContent),
          caption: this.readCaption(mediaContent),
          sizeBytes: this.readFileLength(mediaContent),
          durationSeconds: this.readDuration(mediaContent),
          pageCount: this.readPageCount(mediaContent),
          checksumSha256B64: this.readChecksum(mediaContent),
          metadata,
        },
      ];
    }

    try {
      const buffer = await downloadMediaMessage(
        message,
        'buffer',
        {},
        {}
      );

      return [
        await this.mediaStore.stage({
          messageId: message.key.id || `${Date.now()}`,
          kind: mediaKind,
          mimeType: this.readMimeType(mediaContent),
          data: buffer,
          fileName: this.readFileName(mediaContent),
          caption: this.readCaption(mediaContent),
          durationSeconds: this.readDuration(mediaContent),
          pageCount: this.readPageCount(mediaContent),
          metadata: {
            ...metadata,
            sizeBytes: this.readFileLength(mediaContent),
            checksumSha256B64: this.readChecksum(mediaContent),
          },
        }),
      ];
    } catch (error) {
      return [
        {
          id: message.key.id || `${Date.now()}`,
          kind: mediaKind,
          mimeType: this.readMimeType(mediaContent),
          filename: this.readFileName(mediaContent),
          caption: this.readCaption(mediaContent),
          sizeBytes: this.readFileLength(mediaContent),
          durationSeconds: this.readDuration(mediaContent),
          pageCount: this.readPageCount(mediaContent),
          checksumSha256B64: this.readChecksum(mediaContent),
          metadata: {
            ...metadata,
            downloadError:
              error instanceof Error ? error.message : 'unknown_error',
          },
        },
      ];
    }
  }

  private resolveMediaKind(
    messageType: InboundMessageType
  ): MediaKind | null {
    switch (messageType) {
      case 'image':
        return 'image';
      case 'audio':
        return 'audio';
      case 'voice_note':
        return 'voice_note';
      case 'video':
        return 'video';
      case 'document':
        return 'document';
      case 'pdf':
        return 'pdf';
      case 'sticker':
        return 'sticker';
      default:
        return null;
    }
  }

  private getTypedMediaContent(
    content: proto.IMessage,
    messageType: InboundMessageType
  ):
    | proto.Message.IImageMessage
    | proto.Message.IAudioMessage
    | proto.Message.IVideoMessage
    | proto.Message.IDocumentMessage
    | proto.Message.IStickerMessage
    | null {
    switch (messageType) {
      case 'image':
      case 'audio':
      case 'voice_note':
      case 'video':
      case 'document':
      case 'pdf':
      case 'sticker':
        break;
      default:
        return null;
    }

    try {
      return assertMediaContent(content);
    } catch {
      return null;
    }
  }

  private buildMediaMetadata(
    mediaContent:
      | proto.Message.IImageMessage
      | proto.Message.IAudioMessage
      | proto.Message.IVideoMessage
      | proto.Message.IDocumentMessage
      | proto.Message.IStickerMessage,
    messageType: InboundMessageType
  ): Record<string, unknown> {
    const metadata: Record<string, unknown> = {
      messageType,
    };

    if ('width' in mediaContent && mediaContent.width != null) {
      metadata.width = mediaContent.width;
    }

    if ('height' in mediaContent && mediaContent.height != null) {
      metadata.height = mediaContent.height;
    }

    if ('ptt' in mediaContent && mediaContent.ptt != null) {
      metadata.ptt = mediaContent.ptt;
    }

    if ('seconds' in mediaContent && mediaContent.seconds != null) {
      metadata.seconds = mediaContent.seconds;
    }

    if ('jpegThumbnail' in mediaContent && mediaContent.jpegThumbnail) {
      metadata.hasThumbnail = true;
    }

    if ('pageCount' in mediaContent && mediaContent.pageCount != null) {
      metadata.pageCount = mediaContent.pageCount;
    }

    return metadata;
  }

  private readMimeType(
    mediaContent:
      | proto.Message.IImageMessage
      | proto.Message.IAudioMessage
      | proto.Message.IVideoMessage
      | proto.Message.IDocumentMessage
      | proto.Message.IStickerMessage
  ): string | undefined {
    if ('mimetype' in mediaContent) {
      return mediaContent.mimetype || undefined;
    }

    return undefined;
  }

  private readFileName(
    mediaContent:
      | proto.Message.IImageMessage
      | proto.Message.IAudioMessage
      | proto.Message.IVideoMessage
      | proto.Message.IDocumentMessage
      | proto.Message.IStickerMessage
  ): string | undefined {
    if ('fileName' in mediaContent) {
      return mediaContent.fileName || undefined;
    }

    return undefined;
  }

  private readCaption(
    mediaContent:
      | proto.Message.IImageMessage
      | proto.Message.IAudioMessage
      | proto.Message.IVideoMessage
      | proto.Message.IDocumentMessage
      | proto.Message.IStickerMessage
  ): string | undefined {
    if ('caption' in mediaContent) {
      return mediaContent.caption || undefined;
    }

    return undefined;
  }

  private readFileLength(
    mediaContent:
      | proto.Message.IImageMessage
      | proto.Message.IAudioMessage
      | proto.Message.IVideoMessage
      | proto.Message.IDocumentMessage
      | proto.Message.IStickerMessage
  ): number | undefined {
    if ('fileLength' in mediaContent && mediaContent.fileLength != null) {
      const value = Number(mediaContent.fileLength);
      return Number.isFinite(value) ? value : undefined;
    }

    return undefined;
  }

  private readDuration(
    mediaContent:
      | proto.Message.IImageMessage
      | proto.Message.IAudioMessage
      | proto.Message.IVideoMessage
      | proto.Message.IDocumentMessage
      | proto.Message.IStickerMessage
  ): number | undefined {
    if ('seconds' in mediaContent && mediaContent.seconds != null) {
      const value = Number(mediaContent.seconds);
      return Number.isFinite(value) ? value : undefined;
    }

    return undefined;
  }

  private readPageCount(
    mediaContent:
      | proto.Message.IImageMessage
      | proto.Message.IAudioMessage
      | proto.Message.IVideoMessage
      | proto.Message.IDocumentMessage
      | proto.Message.IStickerMessage
  ): number | undefined {
    if ('pageCount' in mediaContent && mediaContent.pageCount != null) {
      const value = Number(mediaContent.pageCount);
      return Number.isFinite(value) ? value : undefined;
    }

    return undefined;
  }

  private readChecksum(
    mediaContent:
      | proto.Message.IImageMessage
      | proto.Message.IAudioMessage
      | proto.Message.IVideoMessage
      | proto.Message.IDocumentMessage
      | proto.Message.IStickerMessage
  ): string | undefined {
    if ('fileSha256' in mediaContent && mediaContent.fileSha256) {
      return Buffer.from(mediaContent.fileSha256).toString('base64');
    }

    return undefined;
  }

  private extractQuotedText(
    quotedMessage: proto.IMessage | null | undefined
  ): string | null {
    if (!quotedMessage) {
      return null;
    }

    const normalizedQuoted = normalizeMessageContent(quotedMessage);
    if (!normalizedQuoted) {
      return null;
    }

    return (
      normalizedQuoted.conversation ||
      normalizedQuoted.extendedTextMessage?.text ||
      normalizedQuoted.imageMessage?.caption ||
      normalizedQuoted.videoMessage?.caption ||
      normalizedQuoted.documentMessage?.caption ||
      normalizedQuoted.reactionMessage?.text ||
      null
    );
  }

  private extractFirstContactName(
    contactsArrayMessage:
      | proto.Message.IContactsArrayMessage
      | null
      | undefined
  ): string | null {
    const firstContact = contactsArrayMessage?.contacts?.[0];
    return firstContact?.displayName || firstContact?.vcard || null;
  }

  private formatLocationText(content: proto.IMessage): string | null {
    if (content.locationMessage) {
      const loc = content.locationMessage;
      const pieces = [
        loc.name || undefined,
        loc.address || undefined,
        this.formatCoordinates(loc.degreesLatitude, loc.degreesLongitude),
      ].filter(Boolean);

      return pieces.length > 0 ? pieces.join(' | ') : null;
    }

    if (content.liveLocationMessage) {
      const live = content.liveLocationMessage;
      const pieces = [
        live.caption || undefined,
        this.formatCoordinates(live.degreesLatitude, live.degreesLongitude),
      ].filter(Boolean);

      return pieces.length > 0 ? pieces.join(' | ') : null;
    }

    return null;
  }

  private formatCoordinates(
    latitude: number | null | undefined,
    longitude: number | null | undefined
  ): string | null {
    if (latitude == null || longitude == null) {
      return null;
    }

    return `${latitude},${longitude}`;
  }

  private resolveTimestamp(
    messageTimestamp:
      | number
      | Long
      | null
      | undefined
  ): string {
    if (typeof messageTimestamp === 'number') {
      return new Date(messageTimestamp * 1000).toISOString();
    }

    if (
      messageTimestamp &&
      typeof messageTimestamp === 'object' &&
      'toNumber' in messageTimestamp &&
      typeof messageTimestamp.toNumber === 'function'
    ) {
      return new Date(messageTimestamp.toNumber() * 1000).toISOString();
    }

    return new Date().toISOString();
  }
}
