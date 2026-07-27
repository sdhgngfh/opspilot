from __future__ import annotations

import math

from app.embeddings import LocalHashEmbeddings


def test_local_embeddings_are_deterministic_and_normalized() -> None:
    embeddings = LocalHashEmbeddings(dimensions=128)
    first = embeddings.embed_query("销售订单部门权限")
    second = embeddings.embed_query("销售订单部门权限")

    assert first == second
    assert len(first) == 128
    assert math.isclose(sum(value * value for value in first), 1.0, rel_tol=1e-6)


def test_related_text_has_higher_similarity() -> None:
    embeddings = LocalHashEmbeddings(dimensions=512)
    query = embeddings.embed_query("如何限制销售订单部门权限")
    related = embeddings.embed_query("销售订单的数据权限应按销售部门过滤")
    unrelated = embeddings.embed_query("纽约天气预报和气温")

    def similarity(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert similarity(query, related) > similarity(query, unrelated)
