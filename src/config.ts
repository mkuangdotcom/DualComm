import "dotenv/config";

export type LLMProvider = "groq" | "cohere";
export type AgentMode = "python-http";

export interface AppConfig {
  llm: {
    provider: LLMProvider;
    groq: { apiKey: string; model: string };
    cohere: { apiKey: string; model: string };
  };
  agent: {
    mode: AgentMode;
    python: {
      baseUrl: string;
      timeoutMs: number;
      apiKey?: string;
    };
  };
  bot: {
    name: string;
    systemPrompt: string;
  };
  memory: {
    windowSize: number;
  };
  whatsapp: {
    instanceId: string;
    authDirectory: string;
    mediaStagingDirectory: string;
  };
  telegram: {
    enabled: boolean;
    botToken: string;
    mediaStagingDirectory: string;
  };
  translation: {
    enabled: boolean;
    nllb: {
      model: string;
      targetLang: "zsm_Latn";
    };
  };
}

function parseNumber(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }

  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseBoolean(value: string | undefined, fallback: boolean): boolean {
  if (!value) {
    return fallback;
  }

  const normalized = value.trim().toLowerCase();
  if (["true", "1", "yes", "y", "on"].includes(normalized)) {
    return true;
  }
  if (["false", "0", "no", "n", "off"].includes(normalized)) {
    return false;
  }

  return fallback;
}

export const config: AppConfig = {
  llm: {
    provider: (process.env.LLM_PROVIDER || "groq") as LLMProvider,
    groq: {
      apiKey: process.env.GROQ_API_KEY || "",
      model: process.env.GROQ_MODEL || "llama-3.3-70b-versatile",
    },
    cohere: {
      apiKey: process.env.COHERE_API_KEY || "",
      model: process.env.COHERE_MODEL || "command-r-plus",
    },
  },
  agent: {
    mode: "python-http",
    python: {
      baseUrl: process.env.PYTHON_AGENT_BASE_URL || "http://127.0.0.1:8000",
      timeoutMs: parseNumber(process.env.PYTHON_AGENT_TIMEOUT_MS, 30000),
      apiKey: process.env.PYTHON_AGENT_API_KEY || undefined,
    },
  },
  bot: {
    name: process.env.BOT_NAME || "Assistant",
    systemPrompt:
      process.env.SYSTEM_PROMPT ||
      "You are a helpful AI assistant on WhatsApp. Be concise and friendly.",
  },
  memory: {
    windowSize: parseNumber(process.env.MEMORY_WINDOW, 10),
  },
  whatsapp: {
    instanceId: process.env.WHATSAPP_INSTANCE_ID || "default",
    authDirectory: process.env.WHATSAPP_AUTH_DIR || "auth_info_baileys",
    mediaStagingDirectory:
      process.env.WHATSAPP_MEDIA_STAGING_DIR || "media_staging",
  },
  telegram: {
    enabled: parseBoolean(process.env.TELEGRAM_ENABLED, false),
    botToken: process.env.TELEGRAM_BOT_TOKEN || "",
    mediaStagingDirectory:
      process.env.TELEGRAM_MEDIA_STAGING_DIR || "media_staging/telegram",
  },
  translation: {
    enabled: parseBoolean(process.env.TRANSLATION_ENABLED, false),
    nllb: {
      model:
        process.env.NLLB_MODEL || "facebook/nllb-200-distilled-600M",
      targetLang: "zsm_Latn",
    },
  },
};

export function validateConfig(): void {
  if (process.env.AGENT_MODE && process.env.AGENT_MODE !== "python-http") {
    throw new Error("Only AGENT_MODE=python-http is supported");
  }

  if (!config.agent.python.baseUrl) {
    throw new Error(
      "PYTHON_AGENT_BASE_URL is required when AGENT_MODE=python-http",
    );
  }

  if (config.telegram.enabled && !config.telegram.botToken) {
    throw new Error(
      "TELEGRAM_BOT_TOKEN is required when TELEGRAM_ENABLED=true",
    );
  }

  if (config.telegram.enabled && typeof fetch !== "function") {
    throw new Error(
      "Node 18+ is required for Telegram media downloads (native fetch)",
    );
  }
}
