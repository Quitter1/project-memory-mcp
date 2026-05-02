"""配置加载测试 — 验证 projects.yml, defaults 合并, 错误处理, 字段校验。"""

import os
import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.config.loader import ConfigLoader, ConfigError
from project_memory_mcp.config.schema import ProjectConfig


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def tmp_config_dir():
    """创建临时配置目录。"""
    with tempfile.TemporaryDirectory() as td:
        yield td


def _write_yaml(config_dir: str, filename: str, content: str):
    """写入临时 YAML 文件。"""
    path = Path(config_dir) / filename
    path.write_text(content, encoding="utf-8")


def _make_proj(overrides: str) -> str:
    """构造包含项目的 YAML 模板。"""
    return f"""
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      root_paths: ["D:/test"]
      tech_stack_keywords: ["python"]
    {overrides}
"""


# ------------------------------------------------------------------
# 测试：正常加载
# ------------------------------------------------------------------

def test_01_load_projects_normal(tmp_config_dir):
    """projects.yml 正常加载。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
projects:
  test-proj:
    name: "测试项目"
    slug: "test-proj"
    status: active
    recognition:
      root_paths:
        - "D:/workspace/test"
      aliases: ["test"]
      tech_stack_keywords: ["python"]
""")
    loader = ConfigLoader(tmp_config_dir)
    projects = loader.load_all_projects()
    assert len(projects) == 1
    assert projects[0].id == "test-proj"
    assert projects[0].name == "测试项目"


def test_02_defaults_merged(tmp_config_dir):
    """defaults 合并成功 — 项目未定义的字段从 defaults 继承。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
defaults:
  knowledge_policy:
    auto_approve_threshold: -1
    max_candidate_per_task: 10
  review_policy:
    allow_ai_auto_approve: false

projects:
  test-proj:
    name: "测试项目"
    slug: "test-proj"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
    knowledge_policy:
      auto_approve_threshold: 0.9
""")
    loader = ConfigLoader(tmp_config_dir)
    projects = loader.load_all_projects()
    p = projects[0]

    # 项目级覆盖
    assert p.knowledge_policy.auto_approve_threshold == 0.9
    # defaults 继承
    assert p.knowledge_policy.max_candidate_per_task == 10
    assert p.review_policy.allow_ai_auto_approve is False


def test_03_missing_required_field(tmp_config_dir):
    """缺少必填字段时报错。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
projects:
  test-proj:
    name: "测试项目"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
""")
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="slug"):
        loader.load_all_projects()


def test_04_yaml_hash_stable(tmp_config_dir):
    """YAML hash 稳定 — 相同内容产生相同哈希。"""
    content = """
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
"""
    _write_yaml(tmp_config_dir, "projects.yml", content)
    loader = ConfigLoader(tmp_config_dir)
    h1 = loader.compute_yaml_hash()
    h2 = loader.compute_yaml_hash()
    assert h1 == h2
    assert len(h1) == 64  # SHA256


def test_05_empty_projects(tmp_config_dir):
    """空 projects 段报错。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
projects: {}
""")
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="没有定义任何项目"):
        loader.load_all_projects()


def test_06_list_active_projects(tmp_config_dir):
    """list_active_projects 过滤正确。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
projects:
  active-proj:
    name: "活跃"
    slug: "active-proj"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
  archived-proj:
    name: "归档"
    slug: "archived-proj"
    status: archived
    recognition:
      tech_stack_keywords: ["java"]
""")
    loader = ConfigLoader(tmp_config_dir)
    active = loader.list_active_projects()
    assert len(active) == 1
    assert active[0].id == "active-proj"


def test_07_invalid_yaml(tmp_config_dir):
    """YAML 格式错误时给出清晰错误。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
projects:
  - bad: list: not: valid: yaml
    ::::
""")
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises((ConfigError, Exception)):
        loader.load_all_projects()


def test_08_unknown_fields_tolerated(tmp_config_dir):
    """未知字段不引发错误（向前兼容）。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
    unknown_future_field: "should be ignored"
""")
    loader = ConfigLoader(tmp_config_dir)
    projects = loader.load_all_projects()
    assert len(projects) == 1
    assert projects[0].id == "test-proj"


# ------------------------------------------------------------------
# Phase 2.6 新增：字段校验测试
# ------------------------------------------------------------------

def test_09_invalid_status(tmp_config_dir):
    """status 不是 active/archived/disabled 时报错。"""
    _write_yaml(tmp_config_dir, "projects.yml", _make_proj("status: invalid_status_value"))
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="status"):
        loader.load_all_projects()


def test_10_root_paths_not_list(tmp_config_dir):
    """root_paths 不是 list 时报错。"""
    content = _make_proj("")
    content = content.replace('root_paths: ["D:/test"]', "root_paths: not_a_list")
    _write_yaml(tmp_config_dir, "projects.yml", content)
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="root_paths"):
        loader.load_all_projects()


