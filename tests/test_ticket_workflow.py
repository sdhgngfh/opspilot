from __future__ import annotations

import pytest

from app.config import Settings
from app.graph import TicketApprovalWorkflow
from app.graph.ticket_workflow import TicketWorkflowConflictError
from app.models import (
    StartTicketWorkflowRequest,
    TicketDraftChanges,
    TicketReviewRequest,
)
from app.tools import TicketStore


def _start(
    workflow: TicketApprovalWorkflow,
    *,
    thread_id: str,
) -> None:
    workflow.start(
        StartTicketWorkflowRequest(
            request_text="生产环境销售人员能看到其他部门订单，请修复数据权限。",
            requester="alice",
            thread_id=thread_id,
        )
    )


def test_ticket_pauses_before_side_effect(
    ticket_workflow: TicketApprovalWorkflow,
    ticket_store: TicketStore,
) -> None:
    response = ticket_workflow.start(
        StartTicketWorkflowRequest(
            request_text="生产环境销售人员能看到其他部门订单，请修复数据权限。",
            requester="alice",
            thread_id="approval-barrier",
        )
    )

    assert response.status == "awaiting_approval"
    assert response.approval_request is not None
    assert response.approval_request.tool_call.name == "submit_ticket"
    assert response.execution_path == ["draft_ticket"]
    assert ticket_store.count() == 0


def test_approve_submits_exactly_one_ticket(
    ticket_workflow: TicketApprovalWorkflow,
    ticket_store: TicketStore,
) -> None:
    _start(ticket_workflow, thread_id="approve")
    response = ticket_workflow.review(
        "approve",
        TicketReviewRequest(action="approve", reviewer="ops-lead"),
    )

    assert response.status == "submitted"
    assert response.ticket is not None
    assert response.ticket.reviewer == "ops-lead"
    assert response.ticket.review_action == "approve"
    assert response.approval_request is None
    assert response.execution_path == [
        "draft_ticket",
        "human_review",
        "submit_ticket",
        "finalize",
    ]
    assert ticket_store.count() == 1
    assert ticket_store.get(response.ticket.ticket_id) == response.ticket

    with pytest.raises(TicketWorkflowConflictError):
        ticket_workflow.review(
            "approve",
            TicketReviewRequest(action="approve", reviewer="ops-lead"),
        )
    assert ticket_store.count() == 1


def test_edit_changes_tool_arguments_before_submit(
    ticket_workflow: TicketApprovalWorkflow,
) -> None:
    _start(ticket_workflow, thread_id="edit")
    response = ticket_workflow.review(
        "edit",
        TicketReviewRequest(
            action="edit",
            reviewer="ops-lead",
            changes=TicketDraftChanges(
                priority="critical",
                title="修复跨部门销售订单越权访问",
            ),
        ),
    )

    assert response.status == "submitted"
    assert response.review_action == "edit"
    assert response.ticket is not None
    assert response.ticket.draft.priority == "critical"
    assert response.ticket.draft.title == "修复跨部门销售订单越权访问"
    assert response.tool_call.arguments["draft"]["priority"] == "critical"


def test_reject_never_calls_submission_tool(
    ticket_workflow: TicketApprovalWorkflow,
    ticket_store: TicketStore,
) -> None:
    _start(ticket_workflow, thread_id="reject")
    response = ticket_workflow.review(
        "reject",
        TicketReviewRequest(action="reject", reviewer="ops-lead"),
    )

    assert response.status == "rejected"
    assert response.ticket is None
    assert response.execution_path[-2:] == ["reject_ticket", "finalize"]
    assert ticket_store.get_by_workflow("reject") is None


def test_ticket_interrupt_survives_workflow_recreation(
    settings: Settings,
    ticket_store: TicketStore,
    ticket_workflow: TicketApprovalWorkflow,
) -> None:
    _start(ticket_workflow, thread_id="ticket-persistent")

    recreated = TicketApprovalWorkflow(settings, ticket_store)
    pending = recreated.get_state("ticket-persistent")
    assert pending is not None
    assert pending.approval_request is not None

    submitted = recreated.review(
        "ticket-persistent",
        TicketReviewRequest(action="approve", reviewer="ops-lead"),
    )
    assert submitted.status == "submitted"
    assert submitted.ticket is not None
