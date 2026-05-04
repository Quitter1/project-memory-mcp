"""LLM Reviewer config 测试 — env override, API Key isolation。"""

import os
import pytest
from project_memory_mcp.llm.config import LLMReviewerConfig


def test_default_disabled():
    cfg = LLMReviewerConfig()
    assert cfg.enabled is False
    assert cfg.is_configured() is False


def test_env_override_enabled(monkeypatch):
    monkeypatch.setenv("PROJECT_MEMORY_LLM_REVIEWER_ENABLED", "1")
    cfg = LLMReviewerConfig.from_server_config({})
    assert cfg.enabled is True


def test_env_override_disabled(monkeypatch):
    monkeypatch.setenv("PROJECT_MEMORY_LLM_REVIEWER_ENABLED", "0")
    cfg = LLMReviewerConfig.from_server_config({"llm_reviewer": {"enabled": True}})
    assert cfg.enabled is False


def test_env_override_true(monkeypatch):
    monkeypatch.setenv("PROJECT_MEMORY_LLM_REVIEWER_ENABLED", "true")
    cfg = LLMReviewerConfig.from_server_config({})
    assert cfg.enabled is True


def test_api_key_from_env_only(monkeypatch):
    monkeypatch.setenv("PROJECT_MEMORY_LLM_API_KEY", "sk-test-12345")
    cfg = LLMReviewerConfig.from_server_config({
        "llm_reviewer": {"enabled": True}
    })
    assert cfg.api_key == "sk-test-12345"
    # repr should not leak
    assert "sk-test" not in repr(cfg)


def test_not_configured_without_key():
    cfg = LLMReviewerConfig(enabled=True, model="gpt-4")
    assert cfg.is_configured() is False


def test_configured_with_all(monkeypatch):
    monkeypatch.setenv("PROJECT_MEMORY_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PROJECT_MEMORY_LLM_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("PROJECT_MEMORY_LLM_MODEL", "test-model")
    cfg = LLMReviewerConfig(enabled=True)
    cfg.api_key = "sk-test"
    cfg.base_url = "https://api.example.com/v1"
    cfg.model = "test-model"
    assert cfg.is_configured() is True
