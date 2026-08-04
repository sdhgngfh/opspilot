from __future__ import annotations

import re
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import Settings

_CONTEXT_REFERENCE = re.compile(
    r"(这个|那个|它|该问题|上述|上面|刚才|上一条|这种情况|怎么办|怎么处理)"
)

_DOMAIN_EXPANSIONS = {
    "权限": "数据权限 部门权限 数据范围 角色权限",
    "看不到": "查询不到 数据权限 组织范围",
    "看不了": "查询不到 数据权限 组织范围",
    "只能看": "仅查看 本部门 数据权限",
    "审核": "审核失败 单据状态 必填字段 审批流",
    "批不了": "销售订单 审核失败 单据状态 必填字段 审批流",
    "登录": "登录失败 账号状态 密码 锁定",
    "进不去": "登录失败 账号状态 密码 锁定",
    "库存": "现存量 可用量 仓库 库位",
    "备份": "数据库备份 恢复演练 RPO RTO",
    "接口": "集成接口 请求 响应 错误码",
    "错误码": "故障码 原因 处理步骤",
    "403 data": "AUTH-403-DATA 数据权限错误 角色数据范围",
}


class QueryRewriter(Protocol):
    def contextualize(self, question: str, history: list[dict[str, object]]) -> str: ...

    def rewrite(
        self,
        *,
        original_question: str,
        current_query: str,
        history: list[dict[str, object]],
        attempt: int,
        evidence_reason: str,
    ) -> str: ...


class LocalQueryRewriter:
    """Deterministic contextualization and domain expansion for local demos."""

    @staticmethod
    def contextualize(question: str, history: list[dict[str, object]]) -> str:
        cleaned = " ".join(question.split())
        if not history or not _CONTEXT_REFERENCE.search(cleaned):
            return cleaned
        previous = history[-1]
        previous_question = str(previous.get("question", "")).strip()
        if not previous_question:
            return cleaned
        return f"{previous_question}；追问：{cleaned}"

    @staticmethod
    def rewrite(
        *,
        original_question: str,
        current_query: str,
        history: list[dict[str, object]],
        attempt: int,
        evidence_reason: str,
    ) -> str:
        del history, evidence_reason
        expansions = [
            expansion
            for marker, expansion in _DOMAIN_EXPANSIONS.items()
            if marker in original_question and expansion not in current_query
        ]
        if not expansions:
            return current_query
        selected = expansions[:attempt]
        return " ".join([current_query, *selected])


class OpenAIQueryRewriter:
    def __init__(self, settings: Settings) -> None:
        from langchain_openai import ChatOpenAI

        self.model = ChatOpenAI(
            model=settings.chat_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0,
            max_retries=2,
        )

    def contextualize(self, question: str, history: list[dict[str, object]]) -> str:
        if not history:
            return question
        recent = history[-3:]
        transcript = "\n".join(
            f"用户：{turn.get('question', '')}\n助手：{turn.get('answer', '')}"
            for turn in recent
        )
        response = self.model.invoke(
            [
                SystemMessage(
                    content=(
                        "把用户最新问题改写成脱离对话也能理解的中文检索查询。"
                        "只补全指代和必要实体，不回答问题，不添加未知事实。"
                    )
                ),
                HumanMessage(
                    content=f"最近对话:\n{transcript}\n最新问题: {question}"
                ),
            ]
        )
        return str(response.text).strip()

    def rewrite(
        self,
        *,
        original_question: str,
        current_query: str,
        history: list[dict[str, object]],
        attempt: int,
        evidence_reason: str,
    ) -> str:
        del history
        response = self.model.invoke(
            [
                SystemMessage(
                    content=(
                        "你是企业知识库检索查询改写器。上一轮证据不足。"
                        "保留原意和精确错误码，补充同义词、业务实体及排查意图。"
                        "只输出一条简洁查询，不回答问题。"
                    )
                ),
                HumanMessage(
                    content=(
                        f"原始问题: {original_question}\n"
                        f"当前查询: {current_query}\n"
                        f"重写尝试: {attempt}\n"
                        f"证据反馈: {evidence_reason}"
                    )
                ),
            ]
        )
        rewritten = str(response.text).strip()
        return rewritten or current_query


def build_query_rewriter(settings: Settings) -> QueryRewriter:
    if settings.rag_mode == "openai":
        return OpenAIQueryRewriter(settings)
    return LocalQueryRewriter()
