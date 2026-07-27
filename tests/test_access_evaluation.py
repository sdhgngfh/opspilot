from __future__ import annotations

import pytest

from app.access_evaluation import evaluate_access, load_access_dataset
from app.config import PROJECT_ROOT
from app.service import RAGService


def test_access_evaluation_detects_no_protected_source_leakage(
    service: RAGService,
) -> None:
    summary = evaluate_access(
        service,
        PROJECT_ROOT / "data" / "evaluation" / "access_dataset.jsonl",
    )

    assert summary.cases == 12
    assert summary.access_decision_accuracy == 1.0
    assert summary.unauthorized_source_leakage_rate == 0.0
    assert summary.filter_integrity_rate == 1.0
    role_slices = summary.breakdowns["role"]
    assert {item.value for item in role_slices} == {"ops", "sales", "support"}
    assert all(item.cases == 4 for item in role_slices)
    assert all(item.access_decision_accuracy == 1.0 for item in role_slices)
    assert all(item.unauthorized_source_leakage_rate == 0.0 for item in role_slices)
    hard_slice = next(
        item for item in summary.breakdowns["difficulty"] if item.value == "hard"
    )
    assert hard_slice.cases >= 4
    assert hard_slice.filter_integrity_rate == 1.0


def test_access_dataset_rejects_duplicate_case_ids(tmp_path) -> None:
    dataset = tmp_path / "duplicates.jsonl"
    row = (
        '{"id":"duplicate","username":"demo","roles":["sales"],'
        '"departments":["sales"],"question":"订单怎么排查？",'
        '"question_type":"order_troubleshooting","difficulty":"easy",'
        '"protected_source":"orders.md","should_access":true}\n'
    )
    dataset.write_text(row + row, encoding="utf-8")

    with pytest.raises(ValueError, match="重复 id"):
        load_access_dataset(dataset)
