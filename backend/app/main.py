from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.singleton import rag_service, loader_service

app = FastAPI(title="GitChat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RepoRequest(BaseModel):
    repo_url: str

@app.post("/analyze")
async def analyze_repo(request: RepoRequest):
    try:
        print(f"Analyzing repo: {request.repo_url}")
        docs = loader_service.load_repo(request.repo_url)
        print(f"Loaded {len(docs)} documents")
        # 提取仓库名称作为持久化的键
        repo_name = request.repo_url.replace("/", "_")
        rag_service.process_documents(docs, repo_name)
        return {"status": "success", "message": f"Successfully analyzed {request.repo_url}"}
    except Exception as e:
        print(f"Error analyzing repo: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

from app.api.endpoints import chat
app.include_router(chat.router)
