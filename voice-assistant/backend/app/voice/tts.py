import edge_tts


async def synthesize_mp3(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
    communicate = edge_tts.Communicate(text, voice)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)