"""
indexer.py
Parses all PDFs in the knowledge base, chunks the text,
embeds with Cohere embed-v4.0, and uploads to Qdrant.

Run once (or re-run to rebuild the index):
    cd dualcomm
    python -m rag.indexer
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import cohere
import fitz  # PyMuPDF
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

load_dotenv()

COLLECTION_NAME = "dualcomm_kb"
EMBEDDING_MODEL = "embed-v4.0"
EMBEDDING_DIM = 1536
CHUNK_SIZE = 500  # tokens (approx chars / 4)
CHUNK_OVERLAP = 100

KB_ROOT = Path(__file__).resolve().parent.parent / "knowledge_base"
RAW_DIR = KB_ROOT / "raw_pdfs"
META_FILE = KB_ROOT / "metadata" / "documents.json"


def get_clients():
    """Initialise Qdrant and Cohere clients from env vars."""
    qdrant = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
    )
    co = cohere.Client(api_key=os.environ["COHERE_API_KEY"])
    return qdrant, co


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a PDF using PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()
    return "\n".join(pages)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks by character count.
    Uses ~4 chars per token as a rough estimate.
    """
    char_limit = chunk_size * 4
    char_overlap = overlap * 4
    chunks = []
    start = 0

    while start < len(text):
        end = start + char_limit
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += char_limit - char_overlap

    return chunks


def load_metadata() -> dict:
    """Load documents.json and return a lookup by filename."""
    if not META_FILE.exists():
        return {}
    with open(META_FILE) as f:
        docs = json.load(f)
    return {d["filename"]: d for d in docs if d.get("downloaded")}


def embed_texts(co: cohere.Client, texts: list[str], input_type: str = "search_document") -> list[list[float]]:
    """Embed a batch of texts using Cohere embed-v4.0 with retry on rate limit."""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = co.embed(
                texts=texts,
                model=EMBEDDING_MODEL,
                input_type=input_type,
                embedding_types=["float"],
            )
            return response.embeddings.float
        except cohere.errors.TooManyRequestsError:
            wait = 30 * (attempt + 1)
            print(f"    Rate limited. Waiting {wait}s... (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
    raise RuntimeError("Rate limit retries exhausted")


def create_collection(qdrant: QdrantClient):
    """Create the Qdrant collection if it doesn't exist."""
    collections = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME in collections:
        print(f"Collection '{COLLECTION_NAME}' exists. Deleting and recreating.")
        qdrant.delete_collection(COLLECTION_NAME)

    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=EMBEDDING_DIM,
            distance=Distance.COSINE,
        ),
    )
    print(f"Created collection '{COLLECTION_NAME}'.")


def index_all():
    """Main indexing pipeline: parse PDFs, chunk, embed, upload."""
    qdrant, co = get_clients()
    metadata_lookup = load_metadata()

    create_collection(qdrant)

    pdf_files = sorted(RAW_DIR.rglob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {RAW_DIR}. Run download_docs.py first.")
        return

    print(f"Found {len(pdf_files)} PDFs to index.\n")

    all_points = []
    total_chunks = 0

    for pdf_path in pdf_files:
        filename = pdf_path.name
        meta = metadata_lookup.get(filename, {})

        print(f"Processing: {filename}")

        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            print(f"  Skipped (no extractable text)")
            continue

        chunks = chunk_text(text)
        print(f"  Extracted {len(chunks)} chunks")

        # Embed in small batches with throttling for trial key (100k tokens/min)
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            vectors = embed_texts(co, batch)
            time.sleep(5)

            for j, (chunk, vector) in enumerate(zip(batch, vectors)):
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "text": chunk,
                        "source_file": filename,
                        "category": meta.get("category", pdf_path.parent.name),
                        "title": meta.get("title", filename),
                        "language": meta.get("language", "unknown"),
                        "source_org": meta.get("source_org", "unknown"),
                        "chunk_index": i + j,
                    },
                )
                all_points.append(point)

        total_chunks += len(chunks)

    # Upload to Qdrant in batches
    if all_points:
        upload_batch_size = 100
        for i in range(0, len(all_points), upload_batch_size):
            batch = all_points[i:i + upload_batch_size]
            qdrant.upsert(collection_name=COLLECTION_NAME, points=batch)

        print(f"\nDone. Indexed {total_chunks} chunks from {len(pdf_files)} PDFs into '{COLLECTION_NAME}'.")
    else:
        print("\nNo chunks to upload.")


if __name__ == "__main__":
    index_all()
