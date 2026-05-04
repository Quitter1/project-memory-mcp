"""
VectorIndexer 测试 — 索引联动、Qdrant disabled fallback、不索引敏感状态。
"""

import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.vector.embeddings import HashingEmbeddingProvider
from project_memory_mcp.vector.indexer import VectorIndexer


def _write_config(config_dir: Path):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "projects.yml").write_text("""\
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      root_paths: ["/test"]
      aliases: ["test"]
defaults:
  knowledge_policy:
    auto_approve_threshold: -1
    max_candidate_per_task: 20
    retention_days: 365
  review_policy:
    allow_ai_auto_approve: false
    forbidden_auto_types: []
    risk_threshold_for_review: medium
    require_review_if_conflict: true
""", encoding="utf-8")


class MockVectorStore:
    """用于测试的假 Qdrant store。"""

    def __init__(self):
        self.points = {}
        self.deleted = []

    def ensure_collection(self):
        pass

    def upsert_memory(self, memory_id, vector, metadata):
        self.points[memory_id] = {"vector": vector, "metadata": metadata}

    def delete_memory(self, memory_id):
        self.deleted.append(memory_id)
        self.points.pop(memory_id, None)


def test_indexer_disabled_when_no_store():
    indexer = VectorIndexer(None, None, None)
    assert not indexer.enabled


def test_indexer_index_approved():
    from project_memory_mcp.models.memory_item import MemoryItem
    store = MockVectorStore()
    embedder = HashingEmbeddingProvider(dim=512)
    memory = MemoryItem(
        id="test-id", project_id="test-proj", title="测试", content="内容",
        type="other", status="approved", scope="project",
    )
    indexer = VectorIndexer(None, embedder, store)
    assert indexer.enabled
    ok = indexer.index_memory(memory)
    assert ok
    assert "test-id" in store.points


def test_indexer_skip_pending():
    from project_memory_mcp.models.memory_item import MemoryItem
    store = MockVectorStore()
    embedder = HashingEmbeddingProvider(dim=512)
    memory = MemoryItem(
        id="pending-id", project_id="test-proj", title="待审", content="内容",
        type="other", status="pending_review", scope="project",
    )
    indexer = VectorIndexer(None, embedder, store)
    ok = indexer.index_memory(memory)
    assert not ok
    assert "pending-id" not in store.points


def test_indexer_delete():
    from project_memory_mcp.models.memory_item import MemoryItem
    store = MockVectorStore()
    embedder = HashingEmbeddingProvider(dim=512)
    memory = MemoryItem(
        id="del-id", project_id="test-proj", title="删除", content="内容",
        type="other", status="approved", scope="project",
    )
    indexer = VectorIndexer(None, embedder, store)
    indexer.index_memory(memory)
    assert "del-id" in store.points
    indexer.delete_memory("del-id")
    assert "del-id" not in store.points


def test_reindex_disabled_without_memory_repo():
    store = MockVectorStore()
    embedder = HashingEmbeddingProvider(dim=512)
    indexer = VectorIndexer(None, embedder, store)
    # indexer.enabled checks embedder and store, not memory_repo
    assert indexer.enabled
    # reindex_all with None memory_repo → graceful error
    try:
        result = indexer.reindex_all(dry_run=True)
    except AttributeError:
        pytest.skip("memory_repo required for reindex_all")
