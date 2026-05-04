"""
QdrantVectorStore — Qdrant 向量存储，只存安全 payload。

Phase 10: collection 管理, upsert, delete, search, health_check。
"""

import logging

logger = logging.getLogger("project_memory_mcp")

# Qdrant payload 安全字段白名单（不存 content/source_evidence 原文）
SAFE_PAYLOAD_FIELDS = {
    "memory_id", "project_id", "scope", "status", "type", "module",
    "tags", "allowed_projects", "denied_projects", "risk_level", "updated_at",
    "embedding_provider", "embedding_model", "embedding_dim",
}

DEFAULT_COLLECTION = "project_memory_items"


class QdrantStoreError(Exception):
    """Qdrant 操作错误。"""
    pass


class QdrantVectorStore:
    """Qdrant 向量存储封装。"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6333,
        collection: str = DEFAULT_COLLECTION,
        vector_dim: int = 512,
        timeout_seconds: int = 10,
        prefer_grpc: bool = False,
    ):
        self.host = host
        self.port = port
        self.collection_name = collection
        self.vector_dim = vector_dim
        self.timeout = timeout_seconds
        self.prefer_grpc = prefer_grpc
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.http.exceptions import UnexpectedResponse
                self._client = QdrantClient(
                    host=self.host, port=self.port,
                    timeout=self.timeout, prefer_grpc=self.prefer_grpc,
                )
            except ImportError:
                raise QdrantStoreError("qdrant-client 未安装，请 pip install qdrant-client")
        return self._client

    def health_check(self) -> dict:
        try:
            client = self._ensure_client()
            collections = client.get_collections()
            names = [c.name for c in collections.collections]
            exists = self.collection_name in names
            info = {"connected": True, "collection_exists": exists, "collections": names}
            if exists:
                info["collection"] = self.collection_name
            return info
        except Exception as exc:
            logger.warning("qdrant_health_check_failed: %s", exc)
            return {"connected": False, "error": str(exc)}

    def ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams
        client = self._ensure_client()
        try:
            client.get_collection(self.collection_name)
            logger.info("qdrant_collection_exists: %s", self.collection_name)
        except Exception:
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("qdrant_collection_created: %s dim=%d", self.collection_name, self.vector_dim)

    def _build_point(self, memory_id: str, vector: list[float], metadata: dict) -> dict:
        from qdrant_client.models import PointStruct
        safe_payload = {k: v for k, v in metadata.items() if k in SAFE_PAYLOAD_FIELDS}
        return PointStruct(id=memory_id, vector=vector, payload=safe_payload)

    def upsert_memory(self, memory_id: str, vector: list[float], metadata: dict) -> None:
        client = self._ensure_client()
        point = self._build_point(memory_id, vector, metadata)
        client.upsert(collection_name=self.collection_name, points=[point])
        logger.info("qdrant_upsert: memory_id=%s", memory_id)

    def delete_memory(self, memory_id: str) -> None:
        from qdrant_client.models import PointIdsList
        client = self._ensure_client()
        client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=[memory_id]),
        )
        logger.info("qdrant_delete: memory_id=%s", memory_id)

    def count_points(self) -> int:
        """返回当前 collection 的 points 数量。"""
        try:
            client = self._ensure_client()
            result = client.count(collection_name=self.collection_name, exact=True)
            return result.count if hasattr(result, "count") else 0
        except Exception:
            return 0

    def search(
        self,
        vector: list[float],
        project_id: str,
        scope_filter: str = "project",
        top_k: int = 30,
        allowed_projects: list[str] | None = None,
    ) -> list[dict]:
        """向量搜索，按 scope 过滤。

        返回 [{"id": ..., "score": ..., "payload": {...}}, ...]
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = self._ensure_client()

        must_conditions = [
            FieldCondition(key="status", match=MatchValue(value="approved")),
        ]

        if scope_filter == "project":
            must_conditions.append(FieldCondition(key="scope", match=MatchValue(value="project")))
            must_conditions.append(FieldCondition(key="project_id", match=MatchValue(value=project_id)))
        elif scope_filter == "global":
            must_conditions.append(FieldCondition(key="scope", match=MatchValue(value="global")))
        elif scope_filter == "shared":
            must_conditions.append(FieldCondition(key="scope", match=MatchValue(value="shared")))

        qfilter = Filter(must=must_conditions)

        # qdrant-client 1.17+: query_points; old: search
        if hasattr(client, "query_points"):
            result = client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=qfilter,
                limit=top_k,
                with_payload=True,
            )
            points = result.points if hasattr(result, "points") else result
        elif hasattr(client, "search"):
            points = client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=qfilter,
                limit=top_k,
                with_payload=True,
            )
        else:
            raise QdrantStoreError("当前 qdrant-client 不支持 query_points/search")

        return [
            {"id": p.id, "score": p.score, "payload": p.payload}
            for p in points
        ]
