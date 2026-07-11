import { useState, useRef, useEffect } from "react";
import { chatOnce } from "../api/client";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setMessages((p) => [...p, { role: "user", content: text }]);
    setInput("");
    setLoading(true);
    try {
      const res = await chatOnce(text);
      const reply = res.text || "";
      setMessages((p) => [...p, { role: "assistant", content: reply }]);
    } catch {
      setMessages((p) => [
        ...p,
        { role: "assistant", content: "请求失败，请检查后端是否启动" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div style={{ maxWidth: 600, margin: "0 auto", padding: 16 }}>
      <div
        style={{ height: 400, overflow: "auto", border: "1px solid #ccc", padding: 8 }}
      >
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 8 }}>
            <b>{m.role === "user" ? "我" : "助手"}:</b> {m.content}
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="输入消息..."
          style={{ flex: 1, padding: 8 }}
        />
        <button onClick={send} disabled={loading}>
          发送
        </button>
      </div>
    </div>
  );
}