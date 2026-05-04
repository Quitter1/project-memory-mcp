"""
LLM Reviewer 检查 — 检查配置、环境变量、连接。

使用：
    python scripts/check_llm_reviewer.py
    python scripts/check_llm_reviewer.py --dry-run
"""

import argparse
import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="忽略 server.yml enabled=false")
    args = p.parse_args()

    import yaml
    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.llm.config import LLMReviewerConfig

    config_dir, db_path = _paths.get_project_paths()
    yml = config_dir / "server.yml"
    raw = yaml.safe_load(yml.read_text(encoding="utf-8")) if yml.exists() else {}
    cfg = LLMReviewerConfig.from_server_config(raw)

    print("=" * 50)
    print("  LLM Reviewer 检查")
    print("=" * 50)
    print(f"  enabled = {cfg.enabled}")
    print(f"  provider = {cfg.provider}")
    print(f"  model = {cfg.model or '(未设置)'}")
    print(f"  base_url host = {cfg.base_url.split('/')[2] if cfg.base_url and '/' in cfg.base_url else cfg.base_url or '(未设置)'}")
    print(f"  api_key_env = {'present' if os.environ.get('PROJECT_MEMORY_LLM_API_KEY') else 'missing'}")
    print(f"  configured = {cfg.is_configured()}")
    print(f"  timeout_seconds = {cfg.timeout_seconds}")
    print(f"  fail_mode = {cfg.fail_mode}")

    # --dry-run
    exit_code = 0
    can_dry_run = cfg.is_configured()
    if args.dry_run and not can_dry_run:
        if not cfg.enabled:
            print("\n  server.yml 中 llm_reviewer.enabled=false")
            print("  如需临时测试请设置环境变量: PROJECT_MEMORY_LLM_REVIEWER_ENABLED=1")
            print("  或使用: python scripts/check_llm_reviewer.py --dry-run --force")
        if args.force:
            cfg.enabled = True
            if cfg.is_configured():
                can_dry_run = True
        if not can_dry_run and args.force:
            print("\n  [FAIL] --force 后仍缺少必要环境变量")
            exit_code = 1

    if args.dry_run and can_dry_run:
        from project_memory_mcp.llm.client import LLMClient
        from project_memory_mcp.llm.prompts import build_system_prompt, build_user_prompt
        from project_memory_mcp.llm.reviewer import _parse_llm_response

        client = LLMClient(cfg)
        t0 = time.monotonic()
        proposal = {
            "project_id": "rpa-electron",
            "title": "Electron webview 图片上传应走主进程 IPC",
            "content": "在 Electron RPA 中，本地图片上传应由主进程负责",
            "type": "architecture",
            "source_type": "ai_inferred",
            "confidence": 0.7,
        }
        sp = build_system_prompt()
        up = build_user_prompt(proposal)
        try:
            raw = client.chat(sp, up)
            result = _parse_llm_response(raw)
            elapsed = (time.monotonic() - t0) * 1000
            print(f"\n  [dry-run] decision = {result.decision}")
            print(f"  confidence = {result.confidence}")
            print(f"  risk_level = {result.risk_level}")
            print(f"  reason_count = {len(result.reasons)}")
            print(f"  issue_count = {len(result.issues)}")
            print(f"  elapsed_ms = {elapsed:.0f}")
        except Exception as exc:
            print(f"\n  [dry-run] 失败: {type(exc).__name__}")
            exit_code = 1
    elif args.dry_run:
        print("\n  [dry-run] 跳过 — LLM Reviewer 未配置 (缺 API Key/Base URL/Model)")
        for env_name in ("PROJECT_MEMORY_LLM_API_KEY", "PROJECT_MEMORY_LLM_BASE_URL", "PROJECT_MEMORY_LLM_MODEL"):
            print(f"    {env_name} = {'present' if os.environ.get(env_name) else 'missing'}")

    print(f"\n{'=' * 50}")
    print("  检查完成")
    print(f"{'=' * 50}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
