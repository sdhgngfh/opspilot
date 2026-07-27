from __future__ import annotations

import re
import time
from collections.abc import Sequence
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.config import Settings
from app.index import RetrievalHit

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n+")
_TERM_PATTERN = re.compile(r"[a-zA-Z0-9_-]+|[\u3400-\u9fff]")


class AnswerGenerator(Protocol):
    def generate(self, question: str, hits: Sequence[RetrievalHit]) -> str: ...


class ModelUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)


class GeneratedAnswer(BaseModel):
    answer: str
    model_latency_ms: float = Field(ge=0)
    usage: ModelUsage | None


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    return 0


def extract_model_usage(response: object) -> ModelUsage | None:
    usage_metadata = getattr(response, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        input_tokens = _integer(usage_metadata.get("input_tokens"))
        output_tokens = _integer(usage_metadata.get("output_tokens"))
        total_tokens = _integer(usage_metadata.get("total_tokens"))
        input_details = usage_metadata.get("input_token_details", {})
        output_details = usage_metadata.get("output_token_details", {})
        if not isinstance(input_details, dict):
            input_details = {}
        if not isinstance(output_details, dict):
            output_details = {}
        return ModelUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens or input_tokens + output_tokens,
            cached_input_tokens=_integer(
                input_details.get("cache_read")
                or input_details.get("cached_tokens")
            ),
            reasoning_tokens=_integer(output_details.get("reasoning")),
        )

    response_metadata = getattr(response, "response_metadata", None)
    if not isinstance(response_metadata, dict):
        return None
    token_usage = response_metadata.get("token_usage")
    if not isinstance(token_usage, dict):
        return None
    prompt_details = token_usage.get("prompt_tokens_details", {})
    completion_details = token_usage.get("completion_tokens_details", {})
    if not isinstance(prompt_details, dict):
        prompt_details = {}
    if not isinstance(completion_details, dict):
        completion_details = {}
    input_tokens = _integer(token_usage.get("prompt_tokens"))
    output_tokens = _integer(token_usage.get("completion_tokens"))
    total_tokens = _integer(token_usage.get("total_tokens"))
    return ModelUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens or input_tokens + output_tokens,
        cached_input_tokens=_integer(prompt_details.get("cached_tokens")),
        reasoning_tokens=_integer(completion_details.get("reasoning_tokens")),
    )


class LocalExtractiveGenerator:
    """Deterministic generator used for no-key demos and evaluation."""

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {term.lower() for term in _TERM_PATTERN.findall(text)}

    def generate(self, question: str, hits: Sequence[RetrievalHit]) -> str:
        question_terms = self._terms(question)
        candidates: list[tuple[float, int, str]] = []
        for rank, hit in enumerate(hits, start=1):
            for sentence in _SENTENCE_SPLIT.split(hit.document.page_content):
                cleaned = sentence.strip().lstrip("#").strip()
                if len(cleaned) < 8:
                    continue
                overlap = len(question_terms & self._terms(cleaned))
                score = overlap + hit.score + (1 / rank)
                candidates.append((score, rank, cleaned))
        candidates.sort(key=lambda item: item[0], reverse=True)

        selected: list[tuple[int, str]] = []
        seen: set[str] = set()
        top_source_candidates = [
            candidate for candidate in candidates if candidate[1] == 1
        ][:2]
        ordered_candidates = top_source_candidates + [
            candidate for candidate in candidates if candidate not in top_source_candidates
        ]
        for _, rank, sentence in ordered_candidates:
            normalized = re.sub(r"\s+", "", sentence)
            if normalized in seen:
                continue
            selected.append((rank, sentence))
            seen.add(normalized)
            if len(selected) == 3:
                break
        if not selected:
            return "知识库中存在相关资料，但本地生成器未提取到可用句子。"
        return "\n".join(f"{sentence} [{rank}]" for rank, sentence in selected)


class OpenAIAnswerGenerator:
    def __init__(self, settings: Settings) -> None:
        from langchain_openai import ChatOpenAI

        self.model = ChatOpenAI(
            model=settings.chat_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0,
            max_retries=2,
        )

    @staticmethod
    def _messages(
        question: str,
        hits: Sequence[RetrievalHit],
    ) -> list[SystemMessage | HumanMessage]:
        evidence = [
            {
                "citation": rank,
                "source": str(hit.document.metadata["source"]),
                "page": hit.document.metadata.get("page", 1),
                "content": hit.document.page_content,
            }
            for rank, hit in enumerate(hits, start=1)
        ]
        return [
            SystemMessage(
                content=(
                    "你是企业知识库助手。只能依据给定证据回答，不得补充证据中没有的事实。"
                    "每个事实句末必须标注对应证据编号，如 [1]。"
                    "如果证据不足，请明确说无法从知识库确认。回答使用中文，先给结论，再给步骤。"
                )
            ),
            HumanMessage(
                content=f"用户问题: {question}\n知识证据: {evidence}"
            ),
        ]

    def generate_with_usage(
        self,
        question: str,
        hits: Sequence[RetrievalHit],
    ) -> GeneratedAnswer:
        started = time.perf_counter()
        response = self.model.invoke(self._messages(question, hits))
        return GeneratedAnswer(
            answer=str(response.text),
            model_latency_ms=round((time.perf_counter() - started) * 1000, 3),
            usage=extract_model_usage(response),
        )

    def generate(self, question: str, hits: Sequence[RetrievalHit]) -> str:
        return self.generate_with_usage(question, hits).answer


def build_generator(settings: Settings) -> AnswerGenerator:
    if settings.rag_mode == "local":
        return LocalExtractiveGenerator()
    return OpenAIAnswerGenerator(settings)
