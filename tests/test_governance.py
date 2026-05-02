"""治理逻辑测试（多因素审批）。"""

# TODO: 阶段 4 实现
# 测试场景：
# 1. 高置信度 + 允许 AI 自动批准 → approved
# 2. scope=shared → 不自动批准 → pending_review
# 3. risk_level=high → 不自动批准 → pending_review
# 4. AI 来源 + 项目禁止 AI 自动批准 → pending_review
# 5. 安全校验 blocked → rejected
