# PROJECT_MEMORY.md

This file is the shared project memory for AI agents.

## File Roles

- `AGENTS.md`: Codex entrypoint and Codex-specific operating rules.
- `CLAUDE.md`: Claude Code entrypoint and Claude-specific operating rules.
- `PROJECT_MEMORY.md`: shared project rules, durable memory, decisions, commands, identifiers, and follow-up context.

Keep README files for human-facing project documentation. Do not store AI memory in `README.md` unless the user explicitly asks.

## Project Rules

### Instruction File Language

Use English for prose in `AGENTS.md`, `CLAUDE.md`, and `PROJECT_MEMORY.md`. Preserve exact non-English names, paths, UI labels, business terms, and user-facing examples when they are identifiers or source facts.

### Conflict Checks

Before changing `AGENTS.md`, `CLAUDE.md`, or `PROJECT_MEMORY.md`, check the proposed change against all three files and warn the user if it conflicts with existing agent operating rules or project memory.

### Product Positioning

- OpsPilot is an enterprise Agentic RAG reference implementation.
- Prefer evidence-backed depth over adding framework names or speculative features.
- Keep local mode deterministic and usable without external API keys.
- Clearly distinguish locally verified behavior from PostgreSQL, recovery, Kubernetes, OIDC, or online-model claims that still require target infrastructure.

### Security and Data

- Never commit `.env`, API keys, database passwords, bearer tokens, enterprise identity tokens, personal information, or proprietary documents.
- Use only synthetic or explicitly approved knowledge and evaluation data in the public repository.
- Side-effecting tools must remain behind explicit human approval and idempotency controls.
- Document ACL checks must happen before reranking, generation, tracing, or caching can consume unauthorized content.

### Verification Gates

- Standard local gate: `uv run ruff check .`, `uv run pytest`, `uv build`, and `uv run python scripts/acceptance.py`.
- Retrieval or threshold changes require rerunning basic, graph, and access evaluations.
- Authentication, ACL, workflow, or persistence changes require focused security, approval-barrier, and idempotency tests.
- Production-readiness claims require the infrastructure checks to pass; a `partial` acceptance result is not production approval.

## Durable Memory

- Current baseline is release `v0.11.0` at commit `9154e7a`.
- The imported baseline is one consolidated commit; `origin` is the public repository `https://github.com/sdhgngfh/opspilot-rag.git`.
- Python 3.12 is the recommended local and CI baseline; the package supports Python `>=3.11,<3.14`.
- FastAPI runs on port `8000`; Streamlit runs on port `8501`.
- `docs/ROADMAP.md` is the execution backlog; `docs/DEMO_GUIDE.md` is the project review route.
- `docs/DEMO_SCREENSHOTS.md` is the checked-in visual fallback for offline review and demonstrations.
- Default local backends are deterministic and need no OpenAI key. PostgreSQL and production controls are separate validation paths.
- Streamlit AppTest cold starts can exceed 10 seconds on macOS; keep the UI test timeout at 30 seconds unless measured evidence supports lowering it.
- Remote CI run `30199877047` passed on 2026-07-26 for commit `cfd53eb`, including
  Python 3.11/3.12 quality, PostgreSQL integration, isolated recovery, dependency
  degradation, Kubernetes atomic rollback, and the combined evidence artifact.
- On 2026-07-26, the full isolated gate passed with 10 checks, including PostgreSQL 17/pgvector integration and recovery into a separate database.
- Use a psycopg cursor for batched `executemany`; psycopg 3 connections do not expose that method.
- Keep the Docker Python base pinned to Debian Bookworm while the image uses the `bookworm-pgdg` PostgreSQL repository.
- Evidence generation must degrade cleanly when Git is unavailable in a release container or source archive.
- Keep `httpx2` in the development extra while Starlette's `TestClient` requires it;
  `tests/test_testclient_compatibility.py` turns the compatibility deprecation back into a test failure.
- Treat user questions, conversation history, retrieved evidence, and ticket requests as untrusted
  model data; `tests/test_adversarial_security.py` covers direct and indirect prompt injection,
  pre-rerank ACL filtering, identity-scoped threads, and ticket workflow ID collisions.
- The curated synthetic evaluation baseline contains 36 basic cases and 12 ACL cases. Preserve
  `question_type` and `difficulty` labels, keep role-aware breakdowns in reports, and use
  `docs/EVALUATION.md` for the current rubric and limitations.
- Online-model evaluation must use provider-reported token usage and an explicit dated pricing
  snapshot. No authorized API key or real-model result exists in the current local environment;
  use `docs/ONLINE_MODEL_EVALUATION.md` before making online quality or cost claims.
- Deterministic ablation evidence supports hybrid retrieval plus reranking, a
  `MIN_RELEVANCE_SCORE` of `0.18`, and a default `MAX_REWRITES` of `1`. The second rewrite
  added attempts and latency without quality gains; preserve `docs/ABLATION.md` and rerun the
  ablation gate when changing these controls.
