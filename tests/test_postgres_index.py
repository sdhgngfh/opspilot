from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.config import PROJECT_ROOT, Settings
from app.security import SYSTEM_ACCESS, AccessContext
from app.service import RAGService


@pytest.mark.integration
def test_pgvector_rebuild_search_and_acl(tmp_path: Path) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    collection = f"test_{uuid4().hex}"
    settings = Settings(
        rag_mode="local",
        embedding_provider="local",
        index_backend="postgres",
        database_url=database_url,
        pgvector_collection=collection,
        knowledge_dir=PROJECT_ROOT / "data" / "knowledge",
        access_policy_path=PROJECT_ROOT
        / "data"
        / "security"
        / "document_access.json",
        index_path=tmp_path / "unused.json",
    )
    service = RAGService(settings)
    manifest = service.reindex()
    sales = AccessContext(
        user_id="sales",
        username="sales",
        roles=frozenset({"sales"}),
        departments=frozenset({"sales"}),
        scopes=frozenset({"knowledge:read"}),
    )

    admin_hits = service.retrieve(
        "数据库备份恢复演练 RPO RTO",
        access=SYSTEM_ACCESS,
    )
    sales_hits = service.retrieve(
        "数据库备份恢复演练 RPO RTO",
        access=sales,
    )

    assert manifest.chunks > 0
    assert admin_hits[0].document.metadata["source"] == "backup_recovery.md"
    assert all(
        hit.document.metadata["source"] != "backup_recovery.md"
        for hit in sales_hits
    )
