# MCP 工具接口文档 — project-memory-mcp

## 概述

MVP 阶段提供 9 个 MCP 工具，通过 stdio JSON-RPC 暴露给 MCP 客户端（Claude Code、Codex 等）。

所有工具通过 `mcp server` 的 `@mcp.tool()` 装饰器注册，参数和返回值使用 Python 原生类型 + dict 结构。

## 通用约定

### project_id 处理

部分工具（search、propose）的 `project_id` 参数是**可选**的。如果不传：

1. 优先使用 `workspace_path` 自动 resolve
2. 其次使用 `changed_files` 自动 resolve
3. 都失败时返回 `project_id_required` 错误

### 错误响应格式

```json
{
    "error": "error_code",
    "message": "人类可读的错误描述",
    "details": {}
}
```

### 敏感操作审计

所有写入操作（propose/approve/reject/deprecate）自动写入 audit_log。

---

## 工具清单

### 1. list_projects

**分类**：项目识别

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| status_filter | string | 否 | "active" | active / archived / disabled / all |

**返回示例**：
```json
{
    "projects": [
        {
            "id": "biaopai-erp",
            "name": "标牌 ERP",
            "slug": "biaopai-erp",
            "status": "active",
            "memory_count": 128,
            "last_updated": "2026-05-01T10:00:00Z",
            "tech_stack": ["Java", "Spring MVC", "MySQL"]
        }
    ],
    "total": 4
}
```

---

### 2. resolve_project

**分类**：项目识别

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| project_id | string | 否 | null | 显式指定，优先级最高 |
| workspace_path | string | 否 | null | 当前工作目录路径 |
| changed_files | list[string] | 否 | [] | 已修改文件列表 |
| related_files | list[string] | 否 | [] | 相关文件列表 |
| task_description | string | 否 | null | 任务描述文本（弱匹配） |
| allow_multiple | boolean | 否 | false | 多匹配时返回候选而非报错 |

**返回示例（唯一匹配）**：
```json
{
    "resolved": true,
    "project": {
        "id": "biaopai-erp",
        "name": "标牌 ERP",
        "status": "active",
        "tech_stack": ["Java", "Spring MVC", "MySQL"]
    },
    "match_method": "workspace_path",
    "confidence": 0.95
}
```

**返回示例（歧义）**：
```json
{
    "resolved": true,
    "ambiguous": true,
    "candidates": [
        { "project_id": "biaopai-erp", "match_method": "alias", "confidence": 0.8 },
        { "project_id": "cdr-converter", "match_method": "tech_stack", "confidence": 0.5 }
    ]
}
```

**返回示例（失败）**：
```json
{
    "resolved": false,
    "error": "unable_to_resolve_project",
    "message": "请显式指定 project_id，可用项目见 suggest_projects",
    "suggest_projects": [
        { "id": "biaopai-erp", "name": "标牌 ERP" },
        { "id": "cdr-converter", "name": "CDR 转图片工具" }
    ]
}
```

---

### 3. get_project_profile

**分类**：项目识别

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | string | 是 | 项目 ID |

**返回示例**：
```json
{
    "project": {
        "id": "biaopai-erp",
        "name": "标牌 ERP",
        "description": "标牌企业 ERP 系统...",
        "status": "active",
        "tech_stack": ["Java", "Spring MVC", "MySQL"],
        "root_paths": ["D:/workspace/biaopai-erp"],
        "aliases": ["erp", "biaopai"],
        "knowledge_policy": {
            "auto_approve_threshold": -1,
            "max_candidate_per_task": 15
        },
        "review_policy": {
            "allow_ai_auto_approve": false
        },
        "stats": {
            "total_memories": 128,
            "by_status": { "approved": 95, "candidate": 10, "deprecated": 8 },
            "by_type": { "api": 30, "architecture": 25 }
        }
    }
}
```

---

### 4. search_project_context

**分类**：知识检索

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| project_id | string | 否* | null | 项目 ID（可选，支持自动 resolve） |
| workspace_path | string | 否 | null | 用于自动 resolve project_id |
| changed_files | list[string] | 否 | [] | 用于自动 resolve project_id |
| query | string | 是 | - | 自然语言查询 |
| modules | list[string] | 否 | [] | 模块过滤 |
| types | list[string] | 否 | [] | 知识类型过滤 |
| tags | list[string] | 否 | [] | 标签过滤 |
| max_results | integer | 否 | 10 | 最大返回数 |
| min_confidence | number | 否 | 0.5 | 最低置信度 |
| include_shared | boolean | 否 | true | 是否包含 shared 知识 |
| include_global | boolean | 否 | true | 是否包含 global 知识 |
| include_candidates | boolean | 否 | false | 是否包含候选知识 |

> *project_id 为可选，但必须提供 project_id / workspace_path / changed_files 之一

