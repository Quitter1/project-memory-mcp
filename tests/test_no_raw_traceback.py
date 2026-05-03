"""
静态检查 — src/project_memory_mcp/ 下不允许出现直接 print traceback 或 logger.exception。

CLI 脚本（scripts/）中的 print 不受此限制。
"""

from pathlib import Path

_SRC = Path(__file__).parent.parent / "src" / "project_memory_mcp"

_FORBIDDEN = [
    "traceback.format_exc(",
    'print(...file=sys.stderr',
    "logger.exception(",
]


def test_no_traceback_in_tools():
    """tools/ 目录下不允许 traceback.format_exc / print stderr / logger.exception。"""
    tools_dir = _SRC / "tools"
    for f in tools_dir.glob("*.py"):
        content = f.read_text(encoding="utf-8")
        for pattern in _FORBIDDEN:
            assert pattern not in content, f"{f.name}: 包含禁止的模式 {pattern}"


def test_no_traceback_in_server():
    """server.py 不允许 traceback.format_exc / logger.exception。"""
    f = _SRC / "server.py"
    content = f.read_text(encoding="utf-8")
    for pattern in _FORBIDDEN:
        assert pattern not in content, f"server.py: 包含禁止的模式 {pattern}"


def test_no_traceback_in_knowledge():
    """knowledge/ 目录下不允许 traceback.format_exc / logger.exception。"""
    kd = _SRC / "knowledge"
    for f in kd.glob("*.py"):
        content = f.read_text(encoding="utf-8")
        for pattern in _FORBIDDEN:
            assert pattern not in content, f"{f.name}: 包含禁止的模式 {pattern}"
