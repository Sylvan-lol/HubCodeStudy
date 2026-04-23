from app.services.rag_service import RAGService
from app.services.github_loader import GitLoaderService

# 全局共享实例
rag_service = RAGService()
loader_service = GitLoaderService()
