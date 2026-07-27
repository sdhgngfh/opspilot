# OpsPilot 关键流程截图

本页用于项目评审、功能介绍和无法现场启动服务时的离线演示。截图来自本地
`local` 模式，不包含 API Key、数据库密码、企业 Token 或真实业务数据。

## 1. 可演示首页

API 已连接，侧栏明确展示本地索引、混合检索、本地重排和持久化模式。

![OpsPilot 首页](screenshots/01-home.jpg)

## 2. Agentic RAG 问答与执行轨迹

回答包含来源引用；展开的轨迹展示证据分、检索次数和
`prepare_query → retrieve → grade_evidence → generate_answer → finalize`
执行路径。

![RAG 回答与执行轨迹](screenshots/02-rag-answer-trace.jpg)

## 3. 写操作前的人工审批屏障

自然语言请求先生成结构化工单草稿，状态停留在 `awaiting_approval`，此时尚未调用
`submit_ticket`。

![工单等待人工审批](screenshots/03-ticket-awaiting-approval.jpg)

## 4. 批准后的工具调用与审计证据

人工批准后状态变为 `submitted`，并可展开查看待执行工具参数、审批动作和审计记录。

![工单提交与审计证据](screenshots/04-ticket-submitted-audit.jpg)

## 复现方式

```bash
uv sync --locked --extra dev --extra demo
uv run python scripts/ingest.py
uv run uvicorn app.api:app --reload
uv run streamlit run frontend/streamlit_app.py
```

打开 <http://127.0.0.1:8501> 后：

1. 在“知识问答”输入“为什么销售人员能看到其他部门的订单？”，展开 Agent 执行轨迹。
2. 在“工单审批”生成默认草稿，确认状态为 `awaiting_approval`。
3. 点击“批准并提交”，确认状态为 `submitted`，再展开工具调用与审计日志。
