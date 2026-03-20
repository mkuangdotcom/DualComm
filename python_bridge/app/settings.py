from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AgentBackend = Literal["hybrid"]


class Settings(BaseSettings):
    """
    Runtime settings for the messaging Python bridge.

    Values are loaded from environment variables and may also be read from a
    local `.env` file when running the bridge directly.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(
        default="Messaging Python Agent Bridge",
        alias="APP_NAME",
    )
    environment: str = Field(
        default="development",
        alias="ENVIRONMENT",
    )
    host: str = Field(
        default="127.0.0.1",
        alias="HOST",
    )
    port: int = Field(
        default=8000,
        alias="PORT",
    )
    log_level: str = Field(
        default="info",
        alias="LOG_LEVEL",
    )

    agent_backend: AgentBackend = Field(
        default="hybrid",
        alias="AGENT_BACKEND",
    )

    agent_api_key: Optional[str] = Field(
        default=None,
        alias="PYTHON_AGENT_API_KEY",
    )
    require_api_key: bool = Field(
        default=False,
        alias="PYTHON_AGENT_REQUIRE_API_KEY",
    )

    langchain_model: Optional[str] = Field(
        default="groq:qwen/qwen3-32b",
        alias="LANGCHAIN_MODEL",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        alias="OPENAI_API_KEY",
    )
    groq_api_key: Optional[str] = Field(
        default=None,
        alias="GROQ_API_KEY",
    )
    default_system_prompt: str = Field(
        default=(
            "You are a helpful assistant connected to Telegram and WhatsApp. "
            "Be concise, clear, and safe."
        ),
        alias="DEFAULT_SYSTEM_PROMPT",
    )
    langchain_timeout_seconds: float = Field(
        default=25.0,
        alias="LANGCHAIN_TIMEOUT_SECONDS",
    )
    llamaindex_model: Optional[str] = Field(
        default=None,
        alias="LLAMAINDEX_MODEL",
    )
    llamaindex_system_prompt: Optional[str] = Field(
        default=None,
        alias="LLAMAINDEX_SYSTEM_PROMPT",
    )
    llamaindex_timeout_seconds: float = Field(
        default=25.0,
        alias="LLAMAINDEX_TIMEOUT_SECONDS",
    )
    llamaindex_top_k: int = Field(
        default=3,
        alias="LLAMAINDEX_TOP_K",
    )
    llamaindex_score_threshold: float = Field(
        default=0.3,
        alias="LLAMAINDEX_SCORE_THRESHOLD",
    )
    llamaindex_category: Optional[str] = Field(
        default=None,
        alias="LLAMAINDEX_CATEGORY",
    )
    llamaindex_docs_dir: str = Field(
        default="./docs/rag/malay",
        alias="LLAMAINDEX_DOCS_DIR",
    )
    hybrid_rag_language: str = Field(
        default="Malay",
        alias="HYBRID_RAG_LANGUAGE",
    )
    hybrid_rag_top_k: int = Field(
        default=3,
        alias="HYBRID_RAG_TOP_K",
    )
    hybrid_rag_score_threshold: Optional[float] = Field(
        default=None,
        alias="HYBRID_RAG_SCORE_THRESHOLD",
    )
    hybrid_rag_category: Optional[str] = Field(
        default=None,
        alias="HYBRID_RAG_CATEGORY",
    )

    def is_api_key_required(self) -> bool:
        return self.require_api_key

    def validate_api_key(self, provided_api_key: Optional[str]) -> bool:
        """
        Validate an inbound API key.

        Behavior:
        - if API key enforcement is disabled, always return True
        - if enforcement is enabled, require both a configured key and a match
        """
        if not self.require_api_key:
            return True

        if not self.agent_api_key:
            return False

        return provided_api_key == self.agent_api_key

    def is_hybrid_backend(self) -> bool:
        return self.agent_backend == "hybrid"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
