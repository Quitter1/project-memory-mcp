"""
审核脚本测试 — review_memories.py / cleanup_test_memories.py。
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_SCRIPTS_DIR))


def _run(name: str, extra_args: str, env: dict, timeout: int = 30):
    return subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / name)] + extra_args.split(),
        env=env, cwd=str(_PROJECT_ROOT),
        capture_output=True, text=True, timeout=timeout,
    )


def _write_config(config_dir: Path):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "projects.yml").write_text("""\
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      root_paths: ["/test"]
      aliases: ["test"]
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


def _seed_pending(env, config_dir, db_path):
    """创建一条 pending_review 知识。"""
    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext
    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    ctx.sync_projects()
    from project_memory_mcp.models.memory_item import MemoryItem
    from project_memory_mcp.utils.hashing import compute_content_hash
    item = MemoryItem(
        id="", project_id="test-proj", type="other", title="测试审核知识",
        content="用于测试审核流程", content_hash=compute_content_hash("用于测试审核流程"),
        status="pending_review", scope="project", source_type="ai_inferred",
        confidence=0.5, risk_level="low",
    )
    created = ctx.memory_repo.create_memory(item, actor="test")
    ctx.db.close()
    return created.id


def _seed_test_knowledge(config_dir, db_path, title="[CC_TEST] 测试", tags=None, module_name="test", item_type="other"):
    """创建一条测试知识。"""
    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext
    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    ctx.sync_projects()
    from project_memory_mcp.models.memory_item import MemoryItem
    from project_memory_mcp.utils.hashing import compute_content_hash
    content = f"test content for {title}"
    item = MemoryItem(
        id="", project_id="test-proj", type=item_type, title=title,
        content=content, content_hash=compute_content_hash(content),
        status="pending_review", scope="project", source_type="ai_inferred",
        tags=tags or [], module=module_name, confidence=0.5, risk_level="low",
    )
    created = ctx.memory_repo.create_memory(item, actor="test")
    ctx.db.close()
    return created.id


@pytest.fixture
def env_with_db():
    tmp = Path(tempfile.mkdtemp())
    config_dir = tmp / "config"
    db_path = tmp / "data" / "memory.db"
    _write_config(config_dir)
    env = os.environ.copy()
    env["PROJECT_MEMORY_CONFIG_DIR"] = str(config_dir)
    env["PROJECT_MEMORY_DB_PATH"] = str(db_path)
    yield env, config_dir, db_path
    import shutil
    shutil.rmtree(str(tmp), ignore_errors=True)


def test_review_list(env_with_db):
    env, config_dir, db_path = env_with_db
    _seed_pending(env, config_dir, db_path)
    r = _run("review_memories.py", "list --status pending_review", env)
    assert r.returncode == 0, f"exit={r.returncode}\n{r.stderr}"
    assert "测试审核知识" in r.stdout


def test_review_show(env_with_db):
    env, config_dir, db_path = env_with_db
    mid = _seed_pending(env, config_dir, db_path)
    r = _run("review_memories.py", f"show --id {mid}", env)
    assert r.returncode == 0
    assert "测试审核知识" in r.stdout


def test_review_reject_no_yes_does_nothing(env_with_db):
    env, config_dir, db_path = env_with_db
    mid = _seed_pending(env, config_dir, db_path)
    r = _run("review_memories.py", f"reject --id {mid}", env)
    assert "DRY RUN" in r.stdout or "请加 --yes" in r.stdout


def test_review_reject_yes(env_with_db):
    env, config_dir, db_path = env_with_db
    mid = _seed_pending(env, config_dir, db_path)
    r = _run("review_memories.py", f"reject --id {mid} --yes", env)
    assert r.returncode == 0, f"exit={r.returncode}\n{r.stderr}"
    assert "reject" in r.stdout.lower()


def test_review_approve_yes(env_with_db):
    env, config_dir, db_path = env_with_db
    mid = _seed_pending(env, config_dir, db_path)
    r = _run("review_memories.py", f"approve --id {mid} --yes", env)
    assert r.returncode == 0, f"exit={r.returncode}\n{r.stderr}"


def test_review_invalid_id(env_with_db):
    r = _run("review_memories.py", "show --id nonexistent-id", env_with_db[0])
    assert r.returncode != 0


def test_cleanup_cc_test_title(env_with_db):
    env, config_dir, db_path = env_with_db
    _seed_test_knowledge(config_dir, db_path, title="[CC_TEST] title test")
    r = _run("cleanup_test_memories.py", "--dry-run", env)
    assert r.returncode == 0, f"exit={r.returncode}\n{r.stderr}"
    assert "CC_TEST" in r.stdout or "测试知识" in r.stdout or "发现" in r.stdout


def test_cleanup_tag_cc_test(env_with_db):
    env, config_dir, db_path = env_with_db
    _seed_test_knowledge(config_dir, db_path, title="测试", tags=["CC_TEST"])
    r = _run("cleanup_test_memories.py", "--dry-run", env)
    assert r.returncode == 0


def test_cleanup_type_test_module_mcp(env_with_db):
    env, config_dir, db_path = env_with_db
    _seed_test_knowledge(config_dir, db_path, title="mcp test", item_type="test", module_name="mcp")
    r = _run("cleanup_test_memories.py", "--dry-run", env)
    assert r.returncode == 0


