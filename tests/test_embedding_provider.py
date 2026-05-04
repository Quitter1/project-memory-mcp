"""
Embedding provider 测试 — provider/model 属性, SAFE_PAYLOAD_FIELDS, HTTP format。
"""

from project_memory_mcp.vector.embeddings import HashingEmbeddingProvider, HttpEmbeddingProvider
from project_memory_mcp.vector.qdrant_store import SAFE_PAYLOAD_FIELDS


def test_hashing_provider_is_hashing():
    e = HashingEmbeddingProvider(dim=512)
    assert e.provider == "hashing"
    assert e.model == "hashing-v1"
    assert e.dim == 512


def test_http_provider_is_http():
    e = HttpEmbeddingProvider(dim=768, model="bge-v1")
    assert e.provider == "http"
    assert e.model == "bge-v1"
    assert e.dim == 768


def test_safe_payload_includes_embedding_meta():
    assert "embedding_provider" in SAFE_PAYLOAD_FIELDS
    assert "embedding_model" in SAFE_PAYLOAD_FIELDS
    assert "embedding_dim" in SAFE_PAYLOAD_FIELDS


def test_safe_payload_excludes_content():
    assert "content" not in SAFE_PAYLOAD_FIELDS
    assert "source_evidence" not in SAFE_PAYLOAD_FIELDS
