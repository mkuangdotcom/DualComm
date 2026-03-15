import type { Bot } from 'grammy';

import type { AgentRuntime, OutboundAction } from '../core/runtime.js';
import type { InboundMessage } from '../core/messages.js';
import { BaseBridge, type BridgeLogger } from './baseBridge.js';
import { TelegramInboundMessageNormalizer } from '../telegram/normalizers/inboundMessageNormalizer.js';
import { handleTelegramOutboundActions } from '../telegram/outbound/outboundActionHandler.js';

const DEFAULT_FALLBACK_ERROR_MESSAGE =
  'Sorry, something went wrong while processing your message.';

export interface TelegramBridgeOptions {
  instanceId?: string;
  normalizer?: TelegramInboundMessageNormalizer;
  logger?: BridgeLogger;
}

export class TelegramBridge extends BaseBridge<any> {
  private readonly normalizer: TelegramInboundMessageNormalizer;

  constructor(
    private readonly bot: Bot,
    agentRuntime: AgentRuntime,
    options: TelegramBridgeOptions = {},
  ) {
    super(agentRuntime, { logger: options.logger });

    this.normalizer =
      options.normalizer ??
      new TelegramInboundMessageNormalizer({
        botToken: '',
        api: bot.api,
        instanceId: options.instanceId,
      });
  }

  protected get channelTag(): string {
    return 'Telegram';
  }

  public register(): void {
    this.bot.on('edited_message', (ctx) => {
      const messageId = ctx.editedMessage?.message_id;
      const chatId = ctx.editedMessage?.chat?.id;
      this.logger.warn(
        `[Telegram] Discarding edited message ${messageId ?? 'unknown'} from ${chatId ?? 'unknown'}`,
      );
    });

    this.bot.on('message', async (ctx) => {
      if (!ctx.message) {
        return;
      }

      await this.processMessage(ctx.message);
    });

    this.logger.log('[Telegram] Telegram bridge registered');
  }

  protected async normalize(message: any): Promise<InboundMessage | null> {
    return this.normalizer.normalize(message);
  }

  protected async sendOutbound(chatId: string, actions: OutboundAction[]): Promise<void> {
    await handleTelegramOutboundActions(this.bot, chatId, actions);
  }

  protected async sendFallbackError(message: any): Promise<void> {
    if (message?.chat?.id) {
      await this.bot.api.sendMessage(
        String(message.chat.id),
        DEFAULT_FALLBACK_ERROR_MESSAGE,
      );
    }
  }
}
