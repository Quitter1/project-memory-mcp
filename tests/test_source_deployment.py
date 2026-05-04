"""
源码部署准备检查 — example configs, bootstrap, .gitignore, docs。
"""

from pathlib import Path

_PROJECT = Path(__file__).parent.parent


def test_gitignore_excludes_data_db():
    gi = (_PROJECT / ".gitignore").read_text(encoding="utf-8")
    assert "data/" in gi
    assert "*.db" in gi


def test_gitignore_excludes_venv():
    gi = (_PROJECT / ".gitignore").read_text(encoding="utf-8")
    assert ".venv" in gi


def test_gitignore_excludes_logs_backups():
    gi = (_PROJECT / ".gitignore").read_text(encoding="utf-8")
    assert "logs/" in gi
    assert "backups/" in gi


def test_gitignore_excludes_reviews():
    gi = (_PROJECT / ".gitignore").read_text(encoding="utf-8")
    assert "reviews/" in gi


def test_server_example_exists():
    assert (_PROJECT / "config" / "server.example.yml").exists()


def test_projects_example_exists():
    assert (_PROJECT / "config" / "projects.example.yml").exists()


def test_bootstrap_script_exists():
    assert (_PROJECT / "scripts" / "bootstrap_empty.py").exists()


def test_source_deployment_doc_exists():
    assert (_PROJECT / "docs" / "source-deployment.md").exists()


def test_source_deploy_doc_mentions_empty_reindex():
    content = (_PROJECT / "docs" / "source-deployment.md").read_text(encoding="utf-8")
    assert "eligible=0" in content or "空库" in content


def test_source_deploy_doc_mentions_seed():
    content = (_PROJECT / "docs" / "source-deployment.md").read_text(encoding="utf-8")
    assert "seed_demo_data" in content


def test_bootstrap_preserves_existing(tmp_path, monkeypatch):
    """bootstrap 不覆盖已有配置。"""
    import sys
    sys.path.insert(0, str(_PROJECT))
    sys.path.insert(0, str(_PROJECT / "src"))

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "server.yml").write_text("# custom server config", encoding="utf-8")
    (config_dir / "projects.yml").write_text("# custom projects", encoding="utf-8")
    (config_dir / "server.example.yml").write_text("# example server", encoding="utf-8")
    (config_dir / "projects.example.yml").write_text("# example projects", encoding="utf-8")

    import subprocess, os
    r = subprocess.run(
        [sys.executable, str(_PROJECT / "scripts" / "bootstrap_empty.py")],
        cwd=str(tmp_path),
        capture_output=True, text=True,
    )
    assert "已存在，跳过" in r.stdout
    assert (config_dir / "server.yml").read_text() == "# custom server config"


def test_docs_no_api_key_value():
    content = (_PROJECT / "docs" / "source-deployment.md").read_text(encoding="utf-8")
    assert "sk-" not in content
