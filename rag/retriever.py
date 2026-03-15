"""
retriever.py
Queries Qdrant for relevant document chunks given a text query.
Used by the LlamaIndex runtime to provide RAG context.

Usage:
    from rag.retriever import retrieve
    results = retrieve("bagaimana memohon bantuan kewangan?", top_k=5)
"""

import os
from typing import Optional

import cohere
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, models

load_dotenv()

COLLECTION_NAME = "dualcomm_kb"
EMBEDDING_MODEL = "embed-v4.0"


def _get_clients():
    qdrant = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
    )
    co = cohere.Client(api_key=os.environ["COHERE_API_KEY"])
    return qdrant, co


def retrieve(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
    score_threshold: float = 0.3,
) -> dict:
    """
    Embed the query and search Qdrant for the most relevant chunks.

    Args:
        query: The user query text (expected in Malay after translation).
        top_k: Number of results to return.
        category: Optional category filter (e.g. "healthcare", "labor_migrant").
        score_threshold: Minimum similarity score to include.

    Returns:
        {
            "status": "ok" | "no_match" | "error",
            "chunks": [{"text": ..., "source": ..., "category": ..., "score": ...}, ...],
            "error": None | str
        }
    """
    if not query or not query.strip():
        return {"status": "no_match", "chunks": [], "error": None}

    try:
        qdrant, co = _get_clients()

        response = co.embed(
            texts=[query],
            model=EMBEDDING_MODEL,
            input_type="search_query",
            embedding_types=["float"],
        )
        query_vector = response.embeddings.float[0]

        search_filter = None
        if category:
            search_filter = Filter(
                must=[FieldCondition(key="category", match=MatchValue(value=category))]
            )

        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            query_filter=search_filter,
            score_threshold=score_threshold,
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
        return {"status": "error", "chunks": [], "error": str(e)}
