# OpsPilot 项目状态与路线图

本文档记录项目当前状态和后续计划，所有勾选项均可在当前仓库复现。

## P0：本地可开发、可验证、可演示（已完成）

- [x] 建立 `AGENTS.md` 操作规则。
- [x] 固定本地推荐 Python 主版本为 3.12。
- [x] 生成 `uv.lock`，按锁文件安装开发和演示依赖。
- [x] 通过 `uv run ruff check .`。
- [x] 通过 `uv run pytest`。
- [x] 生成三份评测报告：`reports/evaluation.json`、
  `reports/graph_evaluation.json`、`reports/retrieval_comparison.json`。
- [x] 启动本地 API，验证存活、就绪、配置和一次 LangGraph 问答。
- [x] 启动 Streamlit，确认首页可访问且 API 连接状态正常。

## P1：后续工作（未实现）

- [ ] 双人独立标注评测集并统计一致性。
- [ ] 使用真实 Embedding 与在线生成模型评测质量、延迟、Token 和成本。
- [ ] 鉴权与文档级 ACL。
- [ ] 工单工具与人工审批流程。
- [ ] PostgreSQL/pgvector 持久化与迁移。
- [ ] 审计、限流、Prometheus 与 OTel 可观测性。
- [ ] 远程 CI 与发布验收。

## 标准执行顺序

```bash
uv sync --locked --extra dev --extra demo
uv run ruff check .
uv run pytest
uv run python scripts/ingest.py
uv run python scripts/evaluate.py --output reports/evaluation.json
uv run python scripts/evaluate_graph.py --output reports/graph_evaluation.json
uv run python scripts/benchmark_retrieval.py --output reports/retrieval_comparison.json
```

本地演示：

```bash
uv run python scripts/ingest.py
uv run uvicorn app.api:app --reload
uv run streamlit run frontend/streamlit_app.py
```

## 变更验收规则

- 检索、阈值、切分或提示词变化：必须重跑基础与图级评测。
- UI 变化：至少覆盖断连降级、问答成功路径和一次人工演示检查。
- 新增外部服务：默认关闭，提供无密钥本地回退，并记录延迟、成本和数据边界。
