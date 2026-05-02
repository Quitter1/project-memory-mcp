"""敏感信息检测测试。"""

# TODO: 阶段 4 实现
# 测试场景：
# 1. 私钥 → blocked
# 2. 明文数据库密码 → blocked
# 3. API Key 赋值 → risk_level=high, warning
# 4. 大段源码 → risk_level=high, warning
# 5. 正常文本 → 通过
