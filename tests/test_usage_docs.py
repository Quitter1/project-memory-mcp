"""
使用文档存在性 + 内容关键规则检查。
"""

from pathlib import Path

_DOCS = Path(__file__).parent.parent / "docs"
_PROMPTS = _DOCS / "prompts"

_REQUIRED_DOCS = [
    "claude-code-memory-workflow.md",
    "memory-review-guide.md",
    "claude-code-mcp-setup.md",
]

_REQUIRED_PROMPTS = [
    "task-start-search.md",
    "task-end-memory-proposal.md",
    "review-pending-memory.md",
]


def test_docs_exist():
    for name in _REQUIRED_DOCS:
        assert (_DOCS / name).exists(), f"缺少文档: docs/{name}"


def test_prompts_exist():
    for name in _REQUIRED_PROMPTS:
        assert (_PROMPTS / name).exists(), f"缺少提示词: docs/prompts/{name}"


def test_workflow_forbids_auto_propose():
    content = (_DOCS / "claude-code-memory-workflow.md").read_text(encoding="utf-8")
    assert "不允许自动 propose_memory" in content or "默认不允许自动" in content


def test_workflow_mentions_cc_test():
    content = (_DOCS / "claude-code-memory-workflow.md").read_text(encoding="utf-8")
    assert "[CC_TEST]" in content


def test_prompt_list_only():
    content = (_PROMPTS / "task-end-memory-proposal.md").read_text(encoding="utf-8")
    assert "不要调用 propose_memory" in content or "只列候选" in content or "只列出候选项" in content


def test_review_guide_has_standards():
    content = (_DOCS / "memory-review-guide.md").read_text(encoding="utf-8")
    assert "可 approve" in content or "可以 approve" in content
    assert "应 reject" in content or "应该 reject" in content
