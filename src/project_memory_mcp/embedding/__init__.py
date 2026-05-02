"""Embedding 模块 — 抽象接口 + Mock 实现 + 预留扩展点。

后续扩展命名约定：
- http_embedder.py: 通用 HTTP embedding 服务
- openai_compatible_embedder.py: OpenAI 兼容接口
- local_embedder_client.py: 本地 embedding（bge-m3, jina, gte 等）
"""

from .base import Embedder
from .mock_embedder import MockEmbedder

__all__ = ["Embedder", "MockEmbedder"]
