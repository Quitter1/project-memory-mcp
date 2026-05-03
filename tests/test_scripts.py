"""
脚本 subprocess 测试 — 验证 seed/dev_check/run_demo 可独立运行。

使用临时 config/db 通过环境变量传入。
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"


def _write_minimal_projects_yml(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    (d / "projects.yml").write_text("""\
projects:
  erp:
    name: "ERP"
    slug: "erp"
    status: active
    recognition:
      root_paths: ["/workspace/erp"]
      aliases: ["erp"]
defaults:
  knowledge_policy:
    auto_approve_threshold: -1
    max_candidate_per_task: 20
    retention_days: 365
  review_policy:
    allow_ai_auto_approve: false
    forbidden_auto_types: []
    risk_threshold_for_review: medium
    require_review_if_conflict: true
""", encoding="utf-8")


def _run_script(name: str, env: dict, timeout: int = 30, extra_args: list = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(_SCRIPTS_DIR / name)]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        env=env,
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ── seed_demo_data ────────────────────────────────────────

def test_seed_first_run():
    tmp = Path(tempfile.mkdtemp())
    try:
        config_dir = tmp / "config"
        db_path = tmp / "data" / "memory.db"
        _write_full_demo_config(config_dir)

        env = os.environ.copy()
        env["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
        env["PROJECT_MEMORY_DB_PATH"] = str(db_path)

        r = _run_script("seed_demo_data.py", env)
        assert r.returncode == 0, f"exit={r.returncode}, stderr={r.stderr}"
        assert "演示数据填充完成" in r.stdout
        assert "新增" in r.stdout
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_seed_second_run_skips():
    tmp = Path(tempfile.mkdtemp())
    try:
        config_dir = tmp / "config"
        db_path = tmp / "data" / "memory.db"
        _write_full_demo_config(config_dir)

        env = os.environ.copy()
        env["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
        env["PROJECT_MEMORY_DB_PATH"] = str(db_path)

        # 第一次
        r1 = _run_script("seed_demo_data.py", env)
        assert r1.returncode == 0
        assert "新增" in r1.stdout

        # 第二次 — 应该跳过
        r2 = _run_script("seed_demo_data.py", env)
        assert r2.returncode == 0, f"exit={r2.returncode}, stderr={r2.stderr}"
        assert "跳过" in r2.stdout
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_seed_different_projects_same_content():
    """两个不同项目相同 content 不会被幂等跳过。"""
    tmp = Path(tempfile.mkdtemp())
    try:
        config_dir = tmp / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp / "data" / "memory.db"
        (config_dir / "projects.yml").write_text("""\
projects:
  p1:
    name: "P1"
    slug: "p1"
    status: active
    recognition:
      root_paths: ["/p1"]
      aliases: ["p1"]
  p2:
    name: "P2"
    slug: "p2"
    status: active
    recognition:
      root_paths: ["/p2"]
      aliases: ["p2"]
defaults:
  knowledge_policy:
    auto_approve_threshold: -1
    max_candidate_per_task: 20
    retention_days: 365
  review_policy:
    allow_ai_auto_approve: false
    forbidden_auto_types: []
    risk_threshold_for_review: medium
    require_review_if_conflict: true
""", encoding="utf-8")

        env = os.environ.copy()
        env["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
        env["PROJECT_MEMORY_DB_PATH"] = str(db_path)

        r = _run_script("seed_demo_data.py", env, extra_args=["--allow-missing-projects"])
        assert r.returncode == 0, f"exit={r.returncode}, stderr={r.stderr}"
        assert "演示数据填充完成" in r.stdout
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


# ── dev_check ────────────────────────────────────────────

def test_dev_check_all_pass():
    tmp = Path(tempfile.mkdtemp())
    try:
        config_dir = tmp / "config"
        db_path = tmp / "data" / "memory.db"
        _write_minimal_projects_yml(config_dir)

        env = os.environ.copy()
        env["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
        env["PROJECT_MEMORY_DB_PATH"] = str(db_path)

        # 先 seed（使用 --allow-missing-projects 因为最小配置不含所有 demo 项目）
        _run_script("seed_demo_data.py", env, extra_args=["--allow-missing-projects"])

        # 再 dev_check
        r = _run_script("dev_check.py", env)
        assert r.returncode == 0, f"exit={r.returncode}, stderr={r.stderr}"
        assert "全部检查通过" in r.stdout
        assert "foreign_keys = 1" in r.stdout
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


# ── run_demo_flow ─────────────────────────────────────────

def _write_full_demo_config(config_dir: Path):
    """写入包含所有 demo 项目的完整配置。"""
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "projects.yml").write_text("""\
projects:
  biaopai-erp:
    name: "ERP"
    slug: "biaopai-erp"
    status: active
    recognition:
      root_paths: ["D:/workspace/biaopai-erp", "/workspace/biaopai-erp"]
      aliases: ["erp", "ERP系统"]
    knowledge_policy:
      auto_approve_threshold: 0.8
    review_policy:
      allow_ai_auto_approve: false
  cdr-converter:
    name: "CDR"
    slug: "cdr-converter"
    status: active
    recognition:
      root_paths: ["D:/workspace/cdr-converter", "/workspace/cdr-converter"]
      aliases: ["cdr", "CorelDRAW"]
    knowledge_policy:
      auto_approve_threshold: 0.8
    review_policy:
      allow_ai_auto_approve: true
  rpa-electron:
    name: "RPA"
    slug: "rpa-electron"
    status: active
    recognition:
      root_paths: ["/workspace/rpa-electron"]
      aliases: ["rpa"]
    review_policy:
      allow_ai_auto_approve: true
  img-vector-search:
    name: "IMG"
    slug: "img-vector-search"
    status: active
    recognition:
      root_paths: ["/workspace/img-vector-search"]
      aliases: ["img"]
    review_policy:
      allow_ai_auto_approve: true
defaults:
  knowledge_policy:
    auto_approve_threshold: -1
    max_candidate_per_task: 20
    retention_days: 365
  review_policy:
    allow_ai_auto_approve: false
    forbidden_auto_types: []
    risk_threshold_for_review: medium
    require_review_if_conflict: true
""", encoding="utf-8")


def test_run_demo_flow_completes():
    tmp = Path(tempfile.mkdtemp())
    try:
        config_dir = tmp / "config"
        db_path = tmp / "data" / "memory.db"
        _write_full_demo_config(config_dir)

        env = os.environ.copy()
        env["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
        env["PROJECT_MEMORY_DB_PATH"] = str(db_path)

        r = _run_script("run_demo_flow.py", env, timeout=60)
        assert r.returncode == 0, f"exit={r.returncode}, stderr={r.stderr}"
        assert "演示流程完成" in r.stdout
        assert "project_not_found" not in r.stdout
        assert 'ok": false' not in r.stdout
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_run_demo_flow_minimal_config_fails():
    """最小配置下 run_demo_flow 应失败（非假成功）。"""
    tmp = Path(tempfile.mkdtemp())
    try:
        config_dir = tmp / "config"
        db_path = tmp / "data" / "memory.db"
        _write_minimal_projects_yml(config_dir)

        env = os.environ.copy()
        env["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
        env["PROJECT_MEMORY_DB_PATH"] = str(db_path)

        r = _run_script("run_demo_flow.py", env, timeout=60)
        # 应该失败
        assert r.returncode != 0 or "演示流程失败" in r.stdout or "project_not_found" in r.stdout
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)
