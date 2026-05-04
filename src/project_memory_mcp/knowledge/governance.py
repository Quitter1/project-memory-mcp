"""KnowledgeGovernance — 知识治理核心，编排 propose/approve/reject/deprecate 完整流水线。

Phase 4.1 变更：
- propose_memory 全字段安全校验（validate_persisted_payload）
- blocked/duplicate_rejected 审计日志仅保存安全摘要（不含原始敏感内容）
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("project_memory_mcp")

from ..config.schema import ProjectConfig
from ..db.audit_repo import AuditRepository
from ..db.memory_repo import MemoryRepository
from ..models.memory_item import MemoryItem
from ..models.enums import KnowledgeStatus, IndexStatus, Scope, RiskLevel
from ..utils.hashing import compute_content_hash
from .validator import ContentValidator, ValidationResult
from .deduplicator import Deduplicator, DedupResult
from .lifecycle import LifecycleManager, InvalidTransitionError
from .reviewer import RuleBasedReviewer, ReviewDecision


class GovernanceError(Exception):
    """治理操作错误。"""
    def __init__(self, message: str, code: str = "governance_error"):
        super().__init__(message)
        self.code = code


# Phase 4.4: blocked_field 脱敏 — 不允许敏感字符串出现在审计日志和返回值中
_SENSITIVE_FIELD_MARKERS = (
    "sk-", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
    "token=", "password=", "pwd=", "bearer", "secret",
)


def sanitize_blocked_field(field: str) -> str:
    """对 blocked_field 做安全脱敏，移除可能包含的敏感 key 原文。"""
    if not field:
        return field

    for marker in _SENSITIVE_FIELD_MARKERS:
        if marker.lower() in field.lower():
            # 将 source_evidence 下含敏感 key 的路径替换为安全的 $key 路径
            parts = field.split(".")
            safe_parts: list[str] = []
            for p in parts:
                if any(m.lower() in p.lower() for m in _SENSITIVE_FIELD_MARKERS):
                    safe_parts.append("$key")
                else:
                    safe_parts.append(p)
            return ".".join(safe_parts)

    return field


class KnowledgeGovernance:
    """
    知识治理核心。

    编排完整流水线：
    - propose_memory: 全字段校验 → 去重 → 审批判定 → 写入
    - approve_memory: 审核通过候选知识
    - reject_memory: 审核拒绝候选知识
    - deprecate_memory: 废弃已生效知识
    """

    def __init__(
        self,
        repo: MemoryRepository,
        audit: AuditRepository,
        validator: ContentValidator,
        deduplicator: Deduplicator,
        reviewer: RuleBasedReviewer,
        indexer=None,
        llm_reviewer=None,
    ):
        self.repo = repo
        self.audit = audit
        self.validator = validator
        self.deduplicator = deduplicator
        self.reviewer = reviewer
        self.indexer = indexer
        self.llm_reviewer = llm_reviewer

    # ------------------------------------------------------------------
    # propose_memory
    # ------------------------------------------------------------------

    def propose_memory(
        self,
        title: str,
        content: str,
        project: ProjectConfig,
        knowledge_type: str = "other",
        module: str = "",
        tags: list[str] | None = None,
        confidence: float = 0.5,
        source_type: str = "ai_inferred",
        source_evidence: dict | None = None,
        source_file: str | None = None,
        source_line: int | None = None,
        scope: str = "project",
        allowed_projects: list[str] | None = None,
        actor: str = "system",
        task_id: str | None = None,
    ) -> dict:
        """
        提交候选知识，执行完整治理流水线。

        流程：
        1. 全字段安全校验 → blocked 则只写 audit_log（安全摘要），不保存原文
        2. 去重检测 → 哈希冲突则写 audit_log 后拒绝
        3. 多因素审批判定 → 自动批准或进入 pending_review
        4. 写入 memory_items + memory_tags + audit_log
        5. 返回结果
        """
        if not title or not title.strip():
            raise GovernanceError("title 不能为空", code="invalid_params")
        if not content or not content.strip():
            raise GovernanceError("content 不能为空", code="invalid_params")
        if not project or not project.id:
            raise GovernanceError("project 不能为空", code="invalid_params")
        if tags is not None:
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
                raise GovernanceError("tags 必须是字符串列表", code="invalid_params")

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # === Step 1: 全字段安全校验 ===
        validation = self.validator.validate_persisted_payload(
            title=title,
            content=content,
            source_evidence=source_evidence,
            source_file=source_file,
            tags=tags,
        )

        if validation.blocked:
            # 不保存原文，仅写 audit_log（安全摘要，不含原始敏感内容）
            # Phase 4.2: 仅保存安全元信息，不含任何原始字符串值
            safe_summary = json.dumps(
                {
                    "title_present": bool(title and title.strip()),
                    "content_length": len(content) if content else 0,
                    "source_file_present": bool(source_file),
                    "source_evidence_present": bool(source_evidence),
                    "source_evidence_key_count": len(source_evidence) if source_evidence else 0,
                    "tag_count": len(tags) if tags else 0,
                    "blocked_reason": validation.blocked_reason,
                    "blocked_field": sanitize_blocked_field(validation.blocked_field),
                    "type": knowledge_type,
                    "module": module,
                    "source_type": source_type,
                    "scope": scope,
                },
                ensure_ascii=False,
            )
            self.audit.log_action(
                action="blocked",
                project_id=project.id,
                old_value=None,
                new_value=safe_summary,
                actor=actor,
                reason=validation.blocked_reason,
                task_id=task_id,
            )
            self.repo.conn.commit()

            return {
                "memory_id": "",
                "status": KnowledgeStatus.REJECTED,
                "index_status": IndexStatus.NOT_INDEXED,
                "risk_level": validation.risk_level,
                "validation": {
                    "passed": False,
                    "blocked": True,
                    "blocked_reason": validation.blocked_reason,
                    "blocked_field": sanitize_blocked_field(validation.blocked_field),
                    "warnings": validation.warnings,
                },
                "review_decision": {
                    "auto_approved": False,
                    "reason": f"blocked: {validation.blocked_reason}",
                },
            }

        # === Step 2: 去重检测 ===
        dedup_result = self.deduplicator.check_hash_only(
            content, project.id, scope=scope,
        )

        if dedup_result.is_duplicate:
            # 写 audit_log（安全摘要，不保留完整原文）
            safe_summary = json.dumps(
                {
                    "title": title,
                    "title_present": bool(title and title.strip()),
                    "content_length": len(content) if content else 0,
                    "type": knowledge_type,
                    "module": module,
                    "source_type": source_type,
                    "scope": scope,
                    "duplicate_of": dedup_result.duplicate_of,
                    "duplicate_title": dedup_result.duplicate_title,
                },
                ensure_ascii=False,
            )
            self.audit.log_action(
                action="duplicate_rejected",
                project_id=project.id,
                old_value=None,
                new_value=safe_summary,
                actor=actor,
                reason=f"内容哈希冲突: 已有知识 {dedup_result.duplicate_of}",
                task_id=task_id,
            )
            self.repo.conn.commit()

            return {
                "memory_id": "",
                "status": KnowledgeStatus.REJECTED,
                "index_status": IndexStatus.NOT_INDEXED,
                "risk_level": validation.risk_level,
                "validation": {
                    "passed": validation.passed,
                    "blocked": False,
                    "blocked_reason": "",
                    "blocked_field": "",
                    "warnings": validation.warnings,
                },
                "dedup": {
                    "is_duplicate": True,
                    "duplicate_of": dedup_result.duplicate_of,
                    "duplicate_title": dedup_result.duplicate_title,
                },
                "review_decision": {
                    "auto_approved": False,
                    "reason": f"内容哈希冲突: 已有知识 {dedup_result.duplicate_of}",
                },
            }

        # 语义去重（获取相似知识列表）
        semantic_similar = self.deduplicator.find_similar(content, project.id)

        # 确定最终 risk_level（validator 的 warning 可能提升 risk_level）
        final_risk_level = validation.risk_level if validation.risk_level == "high" else "low"

        # === Step 3: 多因素审批判定 ===
        item_for_review = {
            "title": title,
            "content": content,
            "type": knowledge_type,
            "module": module,
            "confidence": confidence,
            "scope": scope,
            "risk_level": final_risk_level,
            "source_type": source_type,
        }

        review_decision = self.reviewer.review(
            item=item_for_review,
            project=project,
            validation_passed=validation.passed,
            has_duplicate=dedup_result.is_duplicate,
            has_conflict=len(semantic_similar) > 0,
        )

        # === Step 4: LLM 二次评审 ===
        llm_result = None
        llm_applied = False
        if self.llm_reviewer is not None and self.llm_reviewer.enabled:
            try:
                llm_result = self.llm_reviewer.review({
                    "project_id": project.id,
                    "title": title, "content": content,
                    "type": knowledge_type, "module": module,
                    "tags": tags, "source_type": source_type,
                    "scope": scope, "confidence": confidence,
                    "risk_level": final_risk_level,
                })
                if llm_result.decision == "reject":
                    review_decision = ReviewDecision(
                        auto_approved=False,
                        reason="LLM Reviewer 建议拒绝",
                    )
                    llm_applied = True
                elif llm_result.decision == "pending_review" and review_decision.auto_approved:
                    review_decision = ReviewDecision(
                        auto_approved=False,
                        reason="LLM Reviewer 降级为 pending_review",
                    )
                    llm_applied = True
            except Exception as _llm_exc:
                logger.error("llm_review_failed exc_type=%s", type(_llm_exc).__name__)

        # === Step 5: 确定目标状态 ===
        if review_decision.auto_approved:
            target_status = KnowledgeStatus.APPROVED
        elif llm_applied and llm_result and llm_result.decision == "reject":
            target_status = KnowledgeStatus.REJECTED
        else:
            target_status = KnowledgeStatus.PENDING_REVIEW

        # === Step 5: 构建 MemoryItem 并写入 ===
        content_hash = compute_content_hash(content)
        item = MemoryItem(
            id="",
            project_id=project.id,
            module=module,
            type=knowledge_type,
            title=title,
            content=content,
            content_hash=content_hash,
            status=target_status,
            index_status=IndexStatus.NOT_INDEXED,
            confidence=confidence,
            risk_level=final_risk_level,
            scope=scope,
            allowed_projects=allowed_projects or [],
            denied_projects=[],
            source_type=source_type,
            source_task_id=task_id,
            source_agent=actor,
            source_evidence=source_evidence or {},
            source_file=source_file,
            source_line=source_line,
            tags=tags or [],
            created_by=actor,
            created_at=now_utc,
            updated_at=now_utc,
        )

        created = self.repo.create_memory(
            item,
            actor=actor,
            reason=f"propose_memory → {target_status}: {review_decision.reason}",
            task_id=task_id,
        )

        return {
            "memory_id": created.id,
            "status": created.status,
            "index_status": created.index_status,
            "risk_level": created.risk_level,
            "validation": {
                "passed": validation.passed,
                "blocked": False,
                "blocked_reason": "",
                "blocked_field": "",
                "warnings": validation.warnings,
                "similar_existing": semantic_similar,
            },
            "review_decision": {
                "auto_approved": review_decision.auto_approved,
                "reason": review_decision.reason,
                "required_reviewers": review_decision.required_reviewers,
            },
        }

    # ------------------------------------------------------------------
    # approve_memory
    # ------------------------------------------------------------------

    def approve_memory(
        self,
        memory_id: str,
        reviewer: str = "system",
        comment: str = "",
        confidence_override: float | None = None,
    ) -> dict:
        """
        审核通过候选知识。

        仅允许从 candidate/pending_review → approved。
        """
        existing = self.repo.get_by_id(memory_id)
        if existing is None:
            raise GovernanceError(f"知识不存在: {memory_id}", code="memory_not_found")

        if not LifecycleManager.is_reviewable(existing.status):
            raise GovernanceError(
                f"知识状态 {existing.status} 不可审核，仅 "
                f"{sorted(LifecycleManager.REVIEWABLE_STATUSES)} 可审核",
                code="invalid_state",
            )

        LifecycleManager.validate_transition(existing.status, KnowledgeStatus.APPROVED)

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        updates: dict = {}
        if confidence_override is not None:
            updates["confidence"] = confidence_override

        self.repo.conn.execute(
            "UPDATE memory_items SET status = ?, reviewed_by = ?, review_comment = ?, "
            "reviewed_at = ?, updated_at = ? WHERE id = ?",
            (KnowledgeStatus.APPROVED, reviewer, comment, now_utc, now_utc, memory_id),
        )

        if updates:
            for key, value in updates.items():
                self.repo.conn.execute(
                    f"UPDATE memory_items SET {key} = ? WHERE id = ?",
                    (value, memory_id),
                )

        updated = self.repo.get_by_id(memory_id)

        self.audit.log_action(
            action="status_changed",
            project_id=existing.project_id,
            memory_id=memory_id,
            old_value=self.repo._item_to_json(existing),
            new_value=self.repo._item_to_json(updated),
            actor=reviewer,
            reason=f"[{existing.status} → approved] {comment}",
        )

        self.repo.conn.commit()

        # Phase 10: 索引向量
        if self.indexer is not None and updated is not None:
            try:
                self.indexer.index_memory(updated)
            except Exception:
                pass

        return {
            "memory_id": memory_id,
            "status": KnowledgeStatus.APPROVED,
            "index_status": updated.index_status if updated else IndexStatus.NOT_INDEXED,
            "reviewed_by": reviewer,
            "reviewed_at": now_utc,
        }

    # ------------------------------------------------------------------
    # reject_memory
    # ------------------------------------------------------------------

    def reject_memory(
        self,
        memory_id: str,
        reviewer: str = "system",
        reason: str = "",
    ) -> dict:
        """
        审核拒绝候选知识。

        仅允许从 candidate/pending_review → rejected。
        rejected 为终态，不可再次转换。
        """
        existing = self.repo.get_by_id(memory_id)
        if existing is None:
            raise GovernanceError(f"知识不存在: {memory_id}", code="memory_not_found")

        if not LifecycleManager.is_reviewable(existing.status):
            raise GovernanceError(
                f"知识状态 {existing.status} 不可审核，仅 "
                f"{sorted(LifecycleManager.REVIEWABLE_STATUSES)} 可审核",
                code="invalid_state",
            )

        LifecycleManager.validate_transition(existing.status, KnowledgeStatus.REJECTED)

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.repo.conn.execute(
            "UPDATE memory_items SET status = ?, reviewed_by = ?, review_comment = ?, "
            "reviewed_at = ?, updated_at = ? WHERE id = ?",
            (KnowledgeStatus.REJECTED, reviewer, reason, now_utc, now_utc, memory_id),
        )

        updated = self.repo.get_by_id(memory_id)

        self.audit.log_action(
            action="status_changed",
            project_id=existing.project_id,
            memory_id=memory_id,
            old_value=self.repo._item_to_json(existing),
            new_value=self.repo._item_to_json(updated),
            actor=reviewer,
            reason=f"[{existing.status} → rejected] {reason}",
        )

        self.repo.conn.commit()

        # Phase 10: 删除向量
        if self.indexer is not None:
            try:
                self.indexer.delete_memory(memory_id)
            except Exception:
                pass

        return {
            "memory_id": memory_id,
            "status": KnowledgeStatus.REJECTED,
            "previous_status": existing.status,
        }

    # ------------------------------------------------------------------
    # deprecate_memory
    # ------------------------------------------------------------------

    def deprecate_memory(
        self,
        memory_id: str,
        reason: str = "",
        actor: str = "system",
    ) -> dict:
        """
        废弃已生效知识。

        仅允许从 approved → deprecated。
        """
        existing = self.repo.get_by_id(memory_id)
        if existing is None:
            raise GovernanceError(f"知识不存在: {memory_id}", code="memory_not_found")

        if not LifecycleManager.is_deprecatable(existing.status):
            raise GovernanceError(
                f"知识状态 {existing.status} 不可废弃，仅 "
                f"{sorted(LifecycleManager.DEPRECATABLE_STATUSES)} 可废弃",
                code="invalid_state",
            )

        LifecycleManager.validate_transition(existing.status, KnowledgeStatus.DEPRECATED)

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.repo.conn.execute(
            "UPDATE memory_items SET status = ?, updated_at = ? WHERE id = ?",
            (KnowledgeStatus.DEPRECATED, now_utc, memory_id),
        )

        updated = self.repo.get_by_id(memory_id)

        self.audit.log_action(
            action="status_changed",
            project_id=existing.project_id,
            memory_id=memory_id,
            old_value=self.repo._item_to_json(existing),
            new_value=self.repo._item_to_json(updated),
            actor=actor,
            reason=f"[{existing.status} → deprecated] {reason}",
        )

        self.repo.conn.commit()

        # Phase 10: 删除向量
        if self.indexer is not None:
            try:
                self.indexer.delete_memory(memory_id)
            except Exception:
                pass

        return {
            "memory_id": memory_id,
            "status": KnowledgeStatus.DEPRECATED,
            "previous_status": existing.status,
        }
