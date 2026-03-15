# Python Bridge README

This directory contains the **Python agent runtime** for the messaging bridge.

The current project architecture is:

- **TypeScript + bridges** handle WhatsApp and Telegram connectivity
- **Python + FastAPI** handles normalized inbound messages and returns outbound actions

This keeps transport layers separate from the agent/runtime layer, so you can later plug in:

- LangChain
- LlamaIndex
- custom Python agents
- retrieval pipelines
- multimodal processors for image, audio, video, and documents

---

## Purpose

The Python bridge is responsible for:

- receiving normalized inbound message payloads from the TypeScript bridge
- validating request structure
- routing messages to a Python runtime service
- returning outbound actions in a stable schema
- staying framework-agnostic so agent logic can evolve later

This is **not** the full backend.  
It is the **Python runtime layer** behind the Telegram/WhatsApp bridges.

---

## Current entrypoint

The recommended FastAPI entrypoint is:

```V Hack/python_bridge/app/main.py#L1-25
from fastapi import FastAPI

from app.routes.messages import router as messages_router


def create_app() -> FastAPI:
    app = FastAPI(
    title="Messaging Python Agent Bridge",
        version="0.1.0",
        description=(
            "Python agent runtime for normalized Telegram/WhatsApp bridge payloads. "
            "Receives normalized inbound messages and returns outbound actions."
        ),
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(messages_router, prefix="")

    return app


app = create_app()
```

This means you should run the service with `app.main:app`.

---

## Recommended structure

The active Python service path is:

```/dev/null/python-bridge-layout.txt#L1-14
python_bridge/
  README.md
  requirements.txt
  .env.service.example
  app/
    __init__.py
    main.py
    settings.py
    routes/
      messages.py
    schemas/
      messages.py
    services/
      base.py
      runtime.py
      runtime_factory.py
      mock_runtime.py
      langchain_runtime.py
      llamaindex_runtime.py
```

There are older scaffold files in this directory from previous planning iterations.  
For now, treat `python_bridge/app/` as the **authoritative service implementation path**.

---

## API overview

### Health check

- `GET /health`

Response:

```/dev/null/health-response.json#L1-3
{
  "status": "ok"
}
```

### Message endpoint

- `POST /messages`

This endpoint receives a normalized message payload from the TypeScript bridge and returns a list of outbound actions.

---

## Request schema

The TypeScript bridge sends a payload shaped like this:

```/dev/null/agent-request.json#L1-25
{
  "message": {
    "instanceId": "default",
    "channel": "telegram",
    "direction": "inbound",
    "messageId": "ABC123",
    "chatId": "123456789",
    "senderId": "123456789",
    "senderName": "Alice",
    "timestamp": "2026-03-13T10:00:00.000Z",
    "messageType": "text",
    "text": "hello",
    "caption": null,
    "media": [],
    "context": {
      "quotedMessageId": null,
      "quotedParticipant": null,
      "quotedText": null,
      "replyToMessageType": null,
      "metadata": null
    },
    "rawProviderPayload": {}
  }
}
```

---

## Response schema

The Python bridge returns outbound actions like this:

```/dev/null/agent-response.json#L1-12
{
  "actions": [
    {
      "type": "send_text",
      "text": "Hello from the Python bridge"
    }
  ],
  "metadata": {
    "runtime": "python-bridge",
    "handled_message_type": "text"
  }
}
```

---

## Supported outbound action types

The schema is already designed to support more than text.

Current supported action types in the contract:

- `send_text`
- `send_image`
- `send_audio`
- `send_video`
- `send_document`
- `ignore`

The current mock Python runtime mostly returns `send_text`, but the interface is ready to expand.

---

## Supported inbound WhatsApp message types

The bridge contract already supports these normalized message types:

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

This matches the long-term goal of handling all major WhatsApp data types.

---

## Current Python runtime behavior

The current runtime implementation lives here:

```V Hack/python_bridge/app/services/runtime.py#L1-168
from __future__ import annotations

from typing import Any, Dict, List, Optional


class BridgeRuntime:
    """
    Minimal Python runtime for the WhatsApp bridge.

    This service is intentionally simple:
    - accepts the normalized inbound payload from the TypeScript bridge
    - returns a list of outbound actions
    - stays framework-agnostic so LangChain/LlamaIndex can be integrated later
    """
```

The request flow is:

- `BridgeRuntime` delegates to `runtime_factory`
- the factory selects the backend from `AGENT_BACKEND`
- a backend adapter (mock, LangChain, LlamaIndex) returns actions

The mock backend currently:

- echoes text-like messages
- acknowledges media messages
- confirms location/contact payloads
- returns stable outbound actions

---

## Environment configuration

Use the service example file:

- `python_bridge/.env.service.example`

Typical values:

```/dev/null/python-env.txt#L1-9
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=info
PYTHON_AGENT_API_KEY=
AGENT_BACKEND=mock
MEDIA_ROOT=./media
TEMP_DIR=./tmp
ENABLE_AUDIO_TRANSCRIPTION=false
ENABLE_IMAGE_ANALYSIS=false
```

### Optional API key
The TypeScript bridge can send:

- `x-agent-api-key`

The Python service settings support optional API key validation so you can secure bridge-to-runtime communication later.

---

## Installation

From the project root or from `python_bridge/`, create a Python environment and install dependencies from:

- `python_bridge/requirements.txt`

Typical dependencies include:

- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `pydantic-settings`
- `python-dotenv`

Future-ready packages are also included for later agent integration.

---

## Running the service

Run the FastAPI app from inside `python_bridge/`:

```/dev/null/run-python-bridge.sh#L1-2
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

If you use environment files, load them before startup or place a `.env` file inside `python_bridge/`.

---

## How it connects to the TypeScript bridge

The TypeScript bridge should use:

- `AGENT_MODE=python-http`
- `PYTHON_AGENT_BASE_URL=http://127.0.0.1:8000`

Then the flow becomes:

```/dev/null/bridge-flow.txt#L1-8
WhatsApp message
  -> Baileys receives event
  -> TypeScript normalizes message
  -> TypeScript stages media if needed
  -> TypeScript POSTs to Python /messages
  -> Python returns outbound actions
  -> TypeScript renders actions back to WhatsApp
```

---

## Next recommended steps

### 1. Replace the mock runtime
Extend `app/services/runtime.py` so it delegates to:

- LangChain adapter
- LlamaIndex adapter
- custom business logic
- multimodal processors

### 2. Add API-key enforcement
Use `app/settings.py` to require and validate `x-agent-api-key`.

### 3. Add preprocessing services
Later, add services for:

- audio transcription
- image OCR / vision
- PDF/document extraction
- video metadata extraction

### 4. Add tests
Recommended future test coverage:

- schema validation
- `/messages` response contract
- media message handling
- API key validation
- runtime adapter switching

---

## Summary

Use `python_bridge/app/main.py` as the **official FastAPI entrypoint**.

This Python bridge now serves as the clean runtime boundary between:

- the **TypeScript/Baileys WhatsApp connector**
- the future **Python LangChain / LlamaIndex agent layer**
