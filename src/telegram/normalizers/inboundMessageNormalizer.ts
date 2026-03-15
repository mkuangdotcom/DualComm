import type { Api } from "grammy";
import type { File, Message, User } from "grammy/types";

import type {
  InboundMessage,
  InboundMessageType,
  MediaAttachment,
  MediaKind,
  MessageContext,
} from "../../core/messages.js";
import type { MediaStore } from "../../whatsapp/media/mediaStore.js";

export interface TelegramInboundMessageNormalizerOptions {
  botToken: string;
  api: Api;
  instanceId?: string;
  mediaStore?: MediaStore;
  logger?: Pick<Console, "log" | "error" | "warn">;
}

const DEFAULT_INSTANCE_ID = "telegram";
const TELEGRAM_FILE_SIZE_LIMIT_BYTES = 20 * 1024 * 1024;

export class TelegramInboundMessageNormalizer {
  private readonly instanceId: string;
  private readonly api: Api;
  private readonly botToken: string;
  private readonly mediaStore?: MediaStore;
  private readonly logger: Pick<Console, "log" | "error" | "warn">;

  constructor(options: TelegramInboundMessageNormalizerOptions) {
    this.instanceId = options.instanceId ?? DEFAULT_INSTANCE_ID;
    this.api = options.api;
    this.botToken = options.botToken;
    this.mediaStore = options.mediaStore;
    this.logger = options.logger ?? console;
  }

  public async normalize(message: Message): Promise<InboundMessage | null> {
    if (!message?.chat?.id || !message.message_id) {
      return null;
    }

    if (message.from?.is_bot) {
      return null;
    }

    const messageType = this.resolveMessageType(message);
    const text = this.extractText(message, messageType);
    const caption = this.extractCaption(message);
    const context = this.extractContext(message);
    const media = await this.extractMedia(message, messageType, caption);

    if (
      messageType === "unknown" &&
      !text &&
      !caption &&
      media.length === 0 &&
      !context
    ) {
      return null;
    }

    return {
      instanceId: this.instanceId,
      channel: "telegram",
      direction: "inbound",
      messageId: String(message.message_id),
      chatId: String(message.chat.id),
      senderId: this.resolveSenderId(message),
      senderName: this.resolveSenderName(message.from),
      timestamp: this.resolveTimestamp(message.date),
      messageType,
      text: text || undefined,
      caption: caption || undefined,
      media,
      context,
      rawProviderPayload: message,
    };
  }

  private resolveMessageType(message: Message): InboundMessageType {
    if (message.text) {
      return "text";
    }

    if (message.photo?.length) {
      return "image";
    }

    if (message.audio) {
      return "audio";
    }

    if (message.voice) {
      return "voice_note";
    }

    if (message.video) {
      return "video";
    }

    if (message.document) {
      const mimeType = message.document.mime_type || "";
      if (mimeType === "application/pdf") {
        return "pdf";
      }

      if (
        message.document.file_name &&
        message.document.file_name.toLowerCase().endsWith(".pdf")
      ) {
        return "pdf";
      }

      return "document";
    }

    if (message.sticker) {
      return "sticker";
    }

    if (message.location) {
      return "location";
    }

    if (message.contact) {
      return "contact";
    }

    return "unknown";
  }

  private extractText(
    message: Message,
    messageType: InboundMessageType,
  ): string | null {
    if (messageType === "text") {
      return message.text || null;
    }

    if (messageType === "location" && message.location) {
      return `${message.location.latitude},${message.location.longitude}`;
    }

    if (messageType === "contact" && message.contact) {
      return (
        message.contact.first_name ||
        message.contact.phone_number ||
        null
      );
    }

    return null;
  }

  private extractCaption(message: Message): string | null {
    return message.caption || null;
  }

  private extractContext(message: Message): MessageContext | undefined {
    const reply = message.reply_to_message;
    if (!reply) {
      return undefined;
    }

    const quotedText =
      reply.text ||
      reply.caption ||
      reply.document?.file_name ||
      reply.sticker?.emoji ||
      null;

    return {
      quotedMessageId: reply.message_id ? String(reply.message_id) : undefined,
      quotedParticipant: reply.from?.id
        ? String(reply.from.id)
        : undefined,
      quotedText: quotedText || undefined,
      replyToMessageType: reply ? this.resolveMessageType(reply) : undefined,
    };
  }

