from __future__ import annotations

from app.graph import RAGGraphWorkflow
from app.service import REFUSAL, RAGService


def test_graph_answers_with_auditable_path(workflow: RAGGraphWorkflow) -> None:
    response = workflow.ask(
        question="如何让销售人员只能查看本部门销售订单？",
        thread_id="known-question",
    )

    assert response.grounded is True
    assert response.rewrite_count == 0
    assert response.attempts[0].sufficient is True
    assert response.citations[0].source == "u9c_permissions.md"
    assert response.execution_path == [
        "prepare_query",
        "retrieve",
        "grade_evidence",
        "generate_answer",
        "finalize",
    ]


def test_graph_rewrites_then_refuses_unknown_question(
    workflow: RAGGraphWorkflow,
) -> None:
    response = workflow.ask(
        question="公司食堂今天的午餐菜单是什么？",
        thread_id="unknown-question",
    )

    assert response.grounded is False
    assert response.answer == REFUSAL
    assert response.rewrite_count == workflow.settings.max_rewrites
    assert len(response.attempts) == workflow.settings.max_rewrites + 1
    assert all(not attempt.sufficient for attempt in response.attempts)
    assert (
        response.execution_path.count("rewrite_query")
        == workflow.settings.max_rewrites
    )
    assert response.execution_path[-2:] == ["fallback", "finalize"]


def test_same_thread_contextualizes_follow_up(workflow: RAGGraphWorkflow) -> None:
    workflow.ask(
        question="销售订单审核失败应该检查什么？",
        thread_id="conversation",
    )
    follow_up = workflow.ask(
        question="这个问题怎么处理？",
        thread_id="conversation",
    )
    thread = workflow.get_thread("conversation")

    assert "销售订单审核失败应该检查什么" in follow_up.retrieval_query
    assert follow_up.grounded is True
    assert thread is not None
    assert len(thread.history) == 2
    assert thread.history[-1].question == "这个问题怎么处理？"


def test_sqlite_checkpoint_survives_workflow_recreation(
    service: RAGService,
    workflow: RAGGraphWorkflow,
) -> None:
    workflow.ask(
        question="AUTH-403-DATA 表示什么？",
        thread_id="persistent-thread",
    )

    recreated = RAGGraphWorkflow(service)
    thread = recreated.get_thread("persistent-thread")

    assert thread is not None
    assert len(thread.history) == 1
    assert thread.history[0].grounded is True
