"""LLM Reviewer JSON parse 测试。"""

from project_memory_mcp.llm.reviewer import _parse_llm_response, LLMReviewer, LLMReviewResult
from project_memory_mcp.llm.config import LLMReviewerConfig


def test_parse_valid_json():
    result = _parse_llm_response('{"decision":"approve","confidence":0.9,"risk_level":"low"}')
    assert result.decision == "approve"
    assert result.confidence == 0.9


def test_parse_json_in_code_block():
    result = _parse_llm_response('```json\n{"decision":"pending_review","confidence":0.5}\n```')
    assert result.decision == "pending_review"


def test_parse_fallback_to_pending_on_invalid():
    result = _parse_llm_response("not json at all")
    assert result.decision == "pending_review"
    assert "json_parse_failed" in result.error


def test_illegal_decision_defaults():
    result = _parse_llm_response('{"decision":"approve_everything","confidence":1.5}')
    assert result.decision == "pending_review"


def test_confidence_clamped():
    result = _parse_llm_response('{"decision":"approve","confidence":2.0}')
    assert result.confidence == 1.0


def test_confidence_negative_clamped():
    result = _parse_llm_response('{"decision":"approve","confidence":-0.5}')
    assert result.confidence == 0.0


def test_risk_level_invalid():
    result = _parse_llm_response('{"decision":"approve","risk_level":"critical"}')
    assert result.risk_level == "low"


def test_reasons_sanitized():
    long_reason = "r" * 400
    result = _parse_llm_response(f'{{"decision":"approve","reasons":["{long_reason}","y","z","a","b","c"]}}')
    assert 1 <= len(result.reasons) <= 5


def test_suggested_tags_only_strings():
    result = _parse_llm_response('{"decision":"approve","suggested_tags":["a",123,"b"]}')
    assert "123" not in result.suggested_tags


def test_reviewer_disabled():
    cfg = LLMReviewerConfig(enabled=False)
    reviewer = LLMReviewer(cfg)
    result = reviewer.review({})
    assert result.decision == "pending_review"
    assert result.error == "llm_disabled"
