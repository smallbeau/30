import ChatWindow from "./components/ChatWindow";
import VoiceInput from "./components/VoiceInput";

export default function App() {
  return (
    <div>
      <h1 style={{ textAlign: "center" }}>语音 AI 助手</h1>
      <VoiceInput />
      <ChatWindow />
    </div>
  );
}