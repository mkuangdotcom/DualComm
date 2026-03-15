import { Bot } from "grammy";

export interface TelegramConnectionOptions {
  token: string;
  logger?: Pick<Console, "log" | "error" | "warn">;
}

export function createTelegramConnection(
  options: TelegramConnectionOptions,
): Bot {
  const logger = options.logger ?? console;
  const bot = new Bot(options.token);

  bot.catch((error) => {
    logger.error("[Telegram] Bot error:", error);
  });

  return bot;
}
