import { ChatCohere } from '@langchain/cohere';
import { ChatGroq } from '@langchain/groq';
import { ChatPromptTemplate, MessagesPlaceholder } from '@langchain/core/prompts';
import { ConversationChain } from 'langchain/chains';
import { BufferWindowMemory } from 'langchain/memory';

import { config } from '../config.js';
import type { InboundMessage } from '../core/messages.js';
import type { AgentRequest, AgentResponse, AgentRuntime } from '../core/runtime.js';

export class LocalLangChainRuntime implements AgentRuntime {
  private readonly llm: any;
  private readonly prompt: ChatPromptTemplate;
  private readonly memories = new Map<string, BufferWindowMemory>();
  private readonly chains = new Map<string, ConversationChain>();

  constructor() {
    this.llm = this.createLLM();
    this.prompt = ChatPromptTemplate.fromMessages([
      ['system', config.bot.systemPrompt],
      new MessagesPlaceholder('history'),
      ['human', '{input}'],
    ]);
  }

  public async handleMessage(request: AgentRequest): Promise<AgentResponse> {
    const { message } = request;
    const input = this.toPromptInput(message);
    const chain = this.getChain(message.chatId);

    try {
      const result = await chain.invoke({ input });
      const text =
        typeof result.response === 'string'
          ? result.response
          : 'Sorry, I could not generate a response.';

      return {
        actions: [
          {
            type: 'send_text',
            text,
          },
        ],
      };
    } catch (error) {
      console.error('[Agent] Local LangChain runtime error:', error);
      return {
        actions: [
          {
            type: 'send_text',
            text: 'Sorry, something went wrong while processing your message.',
          },
        ],
      };
    }
  }

  public dispose(): void {
    this.memories.clear();
    this.chains.clear();
  }

  private getChain(sessionId: string): ConversationChain {
    const existing = this.chains.get(sessionId);
    if (existing) {
      return existing;
    }

    const memory = new BufferWindowMemory({
      k: config.memory.windowSize,
      returnMessages: true,
      memoryKey: 'history',
    });

    const chain = new ConversationChain({
      llm: this.llm,
      prompt: this.prompt,
      memory,
    });

    this.memories.set(sessionId, memory);
    this.chains.set(sessionId, chain);

    return chain;
  }

  private createLLM(): any {
    if (config.llm.provider === 'groq') {
      return new ChatGroq({
        apiKey: config.llm.groq.apiKey,
        model: config.llm.groq.model,
        temperature: 0.7,
        maxTokens: 1024,
      });
    }

    return new ChatCohere({
      apiKey: config.llm.cohere.apiKey,
      model: config.llm.cohere.model,
      temperature: 0.7,
    });
  }

  private toPromptInput(message: InboundMessage): string {
    switch (message.messageType) {
      case 'text':
      case 'button_reply':
      case 'list_reply':
      case 'reaction':
        return message.text || '';

      case 'image':
      case 'video':
      case 'document':
      case 'pdf':
      case 'audio':
      case 'voice_note':
      case 'sticker':
        return [
          `The user sent a ${message.messageType} message.`,
          message.caption ? `Caption: ${message.caption}` : undefined,
          message.media.length > 0
            ? `Media metadata: ${JSON.stringify(message.media)}`
            : undefined,
        ]
          .filter(Boolean)
          .join('\n');

      case 'location':
      case 'contact':
      case 'unknown':
      default:
        return [
          `The user sent a ${message.messageType} message.`,
          message.text ? `Text: ${message.text}` : undefined,
          message.context
            ? `Context: ${JSON.stringify(message.context)}`
            : undefined,
        ]
          .filter(Boolean)
          .join('\n');
    }
  }
}
