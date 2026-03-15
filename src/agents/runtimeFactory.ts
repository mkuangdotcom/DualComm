import { config } from '../config.js';
import type { AgentRuntime } from '../core/runtime.js';
import { LocalLangChainRuntime } from './localLangChainRuntime.js';
import { PythonHttpRuntime } from './pythonHttpRuntime.js';

export function createAgentRuntime(): AgentRuntime {
  if (config.agent.mode === 'python-http') {
    return new PythonHttpRuntime({
      baseUrl: config.agent.python.baseUrl,
      timeoutMs: config.agent.python.timeoutMs,
      apiKey: config.agent.python.apiKey,
    });
  }

  return new LocalLangChainRuntime();
}
