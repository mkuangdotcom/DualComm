import type { AgentRequest, AgentResponse, AgentRuntime } from '../core/runtime.js';

export interface PythonHttpRuntimeOptions {
  baseUrl: string;
  timeoutMs: number;
  apiKey?: string;
}

export class PythonHttpRuntime implements AgentRuntime {
  constructor(private readonly options: PythonHttpRuntimeOptions) {}

  public async handleMessage(request: AgentRequest): Promise<AgentResponse> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.options.timeoutMs);

    try {
      const response = await fetch(this.buildUrl('/messages'), {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          ...(this.options.apiKey ? { 'x-agent-api-key': this.options.apiKey } : {}),
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Python runtime returned ${response.status}: ${text}`);
      }

      const parsed = (await response.json()) as Partial<AgentResponse>;

      if (!parsed.actions || !Array.isArray(parsed.actions)) {
        throw new Error('Python runtime response is missing a valid actions array');
      }

      return {
        actions: parsed.actions,
        metadata: parsed.metadata,
      };
    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error(
          `Python runtime request timed out after ${this.options.timeoutMs}ms`
        );
      }

      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  private buildUrl(pathname: string): string {
    const baseUrl = this.options.baseUrl.endsWith('/')
      ? this.options.baseUrl.slice(0, -1)
      : this.options.baseUrl;

    return `${baseUrl}${pathname}`;
  }
}
