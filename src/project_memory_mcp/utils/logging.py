"""日志配置 — MCP 规范要求日志写 stderr 或文件，不写 stdout。"""

import sys
import logging


def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """
    配置日志系统。
    - stderr handler：MCP 规范（stdout 由 JSON-RPC 独占）
    - file handler：持久化日志（可选）
    """
    logger = logging.getLogger("project_memory_mcp")
    logger.setLevel(getattr(logging, level.upper()))

    # stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)  # stderr 只输出 WARNING+
    stderr_fmt = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    stderr_handler.setFormatter(stderr_fmt)
    logger.addHandler(stderr_handler)

    # File handler
    if log_file:
        from pathlib import Path
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

    return logger
