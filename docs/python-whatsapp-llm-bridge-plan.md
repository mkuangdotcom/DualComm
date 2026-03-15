# Python WhatsApp ↔ LLM Bridge Implementation Plan

## Goal

Build a **Python-first connection layer** between **WhatsApp** and an **LLM/agent runtime**, using **Evolution API** as the WhatsApp gateway.

This phase focuses only on the bridge layer, not the full backend platform.

## Why this approach

### Use Python where possible
Python is the preferred implementation language for the bridge because:

- it aligns well with future **LangChain** usage
- it aligns well with future **LlamaIndex** usage
- it is a good fit for AI orchestration, multimodal preprocessing, and agent runtime composition

### Use Evolution API for WhatsApp transport
Instead of implementing low-level WhatsApp transport directly in Python, use **Evolution API** for:

- WhatsApp session management
- QR connection flow
- webhook delivery for inbound events
- outbound message sending
- media handling endpoints

This keeps the Python code focused on the actual bridge/domain logic.

---

## Scope for this phase

### In scope
- webhook receiver for inbound WhatsApp events
- canonical internal message model
- support for all major WhatsApp message/data types at the type-system level
- media-aware normalization pipeline
- agent runtime abstraction
- outbound response abstraction
- Evolution API client for sending replies
- project structure that is easy to integrate later
- logging, validation, and configuration

### Out of scope
- full business backend
- CRM logic
- complex workflow engine
- production-grade persistence layer
- advanced user management
- distributed queues unless later required
- full analytics/dashboard

---

## Architecture overview

The bridge should be organized into these layers:

1. **Webhook Transport Layer**
   - receives webhook calls from Evolution API
   - validates and parses inbound events

2. **Event Normalization Layer**
   - converts provider-specific payloads into stable internal models

3. **Media Intake Layer**
   - identifies attachments
   - extracts metadata
   - supports later download/storage/transcription/OCR/document extraction

4. **Bridge Orchestrator**
   - coordinates inbound event processing
   - decides whether to ignore, process, or respond
   - invokes the configured agent runtime

5. **Agent Runtime Adapter**
   - provides a framework-agnostic interface
   - can later be implemented with:
     - LangChain Python
     - LlamaIndex Python
     - HTTP-based external agent service

6. **Outbound Renderer**
   - converts agent outputs into WhatsApp-compatible actions
   - sends responses via Evolution API

7. **Observability and Config**
   - structured logs
   - correlation IDs
   - environment-driven configuration

---

## Recommended repository structure

Suggested Python structure:

- `python_bridge/app.py`
- `python_bridge/config.py`
- `python_bridge/logging.py`
- `python_bridge/api/`
  - `routes.py`
  - `schemas.py`
- `python_bridge/core/`
  - `models.py`
  - `enums.py`
  - `context.py`
- `python_bridge/normalizers/`
  - `evolution_webhook.py`
  - `messages.py`
- `python_bridge/media/`
  - `models.py`
  - `resolver.py`
  - `storage.py`
  - `extractors.py`
- `python_bridge/agents/`
  - `base.py`
  - `mock.py`
  - `langchain_adapter.py`
  - `llamaindex_adapter.py`
  - `http_adapter.py`
- `python_bridge/bridge/`
  - `service.py`
  - `router.py`
- `python_bridge/providers/evolution/`
  - `client.py`
  - `sender.py`
  - `webhook_setup.py`
- `python_bridge/session/`
  - `store.py`
- `python_bridge/tests/`
  - normalization and bridge tests

---

## Core design principles

### 1. Provider payloads must not leak into the domain
The rest of the bridge should not depend on raw Evolution or Baileys payload structures.

All inbound events should be normalized into internal models before business processing.

### 2. The bridge must be multimodal-ready
Even if the first working version only answers with text, the internal contracts must support:

- text
- image
- audio
- voice notes
- video
- PDF
- generic documents
- sticker
- location
- contact
- reactions
- interactive replies

### 3. The agent runtime must not be text-only
Do not design the runtime contract as:

- input: text
- output: text

Instead design it as:

- input: canonical inbound message + conversation context
- output: one or more outbound actions

### 4. Keep WhatsApp transport separate from AI logic
The Python bridge should not tightly couple message reception to one specific framework.

---

## Canonical internal models

### Inbound message model

Each inbound WhatsApp event should be normalized into a message envelope with fields like:

