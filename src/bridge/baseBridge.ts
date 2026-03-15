import type { AgentRuntime, OutboundAction } from '../core/runtime.js';
import type { InboundMessage } from '../core/messages.js';

export interface BridgeLogger {
  log: (...args: unknown[]) => void;
  error: (...args: unknown[]) => void;
  warn: (...args: unknown[]) => void;
}

export interface BaseBridgeOptions {
  logger?: BridgeLogger;
}

export abstract class BaseBridge<TRawMessage> {
  protected readonly logger: BridgeLogger;

  constructor(
    protected readonly agentRuntime: AgentRuntime,
    options: BaseBridgeOptions = {},
  ) {
    this.logger = options.logger ?? console;
  }

  /** Platform-specific: convert a raw provider message into a normalised InboundMessage. */
  protected abstract normalize(raw: TRawMessage): Promise<InboundMessage | null>;

  /** Platform-specific: deliver outbound actions to the user. */
  protected abstract sendOutbound(chatId: string, actions: OutboundAction[]): Promise<void>;

  /** Platform-specific: send a user-friendly error when processing fails. */
  protected abstract sendFallbackError(raw: TRawMessage): Promise<void>;

  /** Optional hook executed right before calling the agent (e.g. presence updates). */
  protected onBeforeAgent(_inbound: InboundMessage): void | Promise<void> {}

  /** Optional hook executed right after the agent responds (e.g. clear typing indicator). */
  protected onAfterAgent(_inbound: InboundMessage): void | Promise<void> {}

  /** Channel label used in log prefixes (e.g. "WhatsApp", "Telegram"). */
  protected abstract get channelTag(): string;

  /**
   * The shared message-processing pipeline:
   *   normalize → onBeforeAgent → agent → onAfterAgent → outbound
   */
  public async processMessage(raw: TRawMessage): Promise<void> {
    try {
      const inbound = await this.normalize(raw);
      if (!inbound) {
        return;
      }

      this.logger.log(
        `[${this.channelTag}] Inbound ${inbound.messageType} message from ${inbound.senderId} in ${inbound.chatId}`,
      );

      await this.onBeforeAgent(inbound);

      const response = await this.agentRuntime.handleMessage({
        message: inbound,
      });

      await this.onAfterAgent(inbound);

      if (!response.actions || response.actions.length === 0) {
        this.logger.warn(
          `[${this.channelTag}] Agent returned no actions for message ${inbound.messageId}`,
        );
        return;
      }

      await this.sendOutbound(inbound.chatId, response.actions);

      this.logger.log(
        `[${this.channelTag}] Completed message ${inbound.messageId} with ${response.actions.length} action(s)`,
      );
    } catch (error) {
      this.logger.error(
        `[${this.channelTag}] Failed to process inbound message:`,
        error,
      );

      try {
        await this.sendFallbackError(raw);
      } catch (sendError) {
        this.logger.error(
          `[${this.channelTag}] Failed to send fallback error message:`,
          sendError,
        );
      }
    }
  }

  public dispose(): void {
    this.agentRuntime.dispose?.();
  }
}
