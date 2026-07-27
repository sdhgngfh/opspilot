from __future__ import annotations

import threading
import time
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.graph.rewriting import QueryRewriter, build_query_rewriter
from app.graph.state import (
    RAGGraphState,
    deserialize_hit,
    serialize_hit,
)
from app.models import (
    Citation,
    ConversationTurn,
    GraphAskResponse,
    RetrievalAttempt,
    ThreadStateResponse,
)
from app.persistence import build_checkpointer
from app.service import REFUSAL, RAGService


class RAGGraphWorkflow:
    """Stateful Agentic RAG workflow with evidence grading and bounded retries."""

    def __init__(
        self,
        service: RAGService,
        *,
        checkpointer: BaseCheckpointSaver | None = None,
        rewriter: QueryRewriter | None = None,
    ) -> None:
        self.service = service
        self.settings = service.settings
        self.rewriter = rewriter or build_query_rewriter(self.settings)
        self._checkpointer_resource: object | None = None
        self._lock = threading.RLock()

        if checkpointer is None:
            checkpointer, self._checkpointer_resource = build_checkpointer(
                local_path=self.settings.checkpoint_path,
            )
        self.checkpointer = checkpointer
        self.graph = self._build_graph()

    @staticmethod
    def _path(state: RAGGraphState, node: str) -> list[str]:
        return [*state.get("execution_path", []), node]

    def _prepare_query(self, state: RAGGraphState) -> dict[str, object]:
        question = " ".join(state["question"].split())
        history = state.get("history", [])
        retrieval_query = self.rewriter.contextualize(question, history)
        return {
            "original_question": question,
            "retrieval_query": retrieval_query,
            "top_k": state.get("top_k", self.settings.top_k),
            "max_rewrites": state.get("max_rewrites", self.settings.max_rewrites),
            "rewrite_count": 0,
            "raw_hits": [],
            "selected_hits": [],
            "evidence_score": 0.0,
            "evidence_reason": "",
            "evidence_sufficient": False,
            "answer": "",
            "grounded": False,
            "citations": [],
            "execution_path": ["prepare_query"],
            "attempts": [],
        }

    def _retrieve(self, state: RAGGraphState) -> dict[str, object]:
        hits = self.service.retrieve(
            state["retrieval_query"],
            top_k=state["top_k"],
        )
        return {
            "raw_hits": [serialize_hit(hit) for hit in hits],
            "execution_path": self._path(state, "retrieve"),
        }

    def _grade_evidence(self, state: RAGGraphState) -> dict[str, object]:
        raw_hits = [deserialize_hit(hit) for hit in state.get("raw_hits", [])]
        selected_hits = self.service.select_evidence(raw_hits)
        evidence_score = self.service.evidence_score(raw_hits)
        reason = self.service.evidence_reason(raw_hits, selected_hits)
        sufficient = bool(selected_hits)
        top_source = (
            str(raw_hits[0].document.metadata.get("source"))
            if raw_hits
            else None
        )
        attempt = {
            "attempt": state.get("rewrite_count", 0),
            "query": state["retrieval_query"],
            "top_source": top_source,
            "top_score": round(raw_hits[0].score, 6) if raw_hits else 0.0,
            "evidence_score": round(evidence_score, 6),
            "sufficient": sufficient,
            "reason": reason,
        }
        return {
            "selected_hits": [serialize_hit(hit) for hit in selected_hits],
            "evidence_score": evidence_score,
            "evidence_reason": reason,
            "evidence_sufficient": sufficient,
            "attempts": [*state.get("attempts", []), attempt],
            "execution_path": self._path(state, "grade_evidence"),
        }

    @staticmethod
    def _route_after_grade(
        state: RAGGraphState,
    ) -> Literal["generate_answer", "rewrite_query", "fallback"]:
        if state["evidence_sufficient"]:
            return "generate_answer"
        if state["rewrite_count"] < state["max_rewrites"]:
            return "rewrite_query"
        return "fallback"

    def _rewrite_query(self, state: RAGGraphState) -> dict[str, object]:
        attempt = state["rewrite_count"] + 1
        rewritten = self.rewriter.rewrite(
            original_question=state["original_question"],
            current_query=state["retrieval_query"],
            history=state.get("history", []),
            attempt=attempt,
            evidence_reason=state["evidence_reason"],
        )
        return {
            "retrieval_query": rewritten,
            "rewrite_count": attempt,
            "execution_path": self._path(state, "rewrite_query"),
        }

    def _generate_answer(self, state: RAGGraphState) -> dict[str, object]:
        selected_hits = [
            deserialize_hit(hit) for hit in state.get("selected_hits", [])
        ]
        answer = self.service.generator.generate(
            state["original_question"],
            selected_hits,
        )
        citations = [
            citation.model_dump()
            for citation in self.service.build_citations(selected_hits)
        ]
        return {
            "answer": answer,
            "grounded": True,
            "citations": citations,
            "execution_path": self._path(state, "generate_answer"),
        }

    def _fallback(self, state: RAGGraphState) -> dict[str, object]:
        return {
            "answer": REFUSAL,
            "grounded": False,
            "citations": [],
            "execution_path": self._path(state, "fallback"),
        }

    def _finalize(self, state: RAGGraphState) -> dict[str, object]:
        turn = {
            "question": state["original_question"],
            "retrieval_query": state["retrieval_query"],
            "answer": state["answer"],
            "grounded": state["grounded"],
        }
        history = [*state.get("history", []), turn]
        history = history[-self.settings.conversation_history_limit :]
        return {
            "history": history,
            "execution_path": self._path(state, "finalize"),
        }

    def _build_graph(self):
        builder = StateGraph(RAGGraphState)
        builder.add_node("prepare_query", self._prepare_query)
        builder.add_node("retrieve", self._retrieve)
        builder.add_node("grade_evidence", self._grade_evidence)
        builder.add_node("rewrite_query", self._rewrite_query)
        builder.add_node("generate_answer", self._generate_answer)
        builder.add_node("fallback", self._fallback)
        builder.add_node("finalize", self._finalize)

        builder.add_edge(START, "prepare_query")
        builder.add_edge("prepare_query", "retrieve")
        builder.add_edge("retrieve", "grade_evidence")
        builder.add_conditional_edges(
            "grade_evidence",
            self._route_after_grade,
            {
                "generate_answer": "generate_answer",
                "rewrite_query": "rewrite_query",
                "fallback": "fallback",
            },
        )
        builder.add_edge("rewrite_query", "retrieve")
        builder.add_edge("generate_answer", "finalize")
        builder.add_edge("fallback", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile(checkpointer=self.checkpointer)

    @staticmethod
    def _config(thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": f"rag:{thread_id}"}}

    def ask(
        self,
        *,
        question: str,
        thread_id: str,
        top_k: int | None = None,
        max_rewrites: int | None = None,
    ) -> GraphAskResponse:
        started = time.perf_counter()
        graph_input: RAGGraphState = {
            "question": question,
            "top_k": top_k or self.settings.top_k,
            "max_rewrites": (
                self.settings.max_rewrites
                if max_rewrites is None
                else max_rewrites
            ),
        }
        with self._lock:
            result = self.graph.invoke(graph_input, self._config(thread_id))
        return GraphAskResponse(
            question=result["original_question"],
            answer=result["answer"],
            grounded=result["grounded"],
            citations=[
                Citation.model_validate(citation)
                for citation in result.get("citations", [])
            ],
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            thread_id=thread_id,
            retrieval_query=result["retrieval_query"],
            rewrite_count=result["rewrite_count"],
            evidence_score=round(result["evidence_score"], 6),
            evidence_reason=result["evidence_reason"],
            execution_path=result["execution_path"],
            attempts=[
                RetrievalAttempt.model_validate(attempt)
                for attempt in result.get("attempts", [])
            ],
        )

    def get_thread(self, thread_id: str) -> ThreadStateResponse | None:
        with self._lock:
            snapshot = self.graph.get_state(self._config(thread_id))
        values = snapshot.values
        if not values:
            return None
        return ThreadStateResponse(
            thread_id=thread_id,
            history=[
                ConversationTurn.model_validate(turn)
                for turn in values.get("history", [])
            ],
            last_question=values.get("original_question"),
            last_retrieval_query=values.get("retrieval_query"),
            last_grounded=values.get("grounded"),
            checkpoint_created_at=snapshot.created_at,
        )
