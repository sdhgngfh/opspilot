# OpsPilot 项目路线图与验收状态

本文档是项目的执行入口，用于区分“已经验证”“本地待执行”和“必须依赖真实环境”
三类工作。项目介绍仍以 `README.md` 为准，技术评审路线以 `docs/DEMO_GUIDE.md` 为准。

## 目标

OpsPilot 作为企业 Agentic RAG 参考实现，交付标准不是功能数量，而是：

1. 评审者能在 10 分钟内理解问题、架构、关键取舍和工程边界。
2. 本地无需外部 API Key 即可复现核心 RAG、Agent 工作流和人工审批链路。
3. 每项能力都有代码、测试或报告证据，不把未执行的生产能力描述为已经验证。
4. 密钥、企业 Token、真实业务数据和个人信息不进入 Git、报告或演示画面。

## P0：本地可开发、可验证、可演示

- [x] 从 v0.11.0 交付包恢复正式 Git 工作区。
- [x] 建立 `AGENTS.md` 与 `PROJECT_MEMORY.md`，统一后续 AI 协作规则。
- [x] 固定本地推荐 Python 主版本为 3.12，与主要 CI 验证环境一致。
- [x] 按锁文件安装开发和演示依赖。
- [x] 通过 Ruff、pytest 和 Python 构建。
- [x] 运行统一验收并保留 `reports/ACCEPTANCE.md`。
- [x] 启动本地 API，验证存活、就绪、配置和一次 LangGraph 问答。
- [x] 启动 Streamlit，确认首页可访问且 API 连接状态正常。

完成标准：以上项目全部完成；PostgreSQL 等未配置项必须显示为 `skipped` 或
`partial`，不能表述为生产验收通过。

## P1：公开交付可信度

- [x] 关联公开远程仓库，并补充可审阅的增量提交历史。
- [x] 在远程 CI 留存质量、PostgreSQL、恢复演练和 Kubernetes 回滚证据
  （[GitHub Actions #30199877047](https://github.com/sdhgngfh/opspilot-rag/actions/runs/30199877047)）。
- [x] 使用 PostgreSQL 17/pgvector 执行集成测试与迁移状态检查。
- [x] 使用隔离数据库完成备份恢复演练。
- [x] 准备工程能力概览、架构图和 3 分钟项目导览。
- [x] 录制 3–5 分钟演示视频或准备关键流程截图。
- [x] 对 README 中的指标、版本和验收结果执行发布前一致性检查。
- [x] 构建本地生产镜像，并验证 PostgreSQL 17 备份工具可用。
- [x] 清理 FastAPI/Starlette 测试客户端兼容性警告，并保留对应回归测试。

完成标准：仓库链接可访问、CI 状态可核验、每一项工程声明都能指向代码或证据。

## P2：工程深度

- [x] 扩大人工标注评测集，按问题类型、权限角色和难例分层统计。
- [x] 增加 Prompt Injection、恶意文档和跨租户访问的安全测试。
- [ ] 对真实模型记录质量、P50/P95 延迟、Token 用量和单请求成本。
  - [x] 实现严格的 Token、缓存/推理用量、延迟和价格快照成本采集链路。
  - [ ] 在授权 API Key 环境完成 36 条全量实测并保存脱敏证据。
- [x] 对查询改写、混合召回、重排和证据阈值做消融实验。
- [ ] 补充长时间稳定性、并发容量和模型/数据库故障降级证据。

完成标准：能用数据解释模型和工程取舍，而不是只展示框架或功能列表。

## 标准执行顺序

```bash
uv sync --locked --extra dev --extra demo
uv run ruff check .
uv run pytest
uv build
uv run python scripts/acceptance.py
```

本地演示：

```bash
uv run python scripts/ingest.py
uv run uvicorn app.api:app --reload
uv run streamlit run frontend/streamlit_app.py
```

## 变更验收规则

- 检索、阈值、切分或提示词变化：必须重跑基础、图级和访问权限评测。
- 鉴权、ACL、工单或持久化变化：必须补充越权、审批屏障和幂等测试。
- 数据库迁移变化：必须保持 expand-only，并完成漂移检查和隔离恢复演练。
- 部署配置变化：必须通过 Kubernetes 静态门禁；对外声称可发布前还需真实集群证据。
- UI 变化：至少覆盖断连降级、问答成功路径和一次人工演示检查。
- 新增外部服务：默认关闭，提供无密钥本地回退，并记录延迟、成本和数据边界。
