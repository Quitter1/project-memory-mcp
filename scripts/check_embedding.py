"""
Embedding provider 检查 — 显示配置、测试嵌入、诊断连通性。

使用：
    python scripts/check_embedding.py
    python scripts/check_embedding.py --text "商品图上传到页面"
"""

import argparse
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--text", default="test text for embedding check")
    args = p.parse_args()

    import yaml
    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext

    config_dir, db_path = _paths.get_project_paths()
    ctx = AppContext(config_dir=config_dir, db_path=db_path)

    yml = config_dir / "server.yml"
    raw = yaml.safe_load(yml.read_text(encoding="utf-8")) if yml.exists() else {}
    embed_cfg = raw.get("embedding", {}) if raw else {}

    print("=" * 50)
    print("  Embedding Provider 检查")
    print("=" * 50)
    print(f"  embedding.enabled = {embed_cfg.get('enabled', False)}")
    print(f"  provider = {embed_cfg.get('provider', 'hashing')}")
    print(f"  model = {embed_cfg.get('model', 'hashing-v1')}")
    print(f"  dim = {embed_cfg.get('dim', 512)}")

    if embed_cfg.get("provider") == "http":
        http_cfg = embed_cfg.get("http", {})
        print(f"  base_url = {http_cfg.get('base_url', 'http://127.0.0.1:8008')}")
        print(f"  endpoint = {http_cfg.get('endpoint', '/embed_text')}")
        try:
            import httpx
            with httpx.Client(timeout=3) as client:
                r = client.get(http_cfg.get("base_url", "http://127.0.0.1:8008"))
                print(f"  reachable = yes")
        except Exception:
            print(f"  reachable = no")

    if ctx.embedder is None:
        print("\n  嵌入器未初始化 (embedding.enabled=false?)")
    else:
        t0 = time.monotonic()
        vec = ctx.embedder.embed_text(args.text)
        elapsed = (time.monotonic() - t0) * 1000

        norm = sum(v * v for v in vec) ** 0.5
        print(f"\n  test_text_len = {len(args.text)}")
        print(f"  test_vector_dim = {len(vec)}")
        print(f"  norm = {norm:.4f}")
        print(f"  first_5 = {[round(v, 6) for v in vec[:5]]}")
        print(f"  elapsed_ms = {elapsed:.0f}")

    ctx.db.close()
    print(f"\n{'=' * 50}")
    print("  检查完成")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
