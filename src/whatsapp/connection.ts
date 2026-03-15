import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  type WASocket,
  type ConnectionState,
} from "baileys";
import P from "pino";
import NodeCache from "node-cache";
import qrcode from "qrcode-terminal";

import { config } from "../config.js";

// Enable warn-level logging so we can see actual errors from Baileys
const logger = P({ level: "warn" });

/** Callback type for connection lifecycle events */
export interface ConnectionCallbacks {
  onQR?: (qr: string) => void;
  onConnected?: (sock: WASocket) => void;
  onDisconnected?: (reason: string) => void;
}

export interface ConnectionOptions {
  authDirectory?: string;
}

const MAX_RETRIES = 5;
const RETRY_DELAY_MS = 3000;

/**
 * Creates and manages a Baileys WhatsApp Web socket connection.
 *
 * Handles:
 * - Auth state persistence (file-based for dev, swappable)
 * - QR code generation for pairing
 * - Auto-reconnection with retry limit
 * - Group metadata caching to avoid rate limits
 *
 * Returns the live socket instance.
 */
export async function createWhatsAppConnection(
  callbacks?: ConnectionCallbacks,
  options: ConnectionOptions = {},
): Promise<WASocket> {
  let retryCount = 0;
  const authDirectory = options.authDirectory || config.whatsapp.authDirectory;

  // --- Group metadata cache (prevents ratelimit on group sends) ---
  const groupCache = new NodeCache({ stdTTL: 300, checkperiod: 60 });

  async function connect(): Promise<WASocket> {
    // --- Auth state (file-based for dev; swap for DB in prod) ---
    const { state, saveCreds } = await useMultiFileAuthState(authDirectory);

    // --- Fetch the latest WA Web version (prevents 405 errors) ---
    const { version, isLatest } = await fetchLatestBaileysVersion();
    console.log(
      `[WhatsApp] Using WA v${version.join(".")} (latest: ${isLatest})`,
    );

    // --- Create socket ---
    const sock = makeWASocket({
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      logger,
      version,
      browser: ["WhatsApp LLM Bridge", "Chrome", "22.0"],
      markOnlineOnConnect: false,
      getMessage: async (_key) => {
        // In production, fetch from your message store
        return undefined;
      },
      cachedGroupMetadata: async (jid) => groupCache.get(jid),
      shouldSyncHistoryMessage: () => false,
    });

    // --- Connection lifecycle ---
    sock.ev.on(
      "connection.update",
      async (update: Partial<ConnectionState>) => {
        const { connection, lastDisconnect, qr } = update;

        // QR code received → display in terminal
        if (qr) {
          retryCount = 0; // reset retries on QR (connection is progressing)
          console.log(
            "\n[WhatsApp] Scan this QR code with WhatsApp → Linked Devices:",
          );
          qrcode.generate(qr, { small: true });
          callbacks?.onQR?.(qr);
        }

        // Connection opened
        if (connection === "open") {
          retryCount = 0;
          console.log("[WhatsApp] ✅ Connected successfully!");
          callbacks?.onConnected?.(sock);
        }

        // Connection closed
        if (connection === "close") {
          const statusCode = (lastDisconnect?.error as any)?.output?.statusCode;
          const errorMsg = (lastDisconnect?.error as any)?.message || "unknown";
          const reason = DisconnectReason[statusCode] || `code ${statusCode}`;

          console.log(`[WhatsApp] ⚠️  Disconnected: ${reason} — ${errorMsg}`);

          // --- Fatal: logged out ---
          if (statusCode === DisconnectReason.loggedOut) {
            console.log(
              "[WhatsApp] ❌ Logged out. Delete auth_info_baileys/ and restart.",
            );
            callbacks?.onDisconnected?.("logged_out");
            return;
          }

          // --- Retry with limit ---
          retryCount++;
          if (retryCount > MAX_RETRIES) {
            console.error(
              `[WhatsApp] ❌ Max retries (${MAX_RETRIES}) reached. Giving up.`,
            );
            console.error("   Try deleting auth_info_baileys/ and restarting.");
            callbacks?.onDisconnected?.("max_retries");
            return;
          }

          const delay = RETRY_DELAY_MS * retryCount;
          console.log(
            `[WhatsApp] 🔄 Reconnecting in ${delay / 1000}s... (attempt ${retryCount}/${MAX_RETRIES})`,
          );
          await new Promise((r) => setTimeout(r, delay));

          // Reconnect by creating a new socket
          try {
            const newSock = await connect();
            // Notify the caller about the new socket so it can re-register handlers
            callbacks?.onConnected?.(newSock);
          } catch (err) {
            console.error("[WhatsApp] ❌ Reconnection failed:", err);
            callbacks?.onDisconnected?.("reconnect_failed");
          }
        }
      },
    );

    // --- Persist credentials on update ---
    sock.ev.on("creds.update", saveCreds);

    // --- Cache group metadata when received ---
    sock.ev.on("groups.upsert", (groups) => {
      for (const group of groups) {
        groupCache.set(group.id, group);
      }
    });
    sock.ev.on("groups.update", (updates) => {
      for (const update of updates) {
        const cached = groupCache.get<any>(update.id!);
        if (cached) {
          groupCache.set(update.id!, { ...cached, ...update });
        }
      }
    });

    return sock;
  }

  return connect();
}
