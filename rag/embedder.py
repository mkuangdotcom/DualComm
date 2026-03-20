"""
embedder.py
Handles user-sent images and PDFs.
Extracts text (or embeds images directly with Cohere embed-v4.0),
then queries the knowledge base via the retriever.

Usage:
    from rag.embedder import process_user_image, process_user_pdf
    result = process_user_image("/path/to/photo.jpg", top_k=5)
    result = process_user_pdf("/path/to/file.pdf", top_k=5)
"""

import base64
import os
from pathlib import Path
from typing import Optional

import cohere
import fitz  # PyMuPDF
from dotenv import load_dotenv

from rag.retriever import retrieve

load_dotenv()

EMBEDDING_MODEL = "embed-v4.0"


def _get_cohere():
    return cohere.Client(api_key=os.environ["COHERE_API_KEY"])


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a user-submitted PDF."""
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()
    return "\n".join(pages)


def process_user_pdf(
    pdf_path: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> dict:
    """
    Extract text from a user-sent PDF and search the knowledge base.

    Returns same format as retriever.retrieve().
    """
    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        return {"status": "no_match", "chunks": [], "error": "Could not extract text from PDF"}

    return retrieve(query=text[:2000], top_k=top_k, category=category)


def process_user_image(
    image_path: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> dict:
    """
    Embed a user-sent image using Cohere embed-v4.0 multimodal
    and search the knowledge base.

    Cohere embed-v4.0 accepts images directly as base64.
    Falls back to OCR via PyMuPDF if image embedding fails.
    """
    try:
        co = _get_cohere()

        image_bytes = Path(image_path).read_bytes()
        raw_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        # Cohere embed-v4.0 requires a data URI, not raw base64
        suffix = Path(image_path).suffix.lower().lstrip(".")
        mime = "jpeg" if suffix in ("jpg", "jpeg") else suffix  # png, gif, webp, etc.
        image_b64 = f"data:image/{mime};base64,{raw_b64}"

        # Cohere embed-v4.0 multimodal: embed the image directly
        response = co.embed(
            images=[image_b64],
            model=EMBEDDING_MODEL,
            input_type="image",
            embedding_types=["float"],
        )
        image_vector = response.embeddings.float[0]

        # Search Qdrant with the image vector
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant = QdrantClient(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ["QDRANT_API_KEY"],
        )

        search_filter = None
        if category:
            search_filter = Filter(
                must=[FieldCondition(key="category", match=MatchValue(value=category))]
            )

        results = qdrant.query_points(
            collection_name="dualcomm_kb",
            query=image_vector,
            limit=top_k,
            query_filter=search_filter,
            score_threshold=0.3,
        )

        points = results.points
        if not points:
            return {"status": "no_match", "chunks": [], "error": None}

        chunks = []
        for hit in points:
            chunks.append({
                "text": hit.payload.get("text", ""),
                "source": hit.payload.get("title", hit.payload.get("source_file", "")),
                "category": hit.payload.get("category", ""),
                "language": hit.payload.get("language", ""),
                "score": round(hit.score, 4),
            })

        return {"status": "ok", "chunks": chunks, "error": None}

    except Exception as e:
        # Fallback: try OCR with PyMuPDF (works for scanned docs)
        try:
            doc = fitz.open(image_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            if text.strip():
                return retrieve(query=text[:2000], top_k=top_k, category=category)
        except Exception:
            pass

        return {"status": "error", "chunks": [], "error": str(e)}
