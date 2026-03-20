import { config } from '../config.js';
import type { AgentRuntime } from '../core/runtime.js';
import { PythonHttpRuntime } from './pythonHttpRuntime.js';

export function createAgentRuntime(): AgentRuntime {
  return new PythonHttpRuntime({
    baseUrl: config.agent.python.baseUrl,
    timeoutMs: config.agent.python.timeoutMs,
    apiKey: config.agent.python.apiKey,
  });
}
