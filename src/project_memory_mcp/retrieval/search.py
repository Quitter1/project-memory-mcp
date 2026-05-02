"""统一搜索入口 — keyword + vector 降级，三级范围检索。"""


class KnowledgeSearchService:
    """
    搜索策略（keyword-first）：
    1. 先执行 SQLite keyword search（必须可用）
    2. 如果 vector store 可用，执行语义搜索
    3. 合并 keyword + semantic 结果
    4. 如果 vector store 不可用，返回纯 keyword 结果（不影响主流程）

    三级范围检索：
    1. 当前 project scope=project 知识
    2. scope=shared 且 allowed_projects 包含当前项目
    3. scope=global 知识
    """

    def __init__(self, memory_repo, vector_store, embedder):
        self.memory_repo = memory_repo
        self.vector_store = vector_store
        self.embedder = embedder
        self.keyword_search = None  # TODO: 阶段 3 初始化
        self.ranker = None  # TODO: 阶段 3 初始化

    # TODO: 阶段 3 实现
    # async search(project_id, query, **filters) -> ContextPack