  private async extractMedia(
    message: Message,
    messageType: InboundMessageType,
    caption: string | null,
  ): Promise<MediaAttachment[]> {
    const mediaKind = this.resolveMediaKind(messageType);
    if (!mediaKind) {
      return [];
    }

    const stagingId = this.buildStagingId(message);

    if (message.photo?.length) {
      const photo = message.photo[message.photo.length - 1];
      return [
        await this.buildMediaAttachment({
          messageId: stagingId,
          kind: "image",
          fileId: photo.file_id,
          fileUniqueId: photo.file_unique_id,
          fileSize: photo.file_size,
          mimeType: "image/jpeg",
          width: photo.width,
          height: photo.height,
          caption,
          fileName: this.defaultFileName(
            "photo",
            photo.file_id,
            ".jpg",
          ),
        }),
      ];
    }

    if (message.audio) {
      return [
        await this.buildMediaAttachment({
          messageId: stagingId,
          kind: "audio",
          fileId: message.audio.file_id,
          fileUniqueId: message.audio.file_unique_id,
          fileSize: message.audio.file_size,
          mimeType: message.audio.mime_type || "audio/mpeg",
          durationSeconds: message.audio.duration,
          caption,
          fileName:
            message.audio.file_name ||
            this.defaultFileName("audio", message.audio.file_id, ".mp3"),
        }),
      ];
    }

    if (message.voice) {
      return [
        await this.buildMediaAttachment({
          messageId: stagingId,
          kind: "voice_note",
          fileId: message.voice.file_id,
          fileUniqueId: message.voice.file_unique_id,
          fileSize: message.voice.file_size,
          mimeType: message.voice.mime_type || "audio/ogg",
          durationSeconds: message.voice.duration,
          caption,
          fileName: this.defaultFileName(
            "voice",
            message.voice.file_id,
            ".ogg",
          ),
        }),
      ];
    }

    if (message.video) {
      return [
        await this.buildMediaAttachment({
          messageId: stagingId,
          kind: "video",
          fileId: message.video.file_id,
          fileUniqueId: message.video.file_unique_id,
          fileSize: message.video.file_size,
          mimeType: message.video.mime_type || "video/mp4",
          durationSeconds: message.video.duration,
          width: message.video.width,
          height: message.video.height,
          caption,
          fileName:
            message.video.file_name ||
            this.defaultFileName("video", message.video.file_id, ".mp4"),
        }),
      ];
    }

    if (message.document) {
      const mimeType = message.document.mime_type || "application/octet-stream";
      const isPdf =
        mimeType === "application/pdf" ||
        (message.document.file_name || "").toLowerCase().endsWith(".pdf");

      return [
        await this.buildMediaAttachment({
          messageId: stagingId,
          kind: isPdf ? "pdf" : "document",
          fileId: message.document.file_id,
          fileUniqueId: message.document.file_unique_id,
          fileSize: message.document.file_size,
          mimeType,
          caption,
          fileName:
            message.document.file_name ||
            this.defaultFileName("document", message.document.file_id, ""),
        }),
      ];
    }

    if (message.sticker) {
      return [
        await this.buildMediaAttachment({
          messageId: stagingId,
          kind: "sticker",
          fileId: message.sticker.file_id,
          fileUniqueId: message.sticker.file_unique_id,
          fileSize: message.sticker.file_size,
          mimeType: message.sticker.mime_type || "image/webp",
          width: message.sticker.width,
          height: message.sticker.height,
          caption,
          fileName: this.defaultFileName(
            "sticker",
            message.sticker.file_id,
            ".webp",
          ),
        }),
      ];
    }

    return [];
  }

  private resolveMediaKind(
    messageType: InboundMessageType,
  ): MediaKind | null {
    switch (messageType) {
      case "image":
        return "image";
      case "audio":
        return "audio";
      case "voice_note":
        return "voice_note";
      case "video":
        return "video";
      case "document":
        return "document";
      case "pdf":
        return "pdf";
      case "sticker":
        return "sticker";
      default:
        return null;
    }
  }

