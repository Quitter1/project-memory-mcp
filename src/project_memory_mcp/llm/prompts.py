"""LLM Reviewer prompts — 只构造不含敏感原文的安全 prompt。"""


def build_system_prompt() -> str:
    return (
        "你是项目知识库的二次评审器。\n"
        "你不能批准包含密钥、token、密码、隐私、未经验证事实的内容。\n"
        "你不能因为内容写得像技术知识就自动批准。\n"
        "你要判断该内容是否长期有用、是否具体、是否可复用、是否与项目相关。\n"
        "你只能输出 JSON。\n"
        "JSON 格式：\n"
        '{"decision":"pending_review","confidence":0.5,"risk_level":"low","reasons":[],'
        '"suggested_type":"other","suggested_tags":[],"issues":[]}\n'
        "decision 必须是 approve/pending_review/reject 之一。\n"
        "risk_level 必须是 low/medium/high 之一。\n"
        "confidence 必须是 0-1 的浮点数。\n"
        "reasons 是批准理由的字符串数组。\n"
        "issues 是发现的问题的字符串数组。\n"
        "suggested_type 建议的知识类型。\n"
        "suggested_tags 建议的标签。"
    )


def build_user_prompt(proposal: dict) -> str:
    parts = [
        f"项目ID: {proposal.get('project_id', '')}",
        f"标题: {proposal.get('title', '')}",
        f"类型: {proposal.get('type', 'other')}",
        f"模块: {proposal.get('module', '')}",
        f"来源: {proposal.get('source_type', 'ai_inferred')}",
        f"scope: {proposal.get('scope', 'project')}",
        f"风险等级(检测): {proposal.get('risk_level', 'low')}",
        f"置信度: {proposal.get('confidence', 0.5)}",
    ]
    if proposal.get("tags"):
        parts.append(f"标签: {', '.join(proposal['tags'])}")
    if proposal.get("duplicate_info"):
        parts.append(f"重复信息: {proposal['duplicate_info']}")

    content = proposal.get("content", "")
    if len(content) > 4000:
        content = content[:4000] + "..."
    parts.append(f"\n知识内容:\n{content}")

    return "\n".join(parts)
