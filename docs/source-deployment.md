# 源码部署（空库）

从 GitHub zip 或 git clone 获取源码后在空电脑初始化。

## 步骤

```powershell
# 1. 解压或 clone 到目标目录
cd F:\project\project-memory-mcp

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 3. 初始化配置和空数据库
python scripts\bootstrap_empty.py
```

## 启动外部服务

### Qdrant

```powershell
.\qdrant\qdrant.exe
```

### Embedding Server

嵌入服务是独立仓库，按以下启动：

```powershell
cd F:\project\embedding_server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m embedding_server.main --config config.example.yml
```

## 检查

```powershell
cd F:\project\project-memory-mcp
.\.venv\Scripts\Activate.ps1

python scripts\check_embedding.py
python scripts\check_qdrant.py --warmup
python scripts\diagnose.py --vector-summary
python scripts\reindex_vectors.py --yes
```

## 空库说明

- 空库初始化后 `reindex_vectors.py --yes` 显示 `eligible=0` 是正常的。
- `eval_search.py --mode hybrid` 会失败，因为没有知识数据。
- 如需演示验证，先运行 `python scripts/seed_demo_data.py`。
- 演示数据需要 `config/projects.yml` 包含对应项目。
- 之后 `python scripts/eval_search.py --mode hybrid` 应能命中。

## Claude Code 接入

见 `docs/ClaudeCode接入配置.md`。

## 注意事项

- memory.db 是本机运行数据，不提交到 GitHub。
- Qdrant 索引由 `reindex_vectors.py` 重建。
- embedding_server 是独立仓库/独立服务。
- API Key 只通过环境变量，不写入配置文件。
- LLM Reviewer 默认关闭。
