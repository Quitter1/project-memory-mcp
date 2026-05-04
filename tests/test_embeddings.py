"""
Embedding 测试 — HashingEmbeddingProvider 确定性、维度、build_embedding_text。
"""

from project_memory_mcp.vector.embeddings import HashingEmbeddingProvider


def test_hashing_deterministic():
    e = HashingEmbeddingProvider(dim=512)
    v1 = e.embed_text("订单查询接口")
    v2 = e.embed_text("订单查询接口")
    assert v1 == v2


def test_hashing_dim():
    e = HashingEmbeddingProvider(dim=512)
    v = e.embed_text("test text")
    assert len(v) == 512


def test_hashing_empty():
    e = HashingEmbeddingProvider(dim=512)
    v = e.embed_text("")
    assert len(v) == 512
    assert all(x == 0.0 for x in v)


def test_hashing_different_texts():
    e = HashingEmbeddingProvider(dim=512)
    v1 = e.embed_text("订单查询")
    v2 = e.embed_text("CorelDRAW 弹窗处理")
    assert v1 != v2


def test_build_embedding_text_no_source_evidence():
    from project_memory_mcp.models.memory_item import MemoryItem
    from project_memory_mcp.vector.indexer import VectorIndexer

    memory = MemoryItem(
        title="测试知识", content="正文内容",
        type="api", module="test", tags=["tag1"],
        source_evidence={"file": "secret.py", "excerpt": "password=secret123"},
    )
    indexer = VectorIndexer(None, None, None)
    text = indexer.build_embedding_text(memory)
    assert "secret.py" not in text
    assert "password=secret123" not in text
    assert "标题: 测试知识" in text
