"""
静态检查 — MCP server/tools/knowledge 层不允许 print / traceback / logger.exception。

使用 AST 扫描，不依赖脆弱的文本匹配。
"""

import ast
from pathlib import Path

_SRC = Path(__file__).parent.parent / "src" / "project_memory_mcp"


def _scan_file(filepath: Path) -> list[str]:
    """返回文件中违规项的列表。"""
    issues: list[str] = []
    tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath.name))

    for node in ast.walk(tree):
        # 检测 print() 调用
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                issues.append(f"line {node.lineno}: print() — MCP 层禁止 print，请使用 logger")
            # 检测 traceback.format_exc()
            if isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "traceback"
                    and node.func.attr == "format_exc"
                ):
                    issues.append(f"line {node.lineno}: traceback.format_exc() — 禁止")
            # 检测 logger.exception() / logging.exception()
            if isinstance(node.func, ast.Attribute) and node.func.attr == "exception":
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id in ("logger", "logging"):
                        issues.append(f"line {node.lineno}: logger.exception() — 禁止，请使用 logger.error")

    return issues


def test_no_print_in_server():
    issues = _scan_file(_SRC / "server.py")
    assert not issues, f"server.py: {issues}"


def test_no_print_in_tools():
    for f in sorted((_SRC / "tools").glob("*.py")):
        issues = _scan_file(f)
        assert not issues, f"{f.name}: {issues}"


def test_no_forbidden_in_knowledge():
    for f in sorted((_SRC / "knowledge").glob("*.py")):
        issues = _scan_file(f)
        assert not issues, f"{f.name}: {issues}"
