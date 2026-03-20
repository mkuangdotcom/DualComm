import { config } from '../config.js';
import type { AgentRuntime } from '../core/runtime.js';
import { PythonHttpRuntime } from './pythonHttpRuntime.js';

export function createAgentRuntime(): AgentRuntime {
  if (config.agent.mode === 'python-http') {
    return new PythonHttpRuntime({
      baseUrl: config.agent.python.baseUrl,
      timeoutMs: config.agent.python.timeoutMs,
      apiKey: config.agent.python.apiKey,
    });
  }

  throw new Error(
    'AGENT_MODE=local-langchain is not available in this build. Set AGENT_MODE=python-http.',
  );
}
