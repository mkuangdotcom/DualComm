# DualComm

DualComm is a messaging bridge that connects WhatsApp and Telegram to a Python AI runtime.

The project has two running parts:

- TypeScript bridge (channel connectivity and message forwarding)
- Python bridge (runtime logic: LangChain, LlamaIndex, Hybrid RAG)

## Architecture

1. User sends message in WhatsApp or Telegram.
2. Node bridge normalizes the message payload.
3. If `AGENT_MODE=python-http`, Node forwards to Python `/messages`.
4. Python backend selected by `AGENT_BACKEND` handles the message.
5. Python returns outbound actions.
6. Node sends action output back to user channel.

## Prerequisites

- Node.js 18+
- npm 9+
- Python 3.11+
- Git

## Clone From GitHub

```bash
git clone https://github.com/mkuangdotcom/DualComm.git
cd DualComm
```

## Environment Setup

Create a root environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with your real keys:

- `GROQ_API_KEY`
- `COHERE_API_KEY`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `TELEGRAM_BOT_TOKEN` (if Telegram is enabled)

Do not commit `.env`.

## Install Dependencies

### 1) Node dependencies

```bash
npm install
```

### 2) Python dependencies

Create virtual environment at the parent workspace level, then install:

```powershell
python -m venv ..\.venv
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS/Linux:

```bash
python -m venv ../.venv
../.venv/bin/python -m pip install -r requirements.txt
```

## Choose Runtime Modes

In `.env`:

- `AGENT_MODE=python-http` to use Python runtime (recommended)
- `PYTHON_AGENT_BASE_URL=http://127.0.0.1:8000`

Python backend selection:

- `AGENT_BACKEND=mock`
- `AGENT_BACKEND=langchain`
- `AGENT_BACKEND=llamaindex`
- `AGENT_BACKEND=hybrid` (translation + retrieval + generation)

## Run The Application

Use two terminals.

### Terminal A: Start Python bridge

From repository root:

```powershell
Set-Location "C:\path\to\DualComm"
& "C:/path/to/.venv/Scripts/python.exe" -m uvicorn app.main:app --app-dir python_bridge --host 0.0.0.0 --port 8000 --reload
```

Health check:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health | Select-Object -ExpandProperty Content
```

Expected response:

```json
{"status":"ok"}
```

### Terminal B: Start Node bridge

From repository root:

```bash
npm run dev
```

Expected startup output includes:

- Agent mode and runtime URL
- WhatsApp bridge registered
- Telegram bridge registered (if enabled)
- WhatsApp QR output for linking device

## Verify RAG Is Working

When `AGENT_BACKEND=hybrid` or `AGENT_BACKEND=llamaindex`, monitor metadata from Python `/messages` response.

RAG active indicators:

- `runtime: "hybrid"` or `runtime: "llamaindex"`
- `rag_status` or `llamaindex_status`
- `rag_context_count` or `llamaindex_context_count`

Interpretation:

- `ok` + context count > 0: retrieval hit
- `no_match` + context count 0: no relevant chunk found
- `error`: retrieval call failed (check API keys/network/collection)

## Common Issues

### Error: `ECONNREFUSED 127.0.0.1:8000`

Node cannot reach Python.

Check:

1. Python service is running.
2. `.env` has matching `PYTHON_AGENT_BASE_URL` and Python port.
3. Health endpoint returns `{"status":"ok"}`.

### Error: `Could not import module "app"`

Wrong uvicorn target. Use:

```bash
python -m uvicorn app.main:app --app-dir python_bridge --host 0.0.0.0 --port 8000 --reload
```

### Path errors on Windows with spaces

Always quote paths:

```powershell
Set-Location "C:\Users\name\Desktop\Research\Codex\V Hack new\DualComm"
```

## Recommended Git Hygiene

Do not commit runtime artifacts and secrets:

- `.env`
- `.venv/`, `venv/`
- `node_modules/`
- `auth_info_baileys/`
- `media_staging/`
- `__pycache__/`, `*.pyc`, `*.log`

## Additional Docs

- `python_bridge/README.md` for Python service details
- `docs/python-whatsapp-llm-bridge-plan.md` for implementation plan notes
