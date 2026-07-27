from __future__ import annotations

import argparse
import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from app.config import get_settings
from app.evaluation import load_dataset
from app.graph import RAGGraphWorkflow
from app.graph_evaluation import evaluate_graph, save_graph_summary
from app.service import RAGService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对比基础 RAG 与 LangGraph RAG")
    parser.add_argument("--dataset", type=Path, help="JSONL 图级评测集")
    parser.add_argument("--output", type=Path, help="保存完整 JSON 报告")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    service = RAGService(settings)
    service.ensure_ready()
    workflow = RAGGraphWorkflow(
        service,
        checkpointer=InMemorySaver(),
    )
    cases = load_dataset(args.dataset or settings.graph_evaluation_dataset)
    summary = evaluate_graph(service, workflow, cases)
    if args.output:
        save_graph_summary(summary, args.output)
    print(
        json.dumps(
            summary.model_dump(exclude={"results"}),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
