const BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function chatOnce(message: string, sessionId = "web") {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, stream: false }),
  });
  return res.json();
}

export function connectVoiceWs() {
  const url =
    (import.meta.env.VITE_WS_BASE || "ws://127.0.0.1:8000") +
    "/api/voice/ws";
  return new WebSocket(url);
}