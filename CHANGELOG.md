# Changelog

## Unreleased

- 将公开文档统一为企业 Agentic RAG 参考实现定位，并重组项目概览、路线图和技术评审指南。
- 修复 pgvector 重建索引在 psycopg 3 中错误调用连接级 `executemany` 的问题。
- 固定 Docker 基础镜像为 Debian Bookworm，与 PostgreSQL 软件源保持一致。
- 证据生成在运行环境缺少 Git 客户端时改为明确记录不可用，而不是异常退出。
- 补充 PostgreSQL 17 集成与隔离恢复验收、项目概览和对应回归测试。

## 0.11.0

- 新增统一 `scripts/acceptance.py` 验收入口。
- 新增 JSON/Markdown 发布证据、产物 SHA-256 和敏感输出脱敏。
- 将缺少基础设施的项目标记为 `skipped`，整体状态标记为 `partial`。
- 新增 Streamlit 页面级断连降级和问答成功路径测试。
- 新增 PostgreSQL 用户、工单、审计、限流和迁移适配器契约测试。
- CI 为本地质量、PostgreSQL、恢复演练、依赖故障和 Kubernetes 回滚分别归档证据，
  并生成汇总校验和清单。
- 新增独立项目演示手册。

## 0.10.0

- 新增 Kubernetes/Helm、HPA、PDB、NetworkPolicy、滚动发布和原子回滚验收。

## 0.9.0

- 新增 Prometheus、OpenTelemetry、SLO、并发压测和依赖故障演练。

## 0.8.0

- 新增事务迁移、备份恢复、恢复演练、存活/就绪检查和发布门禁。

## 0.7.0

- 新增 PostgreSQL/pgvector、OIDC、审计和多实例原子限流。
