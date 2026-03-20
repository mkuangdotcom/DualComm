# DualComm

DualComm is a multilingual AI advocacy platform that empowers migrant workers to report workplace issues through WhatsApp and Telegram — in their native dialect. It ingests text, images, audio, and documents, translates across languages, retrieves relevant legal context via RAG, and auto-generates formal government complaint letters with supporting evidence.

## Demo

### Conversation Flow

A migrant worker reports a workplace issue through WhatsApp — in Cantonese. DualComm translates, understands, and guides them through the complaint process.

<p align="center">
  <img src="https://github.com/user-attachments/assets/d4ddddcb-8606-43b0-80a4-8d8bd041b8fc" width="270" />
  <img src="https://github.com/user-attachments/assets/6e0cb101-367f-4ce3-9bf2-850de68069a7" width="270" />
  <img src="https://github.com/user-attachments/assets/1eeabc4f-4395-4af2-a526-97e626078de7" width="270" />
</p>

### Advocacy Output

Once the case is complete, DualComm auto-generates a formal complaint letter (Surat Rasmi), a CSV case report, and emails them directly to the relevant government department.

<p align="center">
  <img src="https://github.com/user-attachments/assets/714d7a1e-dd61-4b8d-9f0e-96085389794c" width="270" />
  <img src="https://github.com/user-attachments/assets/34c7d625-d133-4def-9c8d-58ba8183f733" width="400" />
  <img src="https://github.com/user-attachments/assets/ee49198e-02a6-469c-a53a-9cd616661a1c" width="400" />
</p>

## Architecture

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────────────┐
│   THE BRIDGE     │    │     INGESTION         │    │  TRANSLATION & BRAIN    │
│                  │    │                       │    │                         │
│  WhatsApp ──┐    │    │  Cohere/Qwen3 Vision  │    │  NLLB Translation       │
│             ├──► │──►│  (image understanding) │──►│  (Cantonese/Javanese    │
│  Telegram ──┘    │    │                       │    │   → Malay)              │
│                  │    │  Groq Whisper-v3 STT   │    │                         │
│  Node.js TS      │    │  (audio transcription) │    │  Qwen3 LLM (reasoning) │
│  Bridge          │    │                       │    │                         │
└─────────────────┘    └──────────────────────┘    └────────────┬────────────┘
                                                                │
                       ┌──────────────────────┐                 │
                       │     THE VAULT         │◄───────────────┘
                       │                       │
                       │  LangChain + LlamaIndex│
                       │  Qdrant Vector DB      │
                       │  (legal knowledge RAG) │
                       └───────────┬───────────┘
                                   │
                       ┌───────────▼───────────┐
                       │     EXECUTION          │
                       │                        │
                       │  LangChain Agent       │
                       │  AgentMail (MCP-Based) │
                       │                        │
                       │  Outputs:              │
                       │  ├── PDF (formal letter)│
                       │  ├── CSV (case report)  │
                       │  └── Email (Resend API) │
                       └────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Messaging | WhatsApp (Baileys), Telegram (grammY) |
| Bridge | Node.js + TypeScript |
| Vision | Cohere embed-v4.0, Qwen3 |
| Speech-to-Text | Groq Whisper-large-v3 |
| Translation | NLLB-200 (facebook/nllb-200-distilled-600M via @xenova/transformers) |
| LLM | Qwen3-32B via Groq |
| RAG | LangChain + LlamaIndex + Qdrant Vector DB |
| Agent | LangChain Agent + FastMCP |
| Email | Resend API |
| PDF/CSV | FPDF (with Unicode support) |
| Runtime | Python FastAPI + Uvicorn |

## Supported Languages

| Input Language | Script | Output |
|---------------|--------|--------|
| Cantonese | yue_Hant | → Malay (zsm_Latn) |
| Javanese | jav_Latn | → Malay (zsm_Latn) |
| Malay | zsm_Latn | Native |
| English | eng_Latn | Supported |

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

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with your keys:

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Whisper STT + Qwen3 LLM |
| `COHERE_API_KEY` | Multimodal vision embeddings |
| `QDRANT_URL` | Vector DB endpoint |
| `QDRANT_API_KEY` | Vector DB auth |
| `TELEGRAM_BOT_TOKEN` | Telegram bridge |
| `AGENTMAIL_API_KEY` | MCP-based agent mail |
| `AGENT_BACKEND` | Runtime backend (`langchain`, `llamaindex`, `hybrid`) |
| `LANGCHAIN_MODEL` | LLM model (default: `groq:qwen/qwen3-32b`) |
| `TRANSLATION_ENABLED` | Enable NLLB translation (`true`/`false`) |
| `TRANSLATION_NLLB_MODEL` | NLLB model ID |

