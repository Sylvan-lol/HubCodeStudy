import json
import asyncio
from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
# 关键：从 singleton 导入共享实例
from app.singleton import rag_service

router = APIRouter()

@router.post("/chat")
async def chat_stream(message: str = Body(..., embed=True)):
    async def event_generator():
        try:
            async for content in rag_service.stream_answer(message):
                yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_msg = f"聊天服务暂不可用：{str(e)}"
            yield f"data: {json.dumps({'content': error_msg}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