- `instance_id`
- `channel`
- `provider`
- `event_name`
- `message_id`
- `chat_id`
- `sender_id`
- `sender_name`
- `timestamp`
- `is_from_me`
- `is_group`
- `message_type`
- `text`
- `caption`
- `reply_to_message_id`
- `attachments`
- `location`
- `contacts`
- `reaction`
- `interactive`
- `raw_payload`

### Message types

Support these types from the beginning:

- `text`
- `image`
- `audio`
- `voice_note`
- `video`
- `document`
- `pdf`
- `sticker`
- `location`
- `contact`
- `reaction`
- `button_reply`
- `list_reply`
- `unknown`

### Attachment model

Each media attachment should support fields like:

- `id`
- `kind`
- `mime_type`
- `filename`
- `caption`
- `size_bytes`
- `duration_ms`
- `page_count`
- `sha256`
- `base64_data`
- `remote_url`
- `storage_key`
- `metadata`

### Outbound action model

The runtime should return actions such as:

- `send_text`
- `send_media`
- `send_audio`
- `send_document`
- `send_location`
- `send_reaction`
- `mark_read`
- `no_op`

Even if only `send_text` is implemented first, the schema should already allow the rest.

---

## Supported WhatsApp content types

The bridge should explicitly prepare for all relevant WhatsApp data categories.

### Text
- plain text
- extended text
- quoted text
- interactive reply text

### Image
- image body
- caption
- mime type
- future OCR/vision hook

### Audio
- audio messages
- voice notes / PTT
- mime type
- duration
- future transcription hook

### Video
- video body
- caption
- mime type
- duration
- future metadata extraction hook

### PDF and documents
- PDFs
- office files
- generic documents
- filename
- mime type
- size
- future text extraction hook

### Sticker
- sticker metadata
- pass-through handling for now

### Location
- latitude
- longitude
- name
- address

### Contact
- one or more contacts
- normalized contact details

### Reactions
- emoji reaction
- target message reference

### Interactive
- buttons
- list replies
- future template handling

---

## Evolution API usage plan

Use Evolution API as the WhatsApp provider boundary.

### Inbound
Receive events using **webhooks**, especially:
- `MESSAGES_UPSERT`
- `MESSAGES_UPDATE`
- `MESSAGES_DELETE`
- `CONNECTION_UPDATE`
- optionally `QRCODE_UPDATED`

### Outbound
Use Evolution API send endpoints for:
- text
- media
- audio
- location
- contact
- reaction
- list/button if needed later

### Setup
The bridge should include a helper flow to configure instance webhooks via Evolution API.

---

## Python framework recommendation

Use:

- **FastAPI** for webhook intake and health endpoints
- **Pydantic** for payload validation and canonical models
- **httpx** for Evolution API calls
- **uvicorn** for local serving

Optional later:
- `orjson` for speed
- `structlog` or standard structured logging
- `tenacity` for retries
- `pytest` for tests

---

## Runtime integration strategy

The bridge should define a framework-agnostic runtime interface.

### Runtime input
- normalized inbound message
- session key
- conversation context
- available attachments/media references

### Runtime output
- list of outbound actions

### Planned runtime adapters
1. `MockAgentRuntime`
   - for initial development
2. `LangChainAgentRuntime`
   - future Python LangChain integration
3. `LlamaIndexAgentRuntime`
   - future Python LlamaIndex integration
4. `HttpAgentRuntime`
   - future external service integration

---

## Session and memory strategy

At this stage, keep it simple.

### Session key
Use a stable session key such as:
- per chat
- or per sender + instance

### Initial memory approach
- in-memory only
- simple and replaceable abstraction

### Later upgrade path
- Redis
- database-backed memory
- custom conversation state store

The key is to define the interface now and keep storage replaceable.

---

## Media handling strategy

For this phase, media support should be **structurally complete**, even if deep processing is deferred.

### Phase 1 media behavior
- identify message type
- extract metadata
- preserve base64 if delivered by Evolution API
- preserve provider references
- produce canonical attachment objects

### Phase 2 media behavior
- optionally download/store large media
- map to local or object storage
- create stable storage references

### Phase 3 media behavior
- transcription for audio
- OCR/vision for images
- text extraction for PDF/documents
- optional video preprocessing

Do not hardcode these processors into the webhook layer.

Instead, define replaceable interfaces such as:
- `AudioTranscriber`
- `ImageAnalyzer`
- `DocumentExtractor`

---

## Implementation phases

