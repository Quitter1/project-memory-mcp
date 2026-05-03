"""
日志配置 — MCP 规范要求日志写 stderr 或文件，不写 stdout。

Phase 6.4: 幂等初始化, redaction, AppContext 自动调用。
"""

import re
import sys
import logging
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_log_initialized = False

# 敏感信息 redaction 模式
_REDACT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), "sk-proj-[REDACTED]"),
    (re.compile(r"sk-svcacct-[A-Za-z0-9_-]{20,}"), "sk-svcacct-[REDACTED]"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "sk-ant-[REDACTED]"),
    (re.compile(r"sk-[a-z0-9]{32,}"), "sk-[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "sk-[REDACTED]"),
    (re.compile(r"OPENAI_API_KEY\s*[=:]\s*\S+", re.IGNORECASE), "OPENAI_API_KEY=[REDACTED]"),
    (re.compile(r"ANTHROPIC_API_KEY\s*[=:]\s*\S+", re.IGNORECASE), "ANTHROPIC_API_KEY=[REDACTED]"),
    (re.compile(r"DEEPSEEK_API_KEY\s*[=:]\s*\S+", re.IGNORECASE), "DEEPSEEK_API_KEY=[REDACTED]"),
    (re.compile(r"token\s*[=:]\s*\S{10,}", re.IGNORECASE), "token=[REDACTED]"),
    (re.compile(r"access[_-]?token\s*[=:]\s*\S{10,}", re.IGNORECASE), "access_token=[REDACTED]"),
    (re.compile(r"bearer\s+\S{10,}", re.IGNORECASE), "bearer [REDACTED]"),
    (re.compile(r"password\s*[=:]\s*\S{4,}", re.IGNORECASE), "password=[REDACTED]"),
    (re.compile(r"pwd\s*[=:]\s*\S{4,}", re.IGNORECASE), "pwd=[REDACTED]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA[REDACTED]"),
    (re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|ENCRYPTED) PRIVATE KEY-----"), "[REDACTED PRIVATE KEY]"),
]


def redact_sensitive(text: str) -> str:
    """对字符串做敏感信息脱敏，替换 sk-/token/password 等。"""
    if not text or not isinstance(text, str):
        return text
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_for_log(value: str, max_len: int = 80) -> str:
    """截断 + 脱敏。"""
    if not value:
        return ""
    redacted = redact_sensitive(value)
    if len(redacted) <= max_len:
        return redacted
    return redacted[:max_len] + "..."


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:8]}"


def setup_logging(
    log_dir: Optional[Path] = None,
    level: str = "INFO",
    enable_file: bool = True,
) -> logging.Logger:
    """幂等初始化日志（重复调用不叠加 handler）。"""
    global _log_initialized
    logger = logging.getLogger("project_memory_mcp")

    if _log_initialized:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # stderr — WARNING+
    stderr_h = logging.StreamHandler(sys.stderr)
    stderr_h.setLevel(logging.WARNING)
    stderr_h.setFormatter(formatter)
    logger.addHandler(stderr_h)

    # File handlers
    if enable_file and log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        main_h = RotatingFileHandler(
            log_dir / "project-memory-mcp.log",
            maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
        )
        main_h.setLevel(logging.DEBUG)
        main_h.setFormatter(formatter)
        logger.addHandler(main_h)

        err_h = RotatingFileHandler(
            log_dir / "errors.log",
            maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
        )
        err_h.setLevel(logging.ERROR)
        err_h.setFormatter(formatter)
        logger.addHandler(err_h)

    _log_initialized = True
    logger.info("logging initialized: log_dir=%s, level=%s", log_dir, level)
    return logger
