import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { handleTelegramOutboundAction } from "../src/telegram/outbound/outboundActionHandler.js";

async function createTempFile(): Promise<string> {
  const directory = path.join(tmpdir(), "telegram-bridge-tests");
  await mkdir(directory, { recursive: true });
  const filePath = path.join(directory, `file-${Date.now()}.txt`);
  await writeFile(filePath, "test");
  return filePath;
}

test("maps send_text to sendMessage", async () => {
  const calls: string[] = [];
  const bot = {
    api: {
      sendMessage: async () => {
        calls.push("sendMessage");
      },
    },
  } as any;

  await handleTelegramOutboundAction(bot, "123", {
    type: "send_text",
    text: "hello",
  });

  assert.deepEqual(calls, ["sendMessage"]);
});

test("maps media actions to Telegram send APIs", async () => {
  const calls: string[] = [];
  const bot = {
    api: {
      sendPhoto: async () => calls.push("sendPhoto"),
      sendAudio: async () => calls.push("sendAudio"),
      sendVideo: async () => calls.push("sendVideo"),
      sendDocument: async () => calls.push("sendDocument"),
    },
  } as any;

  const filePath = await createTempFile();

  await handleTelegramOutboundAction(bot, "123", {
    type: "send_image",
    storagePath: filePath,
  });
  await handleTelegramOutboundAction(bot, "123", {
    type: "send_audio",
    storagePath: filePath,
  });
  await handleTelegramOutboundAction(bot, "123", {
    type: "send_video",
    storagePath: filePath,
  });
  await handleTelegramOutboundAction(bot, "123", {
    type: "send_document",
    storagePath: filePath,
  });

  assert.deepEqual(calls, [
    "sendPhoto",
    "sendAudio",
    "sendVideo",
    "sendDocument",
  ]);
});
