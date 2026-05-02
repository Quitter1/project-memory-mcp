"""治理逻辑测试 — lifecycle, reviewer, deduplicator, governance 集成。"""

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
    """创建测试用项目配置。"""
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
    """允许 AI 自动批准 + 更低阈值的项目配置。"""
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
    """同步 ProjectConfig 到 SQLite。"""
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

    def test_07_rejected_can_resubmit(self):
        assert LifecycleManager.can_transition("rejected", "candidate") is True

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


# ==================================================================
# RuleBasedReviewer 测试
# ==================================================================

class TestReviewer:
    """多因素审批判定测试。"""

    def test_13_all_conditions_met_auto_approved(self, reviewer, auto_approve_project_config):
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

    def test_14_scope_shared_no_auto_approve(self, reviewer, auto_approve_project_config):
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

    def test_15_scope_global_no_auto_approve(self, reviewer, auto_approve_project_config):
        item = {
            "confidence": 0.9,
            "scope": "global",
            "risk_level": "low",
            "source_type": "ai_inferred",
            "type": "architecture",
        }
        decision = reviewer.review(item, auto_approve_project_config)
        assert decision.auto_approved is False

    def test_16_risk_high_no_auto_approve(self, reviewer, auto_approve_project_config):
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

    def test_17_confidence_below_threshold(self, reviewer, auto_approve_project_config):
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

    def test_18_ai_source_disabled_no_auto_approve(self, reviewer, project_config):
        """默认 project_config 不允许 AI 自动批准。"""
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

    def test_19_user_confirmed_source_auto_approved(self, reviewer, project_config):
        """user_confirmed 来源在默认配置下也可自动批准。"""
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "user_confirmed",
            "type": "architecture",
        }
        decision = reviewer.review(item, project_config)
        assert decision.auto_approved is True

    def test_20_code_verified_source_auto_approved(self, reviewer, project_config):
        item = {
            "confidence": 0.9,
            "scope": "project",
            "risk_level": "low",
            "source_type": "code_verified",
            "type": "architecture",
        }
        decision = reviewer.review(item, project_config)
        assert decision.auto_approved is True

    def test_21_forbidden_type_no_auto_approve(self, reviewer):
        """即使其它条件满足，forbidden_auto_types 中的类型也不自动批准。"""
        config = ProjectConfig(
            id="test",
            name="test",
            slug="test",
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

    def test_22_validation_failed_no_auto_approve(self, reviewer, auto_approve_project_config):
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

    def test_23_has_duplicate_no_auto_approve(self, reviewer, auto_approve_project_config):
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


# ==================================================================
# KnowledgeGovernance 集成测试
# ==================================================================

class TestGovernancePropose:
    """propose_memory 完整流水线测试。"""

    def test_24_propose_normal_pending_review(
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

    def test_25_propose_auto_approved(
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

    def test_26_propose_blocked_sensitive(
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

    def test_27_propose_duplicate_rejected(
        self, governance, project_repo, project_config,
    ):
        """哈希重复 → 拒绝。"""
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

    def test_28_propose_shared_always_pending_review(
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

    def test_29_propose_with_warnings_risk_high(
        self, governance, project_repo, project_config,
    ):
        """warning 检测命中 → risk_level=high → pending_review。"""
        _seed_project(project_repo, project_config)
        result = governance.propose_memory(
            title="包含 API Key 的知识",
            content='配置: api_key = "sk-thisisaverylongapikeyfortesting12345"',
            project=project_config,
            confidence=0.9,
            source_type="user_confirmed",
            actor="test",
        )
        assert result["risk_level"] == "high"
        assert result["status"] == "pending_review"
        assert len(result["validation"]["warnings"]) >= 1


class TestGovernanceApproveReject:
    """approve/reject/deprecate 操作测试。"""

    def _create_memory(self, memory_repo, project_repo, project_config, **kwargs):
        """辅助：直接创建一条知识。"""
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

    def test_30_approve_candidate(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """批准候选知识 → approved。"""
        item = self._create_memory(memory_repo, project_repo, project_config)
        result = governance.approve_memory(
            memory_id=item.id, reviewer="admin", comment="审核通过"
        )
        assert result["status"] == "approved"
        assert result["reviewed_by"] == "admin"

        # 验证数据库状态
        updated = memory_repo.get_by_id(item.id)
        assert updated.status == "approved"
        assert updated.reviewed_by == "admin"

    def test_31_reject_candidate(
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

    def test_32_deprecate_approved(
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

    def test_33_approve_non_reviewable_raises(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """批准已 approved 的知识应抛出错误。"""
        item = self._create_memory(
            memory_repo, project_repo, project_config, status="approved"
        )
        with pytest.raises(GovernanceError, match="不可审核"):
            governance.approve_memory(memory_id=item.id, reviewer="admin")

    def test_34_deprecate_non_approved_raises(
        self, governance, memory_repo, project_repo, project_config,
    ):
        """废弃 candidate 状态的知识应抛出错误。"""
        item = self._create_memory(memory_repo, project_repo, project_config, status="candidate")
        with pytest.raises(GovernanceError, match="不可废弃"):
            governance.deprecate_memory(memory_id=item.id)

    def test_35_nonexistent_memory_raises(
        self, governance,
    ):
        """操作不存在的知识应抛出错误。"""
        with pytest.raises(GovernanceError, match="不存在"):
            governance.approve_memory(memory_id="nonexistent-id", reviewer="admin")

    def test_36_approve_with_confidence_override(
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

    def test_37_audit_log_for_approve(
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

    def test_38_audit_log_for_deprecate(
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

    def test_39_empty_title_raises(
        self, governance, project_config,
    ):
        """空标题应拒绝。"""
        with pytest.raises(GovernanceError, match="title 不能为空"):
            governance.propose_memory(
                title="", content="some content", project=project_config,
            )

    def test_40_empty_content_raises(
        self, governance, project_config,
    ):
        """空内容应拒绝。"""
        with pytest.raises(GovernanceError, match="content 不能为空"):
            governance.propose_memory(
                title="test", content="", project=project_config,
            )

    def test_41_confidence_override_keeps_approved_status(
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