**返回 — context_pack 格式**：
```json
{
    "query": "订单查询接口",
    "project_id": "biaopai-erp",
    "project_resolved": true,
    "context_pack": {
        "summary": "找到 3 条项目知识、1 条共享知识",
        "project_context": [
            {
                "id": "uuid-1",
                "title": "订单查询 API 接口规范",
                "content": "...",
                "type": "api",
                "module": "订单管理",
                "scope": "project",
                "confidence": 0.9,
                "risk_level": "low",
                "tags": ["order", "query"],
                "source_evidence": {
                    "file": "OrderController.java",
                    "line": 45
                },
                "match_type": "keyword",
                "relevance_score": 0.92
            }
        ],
        "shared_context": [],
        "global_context": []
    },
    "total_found": 3,
    "search_method": "keyword",
    "fallback_activated": false
}
```

> `fallback_activated: true` 表示 vector search 不可用，仅返回 keyword search 结果。

---

### 5. propose_memory

**分类**：知识写入

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| project_id | string | 否* | null | 项目 ID |
| workspace_path | string | 否 | null | 用于自动 resolve |
| changed_files | list[string] | 否 | [] | 用于自动 resolve |
| title | string | 是 | - | 知识标题 |
| content | string | 是 | - | 知识内容 |
| type | string | 是 | - | 知识类型（见枚举） |
| module | string | 否 | "" | 所属模块 |
| tags | list[string] | 否 | [] | 标签列表 |
| confidence | number | 否 | 0.5 | AI 评估的置信度 |
| source_evidence | object | 否 | {} | 来源证据 |
| scope | string | 否 | "project" | project / shared / global |
| source_task_id | string | 否 | null | 关联任务 ID |

> *project_id 为可选，但必须提供 project_id / workspace_path / changed_files 之一

**返回示例（成功提交，待审核）**：
```json
{
    "memory_id": "uuid-xxx",
    "status": "pending_review",
    "index_status": "not_indexed",
    "risk_level": "low",
    "validation": {
        "passed": true,
        "warnings": [
            {
                "type": "similar_existing",
                "items": [
                    { "id": "uuid-yyy", "title": "订单模块事务管理规范", "similarity": 0.78 }
                ]
            }
        ]
    },
    "review_decision": {
        "auto_approved": false,
        "reason": "来源为 ai_inferred 且项目禁止 AI 自动批准",
        "required_reviewers": []
    }
}
```

**返回示例（blocked）**：
```json
{
    "memory_id": null,
    "status": "rejected",
    "validation": {
        "passed": false,
        "errors": [
            { "type": "blocked", "rule": "JDBC URL 含密码", "message": "内容包含明文数据库连接密码，已拒绝入库" }
        ]
    },
    "review_decision": {
        "auto_approved": false,
        "reason": "严重敏感信息 — blocked"
    }
}
```

---

### 6. list_memories

**分类**：知识查询

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| project_id | string | 是 | - | 项目 ID |
| status_filter | list[string] | 否 | ["approved","indexed"] | 状态过滤 |
| type | string | 否 | null | 知识类型过滤 |
| module | string | 否 | null | 模块过滤 |
| tag | string | 否 | null | 标签过滤 |
| limit | integer | 否 | 50 | 最大返回数 |
| offset | integer | 否 | 0 | 分页偏移 |

**返回示例**：
```json
{
    "memories": [
        {
            "id": "uuid-1",
            "title": "订单查询 API 接口规范",
            "type": "api",
            "module": "订单管理",
            "status": "approved",
            "index_status": "not_indexed",
            "confidence": 0.9,
            "risk_level": "low",
            "scope": "project",
            "created_at": "2026-05-01T10:00:00Z"
        }
    ],
    "total": 128,
    "limit": 50,
    "offset": 0
}
```

---

### 7. approve_memory

**分类**：知识治理

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| memory_id | string | 是 | 知识 ID |
| reviewer | string | 是 | 审核人标识 |
| comment | string | 否 | 审核意见 |
| confidence_override | number | 否 | 覆盖置信度 |

**约束**：只能对 status=candidate 或 pending_review 的知识执行

**返回示例**：
```json
{
    "memory_id": "uuid-xxx",
    "status": "approved",
    "index_status": "not_indexed",
    "reviewed_by": "zrw",
    "reviewed_at": "2026-05-02T10:00:00Z",
    "previous_status": "pending_review"
}
```

---

### 8. reject_memory

**分类**：知识治理

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| memory_id | string | 是 | 知识 ID |
| reviewer | string | 是 | 审核人标识 |
| reason | string | 是 | 拒绝原因 |

**约束**：只能对 status=candidate 或 pending_review 的知识执行（不能用于废弃已生效知识）

**返回示例**：
```json
{
    "memory_id": "uuid-xxx",
    "status": "rejected",
    "reviewed_by": "zrw",
    "reviewed_at": "2026-05-02T10:00:00Z",
    "previous_status": "pending_review"
}
```

---

### 9. deprecate_memory

**分类**：知识治理

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| memory_id | string | 是 | 知识 ID |
| reason | string | 是 | 废弃原因 |

**约束**：只能对 status=approved 或 indexed 的知识执行（不能用于拒绝候选知识）

**返回示例**：
```json
{
    "memory_id": "uuid-xxx",
    "status": "deprecated",
    "previous_status": "approved",
    "reason": "接口已重构，旧知识不再适用"
}
```

---
