from app.services.rag_service import RAGService
from app.services.github_loader import GitLoaderService
from app.services.local_loader import LocalLoaderService
from app.services.metrics import metrics

# 全局共享实例（metrics 供路由与评测接口读取）
rag_service = RAGService()
loader_service = GitLoaderService()
local_loader_service = LocalLoaderService()

__all__ = ["rag_service", "loader_service", "local_loader_service", "metrics"]
