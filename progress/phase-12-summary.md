# 阶段 12 — BGE-M3 HTTP embedding 接入

## 完成时间

2026-05-04

## 切换

| 配置项 | 旧值 | 新值 |
|--------|------|------|
| embedding.provider | hashing | http |
| embedding.model | hashing-v1 | BAAI/bge-m3 |
| embedding.dim | 512 | 1024 |
| qdrant.collection | project_memory_items | project_memory_items_bge_m3 |

## 结果

### check_embedding.py
- provider=http, model=BAAI/bge-m3, dim=1024
- norm=1.0, elapsed_ms=93

### reindex_vectors.py --yes
- eligible=7, indexed=7, failed=0
- 新 collection 自动创建

### eval_search.py --mode hybrid
- hit_rate=3/3, top1_rate=3/3
- avg_elapsed_ms=438ms

### 质量提升

| 指标 | hashing | BGE-M3 |
|------|---------|--------|
| vector score (top1) | 0.022 | 0.603 |
| hybrid score (top1) | 0.010 | 0.271 |
| top1 命中 | 3/3 | 3/3 |

BGE-M3 的向量相关性评分提升了约 27 倍。

### 测试
```
390 passed in 12.99s
```

## 审阅包

`reviews/review-pack-phase-12.zip`
