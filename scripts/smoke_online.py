from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from app.config import PROJECT_ROOT, get_settings
from app.graph import RAGGraphWorkflow
from app.service import RAGService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DeepSeek/OpenAI 兼容接口冒烟验证")
    parser.add_argument(
        "--dataset",
        type=Path,
        help="评测集 JSONL 路径，默认取基础评测集前 N 条",
    )
    parser.add_argument("--limit", type=int, default=3, help="最多运行的问题数")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports" / "online_smoke.json",
        help="报告输出路径",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    if settings.rag_mode != "openai":
        raise SystemExit("请先在 .env 中设置 RAG_MODE=openai")
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY 未配置")

    service = RAGService(settings)
    service.ensure_ready()
    workflow = RAGGraphWorkflow(service, checkpointer=InMemorySaver())

    dataset = args.dataset or settings.evaluation_dataset
    cases: list[dict[str, object]] = []
    with dataset.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
            if len(cases) >= args.limit:
                break
    if not cases:
        raise SystemExit(f"评测集为空: {dataset}")

    results: list[dict[str, object]] = []
    started = time.perf_counter()
    for case in cases:
        case_id = str(case["id"])
        question = str(case["question"])
        response = workflow.ask(
            question=question,
            thread_id=f"smoke-{case_id}",
        )
        results.append(
            {
                "id": case_id,
                "question": question,
                "answer": response.answer,
                "grounded": response.grounded,
                "rewrite_count": response.rewrite_count,
                "evidence_score": response.evidence_score,
                "citations": [
                    {"source": citation.source, "title": citation.title}
                    for citation in response.citations
                ],
                "latency_ms": response.latency_ms,
            }
        )

    report = {
        "provider": settings.openai_base_url or "openai",
        "model": settings.chat_model,
        "cases": len(results),
        "total_elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
