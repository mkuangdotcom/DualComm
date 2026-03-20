import { createHash, randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import type { MediaAttachment, MediaKind } from "../../core/messages.js";

export interface StageMediaInput {
  messageId: string;
  kind: MediaKind;
  mimeType?: string;
  data: Buffer;
  fileName?: string;
  caption?: string;
  durationSeconds?: number;
  pageCount?: number;
  metadata?: Record<string, unknown>;
}

export interface MediaStore {
  stage(input: StageMediaInput): Promise<MediaAttachment>;
}

export interface LocalMediaStoreOptions {
  baseDirectory?: string;
}

const DEFAULT_BASE_DIRECTORY = path.resolve(process.cwd(), "media_staging");

export class LocalMediaStore implements MediaStore {
  private readonly baseDirectory: string;

  constructor(options: LocalMediaStoreOptions = {}) {
    this.baseDirectory = options.baseDirectory ?? DEFAULT_BASE_DIRECTORY;
  }

  public async stage(input: StageMediaInput): Promise<MediaAttachment> {
    const checksumSha256B64 = createHash("sha256")
      .update(input.data)
      .digest("base64");

    const extension = inferExtension(input.mimeType, input.fileName);
    const safeMessageId = sanitizePathSegment(input.messageId);
    const directory = path.join(this.baseDirectory, safeMessageId);
    const fileId = randomUUID();
    const outputFileName = input.fileName
      ? sanitizeFileName(input.fileName)
      : `${input.kind}-${fileId}${extension}`;

    await mkdir(directory, { recursive: true });

    const storagePath = path.join(directory, outputFileName);
    await writeFile(storagePath, input.data);

    return {
      id: fileId,
      kind: input.kind,
      mimeType: input.mimeType,
      filename: outputFileName,
      caption: input.caption,
      sizeBytes: input.data.byteLength,
      durationSeconds: input.durationSeconds,
      pageCount: input.pageCount,
      checksumSha256B64,
      storagePath,
      metadata: input.metadata,
    };
  }
}

function inferExtension(mimeType?: string, fileName?: string): string {
  if (fileName) {
    const ext = path.extname(fileName);
    if (ext) {
      return ext;
    }
  }

  const normalizedMimeType = normalizeMimeType(mimeType);

  switch (normalizedMimeType) {
    case "image/jpeg":
      return ".jpg";
    case "image/png":
      return ".png";
    case "image/webp":
      return ".webp";
    case "audio/ogg":
      return ".ogg";
    case "audio/mpeg":
      return ".mp3";
    case "audio/mp4":
      return ".m4a";
    case "video/mp4":
      return ".mp4";
    case "application/pdf":
      return ".pdf";
    default:
      return "";
  }
}

function normalizeMimeType(mimeType?: string): string {
  if (!mimeType) {
    return "";
  }

  return mimeType.split(";")[0]?.trim().toLowerCase() || "";
}

function sanitizePathSegment(value: string): string {
  return value.replace(/[<>:"/\\|?*\x00-\x1F]/g, "_");
}

function sanitizeFileName(fileName: string): string {
  const parsed = path.parse(fileName);
  const safeName = sanitizePathSegment(parsed.name) || "file";
  const safeExt = parsed.ext.replace(/[<>:"/\\|?*\x00-\x1F]/g, "");
  return `${safeName}${safeExt}`;
}
