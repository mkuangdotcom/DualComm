import assert from "node:assert/strict";
import { test } from "node:test";

import { TelegramInboundMessageNormalizer } from "../src/telegram/normalizers/inboundMessageNormalizer.js";

const baseApi = {
  getFile: async () => ({ file_path: "file.dat" }),
};

test("normalizes a text message", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 1,
    chat: { id: 123 },
    date: 1_700_000_000,
    text: "hello",
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.channel, "telegram");
  assert.equal(normalized?.messageType, "text");
  assert.equal(normalized?.text, "hello");
});

test("normalizes a photo message", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 2,
    chat: { id: 123 },
    date: 1_700_000_000,
    photo: [
      { file_id: "small", file_unique_id: "u1", width: 10, height: 10 },
      {
        file_id: "large",
        file_unique_id: "u2",
        width: 100,
        height: 100,
        file_size: 1024,
      },
    ],
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.messageType, "image");
  assert.equal(normalized?.media.length, 1);
  assert.equal(normalized?.media[0].kind, "image");
});

test("flags oversized media with downloadError", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 3,
    chat: { id: 123 },
    date: 1_700_000_000,
    document: {
      file_id: "doc",
      file_unique_id: "doc-unique",
      file_name: "large.pdf",
      mime_type: "application/pdf",
      file_size: 30 * 1024 * 1024,
    },
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.messageType, "pdf");
  assert.equal(normalized?.media[0].metadata?.downloadError, "file_too_large");
});

test("normalizes a voice note message", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 4,
    chat: { id: 123 },
    date: 1_700_000_000,
    voice: {
      file_id: "voice",
      file_unique_id: "voice-unique",
      duration: 4,
      file_size: 2048,
    },
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.messageType, "voice_note");
  assert.equal(normalized?.media[0].kind, "voice_note");
});

test("normalizes an audio message", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 5,
    chat: { id: 123 },
    date: 1_700_000_000,
    audio: {
      file_id: "audio",
      file_unique_id: "audio-unique",
      duration: 8,
      file_size: 2048,
      mime_type: "audio/mpeg",
    },
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.messageType, "audio");
  assert.equal(normalized?.media[0].kind, "audio");
});

test("normalizes a video message", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 6,
    chat: { id: 123 },
    date: 1_700_000_000,
    video: {
      file_id: "video",
      file_unique_id: "video-unique",
      duration: 12,
      file_size: 4096,
      width: 640,
      height: 480,
      mime_type: "video/mp4",
    },
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.messageType, "video");
  assert.equal(normalized?.media[0].kind, "video");
});

test("normalizes a non-pdf document message", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 7,
    chat: { id: 123 },
    date: 1_700_000_000,
    document: {
      file_id: "doc",
      file_unique_id: "doc-unique",
      file_name: "notes.txt",
      mime_type: "text/plain",
      file_size: 512,
    },
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.messageType, "document");
  assert.equal(normalized?.media[0].kind, "document");
});

test("normalizes a sticker message", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 8,
    chat: { id: 123 },
    date: 1_700_000_000,
    sticker: {
      file_id: "sticker",
      file_unique_id: "sticker-unique",
      width: 128,
      height: 128,
      file_size: 1024,
    },
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.messageType, "sticker");
  assert.equal(normalized?.media[0].kind, "sticker");
});

test("normalizes a location message", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 9,
    chat: { id: 123 },
    date: 1_700_000_000,
    location: { latitude: 1.23, longitude: 4.56 },
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.messageType, "location");
  assert.equal(normalized?.text, "1.23,4.56");
});

test("normalizes a contact message", async () => {
  const normalizer = new TelegramInboundMessageNormalizer({
    botToken: "test-token",
    api: baseApi as any,
  });

  const message = {
    message_id: 10,
    chat: { id: 123 },
    date: 1_700_000_000,
    contact: { first_name: "Alice", phone_number: "+123" },
    from: { id: 42, first_name: "Test" },
  };

  const normalized = await normalizer.normalize(message as any);
  assert.equal(normalized?.messageType, "contact");
  assert.equal(normalized?.text, "Alice");
});