def test_11_aliases_not_list(tmp_config_dir):
    """aliases 不是 list 时报错。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      root_paths: ["D:/test"]
      aliases: not_a_list
      tech_stack_keywords: ["python"]
""")
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="aliases"):
        loader.load_all_projects()


def test_12_auto_approve_not_number(tmp_config_dir):
    """auto_approve_threshold 不是数字时报错。"""
    _write_yaml(tmp_config_dir, "projects.yml", _make_proj(
        "knowledge_policy:\n        auto_approve_threshold: \"high\""
    ))
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="auto_approve_threshold"):
        loader.load_all_projects()


def test_13_max_candidate_not_int(tmp_config_dir):
    """max_candidate_per_task 不是整数时报错。"""
    _write_yaml(tmp_config_dir, "projects.yml", _make_proj(
        "knowledge_policy:\n        max_candidate_per_task: \"many\""
    ))
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="max_candidate_per_task"):
        loader.load_all_projects()


def test_14_risk_threshold_invalid(tmp_config_dir):
    """risk_threshold_for_review 非法时报错。"""
    _write_yaml(tmp_config_dir, "projects.yml", _make_proj(
        "review_policy:\n        risk_threshold_for_review: extreme"
    ))
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="risk_threshold_for_review"):
        loader.load_all_projects()


def test_15_allow_ai_not_bool(tmp_config_dir):
    """allow_ai_auto_approve 不是 bool 时报错。"""
    _write_yaml(tmp_config_dir, "projects.yml", _make_proj(
        "review_policy:\n        allow_ai_auto_approve: \"yes\""
    ))
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="allow_ai_auto_approve"):
        loader.load_all_projects()


# ------------------------------------------------------------------
# Phase 2.7 新增：defaults 校验 + bool 排除 + 合并后校验
# ------------------------------------------------------------------

def test_16_defaults_auto_approve_string(tmp_config_dir):
    """defaults.auto_approve_threshold 是字符串时报 ConfigError。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
defaults:
  knowledge_policy:
    auto_approve_threshold: "high"
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
""")
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="defaults.knowledge_policy.auto_approve_threshold"):
        loader.load_all_projects()


def test_17_defaults_allow_ai_string(tmp_config_dir):
    """defaults.allow_ai_auto_approve 是字符串时报 ConfigError。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
defaults:
  review_policy:
    allow_ai_auto_approve: "yes"
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
""")
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="defaults.review_policy.allow_ai_auto_approve"):
        loader.load_all_projects()


def test_18_project_auto_approve_bool(tmp_config_dir):
    """project.auto_approve_threshold: true 报 ConfigError（bool 不是数字）。"""
    _write_yaml(tmp_config_dir, "projects.yml", _make_proj(
        "knowledge_policy:\n        auto_approve_threshold: true"
    ))
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="auto_approve_threshold"):
        loader.load_all_projects()


def test_19_project_max_candidate_bool(tmp_config_dir):
    """project.max_candidate_per_task: true 报 ConfigError。"""
    _write_yaml(tmp_config_dir, "projects.yml", _make_proj(
        "knowledge_policy:\n        max_candidate_per_task: true"
    ))
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="max_candidate_per_task"):
        loader.load_all_projects()


def test_20_defaults_risk_threshold_invalid(tmp_config_dir):
    """defaults 中 risk_threshold_for_review 非法时报 ConfigError。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
defaults:
  review_policy:
    risk_threshold_for_review: extreme
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
""")
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="defaults.review_policy.risk_threshold_for_review"):
        loader.load_all_projects()


def test_21_defaults_forbidden_types_not_list(tmp_config_dir):
    """defaults 中 forbidden_auto_types 不是 list 时报 ConfigError。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
defaults:
  review_policy:
    forbidden_auto_types: not_a_list
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
""")
    loader = ConfigLoader(tmp_config_dir)
    with pytest.raises(ConfigError, match="defaults.review_policy.forbidden_auto_types"):
        loader.load_all_projects()


def test_22_merged_config_types_correct(tmp_config_dir):
    """合并 defaults 后 ProjectConfig 类型正确。"""
    _write_yaml(tmp_config_dir, "projects.yml", """
defaults:
  knowledge_policy:
    auto_approve_threshold: 0.8
    max_candidate_per_task: 15
  review_policy:
    allow_ai_auto_approve: false
    risk_threshold_for_review: high
projects:
  test-proj:
    name: "测试"
    slug: "test-proj"
    status: active
    recognition:
      tech_stack_keywords: ["python"]
""")
    loader = ConfigLoader(tmp_config_dir)
    projects = loader.load_all_projects()
    p = projects[0]
    assert p.knowledge_policy.auto_approve_threshold == 0.8
    assert p.knowledge_policy.max_candidate_per_task == 15
    assert isinstance(p.knowledge_policy.auto_approve_threshold, float)
    assert isinstance(p.knowledge_policy.max_candidate_per_task, int)
    assert p.review_policy.allow_ai_auto_approve is False
    assert p.review_policy.risk_threshold_for_review == "high"
