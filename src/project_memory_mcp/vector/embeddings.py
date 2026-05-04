"""
Embedding 抽象 + HashingEmbeddingProvider + HttpEmbeddingProvider。

Phase 10: 确定性 hash embedding 用于本地测试，HTTP provider 预留真实服务。
"""

import abc
import hashlib
import math
from typing import Optional


class BaseEmbeddingProvider(abc.ABC):
    """Embedding 抽象基类。"""

    dim: int
    model: str

    @abc.abstractmethod
    def embed_text(self, text: str) -> list[float]:
        ...


class HashingEmbeddingProvider(BaseEmbeddingProvider):
    """确定性本地 embedding — 基于 token hashing。

    不依赖外部模型，相同文本每次返回一致向量，L2 normalized。
    仅用于 Qdrant 流程测试，不是高质量语义 embedding。
    """

    def __init__(self, dim: int = 512, model: str = "hashing-v1"):
        self.dim = dim
        self.model = model
        self.provider = "hashing"

    def embed_text(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self.dim

        vec = [0.0] * self.dim
        # 按词切分，对每个 token hash 到某维度位置并累加
        tokens = text.replace("\n", " ").split()
        if not tokens:
            tokens = [text]

        for token in tokens:
            h = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(0, len(h), 4):
                idx = int.from_bytes(h[i:i + 4], "big") % self.dim
                vec[idx] += 1.0

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec


class HttpEmbeddingProvider(BaseEmbeddingProvider):
    """HTTP embedding 服务 — 预留真实文本 embedding。

    POST {base_url}{endpoint}
    body: {"text": "..."}
    response: {"vector": [...]} 或 {"embedding": [...]}
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8008",
        endpoint: str = "/embed_text",
        dim: int = 768,
        model: str = "http-v1",
        timeout_seconds: int = 30,
    ):
        self.dim = dim
        self.model = model
        self.provider = "http"
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint
        self.timeout = timeout_seconds

    def embed_text(self, text: str) -> list[float]:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx 未安装，请 pip install httpx")

        url = f"{self.base_url}{self.endpoint}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json={"text": text})
            resp.raise_for_status()
            data = resp.json()
            vec = data.get("vector") or data.get("embedding") or []
            if len(vec) != self.dim:
                raise ValueError(f"embedding dim 不匹配: 期望 {self.dim}, 实际 {len(vec)}")
            return vec
