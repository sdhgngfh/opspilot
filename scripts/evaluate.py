from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.evaluation import evaluate, load_dataset, save_summary
from app.service import RAGService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 OpsPilot RAG 离线评测")
    parser.add_argument("--dataset", type=Path, help="JSONL 评测集路径")
    parser.add_argument("--output", type=Path, help="保存完整 JSON 报告")
    parser.add_argument("-k", type=int, default=None, help="Top-K")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    service = RAGService(settings)
    service.ensure_ready()
    cases = load_dataset(args.dataset or settings.evaluation_dataset)
    summary = evaluate(service, cases, k=args.k or settings.top_k)
    if args.output:
        save_summary(summary, args.output)
    headline = summary.model_dump(exclude={"results"})
    print(json.dumps(headline, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

