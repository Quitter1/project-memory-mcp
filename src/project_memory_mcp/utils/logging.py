"""
日志配置 — MCP 规范要求日志写 stderr 或文件，不写 stdout。

Phase 6.3: RotatingFileHandler, request_id, 诊断日志。
"""

import sys
import logging
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    log_dir: Optional[Path] = None,
    level: str = "INFO",
    enable_file: bool = True,
) -> logging.Logger:
    """
    配置日志系统。

    - stderr handler: MCP 规范（stdout 由 JSON-RPC 独占）
    - 主日志文件: project-memory-mcp.log (RotatingFileHandler, 5MB x 5)
    - 错误日志: errors.log (只记录 ERROR+)
    """
    logger = logging.getLogger("project_memory_mcp")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # stderr handler — 仅 WARNING+
    stderr_h = logging.StreamHandler(sys.stderr)
    stderr_h.setLevel(logging.WARNING)
    stderr_h.setFormatter(formatter)
    logger.addHandler(stderr_h)

    # File handlers
    if enable_file and log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # 主日志
        main_h = RotatingFileHandler(
            log_dir / "project-memory-mcp.log",
            maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
        )
        main_h.setLevel(logging.DEBUG)
        main_h.setFormatter(formatter)
        logger.addHandler(main_h)

        # 错误日志
        err_h = RotatingFileHandler(
            log_dir / "errors.log",
            maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
        )
        err_h.setLevel(logging.ERROR)
        err_h.setFormatter(formatter)
        logger.addHandler(err_h)

        logger.info("logging initialized: log_dir=%s, level=%s", log_dir, level)

    return logger


def new_request_id() -> str:
    """生成短 request_id：req_ + UUID 前8位。"""
    return f"req_{uuid.uuid4().hex[:8]}"


def sanitize_for_log(value: str, max_len: int = 80) -> str:
    """截断字符串，用于日志安全记录。"""
    if not value:
        return ""
    if len(value) <= max_len:
        return value
    return value[:max_len] + "..."
