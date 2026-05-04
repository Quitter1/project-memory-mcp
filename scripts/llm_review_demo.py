"""
LLM Reviewer 演示 — 使用固定 demo candidate 测试评审，不写库。

使用：
    python scripts/llm_review_demo.py --project rpa-electron
    python scripts/llm_review_demo.py --project rpa-electron --force
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
    p.add_argument("--project", default="rpa-electron")
    p.add_argument("--force", action="store_true", help="忽略 enabled=false 强制运行")
    args = p.parse_args()

    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.llm.config import LLMReviewerConfig
    from project_memory_mcp.llm.reviewer import LLMReviewer
    import yaml

    config_dir, db_path = _paths.get_project_paths()
    yml = config_dir / "server.yml"
    raw = yaml.safe_load(yml.read_text(encoding="utf-8")) if yml.exists() else {}
    cfg = LLMReviewerConfig.from_server_config(raw)

    if args.force and not cfg.enabled:
        cfg.enabled = True

    if not cfg.enabled:
        print("LLM Reviewer 未启用。")
        print("  设置环境变量: PROJECT_MEMORY_LLM_REVIEWER_ENABLED=1")
        print("  或使用: python scripts/llm_review_demo.py --project rpa-electron --force")
        return 1
    if not cfg.is_configured():
        print("LLM Reviewer 未配置 (缺 API Key/Base URL/Model)")
        import os
        for e in ("PROJECT_MEMORY_LLM_API_KEY", "PROJECT_MEMORY_LLM_BASE_URL", "PROJECT_MEMORY_LLM_MODEL"):
            print(f"  {e} = {'present' if os.environ.get(e) else 'missing'}")
        return 1

    reviewer = LLMReviewer(cfg)
    proposal = {
        "project_id": args.project,
        "title": "Electron webview 图片上传应走主进程 IPC",
        "content": "在 Electron RPA 中，本地图片上传应由主进程负责选择和校验文件，再把 base64 返回给渲染进程注入 file input。",
        "type": "architecture",
        "module": "image-upload",
        "source_type": "manual_input",
        "tags": ["Electron", "IPC", "webview"],
        "scope": "project",
        "confidence": 0.8,
        "risk_level": "low",
    }

    print("=" * 50)
    print("  LLM Reviewer Demo")
    print("=" * 50)
    print(f"  project = {args.project}")
    print(f"  title = {proposal['title']}")
    print(f"  provider = {cfg.provider}")
    print(f"  model = {cfg.model}")

    t0 = time.monotonic()
    result = reviewer.review(proposal)
    elapsed = (time.monotonic() - t0) * 1000

    print(f"\n  decision = {result.decision}")
    print(f"  confidence = {result.confidence}")
    print(f"  risk_level = {result.risk_level}")
    print(f"  reason_count = {len(result.reasons)}")
    print(f"  issue_count = {len(result.issues)}")
    if result.error:
        print(f"  error = {result.error}")
    print(f"  elapsed_ms = {elapsed:.0f}")
    print(f"\n{'=' * 50}")
    print("  Demo 完成")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    raise SystemExit(main() or 0)
