import React from "react";
import type { ChatMessage, TakeoverState, AgentActivityEvent } from "../hooks/useWebSocket";
import type { UseVoiceReturn } from "../hooks/useVoice";
import { BrutalistMessageList } from "../components/chat/BrutalistMessageList";
import { BrutalistChatInput } from "../components/chat/BrutalistChatInput";
import "../styles/chat-brutalist.css";

type Props = {
  messages: ChatMessage[];
  isConnected: boolean;
  sendMessage: (text: string) => void;
  voice?: UseVoiceReturn;
  takeoverState?: TakeoverState | null;
  cancelTakeover?: () => void;
  agentActivity?: AgentActivityEvent[];
};

export default function BrutalistChatPage({
  messages, isConnected, sendMessage, voice, takeoverState, cancelTakeover,
}: Props) {

  // Top status line
  const status = (() => {
    if (!isConnected) return { dot: "err", text: "Channel offline · reconnecting" };
    if (voice?.voiceState === "recording") return { dot: "act", text: "Listening" };
    if (voice?.voiceState === "processing") return { dot: "act", text: "Processing" };
    if (voice?.ttsAudioPlaying || voice?.voiceState === "speaking") return { dot: "act", text: "Speaking" };
    if (voice?.voiceState === "wake_detected") return { dot: "warn", text: "Wake word detected" };
    if (voice?.voiceState === "error") return { dot: "err", text: "Voice error" };
    return { dot: "live", text: "Online" };
  })();

  const lastTs = messages.length ? messages[messages.length - 1].timestamp : Date.now();

  return (
    <div className="bch-root">
      {/* Status line */}
      <div className="bch-status">
        <span className={`bch-status-dot ${status.dot}`} />
        <span>{status.text}</span>
        <span className="bch-status-spacer" />
        <span className="bch-status-meta">
          MSG {String(messages.length).padStart(4, "0")} · LAST {new Date(lastTs).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>

      {/* Takeover */}
      {takeoverState?.active && (
        <div className="bch-takeover">
          <span className="bch-takeover-tag">TAKEOVER</span>
          <div className="bch-takeover-info">
            <strong>{takeoverState.task || "Sam is in autonomous control"}</strong>
            {takeoverState.stepNarration && <span className="bch-takeover-info-step">→ {takeoverState.stepNarration}</span>}
          </div>
          <button className="bch-takeover-cancel" onClick={cancelTakeover}>Cancel</button>
        </div>
      )}

      <BrutalistMessageList messages={messages} onPromptClick={sendMessage} />

      <BrutalistChatInput
        onSend={sendMessage}
        disabled={!isConnected}
        voice={voice ? {
          voiceState: voice.voiceState,
          startRecording: voice.startRecording,
          stopRecording: voice.stopRecording,
          isMicAvailable: voice.isMicAvailable,
          isWakeWordReady: voice.isWakeWordReady,
          ttsAudioPlaying: voice.ttsAudioPlaying,
          micLevel: voice.micLevel,
          cancelTTS: voice.cancelTTS,
          activeWakeEngine: voice.activeWakeEngine,
        } : undefined}
      />
    </div>
  );
}
