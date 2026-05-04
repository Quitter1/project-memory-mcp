"""
Qdrant 连接检查 — 检查 qdrant-client、配置、连接、collection。

使用：
    python scripts/check_qdrant.py
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import _paths  # noqa: E402
_ = _paths.ensure_import_paths()


def main():
    print("=" * 50)
    print("  Qdrant 连接检查")
    print("=" * 50)

    # 1. qdrant-client
    try:
        import qdrant_client  # noqa: F401
        print("  [OK] qdrant-client 已安装")
    except ImportError:
        print("  [FAIL] qdrant-client 未安装，请 pip install qdrant-client")
        return 1

    # 2. server.yml
    import yaml
    config_dir, db_path = _paths.get_project_paths()
    yml = config_dir / "server.yml"
    if not yml.exists():
        print("  [FAIL] server.yml 不存在")
        return 1

    raw = yaml.safe_load(yml.read_text(encoding="utf-8"))
    qdrant_cfg = raw.get("qdrant", {}) if raw else {}
    embed_cfg = raw.get("embedding", {}) if raw else {}

    if not qdrant_cfg.get("enabled"):
        print("  [INFO] qdrant.enabled=false, 向量搜索未启用")
        print("  如需启用，修改 config/server.yml: qdrant.enabled=true")
        return 0

    print(f"  host={qdrant_cfg.get('host')} port={qdrant_cfg.get('http_port', 6333)}")
    print(f"  collection={qdrant_cfg.get('collection', 'project_memory_items')}")
    print(f"  embedding: provider={embed_cfg.get('provider')}, dim={embed_cfg.get('dim')}")

    # 3. 连接测试
    from qdrant_client import QdrantClient
    try:
        client = QdrantClient(
            host=qdrant_cfg.get("host", "127.0.0.1"),
            port=qdrant_cfg.get("http_port", 6333),
            timeout=qdrant_cfg.get("timeout_seconds", 10),
        )
        collections = client.get_collections()
        names = [c.name for c in collections.collections]
        collection_name = qdrant_cfg.get("collection", "project_memory_items")
        if collection_name in names:
            print(f"  [OK] collection '{collection_name}' 存在")
            info = client.get_collection(collection_name)
            print(f"    vector dim={info.config.params.vectors.size}")
        else:
            print(f"  [INFO] collection '{collection_name}' 尚未创建")
            print(f"  可用 collections: {names}")
    except Exception as exc:
        print(f"  [FAIL] Qdrant 连接失败: {exc}")
        print(f"  请确认 Qdrant 已在 {qdrant_cfg.get('host')}:{qdrant_cfg.get('http_port')} 启动")
        return 1

    print(f"\n{'=' * 50}")
    print("  Qdrant 连接检查通过")
    print(f"{'=' * 50}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