### Phase 1 — Foundation
Deliver a minimal but correctly structured Python bridge.

#### Deliverables
- FastAPI app
- webhook endpoint
- config module
- structured logger
- canonical internal models
- Evolution API client
- message normalizer for text and basic media detection
- mock agent runtime
- outbound text sending
- health endpoint

#### Success criteria
- receives webhook event
- normalizes text message
- calls runtime
- sends text reply through Evolution API

---

### Phase 2 — Full inbound normalization
Expand inbound coverage for WhatsApp message types.

#### Deliverables
- image normalization
- audio normalization
- voice note normalization
- video normalization
- document/PDF normalization
- location normalization
- contact normalization
- reaction normalization
- button/list reply normalization

#### Success criteria
- all common inbound WhatsApp content types map into stable internal models

---

### Phase 3 — Media pipeline
Add proper media intake and storage abstraction.

#### Deliverables
- attachment resolver
- optional media persistence abstraction
- content metadata enrichment
- storage provider interface

#### Success criteria
- media payloads are available to downstream runtimes in a consistent format

---

### Phase 4 — Agent runtime integration
Integrate real AI frameworks.

#### Deliverables
- LangChain adapter
- LlamaIndex adapter
- optional HTTP runtime adapter
- timeout and retry behavior
- runtime error handling

#### Success criteria
- runtime can consume multimodal-ready payloads and return outbound actions

---

### Phase 5 — Production hardening
Prepare the bridge for later platform integration.

#### Deliverables
- request authentication
- webhook verification strategy
- idempotency handling
- retry-safe processing
- better logging and tracing
- environment profiles
- test coverage for normalization and routing

---

## Concrete first deliverables

The first coding pass should create:

- `python_bridge/app.py`
- `python_bridge/config.py`
- `python_bridge/core/models.py`
- `python_bridge/agents/base.py`
- `python_bridge/agents/mock.py`
- `python_bridge/providers/evolution/client.py`
- `python_bridge/normalizers/evolution_webhook.py`
- `python_bridge/bridge/service.py`
- `python_bridge/api/routes.py`
- `python_bridge/requirements.txt`
- `.env.example`

---

## API endpoints for the bridge

Recommended internal endpoints:

- `GET /health`
- `POST /webhooks/evolution`
- `POST /internal/test/send-text`
- optional `POST /internal/webhook/setup`

These are bridge-facing endpoints, not final product API endpoints.

---

## Configuration plan

Recommended environment variables:

- `BRIDGE_HOST`
- `BRIDGE_PORT`
- `LOG_LEVEL`

- `EVOLUTION_API_BASE_URL`
- `EVOLUTION_API_KEY`
- `EVOLUTION_INSTANCE_NAME`

- `EVOLUTION_WEBHOOK_SECRET`
- `EVOLUTION_WEBHOOK_BASE64`

- `AGENT_RUNTIME`
- `AGENT_TIMEOUT_SECONDS`

- `OPENAI_API_KEY`
- `LANGCHAIN_TRACING_V2`
- other future runtime-specific settings

Keep config centralized and validated at startup.

---

## Risks and mitigation

### Risk: webhook payload variations
Evolution webhook payloads may vary by version or event shape.

**Mitigation:**
- keep raw payload
- write defensive normalizers
- log unknown shapes
- support partial parsing gracefully

### Risk: large media payloads
Base64 media can be large and expensive to process inline.

**Mitigation:**
- keep processing lightweight in webhook path
- optionally defer large media handling
- add size limits and async processing later

### Risk: runtime latency
LLM/agent runtimes may be slow.

**Mitigation:**
- add timeout handling
- optionally send typing/presence later
- keep bridge/runtime boundary explicit

### Risk: overcoupling to one framework
Prematurely binding to LangChain or LlamaIndex could create migration cost.

**Mitigation:**
- runtime abstraction first
- framework adapters second

---

## Final recommendation

The best path is:

- **Evolution API** handles WhatsApp connectivity
- **Python** owns the bridge/domain/orchestration layer
- **LangChain/LlamaIndex** plug in later through adapters
- the internal models are **multimodal-ready from day one**

This gives the fastest route to a clean implementation while preserving long-term flexibility.

## Immediate next step

Implement **Phase 1** first:

1. FastAPI webhook service
2. canonical inbound models
3. Evolution API outbound client
4. mock agent runtime
5. text reply loop
6. media-ready normalization skeleton

After that, expand normalization coverage for images, audio, video, PDF, and other document types.