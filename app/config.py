from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    rag_mode: Literal["local", "openai"] = "local"
    embedding_provider: Literal["local", "openai"] = "local"
    reranker_provider: Literal["local", "cross_encoder"] = "local"
    index_backend: Literal["local", "postgres"] = "local"
    persistence_backend: Literal["local", "postgres"] = "local"

    auth_enabled: bool = False
    auth_provider: Literal["local", "oidc"] = "local"
    tracing_enabled: bool = False
    knowledge_mutations_enabled: bool = True

    openai_api_key: str | None = None
    openai_base_url: str | None = None
    chat_model: str = "gpt-5-mini"
    embedding_model: str = "text-embedding-3-small"

    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "opspilot-rag"

    knowledge_dir: Path = PROJECT_ROOT / "data" / "knowledge"
    index_path: Path = PROJECT_ROOT / "data" / "index" / "vector_store.json"
    access_policy_path: Path = PROJECT_ROOT / "data" / "security" / "document_access.json"
    evaluation_dataset: Path = PROJECT_ROOT / "data" / "evaluation" / "dataset.jsonl"
    graph_evaluation_dataset: Path = PROJECT_ROOT / "data" / "evaluation" / "graph_dataset.jsonl"
    checkpoint_path: Path = PROJECT_ROOT / "data" / "state" / "checkpoints.sqlite"

    cross_encoder_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    cross_encoder_device: str = "cpu"
    cross_encoder_batch_size: int = Field(default=8, ge=1, le=128)
    cross_encoder_weight: float = Field(default=0.80, ge=0.0, le=1.0)

    retrieval_strategy: Literal["vector", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    top_k: int = Field(default=4, ge=1, le=20)
    candidate_k: int = Field(default=12, ge=2, le=100)
    min_relevance_score: float = Field(default=0.18, ge=-1.0, le=1.0)
    min_bm25_score: float = Field(default=0.8, ge=0.0, le=1.0)
    min_lexical_coverage: float = Field(default=0.12, ge=0.0, le=1.0)
    vector_weight: float = Field(default=0.55, ge=0.0, le=1.0)
    bm25_weight: float = Field(default=0.45, ge=0.0, le=1.0)
    rrf_k: int = Field(default=60, ge=1, le=1000)
    chunk_size: int = Field(default=600, ge=100, le=4000)
    chunk_overlap: int = Field(default=100, ge=0, le=1000)
    max_rewrites: int = Field(default=1, ge=0, le=5)
    conversation_history_limit: int = Field(default=8, ge=1, le=50)

    @model_validator(mode="after")
    def validate_provider_credentials(self) -> Settings:
        if self.rag_mode == "openai" and not self.openai_api_key:
            raise ValueError("RAG_MODE=openai 时必须设置 OPENAI_API_KEY")
        if self.embedding_provider == "openai" and not self.openai_api_key:
            raise ValueError("EMBEDDING_PROVIDER=openai 时必须设置 OPENAI_API_KEY")
        if self.langsmith_tracing and not self.langsmith_api_key:
            raise ValueError("LANGSMITH_TRACING=true 时必须设置 LANGSMITH_API_KEY")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP 必须小于 CHUNK_SIZE")
        if self.candidate_k < self.top_k:
            raise ValueError("CANDIDATE_K 不能小于 TOP_K")
        if abs(self.vector_weight + self.bm25_weight - 1.0) > 1e-6:
            raise ValueError("VECTOR_WEIGHT 与 BM25_WEIGHT 之和必须为 1")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
