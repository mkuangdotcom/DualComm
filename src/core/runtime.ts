import type { InboundMessage } from './messages.js';

export type OutboundAction =
  | {
      type: 'send_text';
      text: string;
      replyToMessageId?: string;
    }
  | {
      type: 'send_image';
      storagePath: string;
      caption?: string;
      mimeType?: string;
    }
  | {
      type: 'send_audio';
      storagePath: string;
      mimeType?: string;
      ptt?: boolean;
    }
  | {
      type: 'send_video';
      storagePath: string;
      caption?: string;
      mimeType?: string;
    }
  | {
      type: 'send_document';
      storagePath: string;
      fileName?: string;
      caption?: string;
      mimeType?: string;
    }
  | {
      type: 'ignore';
      reason?: string;
    };

export interface AgentRequest {
  message: InboundMessage;
}

export interface AgentResponse {
  actions: OutboundAction[];
  metadata?: Record<string, unknown>;
}

export interface AgentRuntime {
  handleMessage(request: AgentRequest): Promise<AgentResponse>;
  dispose?(): void;
}
