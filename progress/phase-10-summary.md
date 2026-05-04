# 阶段 10 报告 — Qdrant + embedding 基础框架

## 完成时间

2026-05-04

## 新增模块

### vector/embeddings.py ✅
- `HashingEmbeddingProvider`：确定性本地 embedding（dim=512，L2 normalized）
- `HttpEmbeddingProvider`：HTTP 真实 embedding 预留
- `BaseEmbeddingProvider`：抽象基类

### vector/qdrant_store.py ✅
- `QdrantVectorStore`：collection 管理、upsert、delete、search
- 安全 payload 白名单（不存 content/source_evidence 原文）
- 按 scope 过滤（project/shared/global）

### vector/indexer.py ✅
- `VectorIndexer`：与 governance 联动，索引/删除/重建
- `build_embedding_text()`：不含 source_evidence
- 只索引 approved，跳过 pending/candidate/rejected

### vector/__init__.py ✅

## 集成

### AppContext ✅
- `_init_vector()`：读取 server.yml 配置，创建 embedder/Qdrant/indexer
- qdrant.enabled=false 时跳过，不影响现有功能

### governance.py ✅
- approve_memory 后 index
- reject_memory 后 delete vector
- deprecate_memory 后 delete vector
- indexer 为 None 时静默跳过
- Qdrant 失败不影响主流程

### config/server.yml ✅
- qdrant/embedding/search 三段配置
- search.mode: hybrid/keyword/vector
- fallback_to_keyword: true

## 新增脚本

| 脚本 | 说明 |
|------|------|
| `scripts/check_qdrant.py` | Qdrant 连接检查 |
| `scripts/reindex_vectors.py` | 向量索引重建（dry-run 默认） |

## 测试结果

```
385 passed, 1 skipped in 11.99s
```

| 测试文件 | 新增 | 说明 |
|----------|------|------|
| test_embeddings.py | 5 (新) | Hashing 确定性/维度/build_text |
| test_vector_indexer.py | 5 (新) | 索引/跳过/删除/dry-run |

**新增测试总计：+9**（原 376 → 385）

## 修改文件

| 文件 | 变更 |
|------|------|
| `vector/embeddings.py` | 新增 |
| `vector/qdrant_store.py` | 新增 |
| `vector/indexer.py` | 新增 |
| `vector/__init__.py` | 更新 |
| `app_context.py` | _init_vector + vector fields |
| `knowledge/governance.py` | indexer 参数 + approve/reject/deprecate 联动 |
| `config/server.yml` | qdrant/embedding/search 配置 |
| `scripts/check_qdrant.py` | 新增 |
| `scripts/reindex_vectors.py` | 新增 |
| `tests/test_embeddings.py` | 新增 |
| `tests/test_vector_indexer.py` | 新增 |
| `CLAUDE.md` | Qdrant 规则 + 当前阶段 |

## 审阅包

`reviews/review-pack-phase-10.zip`

## 是否可以进入 Qdrant 人工验证

✅ 可以。本机未安装 Qdrant 时 `qdrant.enabled=false` 不影响现有功能。
如需验证向量搜索，先启动 Qdrant 并修改 `config/server.yml qdrant.enabled=true`。
