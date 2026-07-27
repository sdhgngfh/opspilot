# OpsPilot — Agentic RAG

OpsPilot 是一个面向企业知识问答的 Agentic RAG 项目。它使用
Python、LangChain 和 LangGraph 实现混合检索、证据评分、查询改写、失败重试、来源引用、
无证据拒答、多轮上下文、Cross-Encoder 重排、LangSmith 追踪，
并通过 FastAPI 和 Streamlit 提供可演示产品。
v0.11.0 进一步加入 Streamlit
页面级自动化测试和统一发布验收证据，明确区分通过、失败与基础设施未配置的跳过项。

默认 `local` 模式不需要 API Key，结果可重复，适合本地开发、持续集成和离线回归评测；
切换配置后可以使用 OpenAI 或兼容接口完成真实 Embedding、查询改写和答案生成。

在线仓库：[github.com/sdhgngfh/opspilot-rag](https://github.com/sdhgngfh/opspilot-rag)

[![CI](https://github.com/sdhgngfh/opspilot-rag/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/sdhgngfh/opspilot-rag/actions/workflows/ci.yml)

快速了解完整链路可使用 [项目演示与技术评审指南](docs/DEMO_GUIDE.md)；各版本变更见
[CHANGELOG](CHANGELOG.md)。执行优先级、验收边界和后续工作见
[项目路线图与验收状态](docs/ROADMAP.md)，架构、指标和工程取舍见
[项目架构与工程能力概览](docs/PROJECT_OVERVIEW.md)；无法现场启动服务时可直接查看
[关键流程截图](docs/DEMO_SCREENSHOTS.md)。

## 已完成功能

### 基础 RAG

- Markdown、TXT、PDF 文档加载
- `RecursiveCharacterTextSplitter` 分块及稳定 `chunk_id`
- LangChain `InMemoryVectorStore` 向量检索与磁盘持久化
- 本地可重复 Hash Embedding，支持中文字符 n-gram
- 无外部分词服务的中英文 BM25 检索
- 向量与 BM25 双路召回、加权 RRF 融合
- 基于向量、BM25、词项覆盖率和 RRF 的可解释重排
- 可选 Sentence Transformers Cross-Encoder 二阶段语义重排
- 双信号证据门控、无证据拒答和结构化来源引用
- `vector`、`hybrid`、`hybrid_rerank` 三种策略对照评测

### LangGraph 工作流

- `StateGraph` 显式状态和条件边
- 多轮问题指代补全
- 本地确定性或大模型查询改写
- 检索证据评分及原因说明
- 最多 N 次有界重写与重新检索
- 直接回答、重试恢复、最终拒答三类路径
- 每轮完整执行路径和检索尝试记录
- 使用 `thread_id` 延续多轮会话
- SQLite/PostgreSQL Checkpointer 跨进程、跨实例持久化
- 基础 RAG 与 LangGraph RAG 的图级对照评测

### 工具调用与人工审批

- 将自然语言运维请求生成结构化工单草稿
- 使用 LangChain `StructuredTool` 封装持久化 `submit_ticket` 工具
- 在写操作前调用 LangGraph `interrupt()` 强制暂停
- 支持批准、修改后批准、拒绝三种决定
- `Command(resume=...)` 从 SQLite 或 PostgreSQL checkpoint 恢复执行
- 中断前零业务写入，拒绝路径不调用提交工具
- 使用 `workflow_id` 幂等写入，防止恢复或重试造成重复工单
- 返回待执行工具参数、执行路径和完整审计事件
- 工单工作流 API 与独立离线评测

### 工程能力

- FastAPI：基础问答、图工作流问答、工单审批、会话状态、上传、重建索引
- Streamlit：知识问答、引用证据、执行轨迹、工单审批和知识库管理
- JWT Bearer 登录、PBKDF2 密码哈希和短期访问令牌
- 企业 OIDC/JWKS 令牌校验与外部 subject 账号映射
- 用户角色、部门和 scope 三层授权
- 文档 ACL 在召回阶段过滤，未授权证据不会进入重排、生成或引用
- 相同 `thread_id` 按用户命名空间隔离
- Prompt Injection 不可信数据边界、污染文档过滤和跨身份工单碰撞防护
- 向量索引和业务状态均可在本地/PostgreSQL 间独立切换
- 用户、工单、RAG 会话和待审批中断可统一持久化到 PostgreSQL
- HTTP 审计日志、请求 ID、保留期清理和管理员查询接口
- 单机内存/多实例 PostgreSQL 原子固定窗口限流
- 带 SHA-256 漂移检测和 advisory lock 的事务迁移
- `pg_dump` 自定义格式备份、清单哈希校验和恢复目标确认
- 隔离数据库恢复演练及关键表行数核对
- 存活、就绪健康检查与生产发布门禁
- LangSmith：通过环境配置启用 LangChain/LangGraph 全链路追踪
- 低基数 Prometheus RED 指标与 RAG/审批业务指标
- 不记录问题正文、用户 ID 或 thread ID 的 OpenTelemetry OTLP/HTTP trace
- 99.5% 可用率、5 秒 P95 初始 SLO 与错误预算燃烧告警
- 可重复并发压测、OTLP exporter 冒烟和数据库依赖故障演练
- `/v1/system/info` 安全展示运行模式，不返回密钥
- 8 份易混淆演示文档
- 36 条基础检索、10 条图级、12 条权限和 3 条审批路径评测数据
- pytest、Ruff、GitHub Actions、PostgreSQL 集成和真实恢复演练
- Streamlit AppTest 页面状态、断连降级与问答成功路径
- 可复现统一验收、产物 SHA-256、敏感输出脱敏和机器可读证据
- Docker Compose 启动 pgvector、API 和 Streamlit
- Kubernetes 1.27+ Helm Chart 与外部 Secret 注入
- 迁移/索引 Helm Hook、零停机滚动策略和 `--atomic` 回滚
- API HPA、PDB、非 root/只读根文件系统与 NetworkPolicy

## 检索与重排架构

```mermaid
flowchart LR
    Q["用户问题"] --> V["向量召回"]
    Q --> B["BM25 召回"]
    V --> F["RRF 融合候选"]
    B --> F
    F --> C["Cross-Encoder 或本地重排"]
    C --> G["证据门控"]
```

默认本地重排保证离线环境和 CI 无需下载模型也能运行。启用 Cross-Encoder 后，
只对 `CANDIDATE_K` 个融合候选计算 query-document 成对分数，再与可解释本地分数融合；
它不会替代向量/BM25 召回，因此不会对整个知识库逐条运行模型。

## LangGraph 架构

```mermaid
flowchart TD
    S["START"] --> P["准备 / 上下文化"]
    P --> R["混合检索"]
    R --> G["证据评分"]
    G -->|充分| A["约束生成"]
    G -->|不足且可重试| W["查询改写"]
    W --> R
    G -->|重试耗尽| F["明确拒答"]
    A --> Z["记录会话"]
    F --> Z
    Z --> E["END"]
```

LangChain 负责 `Document`、文本切分、Embedding、VectorStore、消息和模型接口；
LangGraph 负责状态、条件路由、循环、checkpoint 和会话恢复。检索器与图编排解耦，
所以可以先独立验证检索质量，再判断查询改写和重试是否带来增益。

每次图调用都会返回类似下面的可审计信息：

```json
{
  "thread_id": "demo-001",
  "retrieval_query": "接口请求重复了怎么办？ 集成接口 请求 响应 错误码",
  "rewrite_count": 1,
  "evidence_score": 0.444958,
  "execution_path": [
    "prepare_query",
    "retrieve",
    "grade_evidence",
    "rewrite_query",
    "retrieve",
    "grade_evidence",
    "generate_answer",
    "finalize"
  ]
}
```

## 人工审批架构

```mermaid
flowchart TD
    S["运维请求"] --> D["生成工单草稿"]
    D --> I["interrupt 暂停"]
    I -->|批准| T["submit_ticket 工具"]
    I -->|修改后批准| T
    I -->|拒绝| X["取消提交"]
    T --> P["SQLite / PostgreSQL 工单库"]
```

`submit_ticket` 是有副作用的业务工具，只能出现在审批节点之后。图在
`interrupt()` 处保存状态，并把完整工具参数返回给调用者；恢复时使用相同
`thread_id` 和 `Command(resume=...)`。提交工具以 `workflow_id` 作为唯一幂等键，
即使恢复后发生重试，也只会得到同一张工单。

## 身份与知识权限架构

```mermaid
flowchart TD
    L["本地登录 / 企业 OIDC"] --> J["已验证身份"]
    J --> S["Scope 检查"]
    S --> A["角色 + 部门 ACL"]
    A --> R["授权候选召回"]
    R --> G["重排与生成"]
```

本地 JWT 只保存用户 ID；OIDC token 经 JWKS、issuer 和 audience 校验后，只用
`issuer|sub` 映射账号。两种模式都会在每次请求重新读取当前用户状态，因此禁用账号
或修改角色后，旧令牌不会继续携带过期授权。`knowledge:read` 决定能否检索，文档的
`allowed_roles` 与 `allowed_departments` 决定能检索哪些分块；两项必须同时匹配。
`knowledge:read:all` 只授予管理员。

本地索引会扩大候选池后在进入重排前过滤；pgvector 后端则把 ACL 条件直接放入
SQL `WHERE`，避免先从数据库取出未授权向量。上传文档时 ACL 与文档一起写入，
重建失败会一起回滚。访问策略位于 `data/security/document_access.json`，
其内容也参与索引指纹计算。

## 评测结果

### 基础检索对照

本地可重复模式、`Top-K=4`，在 8 份演示文档和 36 条人工整理的合成评测问题上：

| 策略 | Hit Rate@4 | MRR | 答案关键词召回 | 拒答准确率 |
|---|---:|---:|---:|---:|
| 仅向量 | 1.000 | 0.952 | 0.720 | 0.944 |
| 向量 + BM25 + RRF | 1.000 | 0.952 | 0.785 | 1.000 |
| 混合检索 + 重排 | 1.000 | 0.984 | 0.806 | 1.000 |

按难度分层后，hard 样本的 `MRR=0.950`、答案关键词召回为 `0.667`，
低于 easy 样本的 `1.000` 和 `0.926`。正确来源已召回，但复杂约束的答案要点组合
仍是下一步重点。完整问题类型、难度和角色切片见
[分层评测说明](docs/EVALUATION.md)。

### LangGraph 对照

在 10 条包含口语化弱查询、精确错误码和无答案问题的图级评测数据上：

| 指标 | 基础 RAG | LangGraph RAG |
|---|---:|---:|
| 回答/拒答决策准确率 | 0.700 | 1.000 |
| 期望来源命中率 | 0.571 | 1.000 |
| 答案关键词召回 | 0.429 | 0.643 |
| 平均延迟 | 1.98 ms | 6.77 ms |

图工作流的平均检索次数为 `1.6`，发生改写的样本占 `60%`；
在需要重试的可回答问题中，重试恢复率为 `1.0`。

### 消融实验

单变量消融验证了当前默认组合：

- BM25/RRF 相比仅向量使答案关键词召回提升 `0.065`，决策准确率提升 `0.056`；
- 本地重排使 MRR 再提升 `0.032`；
- 证据阈值 `0.12` 会放行全部 5 个越界问题，`0.24` 会误拒可回答问题，保留 `0.18`；
- 允许 1 次查询改写使图级决策准确率从 `0.700` 提升到 `1.000`；第 2 次没有质量增益，
  因此默认 `MAX_REWRITES=1`。

完整对照、失败样本和实验边界见 [消融实验报告](docs/ABLATION.md)。

这些结果来自小规模、受控的演示数据，且本地改写包含领域同义词规则，
只能说明当前工程链路和回归样本表现，不能外推为生产效果。真实项目还应引入双人独立
标注和线上反馈，并将规则改写与 LLM 改写、不同阈值和不同模型分别做消融实验。

### 工单审批工作流

在批准、修改、拒绝 3 条受控路径上：

| 指标 | 结果 |
|---|---:|
| 审批屏障通过率 | 1.000 |
| 决策执行准确率 | 1.000 |
| 修改参数准确率 | 1.000 |
| 提交幂等率 | 1.000 |

审批屏障要求工作流已经暂停并返回待审批参数，同时业务工单库仍为零新增。
该评测主要验证控制流和副作用边界，不评价大模型生成的工单文本质量。

### 知识权限评测

在销售、支持和运维三类身份的 12 条允许/拒绝路径上：

| 指标 | 结果 |
|---|---:|
| 访问决策准确率 | 1.000 |
| 未授权目标来源泄漏率 | 0.000 |
| 返回候选 ACL 完整率 | 1.000 |

三个角色切片的访问决策准确率均为 `1.000`，未授权来源泄漏率均为 `0.000`。
该数据集验证受保护来源是否按角色与部门出现，以及所有返回候选是否都能通过同一 ACL。
对抗性安全覆盖见 [Prompt Injection、恶意文档与跨身份测试](docs/SECURITY_TESTS.md)。
这些测试不替代渗透测试、数据库 RLS 或企业身份系统测试。

### 本地 SLO 容量验收

本地确定性模型、100 个有效基础 RAG 请求、并发 8：

| 指标 | 结果 |
|---|---:|
| 成功请求 | 100/100 |
| 可用率 | 1.000 |
| 吞吐 | 214.4 req/s |
| P50 | 33.6 ms |
| P95 | 52.3 ms |
| P99 | 56.0 ms |
| SLO 门禁 | 通过 |

完整结果位于 `reports/load_test.json`。该测试用于证明压测、指标和门禁链路可重复执行；
本地 Hash Embedding 与抽取式答案的吞吐不能外推到在线模型、Cross-Encoder 或生产数据库。

### v0.11.0 本地全量验收状态

以下结果来自 2026-07-26 的本地隔离环境；PostgreSQL 17/pgvector 运行在临时容器，
恢复目标为独立数据库。

| 项目 | 结果 |
|---|---:|
| 纯本地测试 | 101 通过 |
| PostgreSQL 集成测试 | 2/2 通过 |
| PostgreSQL 迁移 | 2/2 已应用，状态一致 |
| 隔离恢复演练 | 通过，9 张关键表行数一致 |
| 总覆盖率 | 86.5% |
| Streamlit 页面覆盖率 | 49.0% |
| PostgreSQL 索引适配器覆盖率 | 86.7% |
| PostgreSQL 用户/工单适配器覆盖率 | 94.4% |
| Ruff | 通过 |
| Kubernetes 静态门禁 | 11/11 通过 |
| 统一验收 | 10/10 通过，0 跳过 |
| Docker 镜像构建 | 通过 |

该结果证明仓库在当前隔离环境中的代码、评测、PostgreSQL 和恢复链路可复现；
它不等同于远程 CI、托管数据库、企业 OIDC 或真实 Kubernetes 集群的生产批准。

## 1. 本地运行与演示界面

需要 Python 3.11 或 3.12，并安装 [uv](https://docs.astral.sh/uv/)。

```bash
cd opspilot-rag
cp .env.example .env
uv sync --extra dev --extra demo
uv run python scripts/ingest.py
uv run uvicorn app.api:app --reload
```

另开一个终端启动界面：

```bash
uv run streamlit run frontend/streamlit_app.py
```

浏览器打开：

- 演示界面：<http://127.0.0.1:8501>
- Swagger：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>
- 存活检查：<http://127.0.0.1:8000/health/live>
- 就绪检查：<http://127.0.0.1:8000/health/ready>
- 运行配置：<http://127.0.0.1:8000/v1/system/info>
- Prometheus 指标：<http://127.0.0.1:8000/metrics>（需启用）

演示建议按“弱查询自动改写 → 查看证据和执行路径 → 创建工单 →
确认中断前未提交 → 修改优先级并批准”的顺序操作。

## 2. 调用基础 RAG

基础接口只执行一次检索，便于作为对照基线：

```bash
curl -X POST http://127.0.0.1:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"为什么用户还能看到其他部门的销售订单？"}'
```

## 3. 调用 LangGraph RAG

第一次提问：

```bash
curl -X POST http://127.0.0.1:8000/v1/graph/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question":"销售订单审核失败应该检查什么？",
    "thread_id":"opspilot-demo"
  }'
```

使用相同 `thread_id` 追问：

```bash
curl -X POST http://127.0.0.1:8000/v1/graph/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question":"这个问题怎么处理？",
    "thread_id":"opspilot-demo"
  }'
```

查询持久化会话状态：

```bash
curl http://127.0.0.1:8000/v1/graph/threads/opspilot-demo
```

`thread_id` 是 checkpoint 的会话游标。服务重启后重新使用相同 ID，本地模式从
`data/state/checkpoints.sqlite` 恢复；`PERSISTENCE_BACKEND=postgres` 时从
PostgreSQL 恢复。RAG 与工单线程分别使用 `rag:`、`ticket:` 内部前缀隔离。

## 4. 创建并审批工单

创建草稿，工作流会在提交前暂停：

```bash
curl -X POST http://127.0.0.1:8000/v1/tickets/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "request_text":"销售人员可以看到其他部门订单，请创建权限修复工单。",
    "requester":"alice",
    "thread_id":"ticket-demo"
  }'
```

批准提交：

```bash
curl -X POST http://127.0.0.1:8000/v1/tickets/workflows/ticket-demo/review \
  -H "Content-Type: application/json" \
  -d '{"action":"approve","reviewer":"ops-lead"}'
```

也可以在审批时修改草稿并视为批准修改后的工具参数：

```bash
curl -X POST http://127.0.0.1:8000/v1/tickets/workflows/ticket-edit/review \
  -H "Content-Type: application/json" \
  -d '{
    "action":"edit",
    "reviewer":"ops-lead",
    "changes":{"priority":"critical","title":"修复跨部门订单越权访问"}
  }'
```

拒绝时使用 `{"action":"reject","reviewer":"security-lead"}`，不会写入工单库。
可通过 `GET /v1/tickets/workflows/{thread_id}` 查询审批状态和审计轨迹，
通过 `GET /v1/tickets/{ticket_id}` 查询已提交工单。

## 5. 运行评测和测试

```bash
uv run python scripts/evaluate.py \
  --output reports/evaluation.json

uv run python scripts/benchmark_retrieval.py \
  --output reports/retrieval_comparison.json

uv run python scripts/evaluate_graph.py \
  --output reports/graph_evaluation.json

uv run python scripts/evaluate_tickets.py \
  --output reports/ticket_workflow_evaluation.json

uv run python scripts/evaluate_access.py \
  --output reports/access_evaluation.json

uv run python scripts/load_test.py \
  --scenario ask \
  --requests 100 \
  --concurrency 8 \
  --output reports/load_test.json \
  --require-slo

uv run python scripts/otel_smoke.py

uv run pytest
uv run ruff check .

# 一次执行本地可复验项，并记录基础设施跳过边界
uv run python scripts/acceptance.py
```

基础评测集位于 `data/evaluation/dataset.jsonl`，图级评测集位于
`data/evaluation/graph_dataset.jsonl`。每行格式：

```json
{
  "id": "perm-01",
  "question": "如何限制用户只能看本部门订单？",
  "answerable": true,
  "question_type": "policy",
  "difficulty": "easy",
  "expected_sources": ["u9c_permissions.md"],
  "answer_keywords": ["数据权限", "销售部门"]
}
```

基础评测指标：

- Hit Rate@K：Top-K 是否至少命中一个期望来源
- Recall@K：期望来源被召回的比例
- MRR：第一个正确来源排名的倒数均值
- Answer Keyword Recall：参考要点在回答中的覆盖率
- Abstention Accuracy：该回答时回答、无证据时拒答的准确率
- Breakdowns：按问题类型和难度重复计算同一组指标；访问评测额外按角色分层

图级评测额外统计：

- Decision Accuracy：回答或拒答的决策是否正确
- Rewrite Rate：进入查询改写路径的样本比例
- Retry Recovery Rate：需要改写的可回答问题中，被重试成功恢复的比例
- Average Attempts：每个问题平均执行多少次检索
- 图工作流相对基础 RAG 的质量和延迟变化

统一验收会生成：

- `reports/acceptance.json`：命令、状态、耗时、输出尾部和产物 SHA-256
- `reports/ACCEPTANCE.md`：适合人工审阅的验收摘要
- `reports/coverage.json`：逐文件覆盖率

没有设置 `TEST_DATABASE_URL` 或恢复数据库时，PostgreSQL 验收会明确标为
`skipped`，总状态为 `partial`，不会把未执行项目算作通过。生产发布环境使用：

```bash
uv run python scripts/acceptance.py --require-infrastructure
```

此时缺少真实 PostgreSQL/pgvector 或备份恢复环境会直接使验收失败。

审批评测额外检查：

- Approval Barrier：暂停时不得产生业务写入
- Decision Accuracy：批准、修改、拒绝是否进入正确路径
- Edit Accuracy：修改后的工具参数是否被实际提交
- Submission Idempotency：重复的副作用请求是否只生成一张工单

## 6. 配置

默认配置：

```dotenv
RAG_MODE=local
EMBEDDING_PROVIDER=local
RERANKER_PROVIDER=local
INDEX_BACKEND=local
PERSISTENCE_BACKEND=local
RETRIEVAL_STRATEGY=hybrid_rerank
TOP_K=4
CANDIDATE_K=12
MIN_RELEVANCE_SCORE=0.18
MIN_BM25_SCORE=0.80
MIN_LEXICAL_COVERAGE=0.12
VECTOR_WEIGHT=0.55
BM25_WEIGHT=0.45
RRF_K=60
MAX_REWRITES=1
CONVERSATION_HISTORY_LIMIT=8
CHECKPOINT_PATH=data/state/checkpoints.sqlite
TICKET_CHECKPOINT_PATH=data/state/ticket_checkpoints.sqlite
TICKET_STORE_PATH=data/state/tickets.sqlite
AUTH_ENABLED=false
AUTH_PROVIDER=local
AUTH_STORE_PATH=data/state/users.sqlite
ACCESS_POLICY_PATH=data/security/document_access.json
AUDIT_ENABLED=false
RATE_LIMIT_ENABLED=false
METRICS_ENABLED=false
OTEL_TRACING_ENABLED=false
SLO_AVAILABILITY_TARGET=0.995
SLO_P95_LATENCY_MS=5000
SLO_MIN_REQUESTS=20
```

- `vector`：仅使用向量相似度，作为实验基线。
- `hybrid`：向量和 BM25 分别召回，使用加权 RRF 融合。
- `hybrid_rerank`：在融合候选上计算可解释重排分数。
- `RERANKER_PROVIDER=local`：无需模型下载的确定性重排，适合测试与现场兜底。
- `RERANKER_PROVIDER=cross_encoder`：对融合候选执行真实成对语义重排。
- `MAX_REWRITES`：证据不足时最多改写与重试次数。
- `CONVERSATION_HISTORY_LIMIT`：每个 thread 保留的最近对话轮数。
- `CHECKPOINT_PATH`：LangGraph SQLite checkpoint 文件。
- `TICKET_CHECKPOINT_PATH`：工单审批中断与恢复的 checkpoint 文件。
- `TICKET_STORE_PATH`：已批准工单的业务数据文件。
- `INDEX_BACKEND=local`：本地可重复索引；`postgres`：pgvector 向量召回。
- `PERSISTENCE_BACKEND=local`：SQLite 用户/工单/checkpoint；`postgres`：统一 PostgreSQL。
- `AUTH_ENABLED`：是否强制登录。开启时必须配置至少 32 字符的随机密钥。
- `AUTH_PROVIDER`：`local` 使用本地密码和短期 JWT；`oidc` 校验企业 IdP token。
- `AUDIT_ENABLED`：记录请求 ID、操作者、路径、状态和延迟，不记录请求正文或令牌。
- `RATE_LIMIT_ENABLED`：启用固定窗口限流；PostgreSQL 模式可在多实例间共享计数。
- `ACCESS_POLICY_PATH`：文档角色、部门和密级映射。
- `METRICS_ENABLED`：启用 `/metrics`；标签只包含路由模板等有限维度。
- `OTEL_TRACING_ENABLED`：通过 OTLP/HTTP 输出请求、检索、生成和工作流 span。
- `SLO_*`：并发验收所用的最小样本数、可用率和成功请求 P95 门限。
- `KNOWLEDGE_MUTATIONS_ENABLED`：是否允许 API 进程直接上传或重建知识；
  多副本 Kubernetes 部署默认关闭，由受控索引 Job 管理。

审计事件只记录请求元数据，不保存正文、密码或 Bearer Token。拥有 `audit:read`
scope 的管理员可调用 `GET /v1/audit/events?limit=100`；定时执行
`uv run python scripts/purge_audit.py` 会按 `AUDIT_RETENTION_DAYS` 清理。

证据门控要求综合分达标，并且向量信号达标，或 BM25 与词项覆盖率同时达标。
这样可避免“午餐菜单”仅因一个“菜单”词命中“菜单权限”后直接作答。

## 7. 启用登录与知识权限

先生成密钥并写入 `.env`：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```dotenv
AUTH_ENABLED=true
AUTH_SECRET_KEY=替换为刚生成的随机值
```

创建初始用户。密码参数只用于本地初始化，不要写入仓库；正式环境应通过密钥管理系统
注入：

```bash
uv run python scripts/bootstrap_users.py \
  --admin-password '至少10位的临时密码' \
  --sales-password '销售演示账号密码' \
  --support-password '支持演示账号密码'
```

获取令牌：

```bash
curl -X POST http://127.0.0.1:8000/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=sales-demo&password=销售演示账号密码"
```

之后在业务请求中增加 `Authorization: Bearer <access_token>`。Streamlit 会在认证开启时
自动显示登录页。用户只能查询自己的会话；工单申请人和审批人由登录身份确定，
请求体中的同名字段不能用于冒充。

企业 OIDC/SSO 模式由 API 验证身份平台签发的 Access Token：

```dotenv
AUTH_ENABLED=true
AUTH_PROVIDER=oidc
OIDC_ISSUER=https://id.example.com
OIDC_AUDIENCE=opspilot-api
OIDC_JWKS_URL=https://id.example.com/.well-known/jwks.json
OIDC_ALGORITHMS=["RS256"]
```

用户表中的 `external_subject` 必须写成 `<issuer>|<sub>`。初始化时可传入：

```bash
uv run python scripts/bootstrap_users.py \
  --admin-password '仅作本地兜底的随机密码' \
  --admin-external-subject 'https://id.example.com|企业用户sub'
```

OIDC 模式下 `/v1/auth/token` 不提供密码登录；客户端直接携带企业 token。
API 验证签名、issuer、audience、过期时间和必需 claims 后，再从用户表实时加载
角色、部门和 scope。Streamlit 演示页支持粘贴企业 Access Token。

## 8. 使用 PostgreSQL/pgvector

安装生产依赖：

```bash
uv sync --extra dev --extra demo --extra production
```

配置：

```dotenv
INDEX_BACKEND=postgres
PERSISTENCE_BACKEND=postgres
DATABASE_URL=postgresql://opspilot:密码@127.0.0.1:5432/opspilot
PGVECTOR_COLLECTION=opspilot
EMBEDDING_DIMENSIONS=1536
```

先执行迁移/初始化：

```bash
uv run python scripts/migrate.py
uv run python scripts/migrate.py --status
```

迁移器按文件版本顺序执行 SQL，在同一事务中取得 advisory lock，避免多个副本并发执行；
`schema_migrations` 会记录文件名、SHA-256 和应用时间。已执行文件的内容或名称发生变化时，
状态会标记为 `drifted` 并拒绝继续。数据库账号在首次迁移时需要创建扩展和 DDL 的权限，
运行期应改用更小权限账号。`EMBEDDING_DIMENSIONS` 必须与 Embedding 模型输出一致。

pgvector 负责访问过滤后的向量召回，BM25 仍是进程内确定性索引。用户、工单、
RAG 会话、待审批中断、审计和限流均可共享 PostgreSQL。多实例部署仍需为 BM25
增加索引版本通知或共享关键词索引。

## 9. 备份、恢复演练与发布门禁

创建自定义格式备份。连接密码通过 PostgreSQL 环境变量传给客户端，不会出现在
`pg_dump` 命令参数或备份清单中：

```bash
uv run python scripts/backup_database.py \
  --output backups/opspilot.dump
```

脚本会同时生成 `opspilot.dump.manifest.json`，记录大小和 SHA-256。恢复前必须
显式输入目标数据库名；`--clean` 仅建议用于隔离恢复库：

```bash
uv run python scripts/restore_database.py backups/opspilot.dump \
  --confirm-database opspilot_recovery \
  --clean
```

完整恢复演练需要两个不同数据库：

```dotenv
DATABASE_URL=postgresql://opspilot:密码@127.0.0.1:5432/opspilot
RECOVERY_DATABASE_URL=postgresql://opspilot:恢复库密码@127.0.0.1:5433/opspilot_recovery
```

```bash
docker compose --profile recovery up -d postgres recovery-postgres
uv run python scripts/recovery_drill.py
```

演练会执行备份、哈希验证、隔离恢复，并比较用户、工单、知识分块、审计及
LangGraph checkpoint 等关键表的行数。部署前门禁：

```bash
uv run python scripts/release_gate.py \
  --production \
  --require-backup-tools \
  --require-observability
```

门禁要求 PostgreSQL 双后端、认证、审计、限流、迁移、知识索引、备份工具、
Prometheus 指标和 OpenTelemetry 均可用。
逻辑备份应再配合云盘/对象存储异地副本和 PostgreSQL PITR；一次成功的 `pg_dump`
不能替代持续备份策略。

## 10. Prometheus、OpenTelemetry 与 SLO

安装观测依赖并启用：

```bash
uv sync --extra dev --extra demo --extra observability
```

```dotenv
METRICS_ENABLED=true
OTEL_TRACING_ENABLED=true
OTEL_SERVICE_NAME=opspilot-rag
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318/v1/traces
OTEL_SAMPLE_RATIO=1.0
DEPLOYMENT_ENVIRONMENT=staging
```

`/metrics` 提供 HTTP 请求量、状态类别、延迟直方图、并发数、RAG 回答/拒答、
改写次数、审批决定、限流拒绝和就绪状态。路由使用 FastAPI 模板，例如
`/v1/graph/threads/{thread_id}`，不会把真实 ID、用户名或问题文本变成标签。

OpenTelemetry span 覆盖 HTTP、基础 RAG、LangGraph、检索、生成、索引重建和
审批工作流，只写后端类型、候选数量、是否有依据、改写次数等安全属性。它与
LangSmith 互补：OTel 面向平台级请求和依赖链路，LangSmith 面向 LLM/Agent 调试。

启动本地 Prometheus 与 Collector：

```bash
OTEL_TRACING_ENABLED=true \
docker compose --profile observability up --build
```

- Prometheus：<http://127.0.0.1:9090>
- OTLP/HTTP：`http://127.0.0.1:4318/v1/traces`
- 告警规则：`ops/alerts.yml`
- SLO 定义：`ops/SLO.md`

运行真实 API 并保留容量报告：

```bash
uv run python scripts/load_test.py \
  --scenario ask \
  --requests 100 \
  --concurrency 8 \
  --output reports/load_test.json \
  --require-slo
```

故障演练先验证正常状态，再停止 PostgreSQL 后验证服务仍存活但不再接流量：

```bash
uv run python scripts/fault_drill.py --expect ready
docker compose stop postgres
uv run python scripts/fault_drill.py --expect degraded
```

本项目的 5 秒 P95 是包含在线模型时的初始门限；本地确定性实现通常明显更快。
生产环境应按模型、请求类型和硬件分别设定目标，不能用本地数字代替容量规划。

## 11. Kubernetes/Helm 零停机发布

Chart 位于 `deploy/helm/opspilot-rag`，要求 Kubernetes 1.27+ 与 Helm 3。
密钥不写入 values；部署前必须由密钥管理系统创建一个现有 Secret，至少提供
`DATABASE_URL`，本地 JWT 模式还需 `AUTH_SECRET_KEY`。

先执行源文件门禁；装有 Helm 时同时运行 `lint` 与模板渲染：

```bash
uv run python scripts/kubernetes_gate.py --require-helm
```

部署示例：

```bash
helm upgrade --install opspilot deploy/helm/opspilot-rag \
  --namespace opspilot \
  --create-namespace \
  --values deploy/helm/opspilot-rag/values-staging.yaml \
  --atomic \
  --wait \
  --timeout 15m
```

迁移与索引 Job 会在安装/升级前运行，继续复用事务迁移、advisory lock 和 SHA-256
漂移检测。额外的 expand-only 门禁拒绝常见破坏性 SQL，使旧、新应用可在滚动窗口内
同时工作。API 默认两个副本，使用 `maxUnavailable=0`、`maxSurge=1`；Pod 通过
`/health/ready` 后才进入 Service，HPA 可在 2–8 个副本间扩缩，PDB 至少保留一个
可用实例。

由于当前 BM25 是进程内索引，多副本模式把 `KNOWLEDGE_MUTATIONS_ENABLED` 设为
`false`，在线上传与重建返回 503；知识文件随不可变镜像发布，由索引 Hook 一次性
写入 pgvector。完整安装、Secret、验收、NetworkPolicy 和回滚流程见
[`ops/KUBERNETES.md`](ops/KUBERNETES.md)。

## 12. 启用真实 Cross-Encoder

安装可选依赖：

```bash
uv sync --extra dev --extra demo --extra reranker
```

编辑 `.env`：

```dotenv
RERANKER_PROVIDER=cross_encoder
CROSS_ENCODER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
CROSS_ENCODER_DEVICE=cpu
CROSS_ENCODER_BATCH_SIZE=8
CROSS_ENCODER_WEIGHT=0.80
```

模型会在第一次检索时下载。默认模型支持包括中文在内的多语言检索场景；
CPU 可运行但延迟会显著高于本地规则重排。正式对照实验应分别记录 MRR、
Recall@K 和 P95 延迟，不能只比较单个问答效果。

## 13. 启用 LangSmith 追踪

编辑 `.env`：

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=你的LangSmith密钥
LANGSMITH_PROJECT=opspilot-rag
```

服务启动时会在任何 LangChain/LangGraph 工作执行前配置追踪。不开启时不需要密钥，
也不会发送 trace。`GET /v1/system/info` 只返回追踪是否开启和项目名，不暴露密钥。

建议技术评审时展示一次包含改写重试的 LangGraph trace，以及一次在 `interrupt()`
暂停、恢复后调用 `submit_ticket` 的 trace。

## 14. 切换真实生成与 Embedding 模型

编辑 `.env`：

```dotenv
RAG_MODE=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=
CHAT_MODEL=gpt-5-mini
EMBEDDING_MODEL=text-embedding-3-small
```

`RAG_MODE=openai` 会同时启用真实答案生成和 LLM 查询改写。
如果只想比较生成质量，可以保留 `EMBEDDING_PROVIDER=local`，从而固定检索变量。

若使用兼容 OpenAI Chat Completions 的服务，将 `OPENAI_BASE_URL` 改为服务的
`/v1` 地址，并使用该服务支持的模型名。Embedding 提供方改变后，索引清单会检测
签名变化并自动重建向量。

### 真实模型质量、延迟、Token 与成本

真实模型评测固定使用本地 Embedding，避免把检索变量与生成模型变量混在一起。
价格不写死在代码中，执行时必须提供带日期和来源的价格快照：

```bash
uv run python scripts/evaluate_online_model.py \
  --input-price <美元/百万输入Token> \
  --output-price <美元/百万输出Token> \
  --cached-input-price <美元/百万缓存输入Token> \
  --pricing-as-of <YYYY-MM-DD> \
  --pricing-source <价格来源> \
  --output reports/online_model_evaluation.json
```

报告包含问题类型/难度切片、端到端与模型 P50/P95、输入/输出/缓存/推理 Token，
以及总成本和单请求成本。模型不返回 Token 用量时命令会失败，不会用估算值补齐。
当前仓库没有提交 API Key，也没有把本地结果描述为线上模型结果；完整执行口径见
[真实模型评测](docs/ONLINE_MODEL_EVALUATION.md)。

## 15. 上传文档

```bash
curl -X POST \
  "http://127.0.0.1:8000/v1/documents/upload?allowed_roles=support&allowed_departments=it&classification=restricted" \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@你的手册.pdf"
```

支持 `.md`、`.txt`、`.pdf`，默认最大 15 MB。上传成功后自动重建索引。
同名覆盖需增加 `replace=true`。认证开启后此接口要求 `knowledge:write`。
新文档必须同时保存 ACL；未显式提供时采用上传者自身角色和部门，不会默认公开。

## 16. Docker

```bash
cp .env.example .env
docker compose up --build
```

该命令启动 PostgreSQL/pgvector、API 和 Streamlit。PostgreSQL 使用命名卷，
`data` 目录保存知识文档和本地兜底文件。Compose 默认使用 pgvector 索引和 PostgreSQL
业务状态后端，并开启审计、限流；应在 `.env` 中替换数据库密码，若启用本地认证还必须
替换 JWT 密钥。
API 容器会先执行校验和迁移，再启动服务；Compose 使用 `/health/ready` 判断
PostgreSQL、迁移和知识索引均已就绪。镜像包含 PostgreSQL 17 客户端依赖，
但不包含体积较大的 Cross-Encoder/PyTorch。

观测 profile 额外启动 Prometheus 与 OpenTelemetry Collector。默认 Collector
使用 `debug` exporter，便于本地验证；生产环境应将 Collector exporter 替换为
组织已有的 Tempo、Jaeger 或云观测后端，并通过网络策略限制 `/metrics`。

## 17. 项目结构

```text
opspilot-rag/
├── app/
│   ├── graph/
│   │   ├── rewriting.py       # 本地/在线查询改写
│   │   ├── state.py           # 图状态和证据序列化
│   │   ├── workflow.py        # RAG StateGraph、条件边和 checkpoint
│   │   ├── ticket_state.py    # 工单审批图状态
│   │   └── ticket_workflow.py # interrupt、恢复与工具调用
│   ├── tools/
│   │   └── tickets.py         # 工单生成、StructuredTool 和本地存储
│   ├── audit.py               # SQLite/PostgreSQL HTTP 审计
│   ├── ablation.py            # 检索、重排、阈值与改写消融
│   ├── backup.py              # pg_dump/pg_restore、清单与哈希校验
│   ├── api.py                 # FastAPI 接口
│   ├── config.py              # 环境配置
│   ├── embeddings.py          # 本地/在线 Embedding
│   ├── evaluation.py          # 基础离线指标
│   ├── evidence.py            # 验收状态、脱敏、产物哈希与证据报告
│   ├── graph_evaluation.py    # 基础与图工作流对照
│   ├── generator.py           # 本地/在线答案生成
│   ├── health.py              # 存活/就绪依赖检查
│   ├── index.py               # 索引版本和检索
│   ├── kubernetes.py          # Helm、滚动发布与 expand-only 门禁
│   ├── loaders.py             # 文档解析和分块
│   ├── models.py              # API/评测数据模型
│   ├── migrations.py          # 事务迁移、锁与漂移检测
│   ├── load_testing.py        # SLO 统计、分位数与门禁
│   ├── model_evaluation.py    # 真实模型质量、用量、延迟与成本评测
│   ├── observability.py       # Prometheus、OTLP 与 LangSmith
│   ├── persistence.py         # 存储与 Checkpointer 工厂
│   ├── postgres_index.py      # pgvector 持久化、向量搜索与 SQL ACL
│   ├── postgres_stores.py     # PostgreSQL 用户与工单
│   ├── preflight.py           # 生产发布门禁
│   ├── rate_limit.py          # 本地/PostgreSQL 原子限流
│   ├── reranking.py           # 可选 Cross-Encoder 适配器
│   ├── retrieval.py           # BM25、RRF 和本地重排
│   ├── security.py            # 密码、JWT、OIDC、用户存储和文档授权
│   ├── ticket_evaluation.py   # 审批屏障、路径和幂等评测
│   └── service.py             # 基础 RAG 服务
├── frontend/
│   ├── client.py              # 类型清晰的 FastAPI 客户端
│   └── streamlit_app.py       # Streamlit Web 演示界面
├── data/
│   ├── knowledge/             # 合成示例知识库
│   ├── evaluation/            # 检索、图、审批和访问评测集
│   ├── security/              # 文档 ACL 策略
│   └── state/                 # 本地 SQLite 状态
├── migrations/
│   ├── 001_pgvector.sql
│   └── 002_production_persistence.sql
├── deploy/helm/opspilot-rag/  # API/UI、迁移 Job、HPA、PDB、NetworkPolicy
├── docs/
│   ├── ABLATION.md             # 单变量消融结果与工程取舍
│   ├── EVALUATION.md           # 分层评测标签、指标与限制
│   ├── ONLINE_MODEL_EVALUATION.md # 真实模型评测口径
│   ├── DEMO_GUIDE.md           # 项目演示路线与技术评审主线
│   ├── PROJECT_OVERVIEW.md     # 架构、指标与工程能力概览
│   └── ROADMAP.md              # 路线图、验收状态与后续工作
├── ops/
│   ├── KUBERNETES.md          # 发布、验收和回滚手册
│   ├── alerts.yml             # 错误预算、延迟、就绪与限流告警
│   ├── otel-collector.yml     # OTLP Collector 本地配置
│   ├── prometheus.yml         # 指标抓取与规则加载
│   └── SLO.md                 # SLI/SLO 与错误预算定义
├── scripts/
│   ├── bootstrap_users.py
│   ├── backup_database.py
│   ├── migrate.py
│   ├── recovery_drill.py
│   ├── release_gate.py
│   ├── kubernetes_gate.py
│   ├── load_test.py
│   ├── fault_drill.py
│   ├── otel_smoke.py
│   ├── acceptance.py          # 本地/生产统一验收入口
│   ├── restore_database.py
│   ├── purge_audit.py
│   ├── ingest.py
│   ├── evaluate.py
│   ├── evaluate_ablation.py
│   ├── evaluate_online_model.py
│   ├── benchmark_retrieval.py
│   ├── evaluate_graph.py
│   └── evaluate_tickets.py
├── tests/
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## 18. 设计决策与验证要点

1. 为什么基础 RAG 和 LangGraph 接口同时保留？
   基础接口是可重复的实验对照组。没有对照组，无法证明改写和重试是优化还是只增加复杂度。

2. 为什么不让模型无限重试？
   检索重试必须有上限，否则会扩大延迟、成本和错误累积。当前通过
   `MAX_REWRITES` 形成确定的停止条件。

3. 为什么状态中保存序列化证据？
   checkpoint 应只保存稳定、可序列化的数据，而不是依赖进程内对象身份。
   恢复时再重建 `Document` 和检索分数对象。

4. 如何解释证据是否充分？
   图中有独立 `grade_evidence` 节点，综合检查重排分、向量分、
   BM25 和词项覆盖率；响应返回分数、原因和每次尝试，便于调试阈值。

5. SQLite 是否适合生产？
   它适合单机演示和开发。当前生产模式会把用户、工单和两类 LangGraph checkpoint
   迁移到 PostgreSQL；仍需配置连接池、备份、checkpoint 保留和用户级数据隔离。

6. 为什么 Cross-Encoder 不直接搜索整个知识库？
   Cross-Encoder 必须联合编码每个 query-document 对，质量更高但计算昂贵。
   当前先用向量与 BM25 高召回地缩小到 `CANDIDATE_K` 个候选，再执行精排。

7. 为什么 `interrupt()` 放在工具之前？
   模型可以生成草稿和建议，但任何有副作用的提交都必须由人确认。中断前只保存
   checkpoint，不写业务库；批准后才执行 `submit_ticket`。

8. 为什么提交工具还要做幂等？
   人工审批保证“是否允许执行”，但不能消除网络重试、进程崩溃或恢复重放。
   `workflow_id` 唯一约束保证同一审批只产生一个业务结果。

9. 为什么 LangSmith 是可选能力？
   离线测试不应依赖外部服务；开启后可观察节点耗时、模型调用、检索重试和工具执行，
   关闭后核心业务行为必须完全相同。

10. 当前最大局限是什么？
    36 条人工整理的合成评测样本仍小，未做双人标注一致性统计；本地改写仍包含领域规则，
    Cross-Encoder 默认模型也未经企业语料微调。下一步应加入线上反馈闭环、独立复标，
    并用真实工单沙箱验证。

11. 为什么权限过滤必须在召回阶段？
    如果先取回未授权文档再在回答末尾隐藏引用，内容仍可能进入重排、模型上下文和 trace。
    当前本地与 pgvector 两个后端都在候选进入这些环节前执行 ACL。

12. 为什么 JWT 里不直接保存角色？
    角色写进令牌会一直有效到令牌过期。当前令牌只保存用户 ID，每次请求重新读取账号，
    让停用账号和撤销权限立即生效；代价是多一次身份存储查询。

13. “修改”为什么等于修改后批准？
   审批响应同时表达了决定和新参数。修改内容先经过 Pydantic 校验，再替换
   pending tool call 的参数，随后执行；原始草稿、决定和最终参数都可审计。

14. OIDC token 里已有角色，为什么还查用户表？
   外部 token 只建立身份真实性，应用授权仍以当前用户表为准。这样企业账号与应用 scope
   可以独立撤销，也避免把 IdP 的通用角色直接等同于知识库和工具权限。

15. 多实例限流如何避免竞态？
   PostgreSQL 后端使用 `INSERT ... ON CONFLICT DO UPDATE ... RETURNING` 原子增加窗口计数；
   同一客户端和窗口只有一行。单机演示则使用带锁内存计数，不引入数据库依赖。

16. 为什么迁移文件执行后不能直接修改？
   数据库只知道某个版本已执行，不知道开发者后来改了什么。记录文件 SHA-256 并在发布前
   对比，可以把不可重复的历史修改变成明确失败；新变化必须写成新迁移。

17. 为什么备份成功还要做恢复演练？
   文件存在不代表可恢复。演练同时验证备份工具版本、哈希、目标权限、扩展、DDL、数据和
   checkpoint，并用隔离数据库避免触碰生产库。

18. 为什么指标不能直接把路径和用户 ID 当标签？
   Prometheus 会为每种标签组合创建时间序列。真实 ID、问题文本和 thread ID 会造成
   基数爆炸，同时泄漏业务内容；因此只记录路由模板、状态类别和有限枚举。

19. LangSmith 与 OpenTelemetry 为什么同时存在？
   LangSmith 适合检查 prompt、模型调用、图节点和工具轨迹；OpenTelemetry 用统一协议
   串联 HTTP、数据库和其他服务。两者用途不同，且都必须可关闭而不改变业务语义。

20. 为什么故障时 liveness 仍为 200、readiness 返回 503？
   进程仍健康时不应被容器运行时反复重启，但数据库或索引不可用时必须从负载均衡摘除。
   把存活与接流量资格分开，才能区分“需要重启”和“等待依赖恢复”。

## 参考

- [LangGraph：Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph：Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph：Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph：Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangChain：Retrieval](https://docs.langchain.com/oss/python/langchain/retrieval)
- [LangChain：ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [pgvector：PostgreSQL 向量相似度搜索](https://github.com/pgvector/pgvector)
- [pgvector-python：Psycopg 3 集成](https://github.com/pgvector/pgvector-python)
- [PyJWT：使用示例](https://pyjwt.readthedocs.io/en/stable/usage.html)
- [PostgreSQL：事务隔离与 ON CONFLICT](https://www.postgresql.org/docs/current/transaction-iso.html)
- [PostgreSQL：pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html)
- [PostgreSQL：pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html)
- [PostgreSQL：Advisory Locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
- [OpenTelemetry Python：Exporters](https://opentelemetry.io/docs/languages/python/exporters/)
- [OpenTelemetry：OTLP exporter configuration](https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/)
- [Prometheus：Alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [uv：GitHub Actions 集成](https://docs.astral.sh/uv/guides/integration/github/)
