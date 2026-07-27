from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.evaluation import evaluate, load_dataset
from app.service import RAGService

STRATEGIES = ("vector", "hybrid", "hybrid_rerank")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对比向量、混合与重排检索")
    parser.add_argument("--dataset", type=Path, help="JSONL 评测集路径")
    parser.add_argument("--output", type=Path, help="保存完整 JSON 对比报告")
    parser.add_argument("-k", type=int, default=None, help="Top-K")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_settings = get_settings()
    cases = load_dataset(args.dataset or base_settings.evaluation_dataset)
    k = args.k or base_settings.top_k
    reports: dict[str, object] = {}
    for strategy in STRATEGIES:
        settings = base_settings.model_copy(update={"retrieval_strategy": strategy})
        service = RAGService(settings)
        service.ensure_ready()
        reports[strategy] = evaluate(service, cases, k=k).model_dump()

    headline_fields = (
        "hit_rate_at_k",
        "recall_at_k",
        "mrr",
        "answer_keyword_recall",
        "abstention_accuracy",
        "average_latency_ms",
        "p95_latency_ms",
    )
    comparison = {
        strategy: {
            field: report[field]
            for field in headline_fields
        }
        for strategy, report in reports.items()
    }
    output = {
        "cases": len(cases),
        "k": k,
        "comparison": comparison,
        "reports": reports,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
