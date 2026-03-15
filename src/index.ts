import { config, validateConfig } from "./config.js";
import { createAgentRuntime } from "./agents/runtimeFactory.js";
import { TelegramBridge } from "./bridge/telegramBridge.js";
import { WhatsAppBridge } from "./bridge/whatsappBridge.js";
import { createTelegramConnection } from "./telegram/connection.js";
import { TelegramInboundMessageNormalizer } from "./telegram/normalizers/inboundMessageNormalizer.js";
import { createWhatsAppConnection } from "./whatsapp/connection.js";
import { LocalMediaStore } from "./whatsapp/media/mediaStore.js";
import { InboundMessageNormalizer } from "./whatsapp/normalizers/inboundMessageNormalizer.js";
import type { WASocket } from "baileys";
import type { Bot } from "grammy";

async function main() {
  console.log("=".repeat(60));
  console.log(`  🤖 ${config.bot.name} — WhatsApp Hybrid Bridge`);
  console.log(`  Agent mode: ${config.agent.mode}`);
  console.log(
    `  Runtime: ${
      config.agent.mode === "python-http"
        ? config.agent.python.baseUrl
        : `local-${config.llm.provider}`
    }`,
  );
  console.log("=".repeat(60));

  try {
    validateConfig();
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "Unknown configuration error";
    console.error(`\n❌ Configuration error: ${message}`);
    console.error("   Update your environment settings and try again.\n");
    process.exit(1);
  }

  const agentRuntime = createAgentRuntime();
  const mediaStore = new LocalMediaStore({
    baseDirectory: config.whatsapp.mediaStagingDirectory,
  });
  const telegramMediaStore = new LocalMediaStore({
    baseDirectory: config.telegram.mediaStagingDirectory,
  });

  let activeBridge: WhatsAppBridge | null = null;
  let activeSock: WASocket | null = null;
  let telegramBridge: TelegramBridge | null = null;
  let telegramBot: Bot | null = null;

  function wireBridge(sock: WASocket) {
    if (activeSock === sock && activeBridge) {
      return;
    }

    activeBridge?.dispose();
    activeSock = sock;

    const normalizer = new InboundMessageNormalizer({
      instanceId: config.whatsapp.instanceId,
      mediaStore,
    });

    const bridge = new WhatsAppBridge(sock, agentRuntime, {
      instanceId: config.whatsapp.instanceId,
      normalizer,
      logger: console,
    });

    bridge.register();
    activeBridge = bridge;
  }

  const sock = await createWhatsAppConnection(
    {
      onConnected: (newSock) => {
        console.log(
          "\n✅ WhatsApp bridge is live. Send a message on WhatsApp to test it.\n",
        );
        wireBridge(newSock);
      },
      onDisconnected: (reason) => {
        console.log(`[Main] Connection ended: ${reason}`);
        if (reason === "logged_out" || reason === "max_retries") {
          agentRuntime.dispose?.();
          process.exit(1);
        }
      },
    },
    {
      authDirectory: config.whatsapp.authDirectory,
    },
  );

  wireBridge(sock);

  if (config.telegram.enabled) {
    const bot = createTelegramConnection({
      token: config.telegram.botToken,
      logger: console,
    });

    const telegramNormalizer = new TelegramInboundMessageNormalizer({
      botToken: config.telegram.botToken,
      api: bot.api,
      mediaStore: telegramMediaStore,
      logger: console,
    });

    const bridge = new TelegramBridge(bot, agentRuntime, {
      normalizer: telegramNormalizer,
      logger: console,
    });

    bridge.register();
    void bot.start();

    telegramBot = bot;
    telegramBridge = bridge;

    console.log("[Telegram] Bot started (long polling).");
  }

  process.on("SIGINT", () => {
    console.log("\n[Main] Shutting down...");
    activeBridge?.dispose();
    telegramBridge?.dispose();
    telegramBot?.stop();
    sock.end(undefined);
    process.exit(0);
  });
}

main().catch((error) => {
  console.error("[Main] Fatal error:", error);
  process.exit(1);
});
