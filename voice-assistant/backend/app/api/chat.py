from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import get_engine

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    stream: bool = True


@router.post("/chat")
def chat(req: ChatRequest):
    engine = get_engine()
    if not req.stream:
        result = engine.handle(req.message, req.session_id)
        return {"text": result.text, "source": result.source}

    def event_gen():
        for token in engine.stream_handle(req.message, req.session_id):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")