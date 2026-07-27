from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Any

import pytest

from app.embeddings import LocalHashEmbeddings
from app.postgres_index import PostgresKnowledgeIndex
from app.security import SYSTEM_ACCESS, AccessContext


class _EmptyResult:
    def fetchall(self) -> list[dict[str, object]]:
        return []


class _RecordingConnection:
    def __init__(self) -> None:
        self.row_factory: object | None = None
        self.sql = ""
        self.params: list[object] = []

    def execute(self, sql: str, params: list[object]) -> _EmptyResult:
        self.sql = sql
        self.params = params
        return _EmptyResult()


def test_pgvector_query_pushes_acl_into_sql(settings, monkeypatch) -> None:
    postgres_settings = settings.model_copy(
        update={
            "index_backend": "postgres",
            "database_url": "postgresql://unused",
        }
    )
    index = PostgresKnowledgeIndex(
        postgres_settings,
        LocalHashEmbeddings(),
    )
    connection = _RecordingConnection()

    @contextmanager
    def fake_connect() -> Any:
        yield connection

    monkeypatch.setattr(index, "_connect", fake_connect)
    access = AccessContext(
        user_id="sales",
        username="sales",
        roles=frozenset({"sales"}),
        departments=frozenset({"sales"}),
        scopes=frozenset({"knowledge:read"}),
    )

    assert index._vector_search("订单权限", 4, access) == []
    assert "allowed_roles && %s::text[]" in connection.sql
    assert "allowed_departments && %s::text[]" in connection.sql
    assert any(
        isinstance(param, list) and param == ["sales"]
        for param in connection.params
    )


class _RowsResult:
    def __init__(
        self,
        *,
        one: dict[str, object] | None = None,
        rows: list[dict[str, object]] | None = None,
    ) -> None:
        self.one = one
        self.rows = rows or []

    def fetchone(self) -> dict[str, object] | None:
        return self.one

    def fetchall(self) -> list[dict[str, object]]:
        return self.rows


def _chunk_row(*, similarity: float = 0.8) -> dict[str, object]:
    return {
        "chunk_id": "chunk-1",
        "source": "permissions.md",
        "title": "权限手册",
        "page": 2,
        "content": "按部门配置数据权限。",
        "metadata": {"classification": "restricted"},
        "allowed_roles": ["support"],
        "allowed_departments": ["it"],
        "similarity": similarity,
    }


def test_pgvector_setup_and_document_mapping(settings) -> None:
    postgres_settings = settings.model_copy(
        update={
            "index_backend": "postgres",
            "database_url": "postgresql://unused",
        }
    )
    index = PostgresKnowledgeIndex(postgres_settings, LocalHashEmbeddings())

    class SetupConnection:
        def __init__(self) -> None:
            self.sql: list[str] = []

        def execute(self, sql: str) -> _EmptyResult:
            self.sql.append(" ".join(sql.split()))
            return _EmptyResult()

    connection = SetupConnection()
    index._setup(connection)
    document = index._document(_chunk_row())

    assert len(connection.sql) == 5
    assert any("VECTOR(1536)" in sql for sql in connection.sql)
    assert document.page_content == "按部门配置数据权限。"
    assert document.metadata["allowed_departments"] == ["it"]


def test_pgvector_vector_search_maps_and_clamps_similarity(settings, monkeypatch) -> None:
    postgres_settings = settings.model_copy(
        update={
            "index_backend": "postgres",
            "database_url": "postgresql://unused",
        }
    )
    index = PostgresKnowledgeIndex(
        postgres_settings,
        LocalHashEmbeddings(),
    )

    class SearchConnection:
        row_factory: object | None = None

        def __init__(self) -> None:
            self.sql = ""
            self.params: list[object] = []

        def execute(self, sql: str, params: list[object]) -> _RowsResult:
            self.sql = sql
            self.params = params
            return _RowsResult(rows=[_chunk_row(similarity=1.4)])

    connection = SearchConnection()

    @contextmanager
    def fake_connect() -> Any:
        yield connection

    monkeypatch.setattr(index, "_connect", fake_connect)
    hits = index._vector_search("权限", 2, SYSTEM_ACCESS)

    assert hits[0].score == 1.0
    assert hits[0].document.metadata["source"] == "permissions.md"
    assert "allowed_roles &&" not in connection.sql
    assert connection.params[-1] == 2


def test_pgvector_ensure_ready_reuses_matching_manifest(settings, monkeypatch) -> None:
    postgres_settings = settings.model_copy(
        update={
            "index_backend": "postgres",
            "database_url": "postgresql://unused",
        }
    )
    index = PostgresKnowledgeIndex(
        postgres_settings,
        LocalHashEmbeddings(),
    )
    manifest = {
        **index._expected_manifest(),
        "documents": 1,
        "chunks": 1,
    }

    class ReadyConnection:
        row_factory: object | None = None

        def execute(
            self,
            sql: str,
            params: tuple[object, ...] | None = None,
        ) -> _RowsResult:
            if "SELECT manifest" in sql:
                return _RowsResult(one={"manifest": manifest})
            if "SELECT chunk_id" in sql:
                return _RowsResult(rows=[_chunk_row()])
            return _RowsResult()

    @contextmanager
    def fake_connect() -> Any:
        yield ReadyConnection()

    monkeypatch.setattr(index, "_connect", fake_connect)
    result = index.ensure_ready()

    assert result["rebuilt"] is False
    assert index._manifest["chunks"] == 1
    assert index._is_ready() is True


def test_pgvector_rebuild_rejects_embedding_dimension_mismatch(settings) -> None:
    class WrongDimensions(LocalHashEmbeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2] for _ in texts]

    postgres_settings = settings.model_copy(
        update={
            "index_backend": "postgres",
            "database_url": "postgresql://unused",
        }
    )
    index = PostgresKnowledgeIndex(postgres_settings, WrongDimensions())

    with pytest.raises(ValueError, match="Embedding 维度"):
        index.rebuild()


def test_pgvector_rebuild_batches_rows_with_cursor(settings, monkeypatch) -> None:
    postgres_settings = settings.model_copy(
        update={
            "index_backend": "postgres",
            "database_url": "postgresql://unused",
        }
    )
    index = PostgresKnowledgeIndex(postgres_settings, LocalHashEmbeddings())

    class RecordingCursor:
        def __init__(self) -> None:
            self.sql = ""
            self.rows: list[tuple[object, ...]] = []

        def __enter__(self) -> RecordingCursor:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def executemany(
            self,
            sql: str,
            rows: list[tuple[object, ...]],
        ) -> None:
            self.sql = " ".join(sql.split())
            self.rows = rows

    class RebuildConnection:
        def __init__(self) -> None:
            self.cursor_instance = RecordingCursor()

        def execute(
            self,
            sql: str,
            params: tuple[object, ...] | None = None,
        ) -> _EmptyResult:
            return _EmptyResult()

        def transaction(self):
            return nullcontext()

        def cursor(self) -> RecordingCursor:
            return self.cursor_instance

    connection = RebuildConnection()

    @contextmanager
    def fake_connect() -> Any:
        yield connection

    monkeypatch.setattr(index, "_connect", fake_connect)
    result = index.rebuild()

    assert result["rebuilt"] is True
    assert len(connection.cursor_instance.rows) == result["chunks"]
    assert "INSERT INTO knowledge_chunks" in connection.cursor_instance.sql
