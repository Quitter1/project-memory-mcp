# 项目配置说明文档 — project-memory-mcp

## 概述

项目配置定义在 `config/projects.yml`，是 MCP 服务的**权威配置源**。

SQLite 中的 project 表是**运行时缓存**，由 `sync_projects` 命令从 YAML 同步。

## 配置文件结构

```yaml
projects:
  <project-id>:          # 项目唯一标识（slug 格式）
    name: ""             # 显示名称
    slug: ""             # URL 友好标识（与 project-id 一致）
    description: ""      # 项目描述
    status: active       # active | archived | disabled

    recognition:         # 项目识别配置
      root_paths: []     # 项目根目录（用于 workspace_path 匹配）
      path_patterns: []  # Glob 路径模式
      aliases: []        # 项目别名
      tech_stack_keywords: []  # 技术栈关键词
      module_keywords: []      # 模块关键词

    knowledge_policy:    # 知识策略
      default_confidence: 0.5
      auto_approve_threshold: -1   # -1 = 禁止自动批准
      max_candidate_per_task: 20
      retention_days: 365
      forbidden_content_patterns: []  # 项目级敏感信息额外规则

    review_policy:       # 审核策略
      allow_ai_auto_approve: false
      forbidden_auto_types: []
      risk_threshold_for_review: medium
      require_review_if_conflict: true

    metadata: {}         # 扩展元数据

defaults:                # 全局默认值
  knowledge_policy: {}
  review_policy: {}

sharing_rules:           # 共享知识规则
  global_require_review: true
  shared_require_review: true
  max_shared_projects: 10
  auto_deny_projects_on_conflict: true
```

## 字段说明

### project

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 项目显示名称 |
| slug | string | 是 | URL 友好标识，与 project-id 一致 |
| description | string | 否 | 项目简介 |
| status | string | 是 | active / archived / disabled |

### recognition

| 字段 | 类型 | 说明 |
|------|------|------|
| root_paths | list[string] | 项目根目录绝对路径 |
| path_patterns | list[string] | Glob 路径模式，用于匹配任意子目录 |
| aliases | list[string] | 项目别名、简称、中文名 |
| tech_stack_keywords | list[string] | 技术栈关键词（用于文本匹配） |
| module_keywords | list[string] | 模块关键词（用于文本匹配） |

### knowledge_policy

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| default_confidence | number | 0.5 | 新知识默认置信度 |
| auto_approve_threshold | number | -1 | 自动批准置信度阈值，-1=禁止 |
| max_candidate_per_task | integer | 20 | 单次任务最大候选数 |
| retention_days | integer | 365 | 知识保留天数 |
| forbidden_content_patterns | list[string] | [] | 项目级额外敏感信息正则 |

### review_policy

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| allow_ai_auto_approve | boolean | false | 是否允许 AI 来源自动批准 |
| forbidden_auto_types | list[string] | [] | 禁止自动批准的知识类型 |
| risk_threshold_for_review | string | "medium" | 超过此风险等级强制审核 |
| require_review_if_conflict | boolean | true | 存在冲突时是否强制审核 |

## 项目识别优先级

当 MCP 工具需要确定当前项目时，按以下优先级逐级尝试：

1. **显式 project_id**：工具参数中直接传入
2. **workspace_path 前缀匹配**：与各项目的 root_paths 做前缀比较
3. **changed_files 路径匹配**：与各项目的 root_paths 做前缀比较
4. **任务描述关键词打分**：
   - 别名匹配：+3 分
   - 技术栈关键词：+2 分
   - 模块关键词：+1 分
   - 最高分 > 5 且领先第二名 ≥ 2 分 → 匹配
5. **多匹配处理**：
   - `allow_multiple=false` → 返回 ambiguous 错误 + 候选列表
   - `allow_multiple=true` → 返回全部候选
6. **无匹配**：返回 unable_to_resolve_project 错误

## sync_projects 命令

```bash
python scripts/sync_projects.py
```

功能：
1. 读取 `config/projects.yml`
2. 对每个项目执行 UPSERT 到 SQLite projects 表
3. 计算 YAML 配置哈希存入 `yaml_hash`
4. 记录变更到 audit_log
5. 输出同步摘要

## MCP Server 启动检查

启动时自动执行：
1. 读取 YAML 配置哈希
2. 与 SQLite 中存储的 yaml_hash 对比
3. 不一致 → 写入 stderr 告警日志，提示执行 sync_projects
4. 不阻断启动（使用 SQLite 中最后同步的配置继续运行）

## 添加新项目

1. 在 `config/projects.yml` 的 `projects` 下添加新条目
2. 至少配置 `name`、`slug`、`recognition.root_paths`、`recognition.tech_stack_keywords`
3. 执行 `python scripts/sync_projects.py`
4. 重启 MCP server（或自动检测到配置变更）
5. 执行 `python scripts/seed_demo_data.py --project-id <new-project>` 填充初始数据（可选）
