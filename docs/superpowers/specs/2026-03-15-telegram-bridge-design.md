# Telegram Transport Integration Design (Hybrid Bridge)

Date: 2026-03-15  
Status: Draft (approved direction, pending review)  
Owner: Codex + User

## Summary

Add **Telegram** as a second transport alongside WhatsApp in the Node/TypeScript bridge.  
Both transports normalize into the **same canonical message schema** and send requests to the **same agent runtime** (local LangChain or Python HTTP).

This preserves the current architecture while expanding channel coverage with minimal risk.

## Goals

- Support Telegram inbound **text + media** (image, audio, video, document) from day one.
- Reuse the existing canonical message and outbound action contracts.
- Keep the Python runtime unchanged.
- Preserve the current WhatsApp behavior and code paths.

## Non‑Goals

- Migrating WhatsApp transport into Python.
- Advanced Telegram‑specific features (inline queries, callback buttons, payments).
- Message bus / distributed architecture (out of scope for v1).

## Architecture

**Node layer (transport + normalization):**
- WhatsApp (Baileys)
- Telegram (Telegram Bot API client)

**Runtime layer (same as today):**
- `local-langchain` runtime in Node **or**
- `python-http` runtime via FastAPI

**Flow:**
Telegram → Normalize → Canonical Message → Agent Runtime → Outbound Actions → Telegram send APIs.

## Proposed Structure

```
src/
  telegram/
    connection.ts
    normalizers/
      inboundMessageNormalizer.ts
    outbound/
      outboundActionHandler.ts
  bridge/
    telegramBridge.ts
  core/
    messages.ts
    runtime.ts
```

This mirrors the WhatsApp bridge and keeps structure consistent.

## Telegram API Integration (Node)

**Recommended client:** `grammY` (TypeScript‑friendly, actively maintained).

**Mode:**
- v1: long polling for simplicity
- future: switch to webhook (no structural change)

## Canonical Message Contract Updates

Update `Channel` to include `telegram`:

- `Channel = 'whatsapp' | 'telegram'`

No other schema changes required; Telegram events map to existing fields:

- `chatId`: Telegram chat id
- `senderId`: Telegram user id
- `senderName`: from Telegram user profile
- `messageId`, `timestamp`, `messageType`, `text`, `caption`, `media`

## Inbound Normalization (Telegram)

Map Telegram message types into existing `InboundMessageType`:

- Text → `text`
- Photo → `image`
- Audio → `audio`
- Voice → `voice_note`
- Video → `video`
- Document → `document` / `pdf`
- Sticker → `sticker`
- Location → `location`
- Contact → `contact`

If a message does not match any known type, set `messageType = 'unknown'`.

Event filtering:

- Explicitly detect Telegram message edit events and discard them with a log entry.
  Do not silently ignore edits, to avoid duplicate or mutated message handling.

## Media Handling

Telegram media flow:

1. Receive Telegram message with `file_id`
2. Call `getFile` to obtain `file_path`
3. Download file via `https://api.telegram.org/file/bot<TOKEN>/<file_path>`
4. Store to `media_staging/<messageId>/...`
5. Create `MediaAttachment` with `storagePath`, `mimeType`, `filename`, etc.

Media staging should reuse the existing `LocalMediaStore` implementation where possible.

Telegram Bot API note:

- Bot downloads are capped at 20MB. If a file exceeds this limit, surface a graceful
  `downloadError` in `metadata` and continue without crashing.

## Outbound Actions (Telegram)

Map existing outbound actions to Telegram send APIs:

- `send_text` → `sendMessage`
- `send_image` → `sendPhoto`
- `send_audio` → `sendAudio`
- `send_video` → `sendVideo`
- `send_document` → `sendDocument`

If an action cannot be mapped, log and skip (never crash the bridge).

## Configuration

Add Telegram environment variables:

- `TELEGRAM_BOT_TOKEN` (required if Telegram enabled)
- `TELEGRAM_ENABLED=true|false` (optional, default false)
- `TELEGRAM_MEDIA_STAGING_DIR` (optional, default `media_staging`)

Startup validation:

- If `TELEGRAM_ENABLED=true` and `TELEGRAM_BOT_TOKEN` is missing, fail fast with a clear error.

## Error Handling

- Any failure in Telegram API calls should be logged with context.
- If media download fails, still emit a `MediaAttachment` with `metadata.downloadError`.
- Runtime errors should return a fallback `send_text` action where possible.
- Define a default fallback message template (for example: "Sorry, something went wrong.")
  so users never receive silence.

## Testing

Unit tests:
- Telegram normalizer for each supported message type.
- Media download + staging flow.
- Outbound action mapping.

Integration tests (manual):
- Send each media type from Telegram and confirm responses.
- Verify long‑polling reconnect behavior.

## Rollout Plan

1. Implement Telegram transport and normalization.
2. Validate with the mock runtime.
3. Enable the Python runtime path.
4. Add optional webhook support later.

## Open Questions

- Should we support Telegram replies / quoted messages in v1?
- Do we need message editing events or only new messages?
