"""LLM Reviewer 配置 — 只读非敏感字段，API Key 永远不进此文件。"""

import os
from dataclasses import dataclass, field


@dataclass
class LLMReviewerConfig:
    enabled: bool = False
    provider: str = "deepseek"
    base_url: str = ""
    api_key: str = field(default="", repr=False)  # never logged
    model: str = ""
    timeout_seconds: int = 30
    max_retries: int = 1
    temperature: float = 0.0
    max_input_chars: int = 6000
    max_output_tokens: int = 800
    fail_mode: str = "pending_review"

    @classmethod
    def from_server_config(cls, server_yml: dict | None) -> "LLMReviewerConfig":
        cfg = (server_yml or {}).get("llm_reviewer", {}) or {}
        env_base = os.environ.get(cfg.get("base_url_env", "PROJECT_MEMORY_LLM_BASE_URL"), "")
        env_key = os.environ.get(cfg.get("api_key_env", "PROJECT_MEMORY_LLM_API_KEY"), "")
        env_model = os.environ.get(cfg.get("model_env", "PROJECT_MEMORY_LLM_MODEL"), "")

        enabled_val = cfg.get("enabled", False)
        env_enabled = os.environ.get("PROJECT_MEMORY_LLM_REVIEWER_ENABLED", "")
        if env_enabled.lower() in ("1", "true", "yes"):
            enabled_val = True
        elif env_enabled.lower() in ("0", "false", "no"):
            enabled_val = False

        return cls(
            enabled=enabled_val,
            provider=cfg.get("provider", "deepseek"),
            base_url=env_base or cfg.get("base_url", ""),
            api_key=env_key,
            model=env_model or cfg.get("model", ""),
            timeout_seconds=cfg.get("timeout_seconds", 30),
            max_retries=cfg.get("max_retries", 1),
            temperature=cfg.get("temperature", 0.0),
            max_input_chars=cfg.get("max_input_chars", 6000),
            max_output_tokens=cfg.get("max_output_tokens", 800),
            fail_mode=cfg.get("fail_mode", "pending_review"),
        )

    def is_configured(self) -> bool:
        return bool(self.enabled and self.api_key and self.model and self.base_url)
