import time
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.endpoints import chat
from app.services.error_codes import classify_analyze_error, human_message_for_code
from app.services.metrics import metrics
from app.singleton import loader_service, local_loader_service, rag_service

app = FastAPI(title="GitChat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RepoRequest(BaseModel):
    repo_url: str


class LocalRepoRequest(BaseModel):
    local_path: str


@app.get("/metrics")
async def get_metrics():
    """Aggregated rates for /benchmark dashboard."""
    return {"ok": True, "metrics": metrics.snapshot()}


@app.post("/analyze")
async def analyze_repo(request: RepoRequest):
    repo_slug = loader_service.normalize_repo_key(request.repo_url)
    t0 = time.perf_counter()
    cache_hit = False
    try:
        docs, cache_hit = loader_service.load_repo(request.repo_url)
        t_after_load = time.perf_counter()
        repo_name = repo_slug.replace("/", "_")
        rag_service.process_documents(docs, repo_name, repo_slug=repo_slug)
        t_end = time.perf_counter()
        metrics.record_analyze_finish(success=True, cache_hit=cache_hit)
        load_ms = round((t_after_load - t0) * 1000)
        index_ms = round((t_end - t_after_load) * 1000)
        return {
            "status": "success",
            "message": f"Successfully analyzed {repo_slug}",
            "repo_slug": repo_slug,
            "cache_hit": cache_hit,
            "timings_ms": {
                "load": load_ms,
                "index": index_ms,
                "total": load_ms + index_ms,
            },
            "stages": {
                "queue": "done",
                "clone_or_cache": "cache_hit" if cache_hit else "cloned",
                "index": "done",
                "ready": "chat",
            },
        }
    except Exception as e:
        code = classify_analyze_error(e)
        metrics.record_analyze_finish(success=False, cache_hit=False)
        detail = {
            "code": code,
            "message": str(e),
            "hint": human_message_for_code(code, str(e)),
            "repo_slug": repo_slug,
        }
        raise HTTPException(status_code=400, detail=detail)


@app.post("/analyze-local")
async def analyze_local_repo(request: LocalRepoRequest):
    local_path = request.local_path.strip()
    t0 = time.perf_counter()
    cache_hit = False
    try:
        abs_path = local_loader_service.normalize_path(local_path)
        repo_name = os.path.basename(abs_path)
        repo_slug = repo_name.replace(" ", "_")
        
        docs, cache_hit = local_loader_service.load_repo(local_path)
        t_after_load = time.perf_counter()
        
        rag_service.process_documents(docs, repo_name, repo_slug=repo_slug)
        t_end = time.perf_counter()
        
        metrics.record_analyze_finish(success=True, cache_hit=cache_hit)
        load_ms = round((t_after_load - t0) * 1000)
        index_ms = round((t_end - t_after_load) * 1000)
        return {
            "status": "success",
            "message": f"成功分析本地项目 {repo_name}",
            "repo_slug": repo_slug,
            "repo_name": repo_name,
            "local_path": abs_path,
            "cache_hit": cache_hit,
            "timings_ms": {
                "load": load_ms,
                "index": index_ms,
                "total": load_ms + index_ms,
            },
            "stages": {
                "queue": "done",
                "clone_or_cache": "cache_hit" if cache_hit else "scanned",
                "index": "done",
                "ready": "chat",
            },
        }
    except Exception as e:
        code = classify_analyze_error(e)
        metrics.record_analyze_finish(success=False, cache_hit=False)
        abs_path = local_loader_service.normalize_path(local_path) if local_path.strip() else ""
        detail = {
            "code": code,
            "message": str(e),
            "hint": human_message_for_code(code, str(e)),
            "repo_slug": os.path.basename(abs_path) if abs_path else "unknown",
        }
        raise HTTPException(status_code=400, detail=detail)


app.include_router(chat.router)