def test_cleanup_reject_yes(env_with_db):
    env, config_dir, db_path = env_with_db
    _seed_test_knowledge(config_dir, db_path, title="[CC_TEST] reject test")
    r = _run("cleanup_test_memories.py", "--reject --yes", env)
    assert r.returncode == 0, f"exit={r.returncode}\n{r.stderr}"
    assert "已 reject" in r.stdout or "reject" in r.stdout.lower()


def test_cleanup_no_traceback(env_with_db):
    env, config_dir, db_path = env_with_db
    _seed_test_knowledge(config_dir, db_path, title="[CC_TEST] no tb")
    r = _run("cleanup_test_memories.py", "--dry-run", env)
    assert "Traceback" not in r.stdout
    assert "Traceback" not in r.stderr


def test_diagnose_review_summary(env_with_db):
    env, config_dir, db_path = env_with_db
    _seed_test_knowledge(config_dir, db_path, title="[CC_TEST] diag test")
    r = _run("diagnose.py", "--review-summary", env)
    assert r.returncode == 0, f"exit={r.returncode}\n{r.stderr}"
    assert "Traceback" not in r.stdout


def test_list_with_module_filter(env_with_db):
    env, config_dir, db_path = env_with_db
    _seed_test_knowledge(config_dir, db_path, title="module test A", module_name="mcp")
    _seed_test_knowledge(config_dir, db_path, title="module test B", module_name="order")
    r = _run("review_memories.py", "list --status pending_review --module mcp", env)
    assert "mcp" in r.stdout


def _seed_rejected_test(config_dir, db_path, title="[CC_TEST] rejected"):
    import sys
    sys.path.insert(0, str(_PROJECT_ROOT))
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))
    sys.path.insert(0, str(_SCRIPTS_DIR))
    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext
    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    ctx.sync_projects()
    from project_memory_mcp.models.memory_item import MemoryItem
    from project_memory_mcp.utils.hashing import compute_content_hash
    content = f"rejected test {title}"
    item = MemoryItem(
        id="", project_id="test-proj", type="other", title=title,
        content=content, content_hash=compute_content_hash(content),
        status="rejected", scope="project", source_type="ai_inferred",
        confidence=0.5, risk_level="low",
    )
    ctx.memory_repo.create_memory(item, actor="test")
    ctx.db.close()


def test_cleanup_rejected_shown_not_hidden(env_with_db):
    """rejected 测试知识存在时，dry-run 应显示"发现测试知识"而非"没有发现"。"""
    env, config_dir, db_path = env_with_db
    _seed_rejected_test(config_dir, db_path)
    r = _run("cleanup_test_memories.py", "--dry-run", env)
    assert r.returncode == 0
    assert "发现测试知识" in r.stdout
    assert "已跳过 rejected" in r.stdout


def test_cleanup_rejected_only_says_no_actionable(env_with_db):
    """只有 rejected 时不输出"没有发现测试知识"。"""
    env, config_dir, db_path = env_with_db
    _seed_rejected_test(config_dir, db_path)
    r = _run("cleanup_test_memories.py", "--dry-run", env)
    assert "没有发现测试知识" not in r.stdout
    assert "没有可处理" in r.stdout or "可处理: 0" in r.stdout


def test_cleanup_only_rejects_actionable(env_with_db):
    """--reject --yes 只拒绝 candidate/pending_review。"""
    env, config_dir, db_path = env_with_db
    _seed_rejected_test(config_dir, db_path)
    _seed_test_knowledge(config_dir, db_path, title="[CC_TEST] actionable")
    r = _run("cleanup_test_memories.py", "--reject --yes", env)
    assert r.returncode == 0
    # 应该只处理 1 条 (actionable)
    assert "处理完成: 1/1" in r.stdout or "可处理" in r.stdout


def test_cleanup_include_terminal(env_with_db):
    """--include-terminal 显示 rejected 测试知识列表。"""
    env, config_dir, db_path = env_with_db
    _seed_rejected_test(config_dir, db_path)
    r = _run("cleanup_test_memories.py", "--dry-run --include-terminal", env)
    assert r.returncode == 0
    assert "发现测试知识" in r.stdout


def test_cleanup_include_approved_shows_approved(env_with_db):
    """--include-approved 显示 approved 测试知识。"""
    env, config_dir, db_path = env_with_db
    # 需要先创建 approved 测试知识
    import sys
    sys.path.insert(0, str(_PROJECT_ROOT))
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))
    sys.path.insert(0, str(_SCRIPTS_DIR))
    import _paths
    _ = _paths.ensure_import_paths()
    from project_memory_mcp.app_context import AppContext
    ctx = AppContext(config_dir=config_dir, db_path=db_path)
    ctx.sync_projects()
    from project_memory_mcp.models.memory_item import MemoryItem
    from project_memory_mcp.utils.hashing import compute_content_hash
    item = MemoryItem(
        id="", project_id="test-proj", type="other", title="[CC_TEST] approved test",
        content="approved content", content_hash=compute_content_hash("approved content"),
        status="approved", scope="project", source_type="user_confirmed",
        confidence=0.9, risk_level="low",
    )
    ctx.memory_repo.create_memory(item, actor="test")
    ctx.db.close()

    r = _run("cleanup_test_memories.py", "--dry-run --include-approved", env)
    assert r.returncode == 0
    assert "发现测试知识" in r.stdout
