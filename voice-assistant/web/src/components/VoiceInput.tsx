import { useState, useRef } from "react";
import { connectVoiceWs } from "../api/client";

declare global {
  interface Window {
    webkitSpeechRecognition: any;
  }
}

export default function VoiceInput() {
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const recognitionRef = useRef<any>(null);

  const startListening = () => {
    const SpeechRecognition =
      window.webkitSpeechRecognition || ((window as any).SpeechRecognition as any);

    if (!SpeechRecognition) {
      setStatus("浏览器不支持语音识别");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "zh-CN";
    recognition.interimResults = false;
    recognition.continuous = false;

    recognition.onresult = (event: any) => {
      const text = event.results[0][0].transcript;
      setStatus(`识别: ${text}`);
      sendText(text);
    };

    recognition.onerror = (event: any) => {
      setStatus(`识别错误: ${event.error}`);
      setListening(false);
    };

    recognition.onend = () => setListening(false);

    recognition.start();
    setListening(true);
    setStatus("正在听...");
    recognitionRef.current = recognition;
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setListening(false);
    setStatus("");
  };

  const sendText = (text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      wsRef.current = connectVoiceWs();
      wsRef.current.onopen = () => wsRef.current?.send(JSON.stringify({ type: "text", text }));
      return;
    }
    wsRef.current.send(JSON.stringify({ type: "text", text }));
  };

  return (
    <div style={{ textAlign: "center", margin: 12 }}>
      <button
        onMouseDown={startListening}
        onMouseUp={stopListening}
        style={{ padding: "12px 24px", fontSize: 16 }}
      >
        {listening ? "松开结束" : "按住说话"}
      </button>
      {status && <div style={{ marginTop: 8, color: "#666" }}>{status}</div>}
    </div>
  );
}