  private async buildMediaAttachment(input: {
    messageId: string;
    kind: MediaKind;
    fileId: string;
    fileUniqueId?: string;
    fileName?: string;
    mimeType?: string;
    fileSize?: number;
    durationSeconds?: number;
    width?: number;
    height?: number;
    caption?: string | null;
  }): Promise<MediaAttachment> {
    const metadata: Record<string, unknown> = {
      fileId: input.fileId,
      fileUniqueId: input.fileUniqueId,
    };

    if (input.width != null) {
      metadata.width = input.width;
    }
    if (input.height != null) {
      metadata.height = input.height;
    }
    if (input.durationSeconds != null) {
      metadata.durationSeconds = input.durationSeconds;
    }

    const baseAttachment: MediaAttachment = {
      id: input.fileId,
      kind: input.kind,
      mimeType: input.mimeType,
      filename: input.fileName,
      caption: input.caption || undefined,
      sizeBytes: input.fileSize,
      durationSeconds: input.durationSeconds,
      metadata,
    };

    if (!this.mediaStore) {
      if (
        input.fileSize != null &&
        input.fileSize > TELEGRAM_FILE_SIZE_LIMIT_BYTES
      ) {
        return {
          ...baseAttachment,
          metadata: {
            ...metadata,
            downloadError: "file_too_large",
          },
        };
      }

      return baseAttachment;
    }

    if (
      input.fileSize != null &&
      input.fileSize > TELEGRAM_FILE_SIZE_LIMIT_BYTES
    ) {
      return {
        ...baseAttachment,
        metadata: {
          ...metadata,
          downloadError: "file_too_large",
        },
      };
    }

    let fileInfo: File;
    try {
      fileInfo = await this.api.getFile(input.fileId);
    } catch (error) {
      this.logger.warn("[Telegram] Failed to fetch file info:", error);
      return {
        ...baseAttachment,
        metadata: {
          ...metadata,
          downloadError: "get_file_failed",
        },
      };
    }

    if (
      fileInfo.file_size != null &&
      fileInfo.file_size > TELEGRAM_FILE_SIZE_LIMIT_BYTES
    ) {
      return {
        ...baseAttachment,
        sizeBytes: fileInfo.file_size,
        metadata: {
          ...metadata,
          downloadError: "file_too_large",
        },
      };
    }

    if (!fileInfo.file_path) {
      return {
        ...baseAttachment,
        metadata: {
          ...metadata,
          downloadError: "missing_file_path",
        },
      };
    }

    const url = `https://api.telegram.org/file/bot${this.botToken}/${fileInfo.file_path}`;

    try {
      const response = await fetch(url);
      if (!response.ok) {
        return {
          ...baseAttachment,
          metadata: {
            ...metadata,
            downloadError: `http_${response.status}`,
          },
        };
      }

      const buffer = Buffer.from(await response.arrayBuffer());
      return await this.mediaStore.stage({
        messageId: input.messageId,
        kind: input.kind,
        mimeType: input.mimeType,
        data: buffer,
        fileName: input.fileName,
        caption: input.caption || undefined,
        durationSeconds: input.durationSeconds,
        metadata: {
          ...metadata,
          sizeBytes: buffer.byteLength,
        },
      });
    } catch (error) {
      return {
        ...baseAttachment,
        metadata: {
          ...metadata,
          downloadError:
            error instanceof Error ? error.message : "download_failed",
        },
      };
    }
  }

  private buildStagingId(message: Message): string {
    return `telegram-${message.chat.id}-${message.message_id}`;
  }

  private resolveSenderId(message: Message): string {
    if (message.from?.id != null) {
      return String(message.from.id);
    }

    return String(message.chat.id);
  }

  private resolveSenderName(sender?: User): string | undefined {
    if (!sender) {
      return undefined;
    }

    const pieces = [sender.first_name, sender.last_name].filter(Boolean);
    if (pieces.length > 0) {
      return pieces.join(" ");
    }

    return sender.username || undefined;
  }

  private resolveTimestamp(timestamp: number | undefined): string {
    if (!timestamp) {
      return new Date().toISOString();
    }

    return new Date(timestamp * 1000).toISOString();
  }

  private defaultFileName(
    prefix: string,
    fileId: string,
    extension: string,
  ): string {
    return `${prefix}-${fileId}${extension}`;
  }
}
