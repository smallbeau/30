from __future__ import annotations

import asyncio
import base64
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import get_engine
from app.voice.pipeline import VoicePipeline, VoicePipelineConfig
from app.voice.tts import synthesize_mp3

router = APIRouter(tags=["voice"])
_pipeline: VoicePipeline | None = None


def get_pipeline() -> VoicePipeline:
    global _pipeline
    if _pipeline is None:
        import yaml
        from app.config import get_settings
        s = get_settings()
        cfg_data = yaml.safe_load(s.voice_config_path.read_text(encoding="utf-8")) or {}
        w = cfg_data.get("wake", {})
        a = cfg_data.get("asr", {})
        t = cfg_data.get("tts", {})
        p = cfg_data.get("pipeline", {})
        vad_data = yaml.safe_load(s.vad_config_path.read_text(encoding="utf-8")) or {}
        _pipeline = VoicePipeline(VoicePipelineConfig(
            wake_enabled=w.get("enabled", False),
            wake_keyword=w.get("keyword", "小助手"),
            wake_sensitivity=w.get("sensitivity", 0.5),
            asr_provider=a.get("provider", "mock"),
            asr_model=a.get("model", "base"),
            asr_device=a.get("device", "cpu"),
            asr_language=a.get("language", "zh"),
            tts_provider=t.get("primary", "edge-tts"),
            tts_voice=t.get("edge_tts", {}).get("voice", "zh-CN-XiaoxiaoNeural"),
            auto_send_audio=p.get("auto_send_audio", True),
            vad_silence_ms=vad_data.get("silence_threshold_ms", 500),
            vad_threshold=vad_data.get("threshold", 0.5),
            vad_min_speech_ms=vad_data.get("min_speech_duration_ms", 300),
            vad_min_silence_ms=vad_data.get("min_silence_duration_ms", 200),
            vad_speech_pad_ms=vad_data.get("speech_pad_ms", 300),
        ))
    return _pipeline


@router.websocket("/voice/ws")
async def voice_ws(ws: WebSocket):
    await ws.accept()
    engine = get_engine()
    pipeline = get_pipeline()
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
                    audio = await pipeline.synthesize(full)
                    await ws.send_json({
                        "type": "audio",
                        "format": "mp3",
                        "data": base64.b64encode(audio).decode("ascii"),
                    })
                await ws.send_json({"type": "done"})
                speaking = False
            elif typ == "audio":
                pcm = base64.b64decode(data.get("data", ""))
                if not pcm:
                    continue
                text = await pipeline.transcribe_audio(pcm)
                if text.strip():
                    await ws.send_json({"type": "transcription", "text": text.strip()})
    except WebSocketDisconnect:
        return
    except (ValueError, json.JSONDecodeError):
        try:
            await ws.send_json({"type": "error", "detail": "invalid message"})
        except Exception:
            pass


@router.get("/voice/pipeline")
def pipeline_status():
    p = get_pipeline()
    return {
        "asr_available": p.asr.available,
        "asr_provider": p.config.asr_provider,
        "tts_provider": p.config.tts_provider,
        "wake_enabled": p.config.wake_enabled,
        "wake_keyword": p.config.wake_keyword,
    }


@router.websocket("/voice/full_duplex")
async def voice_full_duplex(ws: WebSocket, session_id: str = "default", mode: str = "fallback"):
    await ws.accept()
    pipeline = get_pipeline()
    gateway = FullDuplexGateway(pipeline)
    session = gateway.create_session(session_id, mode)
    engine = get_engine()

    async def _stream_handle(text: str, session_id: str):
        for token in engine.stream_handle(text, session_id):
            yield token

    try:
        while True:
            data = await ws.receive_json()
            typ = data.get("type")
            if typ == "audio":
                pcm = base64.b64decode(data.get("data", ""))
                if not pcm:
                    continue
                text = await gateway.process_audio_frame(session_id, pcm)
                if text:
                    await ws.send_json({"type": "transcription", "text": text})
                    parts: list[str] = []
                    async for token in gateway.process_text(session_id, text, _stream_handle):
                        parts.append(token)
                        await ws.send_json({"type": "token", "text": token})
                    full = "".join(parts)
                    if full:
                        audio = await pipeline.synthesize(full)
                        await ws.send_json({
                            "type": "audio", "format": "mp3",
                            "data": base64.b64encode(audio).decode("ascii"),
                        })
                    await ws.send_json({"type": "done"})
            elif typ == "interrupt":
                await ws.send_json({"type": "interrupted"})
            elif typ == "end":
                gateway.end_session(session_id)
                await ws.send_json({"type": "ended"})
                break
    except WebSocketDisconnect:
        gateway.end_session(session_id)
    except PCMBufferLimitError as e:
        await ws.send_json({"type": "error", "detail": str(e)})
        gateway.end_session(session_id)
    except (ValueError, json.JSONDecodeError):
        await ws.send_json({"type": "error", "detail": "invalid message"})
        gateway.end_session(session_id)



