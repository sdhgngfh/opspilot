# OpsPilot 本地验收记录

本文件记录 2026-08-04 在本地 `E:\workspace\opspilot` 完成的验收，所有命令均可从
当前仓库复现。报告数字来自受控合成数据，不代表生产效果。

## 环境

- Python 3.12.13（uv 管理）
- 依赖锁文件：`uv.lock`
- 本地 local 模式，无 API Key

## 检查项

| 检查项 | 结果 |
|---|---:|
| `uv sync --locked --extra dev --extra demo` | 通过 |
| `uv run ruff check .` | 通过 |
| `uv run pytest` | 通过（30 个测试） |
| `uv run python scripts/ingest.py` | 通过（8 份文档，9 个分块） |
| `scripts/evaluate.py` | 通过，报告 `reports/evaluation.json` |
| `scripts/evaluate_graph.py` | 通过，报告 `reports/graph_evaluation.json` |
| `scripts/benchmark_retrieval.py` | 通过，报告 `reports/retrieval_comparison.json` |
| `GET /health` | 200 |
| `GET /health/live` | 200 |
| `GET /health/ready` | 200，knowledge_index ok |
| `GET /v1/system/info` | 200，local 模式字段正确 |
| `POST /v1/ask`（中文问题） | 200，grounded=true 且带引用 |
| `POST /v1/graph/ask` | 200，执行到 finalize |
| `GET /v1/graph/threads/{id}` | 200，会话历史与状态正确 |
| 纯标点输入 `？？` | 拒答 grounded=false，不抛 500 |
| Streamlit 首页 | 200，标题正常 |

## 关键指标（本次运行）

- 混合检索 + 重排：`Hit Rate@4=1.000`、`MRR=0.984`、答案关键词召回 `0.796`、
  拒答准确率 `1.000`。
- LangGraph：决策准确率 `0.700 -> 1.000`，来源命中 `0.571 -> 1.000`，
  答案关键词召回 `0.429 -> 0.643`。
- hard 难度切片答案关键词召回 `0.633`，为下一步改进方向。

## 未覆盖 / 后续工作

- 真实 Embedding 与在线生成模型评测未执行。
- 鉴权、ACL、工单审批、PostgreSQL、可观测性未实现。
