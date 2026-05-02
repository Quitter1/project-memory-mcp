"""SHA256 内容哈希 — 用于知识去重。"""

import hashlib


def compute_content_hash(content: str) -> str:
    """计算内容的 SHA256 哈希。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
