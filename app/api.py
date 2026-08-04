from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from app import __version__
from app.config import get_settings
from app.graph import RAGGraphWorkflow
from app.models import (
    AskRequest,
    AskResponse,
    GraphAskRequest,
    GraphAskResponse,
    IngestResponse,
    SystemInfoResponse,
    ThreadStateResponse,
)
from app.service import RAGService

app = FastAPI(
    title="OpsPilot RAG API",
    description="Agentic RAG 知识与运维助手",
    version=__version__,
)


@lru_cache(maxsize=1)
def get_service() -> RAGService:
    service = RAGService(get_settings())
    service.ensure_ready()
    return service


@lru_cache(maxsize=1)
def get_graph_workflow() -> RAGGraphWorkflow:
    return RAGGraphWorkflow(get_service())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def health_ready() -> dict[str, object]:
    try:
        service = get_service()
        service.ensure_ready()
    except Exception:
        return {
            "status": "not_ready",
            "components": {"knowledge_index": {"status": "error"}},
        }
    return {
        "status": "ready",
        "components": {"knowledge_index": {"status": "ok"}},
    }


@app.get("/v1/system/info", response_model=SystemInfoResponse)
def system_info() -> SystemInfoResponse:
    settings = get_settings()
    return SystemInfoResponse(
        version=__version__,
        rag_mode=settings.rag_mode,
        embedding_provider=settings.embedding_provider,
        retrieval_strategy=settings.retrieval_strategy,
        reranker_provider=settings.reranker_provider,
        index_backend=settings.index_backend,
        persistence_backend=settings.persistence_backend,
        auth_enabled=settings.auth_enabled,
        auth_provider=settings.auth_provider,
        tracing_enabled=settings.tracing_enabled,
    )


@app.post("/v1/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    service: Annotated[RAGService, Depends(get_service)],
) -> AskResponse:
    return service.ask(payload.question, payload.top_k)


@app.post("/v1/graph/ask", response_model=GraphAskResponse)
def graph_ask(
    payload: GraphAskRequest,
    workflow: Annotated[RAGGraphWorkflow, Depends(get_graph_workflow)],
) -> GraphAskResponse:
    return workflow.ask(
        question=payload.question,
        thread_id=payload.thread_id,
        top_k=payload.top_k,
        max_rewrites=payload.max_rewrites,
    )


@app.get("/v1/graph/threads/{thread_id}", response_model=ThreadStateResponse)
def graph_thread(
    thread_id: str,
    workflow: Annotated[RAGGraphWorkflow, Depends(get_graph_workflow)],
) -> ThreadStateResponse:
    state = workflow.get_thread(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return state.model_copy(update={"thread_id": thread_id})


@app.post("/v1/documents/reindex", response_model=IngestResponse)
def reindex(
    service: Annotated[RAGService, Depends(get_service)],
) -> IngestResponse:
    return service.reindex()
