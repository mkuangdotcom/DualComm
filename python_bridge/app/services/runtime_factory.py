from __future__ import annotations

from functools import lru_cache

from app.services.base import AgentRuntime
from app.services.hybrid_runtime import HybridRuntime
from app.services.langchain_runtime import LangChainRuntime
from app.services.llamaindex_runtime import LlamaIndexRuntime
from app.services.mock_runtime import MockRuntime
from app.settings import get_settings


def create_runtime_backend() -> AgentRuntime:
    """
    Create the active runtime backend based on environment configuration.

    Supported values for `AGENT_BACKEND`:
    - `mock`
    - `langchain`
    - `llamaindex`
    - `hybrid`

    Unknown values fall back to the mock runtime so the bridge remains usable.
    """
    settings = get_settings()
    backend = settings.agent_backend.strip().lower()

    if backend == "langchain":
        return LangChainRuntime(
            model_name=settings.langchain_model,
            system_prompt=settings.default_system_prompt,
            timeout_seconds=settings.langchain_timeout_seconds,
        )

    if backend == "llamaindex":
        return LlamaIndexRuntime(
            model_name=settings.llamaindex_model,
        )

    if backend == "hybrid":
        langchain_runtime = LangChainRuntime(
            model_name=settings.langchain_model,
            system_prompt=settings.default_system_prompt,
            timeout_seconds=settings.langchain_timeout_seconds,
        )
        llamaindex_runtime = LlamaIndexRuntime(
            model_name=settings.llamaindex_model,
        )
        return HybridRuntime(
            agent_runtime=langchain_runtime,
            rag_runtime=llamaindex_runtime,
            target_language=settings.hybrid_rag_language,
            rag_top_k=settings.hybrid_rag_top_k,
        )

    return MockRuntime()


@lru_cache(maxsize=1)
def get_runtime_backend() -> AgentRuntime:
    """
    Return a cached runtime backend instance.

    A cached instance is sufficient for the current bridge design and avoids
    rebuilding runtime adapters on every request.
    """
    return create_runtime_backend()
