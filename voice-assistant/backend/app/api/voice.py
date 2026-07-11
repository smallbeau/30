import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import get_engine
from app.voice.tts import synthesize_mp3

router = APIRouter(tags=["voice"])


@router.websocket("/voice/ws")
async def voice_ws(ws: WebSocket):
    await ws.accept()
    engine = get_engine()
    speaking = False
    try:
        while True:
            data = await ws.receive_json()
            typ = data.get("type")
            if typ == "interrupt":
                speaking = False
                await ws.send_json({"type": "interrupted"})
                continue
            if typ == "text":
                text = data.get("text", "").strip()
                session_id = data.get("session_id", "default")
                if not text:
                    continue
                speaking = True
                parts: list[str] = []
                for token in engine.stream_handle(text, session_id):
                    if not speaking:
                        break
                    parts.append(token)
                    await ws.send_json({"type": "token", "text": token})
                full = "".join(parts)
                if speaking and full:
                    audio = await synthesize_mp3(full)
                    await ws.send_json({
                        "type": "audio",
                        "format": "mp3",
                        "data": base64.b64encode(audio).decode("ascii"),
                    })
                await ws.send_json({"type": "done"})
                speaking = False
    except WebSocketDisconnect:
        return