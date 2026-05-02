"""文本处理工具。"""


def truncate_text(text: str, max_length: int = 500) -> str:
    """截断文本到指定长度。"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "…"


def sanitize_text(text: str) -> str:
    """清洗文本（移除不可见字符、规范化空白）。"""
    # TODO: 后续实现更完善的清洗逻辑
    return text.strip()
