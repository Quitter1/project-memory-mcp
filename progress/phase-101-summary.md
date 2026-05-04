# 阶段 10.1 报告 — Qdrant 收口

## 完成时间

2026-05-04

## 修复

### 1. reindex_vectors.py --yes 修复 ✅
- `reindex_all()` 无 project_id 时遍历 project_repo 所有 active 项目
- 逐项目调用 `list_memories(project_id=p.id, status_filter=["approved"])`
- dry-run 不写 Qdrant
- collection 自动创建

### 2. vector_search_demo.py ✅
- keyword vs vector 对比展示
- Qdrant disabled 时只展示 keyword
- 输出 memory_id/score/title，不含 source_evidence

### 3. diagnose.py --vector-summary ✅
- qdrant.enabled / embedding.provider/dim / collection
- Qdrant reachable / points count
- approved / indexed / index_failed / not_indexed

### 4. pyproject.toml 依赖 ✅
- dev + vector optional-dependencies 增加 qdrant-client>=1.10, httpx>=0.25

### 5. check_qdrant.py 增强 ✅
- collection 存在时显示 dim
- Qdrant 未启动时友好提示

## 测试结果

```
386 passed in 11.88s
```

**新增测试总计：+1**

## 修改文件

| 文件 | 变更 |
|------|------|
| `vector/indexer.py` | reindex_all(project_repo) 修复 |
| `scripts/reindex_vectors.py` | 传入 project_repo, collection 创建 |
| `scripts/vector_search_demo.py` | 新增 |
| `scripts/diagnose.py` | --vector-summary |
| `scripts/check_qdrant.py` | 增强：dim/points/友好提示 |
| `pyproject.toml` | dev+vector: qdrant-client, httpx |
| `CLAUDE.md` | 更新当前阶段 |

## 审阅包

`reviews/review-pack-phase-101.zip`

## 是否可以进入 Qdrant 人工验证

✅ 可以。先 `pip install -e ".[dev]"` 安装依赖，再按 docs/qdrant-vector-search.md 验证。
