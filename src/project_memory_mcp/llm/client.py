"""LLM client — OpenAI-compatible chat completions，不记录 API Key / prompt 原文。"""

import json
import logging
from .config import LLMReviewerConfig

logger = logging.getLogger("project_memory_mcp")


class LLMClientError(Exception):
    pass


class LLMClientNotConfigured(LLMClientError):
    pass


class LLMClient:
    def __init__(self, config: LLMReviewerConfig):
        self.config = config

    def _check(self):
        if not self.config.is_configured():
            raise LLMClientNotConfigured("llm_not_configured")

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        self._check()
        try:
            import httpx
        except ImportError:
            raise LLMClientError("httpx not installed")

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
        }

        last_err = None
        for attempt in range(self.config.max_retries + 1):
            try:
                with httpx.Client(timeout=self.config.timeout_seconds) as client:
                    resp = client.post(
                        url,
                        json=body,
                        headers={
                            "Authorization": f"Bearer {self.config.api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info(
                        "llm_client_done model=%s prompt_len=%d resp_len=%d attempt=%d",
                        self.config.model, len(user_prompt), len(content), attempt,
                    )
                    return content
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "llm_client_retry attempt=%d exc_type=%s", attempt, type(exc).__name__,
                )

        raise LLMClientError(f"llm_client_failed after retries: {type(last_err).__name__}") from last_err
