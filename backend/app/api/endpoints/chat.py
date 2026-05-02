import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.singleton import rag_service

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat_stream(body: ChatRequest):
    async def event_generator():
        try:
            async for chunk in rag_service.stream_answer(body.message):
                if isinstance(chunk, dict):
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                else:
                    # 兼容旧格式（纯字符串）
                    yield f"data: {json.dumps({'type': 'response', 'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_msg = f"聊天服务暂不可用：{str(e)}"
            yield f"data: {json.dumps({'type': 'response', 'content': error_msg}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