Do not commit `.env`.

## Install Dependencies

### 1) Node dependencies

```bash
npm install
```

### 2) Python dependencies

Create virtual environment, then install:

```bash
python -m venv ../.venv
../.venv/bin/python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv ..\.venv
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run The Application

Use two terminals.

### Terminal A: Start Python bridge

```bash
python -m uvicorn app.main:app --app-dir python_bridge --host 0.0.0.0 --port 8000 --reload
```

On Windows PowerShell:

```powershell
Set-Location "C:\path\to\DualComm"
& "C:/path/to/.venv/Scripts/python.exe" -m uvicorn app.main:app --app-dir python_bridge --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected: `{"status":"ok"}`

### Terminal B: Start Node bridge

```bash
npm run dev
```

Expected startup output includes:

- Agent mode and runtime URL
- WhatsApp bridge registered
- Telegram bridge registered (if enabled)
- WhatsApp QR output for linking device

## How It Works

1. **User sends a message** (text, image, audio, or PDF) via WhatsApp or Telegram.
2. **The Bridge** normalizes the payload and stages media files.
3. **Ingestion** processes multimodal inputs — Cohere/Qwen3 Vision for images, Groq Whisper-large-v3 for audio transcription.
4. **Translation** converts dialect input (Cantonese, Javanese) to Malay via NLLB-200.
5. **The Vault** retrieves relevant legal context from Qdrant using LangChain + LlamaIndex hybrid RAG.
6. **Qwen3 LLM** reasons over the translated input + retrieved context.
7. **Execution** generates formal outputs — PDF complaint letters, CSV case reports, and emails sent to government departments (JTK, JKM, KKM, JPN) via Resend API.

## RAG Pipeline

DualComm uses a **hybrid retrieval** architecture — combining LangChain and LlamaIndex in a single pipeline for higher recall and accuracy.

**What's in the knowledge base:**
- Malaysian labor laws and worker protection policies
- Government department mandates (JTK, JKM, KKM, JPN)
- Complaint filing procedures and legal precedents

**Why hybrid RAG:**
- **LangChain** handles structured retrieval with chain-of-thought reasoning
- **LlamaIndex** provides document-level indexing and semantic chunking
- Both query **Qdrant Vector DB** (cloud-hosted) in parallel — best result wins

**Multimodal retrieval:**
- Text, images, and PDFs all pass through the same vector search pipeline
- Images are embedded via **Cohere embed-v4.0** multimodal embeddings — no OCR-only fallback
- PDFs are extracted with PyMuPDF and chunked for semantic search

This means a worker can send a **photo of a payslip** or a **voice note in Cantonese**, and the system retrieves the relevant legal context to build their case automatically.

## Benchmarks

We evaluated every model in the pipeline against real datasets — not just plugged in and hoped for the best.

### Speech-to-Text (STT)

Evaluated on FLEURS test sets, 50 samples per dataset.

| Language | Model | WER | BLEU | BERT F1 |
|----------|-------|-----|------|---------|
| **Cantonese** (yue_hant_hk) | Groq Whisper-large-v3 | **0.1449** | **74.63** | **0.9329** |
| **Cantonese** (yue_hant_hk) | simonl0909-large-v2 | 0.1975 | 63.20 | 0.9069 |
| **Javanese** (jv_id) | Wav2Vec2-jv-id-su | **0.5005** | **24.16** | **0.8446** |
| **Javanese** (jv_id) | Groq Whisper-large-v3 | 0.7889 | 8.97 | 0.7526 |

> Groq Whisper wins on Cantonese but underperforms on Javanese — it tends to output Indonesian instead of authentic Javanese. We selected the best model per language accordingly.

### Text-to-Text Translation (TTT)

Evaluated on FLORES+ dataset, 10,000 samples. Model: NLLB-200-distilled-600M.

| Language Pair | BLEU | COMET (wmt22-da) |
|--------------|------|-------------------|
| Cantonese → Malay | 10.70 | **0.8452** |
| Javanese → Malay | 15.35 | **0.8262** |
| Malay → Cantonese (NLLB) | 13.37 | 0.7782 |
| Malay → Cantonese (Qwen 2.5 LLM) | 0.21 | 0.6627 |

> NLLB-200 significantly outperforms general-purpose LLMs on low-resource dialect translation. COMET scores > 0.82 indicate strong human-judged quality.

## Roadmap

We currently support **Cantonese**, **Javanese**, **Malay**, and **English**. We are actively working towards expanding language support to cover more Southeast Asian migrant worker communities — including **Burmese**, **Vietnamese**, **Tagalog**, and **Bangla** — to broaden DualComm's reach across Malaysia's diverse workforce.

