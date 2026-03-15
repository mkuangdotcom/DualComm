import assert from "node:assert/strict";
import { test } from "node:test";

import { TelegramBridge } from "../src/bridge/telegramBridge.js";

test("edited messages are logged and discarded", async () => {
  const handlers: Record<string, ((ctx: any) => void)[]> = {};
  const logs: string[] = [];

  const bot = {
    on(event: string, handler: (ctx: any) => void) {
      handlers[event] = handlers[event] || [];
      handlers[event].push(handler);
    },
    api: {
      sendMessage: async () => {},
    },
  } as any;

  const runtime = {
    handleMessage: async () => ({ actions: [] }),
  };

  const bridge = new TelegramBridge(bot, runtime, {
    normalizer: {
      normalize: async () => null,
    } as any,
    logger: {
      log: () => {},
      error: () => {},
      warn: (message: string) => logs.push(message),
    },
  });

  bridge.register();

  const editedHandler = handlers["edited_message"]?.[0];
  assert.ok(editedHandler, "edited_message handler should be registered");

  editedHandler({
    editedMessage: { message_id: 123, chat: { id: 999 } },
  });

  assert.ok(
    logs.some((line) => line.includes("Discarding edited message 123")),
  );
});
