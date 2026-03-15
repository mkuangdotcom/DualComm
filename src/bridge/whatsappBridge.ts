import type { WASocket } from 'baileys';

import type { AgentRuntime, OutboundAction } from '../core/runtime.js';
import type { InboundMessage } from '../core/messages.js';
import { BaseBridge, type BridgeLogger } from './baseBridge.js';
import { InboundMessageNormalizer } from '../whatsapp/normalizers/inboundMessageNormalizer.js';
import { handleOutboundActions } from '../whatsapp/outbound/outboundActionHandler.js';

export interface WhatsAppBridgeOptions {
  instanceId?: string;
  normalizer?: InboundMessageNormalizer;
  logger?: BridgeLogger;
}

export class WhatsAppBridge extends BaseBridge<any> {
  private readonly normalizer: InboundMessageNormalizer;

  constructor(
    private readonly sock: WASocket,
    agentRuntime: AgentRuntime,
    options: WhatsAppBridgeOptions = {},
  ) {
    super(agentRuntime, { logger: options.logger });

    this.normalizer =
      options.normalizer ??
      new InboundMessageNormalizer({
        instanceId: options.instanceId,
      });
  }

  protected get channelTag(): string {
    return 'Bridge';
  }

  public register(): void {
    this.sock.ev.on('messages.upsert', async (event: any) => {
      if (!event || event.type !== 'notify') {
        return;
      }

      const messages = Array.isArray(event.messages) ? event.messages : [];

      for (const rawMessage of messages) {
        await this.processMessage(rawMessage);
      }
    });

    this.logger.log('[Bridge] WhatsApp bridge registered');
  }

  protected async normalize(rawMessage: any): Promise<InboundMessage | null> {
    return this.normalizer.normalize(rawMessage);
  }

  protected async onBeforeAgent(inbound: InboundMessage): Promise<void> {
    void this.sock.presenceSubscribe(inbound.chatId).catch((error) => {
      this.logger.warn('[Bridge] Failed to subscribe to presence:', error);
    });
    void this.sock.sendPresenceUpdate('composing', inbound.chatId).catch((error) => {
      this.logger.warn('[Bridge] Failed to send composing presence:', error);
    });
  }

  protected async onAfterAgent(inbound: InboundMessage): Promise<void> {
    void this.sock.sendPresenceUpdate('paused', inbound.chatId).catch((error) => {
      this.logger.warn('[Bridge] Failed to send paused presence:', error);
    });
  }

  protected async sendOutbound(chatId: string, actions: OutboundAction[]): Promise<void> {
    await handleOutboundActions(this.sock, chatId, actions);
  }

  protected async sendFallbackError(rawMessage: any): Promise<void> {
    if (rawMessage?.key?.remoteJid) {
      await this.sock.sendPresenceUpdate('paused', rawMessage.key.remoteJid);
      await this.sock.sendMessage(rawMessage.key.remoteJid, {
        text: 'Sorry, something went wrong while processing your message.',
      });
    }
  }
}
