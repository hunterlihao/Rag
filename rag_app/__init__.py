__all__ = ["KnowledgeBaseService", "RagService"]


def __getattr__(name: str):
    if name == "KnowledgeBaseService":
        from rag_app.services.knowledge_base import KnowledgeBaseService

        return KnowledgeBaseService
    if name == "RagService":
        from rag_app.services.rag_service import RagService

        return RagService
    raise AttributeError(f"module 'rag_app' has no attribute {name!r}")
