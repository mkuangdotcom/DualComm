import { readFile } from "node:fs/promises";

import { InputFile, type Bot } from "grammy";

import type { OutboundAction } from "../../core/runtime.js";

export async function handleTelegramOutboundActions(
  bot: Bot,
  chatId: string,
  actions: OutboundAction[],
): Promise<void> {
  for (const action of actions) {
    await handleTelegramOutboundAction(bot, chatId, action);
  }
}

export async function handleTelegramOutboundAction(
  bot: Bot,
  chatId: string,
  action: OutboundAction,
): Promise<void> {
  switch (action.type) {
    case "send_text": {
      await bot.api.sendMessage(chatId, action.text, {
        reply_to_message_id: parseReplyId(action.replyToMessageId),
      });
      return;
    }

    case "send_image": {
      const buffer = await readFile(action.storagePath);
      await bot.api.sendPhoto(chatId, new InputFile(buffer), {
        caption: action.caption,
      });
      return;
    }

    case "send_audio": {
      const buffer = await readFile(action.storagePath);
      await bot.api.sendAudio(chatId, new InputFile(buffer));
      return;
    }

    case "send_video": {
      const buffer = await readFile(action.storagePath);
      await bot.api.sendVideo(chatId, new InputFile(buffer), {
        caption: action.caption,
      });
      return;
    }

    case "send_document": {
      const buffer = await readFile(action.storagePath);
      await bot.api.sendDocument(
        chatId,
        new InputFile(buffer, action.fileName || undefined),
        {
        caption: action.caption,
        },
      );
      return;
    }

    case "ignore": {
      return;
    }

    default: {
      const exhaustiveCheck: never = action;
      throw new Error(
        `Unsupported Telegram outbound action: ${JSON.stringify(exhaustiveCheck)}`,
      );
    }
  }
}

function parseReplyId(replyToMessageId?: string): number | undefined {
  if (!replyToMessageId) {
    return undefined;
  }

  const parsed = Number.parseInt(replyToMessageId, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}
