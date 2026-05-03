"""治理逻辑测试 — lifecycle, reviewer, deduplicator, governance 集成。

Phase 4.1 新增：
- rejected 终态测试
- manual_input 可信来源测试
- dedup 活跃状态过滤测试
- duplicate_rejected audit_log 测试
- 全字段安全校验测试
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from project_memory_mcp.db.connection import DatabaseConnection
from project_memory_mcp.db.memory_repo import MemoryRepository
from project_memory_mcp.db.project_repo import ProjectRepository
from project_memory_mcp.db.audit_repo import AuditRepository
from project_memory_mcp.models.project import Project
from project_memory_mcp.models.memory_item import MemoryItem
from project_memory_mcp.config.schema import (
    ProjectConfig, RecognitionConfig, KnowledgePolicyConfig, ReviewPolicyConfig,
)
from project_memory_mcp.knowledge.lifecycle import LifecycleManager, InvalidTransitionError
from project_memory_mcp.knowledge.reviewer import RuleBasedReviewer, ReviewDecision
from project_memory_mcp.knowledge.validator import ContentValidator
from project_memory_mcp.knowledge.deduplicator import Deduplicator
from project_memory_mcp.knowledge.governance import KnowledgeGovernance, GovernanceError
from project_memory_mcp.models.enums import KnowledgeStatus, IndexStatus, Scope, RiskLevel
from project_memory_mcp.utils.hashing import compute_content_hash


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    Path(path).unlink(missing_ok=True)
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def conn(db_path) -> sqlite3.Connection:
    db = DatabaseConnection(db_path)
    c = db.connect()
    yield c
    db.close()


@pytest.fixture
def memory_repo(conn) -> MemoryRepository:
    return MemoryRepository(conn)


@pytest.fixture
def project_repo(conn) -> ProjectRepository:
    return ProjectRepository(conn)


@pytest.fixture
def audit_repo(conn) -> AuditRepository:
    return AuditRepository(conn)


@pytest.fixture
def project_config() -> ProjectConfig:
    return ProjectConfig(
        id="test-project",
        name="测试项目",
        slug="test-project",
        status="active",
        recognition=RecognitionConfig(
            root_paths=["/test"],
            aliases=["test"],
        ),
        knowledge_policy=KnowledgePolicyConfig(
            default_confidence=0.5,
            auto_approve_threshold=0.8,
            max_candidate_per_task=20,
            retention_days=365,
        ),
        review_policy=ReviewPolicyConfig(
            allow_ai_auto_approve=False,
            forbidden_auto_types=["business_rule", "security_config"],
            risk_threshold_for_review="medium",
            require_review_if_conflict=True,
        ),
    )


@pytest.fixture
def auto_approve_project_config() -> ProjectConfig:
    return ProjectConfig(
        id="auto-project",
        name="自动批准项目",
        slug="auto-project",
        status="active",
        recognition=RecognitionConfig(root_paths=["/auto"], aliases=["auto"]),
        knowledge_policy=KnowledgePolicyConfig(
            auto_approve_threshold=0.7,
        ),
        review_policy=ReviewPolicyConfig(
            allow_ai_auto_approve=True,
            forbidden_auto_types=[],
        ),
    )


@pytest.fixture
def validator():
    return ContentValidator()


@pytest.fixture
def deduplicator(memory_repo):
    return Deduplicator(repo=memory_repo, vector_store=None, embedder=None)


@pytest.fixture
def reviewer():
    return RuleBasedReviewer()


@pytest.fixture
def governance(memory_repo, audit_repo, validator, deduplicator, reviewer):
    return KnowledgeGovernance(
        repo=memory_repo,
        audit=audit_repo,
        validator=validator,
        deduplicator=deduplicator,
        reviewer=reviewer,
    )


def _seed_project(project_repo, project_config):
    return project_repo.upsert_project(
        Project(
            id=project_config.id,
            name=project_config.name,
            slug=project_config.slug,
            status=project_config.status,
            root_paths=project_config.recognition.root_paths,
            aliases=project_config.recognition.aliases,
            auto_approve_threshold=project_config.knowledge_policy.auto_approve_threshold,
            review_policy={
                "allow_ai_auto_approve": project_config.review_policy.allow_ai_auto_approve,
                "forbidden_auto_types": project_config.review_policy.forbidden_auto_types,
                "risk_threshold_for_review": project_config.review_policy.risk_threshold_for_review,
                "require_review_if_conflict": project_config.review_policy.require_review_if_conflict,
            },
        ),
        actor="test",
    )


# ==================================================================
# LifecycleManager 测试
# ==================================================================

class TestLifecycle:
    """状态机转换测试。"""

    def test_01_valid_transition_candidate_to_pending(self):
        assert LifecycleManager.can_transition("candidate", "pending_review") is True

    def test_02_valid_transition_pending_to_approved(self):
        assert LifecycleManager.can_transition("pending_review", "approved") is True

    def test_03_valid_transition_approved_to_deprecated(self):
        assert LifecycleManager.can_transition("approved", "deprecated") is True

    def test_04_invalid_transition_raises(self):
        with pytest.raises(InvalidTransitionError, match="非法的状态转换"):
            LifecycleManager.validate_transition("approved", "candidate")

    def test_05_terminal_deprecated_no_transition(self):
        allowed = LifecycleManager.get_allowed_transitions("deprecated")
        assert allowed == set()

    def test_06_terminal_superseded_no_transition(self):
        allowed = LifecycleManager.get_allowed_transitions("superseded")
        assert allowed == set()

    def test_07_rejected_is_terminal(self):
        """Phase 4.1: rejected 是终态，不可再转换。"""
        allowed = LifecycleManager.get_allowed_transitions("rejected")
        assert allowed == set()
        assert LifecycleManager.is_terminal("rejected") is True

    def test_08_reviewable_statuses(self):
        assert LifecycleManager.is_reviewable("candidate") is True
        assert LifecycleManager.is_reviewable("pending_review") is True
        assert LifecycleManager.is_reviewable("approved") is False

    def test_09_deprecatable_statuses(self):
        assert LifecycleManager.is_deprecatable("approved") is True
        assert LifecycleManager.is_deprecatable("candidate") is False

    def test_10_index_transition_valid(self):
        assert LifecycleManager.can_transition_index("not_indexed", "indexed") is True
        assert LifecycleManager.can_transition_index("indexed", "stale") is True

    def test_11_index_transition_invalid(self):
        with pytest.raises(InvalidTransitionError, match="非法的索引状态转换"):
            LifecycleManager.validate_transition_index("indexed", "not_indexed")

    def test_12_initial_statuses(self):
        assert LifecycleManager.initial_status() == "candidate"
        assert LifecycleManager.initial_index_status() == "not_indexed"

    # ── Phase 4.1 新增: rejected 终态验证 ──

    def test_13_rejected_cannot_transition_to_candidate(self):
        """Phase 4.1: rejected → candidate 非法。"""
        assert LifecycleManager.can_transition("rejected", "candidate") is False
        with pytest.raises(InvalidTransitionError, match="非法的状态转换"):
            LifecycleManager.validate_transition("rejected", "candidate")

    def test_14_rejected_to_approved_raises(self):
        """Phase 4.1: rejected → approved 非法。"""
        with pytest.raises(InvalidTransitionError, match="非法的状态转换"):
            LifecycleManager.validate_transition("rejected", "approved")


# ==================================================================
# RuleBasedReviewer 测试
# ==================================================================

class TestReviewer:
    """多因素审批判定测试。"""

    def test_15_all_conditions_met_auto_approved(self, reviewer, auto_approve_project_config):
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "ai_inferred",
            "type": "architecture",
        }
        decision = reviewer.review(item, auto_approve_project_config)
        assert decision.auto_approved is True
        assert "满足全部" in decision.reason

    def test_16_scope_shared_no_auto_approve(self, reviewer, auto_approve_project_config):
        item = {
            "confidence": 0.9,
            "scope": "shared",
            "risk_level": "low",
            "source_type": "ai_inferred",
            "type": "architecture",
        }
        decision = reviewer.review(item, auto_approve_project_config)
        assert decision.auto_approved is False
        assert "shared" in decision.reason

    def test_17_scope_global_no_auto_approve(self, reviewer, auto_approve_project_config):
        item = {
            "confidence": 0.9,
            "scope": "global",
            "risk_level": "low",
            "source_type": "ai_inferred",
            "type": "architecture",
        }
        decision = reviewer.review(item, auto_approve_project_config)
        assert decision.auto_approved is False

    def test_18_risk_high_no_auto_approve(self, reviewer, auto_approve_project_config):
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "high",
            "source_type": "ai_inferred",
            "type": "architecture",
        }
        decision = reviewer.review(item, auto_approve_project_config)
        assert decision.auto_approved is False
        assert "high" in decision.reason

    def test_19_confidence_below_threshold(self, reviewer, auto_approve_project_config):
        item = {
            "confidence": 0.5,
            "scope": "project",
            "risk_level": "low",
            "source_type": "ai_inferred",
            "type": "architecture",
        }
        decision = reviewer.review(item, auto_approve_project_config)
        assert decision.auto_approved is False
        assert "confidence" in decision.reason

    def test_20_ai_source_disabled_no_auto_approve(self, reviewer, project_config):
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "ai_inferred",
            "type": "architecture",
        }
        decision = reviewer.review(item, project_config)
        assert decision.auto_approved is False
        assert "AI 来源" in decision.reason

    def test_21_user_confirmed_source_auto_approved(self, reviewer, project_config):
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "user_confirmed",
            "type": "architecture",
        }
        decision = reviewer.review(item, project_config)
        assert decision.auto_approved is True

    def test_22_code_verified_source_auto_approved(self, reviewer, project_config):
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "code_verified",
            "type": "architecture",
        }
        decision = reviewer.review(item, project_config)
        assert decision.auto_approved is True

    def test_23_forbidden_type_no_auto_approve(self, reviewer):
        config = ProjectConfig(
            id="test",
            name="test",
            slug="test",
            knowledge_policy=KnowledgePolicyConfig(
                auto_approve_threshold=0.7,
            ),
            review_policy=ReviewPolicyConfig(
                allow_ai_auto_approve=True,
                forbidden_auto_types=["business_rule"],
            ),
        )
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "ai_inferred",
            "type": "business_rule",
        }
        decision = reviewer.review(item, config)
        assert decision.auto_approved is False
        assert "forbidden_auto_types" in decision.reason

    def test_24_validation_failed_no_auto_approve(self, reviewer, auto_approve_project_config):
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "ai_inferred",
            "type": "architecture",
        }
        decision = reviewer.review(item, auto_approve_project_config, validation_passed=False)
        assert decision.auto_approved is False
        assert "安全校验" in decision.reason

    def test_25_has_duplicate_no_auto_approve(self, reviewer, auto_approve_project_config):
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "ai_inferred",
            "type": "architecture",
        }
        decision = reviewer.review(item, auto_approve_project_config, has_duplicate=True)
        assert decision.auto_approved is False
        assert "哈希冲突" in decision.reason

    # ── Phase 4.1 新增: manual_input 可信来源 ──

    def test_26_manual_input_source_auto_approved(self, reviewer, project_config):
        """manual_input 来源在默认配置下也可自动批准。"""
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "manual_input",
            "type": "architecture",
        }
        decision = reviewer.review(item, project_config)
        assert decision.auto_approved is True

    def test_27_manual_input_low_confidence_no_auto(self, reviewer, project_config):
        """manual_input 但 confidence 不足不自动批准。"""
        item = {
            "confidence": 0.5,
            "scope": "project",
            "risk_level": "low",
            "source_type": "manual_input",
            "type": "architecture",
        }
        decision = reviewer.review(item, project_config)
        assert decision.auto_approved is False

    def test_28_imported_doc_not_trusted(self, reviewer, auto_approve_project_config):
        """imported_doc 不在可信来源列表中。"""
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "imported_doc",
            "type": "architecture",
        }
        decision = reviewer.review(item, auto_approve_project_config)
        assert decision.auto_approved is False
        assert "可信来源" in decision.reason

    # ── Phase 4.2: auto_approve_threshold=-1 禁用自动批准 ──

    def test_29_threshold_neg1_user_confirmed_no_auto(self, reviewer):
        """threshold=-1 + user_confirmed + high confidence → 不自动批准。"""
        config = ProjectConfig(
            id="test",
            name="test",
            slug="test",
            knowledge_policy=KnowledgePolicyConfig(auto_approve_threshold=-1),
        )
        item = {
            "confidence": 0.95,
            "scope": "project",
            "risk_level": "low",
            "source_type": "user_confirmed",
            "type": "architecture",
        }
        decision = reviewer.review(item, config)
        assert decision.auto_approved is False
        assert "auto_approve_threshold" in decision.reason

    def test_30_threshold_neg1_manual_input_no_auto(self, reviewer):
        """threshold=-1 + manual_input + high confidence → 不自动批准。"""
        config = ProjectConfig(
            id="test",
            name="test",
            slug="test",
            knowledge_policy=KnowledgePolicyConfig(auto_approve_threshold=-1),
        )
        item = {
            "confidence": 0.95,
            "scope": "project",
            "risk_level": "low",
            "source_type": "manual_input",
            "type": "architecture",
        }
        decision = reviewer.review(item, config)
        assert decision.auto_approved is False

    def test_31_threshold_08_manual_input_conf09_auto(self, reviewer):
        """threshold=0.8 + manual_input + confidence=0.9 → 自动批准。"""
        config = ProjectConfig(
            id="test",
            name="test",
            slug="test",
            knowledge_policy=KnowledgePolicyConfig(auto_approve_threshold=0.8),
        )
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "manual_input",
            "type": "architecture",
        }
        decision = reviewer.review(item, config)
        assert decision.auto_approved is True

    def test_32_threshold_08_manual_input_conf07_no_auto(self, reviewer):
        """threshold=0.8 + manual_input + confidence=0.7 → 不自动批准。"""
        config = ProjectConfig(
            id="test",
            name="test",
            slug="test",
            knowledge_policy=KnowledgePolicyConfig(auto_approve_threshold=0.8),
        )
        item = {
            "confidence": 0.7,
            "scope": "project",
            "risk_level": "low",
            "source_type": "manual_input",
            "type": "architecture",
        }
        decision = reviewer.review(item, config)
        assert decision.auto_approved is False
        assert "confidence" in decision.reason


# ==================================================================
# KnowledgeGovernance 集成测试
# ==================================================================

class TestGovernancePropose:
    """propose_memory 完整流水线测试。"""

    def test_29_propose_normal_pending_review(
        self, governance, project_repo, project_config,
    ):
        """AI 来源 + 项目禁止 AI 自动批准 → pending_review。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title="订单查询接口规范",
            content="订单查询接口需要添加 @Transactional 注解确保事务一致性",
            project=project_config,
            knowledge_type="api",
            module="订单管理",
            tags=["order", "transaction"],
            confidence=0.7,
            source_type="ai_inferred",
            actor="claude-code",
        )
        assert result["status"] == "pending_review"
        assert result["review_decision"]["auto_approved"] is False
        assert result["memory_id"] != ""
        assert result["validation"]["passed"] is True
        assert result["validation"]["blocked"] is False

    def test_30_propose_auto_approved(
        self, governance, project_repo, auto_approve_project_config,
    ):
        """高置信度 + 允许 AI 自动批准 → approved。"""
        _seed_project(project_repo, auto_approve_project_config)
        result = governance.propose_memory(
            title="测试自动批准",
            content="这是一条高置信度的用户确认知识",
            project=auto_approve_project_config,
            knowledge_type="architecture",
            confidence=0.95,
            source_type="user_confirmed",
            actor="test-user",
        )
        assert result["status"] == "approved"
        assert result["review_decision"]["auto_approved"] is True

    def test_31_propose_blocked_sensitive(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """blocked 敏感信息 → rejected, 不保存原文, 但有 audit_log。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title="包含私钥的内容",
            content="-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...",
            project=project_config,
            confidence=0.9,
            actor="test-agent",
        )
        assert result["status"] == "rejected"
        assert result["memory_id"] == ""
        assert result["validation"]["blocked"] is True

        # 验证 audit_log 被写入
        logs = audit_repo.list_by_project_id(project_config.id)
        assert any("blocked" in (log["action"] or "") for log in logs)

    def test_32_propose_duplicate_rejected(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """哈希重复 → 拒绝 + duplicate_rejected audit_log。"""
        _seed_project(project_repo, project_config)

        content = "完全相同的知识内容，用于测试哈希去重功能"

        # 第一次提交
        result1 = governance.propose_memory(
            title="去重测试",
            content=content,
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )

        # 第二次提交相同内容
        result2 = governance.propose_memory(
            title="去重测试 2",
            content=content,
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )

        assert result2["status"] == "rejected"
        assert result2.get("dedup", {}).get("is_duplicate") is True

        # Phase 4.1: 验证 duplicate_rejected audit_log
        logs = audit_repo.list_by_project_id(project_config.id)
        dup_logs = [l for l in logs if l.get("action") == "duplicate_rejected"]
        assert len(dup_logs) >= 1
        assert "duplicate_of" in (dup_logs[0].get("new_value") or "")

    def test_33_propose_shared_always_pending_review(
        self, governance, project_repo, auto_approve_project_config,
    ):
        """shared scope 即使在允许自动批准的项目中也强制 pending_review。"""
        _seed_project(project_repo, auto_approve_project_config)
        result = governance.propose_memory(
            title="共享知识测试",
            content="跨项目共享的通用架构知识",
            project=auto_approve_project_config,
            scope="shared",
            allowed_projects=["project-a", "project-b"],
            confidence=0.95,
            source_type="user_confirmed",
            actor="test",
        )
        assert result["status"] == "pending_review"
        assert result["review_decision"]["auto_approved"] is False
        assert "shared" in result["review_decision"]["reason"]

    def test_34_propose_large_sql_warning_risk_high(
        self, governance, project_repo, project_config,
    ):
        """Phase 4.1: 大段 SQL 触发 warning → risk_level=high → pending_review。"""
        _seed_project(project_repo, project_config)
        sql = (
            "SELECT id, name, value, created_at, updated_at "
            "FROM orders WHERE status = 'active' "
            "AND type IN ('a', 'b', 'c') "
        ) * 8
        sql += " OR customer_id IN (SELECT id FROM customers WHERE region = 'CN')"
        assert len(sql) > 500
        result = governance.propose_memory(
            title="大段 SQL 查询",
            content=sql,
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )
        assert result["risk_level"] == "high"
        assert result["status"] == "pending_review"
        assert len(result["validation"]["warnings"]) >= 1

    # ── Phase 4.1 新增: 全字段安全校验 ──

    def test_35_sensitive_in_title_blocked(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """title 中包含敏感信息 → blocked。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title='api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"',
            content="安全的正文内容",
            project=project_config,
            actor="test",
        )
        assert result["status"] == "rejected"
        assert result["validation"]["blocked"] is True
        assert "title" in result["validation"].get("blocked_field", "")

    def test_36_sensitive_in_source_evidence_blocked(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """source_evidence 中包含敏感信息 → blocked。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title="安全的标题",
            content="安全的正文内容",
            project=project_config,
            source_evidence={
                "file": "config.py",
                "excerpt": 'secret_key = "super-secret-1234567890"',
            },
            actor="test",
        )
        assert result["status"] == "rejected"
        assert result["validation"]["blocked"] is True
        blocked_field = result["validation"].get("blocked_field", "")
        assert "source_evidence" in blocked_field

    def test_37_sensitive_in_tags_blocked(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """tags 中包含敏感信息 → blocked。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title="安全的标题",
            content="安全的正文内容",
            project=project_config,
            tags=["order", "AKIA1234567890ABCDEF"],
            actor="test",
        )
        assert result["status"] == "rejected"
        assert result["validation"]["blocked"] is True
        assert "tags" in result["validation"].get("blocked_field", "")

    def test_38_blocked_audit_safe_summary(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """blocked audit_log 仅含安全摘要，不含原始敏感内容。"""
        _seed_project(project_repo, project_config)
        sensitive_content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        governance.propose_memory(
            title="私钥知识",
            content=sensitive_content,
            project=project_config,
            actor="test-agent",
        )

        logs = audit_repo.list_by_project_id(project_config.id)
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1

        new_value = blocked_logs[0].get("new_value") or ""
        # 安全摘要应包含元信息但不含原始私钥正文
        assert "content_length" in new_value
        assert "blocked_reason" in new_value
        assert "blocked_field" in new_value
        assert "MIIEpA" not in new_value  # 私钥正文不应出现在 audit_log 中

    def test_39_duplicate_audit_safe_summary(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """duplicate_rejected audit_log 仅含安全摘要。"""
        _seed_project(project_repo, project_config)
        content = "用于测试重复审计日志安全摘要的知识内容"

        # 第一次提交
        governance.propose_memory(
            title="原始知识",
            content=content,
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )

        # 第二次提交（重复）
        governance.propose_memory(
            title="重复知识",
            content=content,
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )

        logs = audit_repo.list_by_project_id(project_config.id)
        dup_logs = [l for l in logs if l.get("action") == "duplicate_rejected"]
        assert len(dup_logs) >= 1

        new_value = dup_logs[0].get("new_value") or ""
        assert "duplicate_of" in new_value
        assert "content_length" in new_value

    # ── Phase 4.1 新增: dedup 活跃状态过滤 ──

    def test_40_dedup_ignores_rejected(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """rejected 状态的知识不阻止相同内容再次提交。"""
        _seed_project(project_repo, project_config)

        # 先创建一条被拒绝的知识（通过提交包含私钥的内容）
        governance.propose_memory(
            title="被拒绝的知识",
            content="-----BEGIN RSA PRIVATE KEY-----\nblocked",
            project=project_config,
            actor="test",
        )

        # 手动创建一条被拒绝的知识（非敏感内容但被拒绝）
        item = MemoryItem(
            project_id=project_config.id,
            type="architecture",
            title="之前被拒绝的知识",
            content="安全的重复内容用于测试",
            content_hash=compute_content_hash("安全的重复内容用于测试"),
            status="rejected",
            scope="project",
            source_type="ai_inferred",
        )
        memory_repo.create_memory(item, actor="test")

        # 再次提交相同内容
        result = governance.propose_memory(
            title="重新提交的知识",
            content="安全的重复内容用于测试",
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )
        # 不应被去重拦截（rejected 不参与去重）
        assert result.get("dedup", {}).get("is_duplicate", False) is False
        assert result["status"] != "rejected" or "blocked" in str(result)

    def test_41_dedup_ignores_deprecated(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """deprecated 状态的知识不阻止相同内容再次提交。"""
        _seed_project(project_repo, project_config)

        content = "被废弃的旧知识内容"
        item = MemoryItem(
            project_id=project_config.id,
            type="architecture",
            title="已废弃的知识",
            content=content,
            content_hash=compute_content_hash(content),
            status="deprecated",
            scope="project",
            source_type="user_confirmed",
        )
        memory_repo.create_memory(item, actor="test")

        result = governance.propose_memory(
            title="新知识（内容同废弃知识）",
            content=content,
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )
        assert result.get("dedup", {}).get("is_duplicate", False) is False

    def test_42_dedup_blocks_approved_duplicate(
        self, governance, project_repo, project_config,
    ):
        """approved 状态的知识仍然阻止相同内容提交。"""
        _seed_project(project_repo, project_config)

        content = "已批准的活跃知识内容"
        # 第一次提交（自动批准）
        result1 = governance.propose_memory(
            title="已批准的知识",
            content=content,
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )
        assert result1["status"] == "approved"

        # 第二次提交相同内容
        result2 = governance.propose_memory(
            title="重复的知识",
            content=content,
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )
        assert result2["status"] == "rejected"
        assert result2.get("dedup", {}).get("is_duplicate") is True

    # ── Phase 4.1 新增: manual_input 集成 ──

    def test_43_manual_input_auto_approve_integration(
        self, governance, project_repo, project_config,
    ):
        """manual_input + 高置信度 + 低风险 → 自动批准。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title="人工录入的知识",
            content="这是用户手动录入的确认知识",
            project=project_config,
            confidence=0.9,
            source_type="manual_input",
            actor="user",
        )
        assert result["status"] == "approved"
        assert result["review_decision"]["auto_approved"] is True

    # ── Phase 4.2: threshold=-1 禁用集成测试 ──

    def test_44_threshold_neg1_propose_pending_review(
        self, governance, project_repo,
    ):
        """threshold=-1 的 project，即使 user_confirmed+high confidence 也 pending_review。"""
        config = ProjectConfig(
            id="neg1-project",
            name="禁用自动批准项目",
            slug="neg1-project",
            status="active",
            recognition=RecognitionConfig(root_paths=["/neg1"], aliases=["neg1"]),
            knowledge_policy=KnowledgePolicyConfig(auto_approve_threshold=-1),
        )
        _seed_project(project_repo, config)
        result = governance.propose_memory(
            title="任何知识",
            content="即使高置信度用户确认也强制人工审核",
            project=config,
            confidence=0.99,
            source_type="user_confirmed",
            actor="test",
        )
        assert result["status"] == "pending_review"
        assert result["review_decision"]["auto_approved"] is False
        assert "auto_approve_threshold" in result["review_decision"]["reason"]

    # ── Phase 4.2: blocked audit_log 安全摘要 ──

    def test_45_source_file_with_api_key_blocked(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """source_file 含 API key → blocked。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title="安全的标题",
            content="安全的正文",
            project=project_config,
            source_file='api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"',
            actor="test",
        )
        assert result["status"] == "rejected"
        assert result["validation"]["blocked"] is True

    def test_46_audit_log_no_api_key(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """blocked audit_log 不包含 API key 原始值。"""
        _seed_project(project_repo, project_config)
        governance.propose_memory(
            title="安全的标题",
            content="安全的正文",
            project=project_config,
            source_file='api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"',
            actor="test",
        )
        logs = audit_repo.list_by_project_id(project_config.id)
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        new_value = blocked_logs[0].get("new_value") or ""
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in new_value

    def test_47_audit_log_no_raw_source_file(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """blocked 时（由 content 触发），audit_log 不包含 source_file 原始值。"""
        _seed_project(project_repo, project_config)
        governance.propose_memory(
            title="安全的标题",
            content="-----BEGIN RSA PRIVATE KEY-----\nblocked content",
            project=project_config,
            source_file="/etc/secrets/passwords.txt",
            actor="test",
        )
        logs = audit_repo.list_by_project_id(project_config.id)
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        new_value = blocked_logs[0].get("new_value") or ""
        assert "/etc/secrets/passwords.txt" not in new_value
        assert "source_file_present" in new_value

    def test_48_audit_log_tag_with_token_no_leak(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """tags 含 token 被 blocked，audit_log 不包含原始 tag。"""
        _seed_project(project_repo, project_config)
        governance.propose_memory(
            title="安全的标题",
            content="安全的正文",
            project=project_config,
            tags=["order", "token=ghp_abcdefghijklmnopqrstuvwxyz"],
            actor="test",
        )
        logs = audit_repo.list_by_project_id(project_config.id)
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        new_value = blocked_logs[0].get("new_value") or ""
        assert "ghp_abcdefghijklmnopqrstuvwxyz" not in new_value
        assert "token=" not in new_value

    def test_49_audit_log_title_with_api_key_no_leak(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """title 含 API key 被 blocked，audit_log 不包含 title 原文。"""
        _seed_project(project_repo, project_config)
        governance.propose_memory(
            title='API Key = "sk-abcdefghijklmnopqrstuvwxyz123456" 泄露',
            content="安全的正文",
            project=project_config,
            actor="test",
        )
        logs = audit_repo.list_by_project_id(project_config.id)
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        new_value = blocked_logs[0].get("new_value") or ""
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in new_value
        assert "泄露" not in new_value

    # ── Phase 4.3: source_evidence key 审计 ──

    def test_50_source_evidence_key_with_api_key_blocked(
        self, governance, project_repo, project_config,
    ):
        """source_evidence 的 key 含 API key → blocked。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title="安全的标题",
            content="安全的正文",
            project=project_config,
            source_evidence={
                "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456": "safe",
            },
            actor="test",
        )
        assert result["status"] == "rejected"
        assert result["validation"]["blocked"] is True
        assert "$OPENAI_API_KEY" in result["validation"]["blocked_field"]

    def test_51_audit_no_raw_key_text(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """blocked audit_log 不包含 source_evidence key 原文。"""
        _seed_project(project_repo, project_config)
        governance.propose_memory(
            title="安全的标题",
            content="安全的正文",
            project=project_config,
            source_evidence={
                "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456": "safe",
            },
            actor="test",
        )
        logs = audit_repo.list_by_project_id(project_config.id)
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        new_value = blocked_logs[0].get("new_value") or ""
        assert "OPENAI_API_KEY" not in new_value

    def test_52_audit_no_sk_in_log(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """blocked audit_log 不包含 sk-... 敏感值。"""
        _seed_project(project_repo, project_config)
        governance.propose_memory(
            title="安全的标题",
            content="安全的正文",
            project=project_config,
            source_evidence={
                "api-key-sk-abcdefghijklmnopqrstuvwxyz123456": "safe",
            },
            actor="test",
        )
        logs = audit_repo.list_by_project_id(project_config.id)
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        new_value = blocked_logs[0].get("new_value") or ""
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in new_value

    def test_53_audit_has_source_evidence_present(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """blocked audit_log 包含 source_evidence_present（非 raw key）。"""
        _seed_project(project_repo, project_config)
        governance.propose_memory(
            title="安全的标题",
            content="-----BEGIN RSA PRIVATE KEY-----\nblocked content",
            project=project_config,
            source_evidence={"config": "some_value"},
            actor="test",
        )
        logs = audit_repo.list_by_project_id(project_config.id)
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        new_value = blocked_logs[0].get("new_value") or ""
        assert "source_evidence_present" in new_value

    def test_54_audit_has_source_evidence_key_count(
        self, governance, project_repo, project_config, audit_repo,
    ):
        """blocked audit_log 包含 source_evidence_key_count。"""
        _seed_project(project_repo, project_config)
        governance.propose_memory(
            title="安全的标题",
            content="-----BEGIN RSA PRIVATE KEY-----\nblocked content",
            project=project_config,
            source_evidence={"a": "1", "b": "2", "c": "3"},
            actor="test",
        )
        logs = audit_repo.list_by_project_id(project_config.id)
        blocked_logs = [l for l in logs if l.get("action") == "blocked"]
        assert len(blocked_logs) >= 1
        new_value = blocked_logs[0].get("new_value") or ""
        assert "source_evidence_key_count" in new_value


class TestGovernanceApproveReject:
    """approve/reject/deprecate 操作测试。"""

    def _create_memory(self, memory_repo, project_repo, project_config, **kwargs):
        from project_memory_mcp.utils.hashing import compute_content_hash

        _seed_project(project_repo, project_config)
        content = kwargs.pop("content", "测试知识内容")
        item = MemoryItem(
            project_id=project_config.id,
            type=kwargs.pop("type", "architecture"),
            title=kwargs.pop("title", "测试知识"),
            content=content,
            content_hash=compute_content_hash(content),
            status=kwargs.pop("status", "candidate"),
            confidence=kwargs.pop("confidence", 0.5),
            scope=kwargs.pop("scope", "project"),
            source_type=kwargs.pop("source_type", "ai_inferred"),
            **kwargs,
        )
        return memory_repo.create_memory(item, actor="test")

    def test_44_approve_candidate(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """批准候选知识 → approved。"""
        item = self._create_memory(memory_repo, project_repo, project_config)
        result = governance.approve_memory(
            memory_id=item.id, reviewer="admin", comment="审核通过"
        )
        assert result["status"] == "approved"
        assert result["reviewed_by"] == "admin"

        updated = memory_repo.get_by_id(item.id)
        assert updated.status == "approved"
        assert updated.reviewed_by == "admin"

    def test_45_reject_candidate(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """拒绝候选知识 → rejected。"""
        item = self._create_memory(memory_repo, project_repo, project_config)
        result = governance.reject_memory(
            memory_id=item.id, reviewer="admin", reason="信息不准确"
        )
        assert result["status"] == "rejected"

        updated = memory_repo.get_by_id(item.id)
        assert updated.status == "rejected"

    def test_46_deprecate_approved(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """废弃已批准知识 → deprecated。"""
        item = self._create_memory(
            memory_repo, project_repo, project_config, status="approved"
        )
        result = governance.deprecate_memory(
            memory_id=item.id, reason="接口已重构"
        )
        assert result["status"] == "deprecated"

        updated = memory_repo.get_by_id(item.id)
        assert updated.status == "deprecated"

    def test_47_approve_non_reviewable_raises(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """批准已 approved 的知识应抛出错误。"""
        item = self._create_memory(
            memory_repo, project_repo, project_config, status="approved"
        )
        with pytest.raises(GovernanceError, match="不可审核"):
            governance.approve_memory(memory_id=item.id, reviewer="admin")

    def test_48_approve_rejected_raises(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """Phase 4.1: rejected 为终态，不可再 approve。"""
        item = self._create_memory(
            memory_repo, project_repo, project_config, status="rejected"
        )
        with pytest.raises(GovernanceError, match="不可审核"):
            governance.approve_memory(memory_id=item.id, reviewer="admin")

    def test_49_deprecate_non_approved_raises(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """废弃 candidate 状态的知识应抛出错误。"""
        item = self._create_memory(memory_repo, project_repo, project_config, status="candidate")
        with pytest.raises(GovernanceError, match="不可废弃"):
            governance.deprecate_memory(memory_id=item.id)

    def test_50_nonexistent_memory_raises(
        self, governance,
    ):
        """操作不存在的知识应抛出错误。"""
        with pytest.raises(GovernanceError, match="不存在"):
            governance.approve_memory(memory_id="nonexistent-id", reviewer="admin")

    def test_51_approve_with_confidence_override(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """审核通过时可覆盖置信度。"""
        item = self._create_memory(memory_repo, project_repo, project_config)
        result = governance.approve_memory(
            memory_id=item.id, reviewer="admin", confidence_override=0.99
        )
        assert result["status"] == "approved"

        updated = memory_repo.get_by_id(item.id)
        assert updated.confidence == 0.99

    def test_52_audit_log_for_approve(
        self, governance, memory_repo, project_repo, project_config, audit_repo,
    ):
        """审批操作写入 audit_log。"""
        item = self._create_memory(memory_repo, project_repo, project_config)
        governance.approve_memory(memory_id=item.id, reviewer="admin", comment="确认正确")

        logs = audit_repo.list_by_memory_id(item.id)
        assert len(logs) >= 1
        status_changes = [l for l in logs if l["action"] == "status_changed"]
        assert len(status_changes) >= 1
        assert "approved" in status_changes[0]["reason"]

    def test_53_audit_log_for_deprecate(
        self, governance, memory_repo, project_repo, project_config, audit_repo,
    ):
        """废弃操作写入 audit_log。"""
        item = self._create_memory(
            memory_repo, project_repo, project_config, status="approved"
        )
        governance.deprecate_memory(memory_id=item.id, reason="不再适用")

        logs = audit_repo.list_by_memory_id(item.id)
        status_changes = [l for l in logs if l["action"] == "status_changed"]
        assert any("deprecated" in l["reason"] for l in status_changes)

    def test_54_empty_title_raises(
        self, governance, project_config,
    ):
        """空标题应拒绝。"""
        with pytest.raises(GovernanceError, match="title 不能为空"):
            governance.propose_memory(
                title="", content="some content", project=project_config,
            )

    def test_55_empty_content_raises(
        self, governance, project_config,
    ):
        """空内容应拒绝。"""
        with pytest.raises(GovernanceError, match="content 不能为空"):
            governance.propose_memory(
                title="test", content="", project=project_config,
            )

    def test_56_confidence_override_keeps_approved_status(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """审核通过后 confidence 更新不影响 approved 状态。"""
        item = self._create_memory(memory_repo, project_repo, project_config)
        result = governance.approve_memory(
            memory_id=item.id, reviewer="admin", confidence_override=0.85
        )
        assert result["status"] == "approved"

        updated = memory_repo.get_by_id(item.id)
        assert updated.status == "approved"
        assert updated.confidence == 0.85

    def test_57_reject_rejected_raises(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """Phase 4.1: 再次拒绝已 rejected 的知识应抛出错误（终态）。"""
        item = self._create_memory(
            memory_repo, project_repo, project_config, status="rejected"
        )
        with pytest.raises(GovernanceError, match="不可审核"):
            governance.reject_memory(memory_id=item.id, reason="再次拒绝")

    # ── Phase 4.3: tags 类型校验 ──

    def test_58_tags_with_non_string_raises(
        self, governance, project_config,
    ):
        """tags 中包含非字符串元素 → GovernanceError。"""
        with pytest.raises(GovernanceError, match="tags 必须是字符串列表"):
            governance.propose_memory(
                title="test",
                content="safe content",
                project=project_config,
                tags=["ok", 123],
            )

    def test_59_tags_all_strings_ok(
        self, governance, project_repo, project_config,
    ):
        """全字符串 tags 正常通过。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title="test",
            content="safe content",
            project=project_config,
            tags=["order", "transaction"],
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )
        assert result["status"] in ("approved", "pending_review")
