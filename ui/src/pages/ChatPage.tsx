import React from "react";
import type { ChatMessage, TakeoverState } from "../hooks/useWebSocket";
import type { UseVoiceReturn } from "../hooks/useVoice";
import { MessageList } from "../components/chat/MessageList";
import { ChatInput } from "../components/chat/ChatInput";
import "../styles/chat.css";

type ChatPageProps = {
  messages: ChatMessage[];
  isConnected: boolean;
  sendMessage: (text: string) => void;
  voice?: UseVoiceReturn;
  takeoverState?: TakeoverState | null;
  cancelTakeover?: () => void;
};

export default function ChatPage({ messages, isConnected, sendMessage, voice, takeoverState, cancelTakeover }: ChatPageProps) {
  const voiceStatus = voice
    ? voice.voiceState === "speaking" || voice.ttsAudioPlaying
      ? { text: "Sam is speaking...", cls: "chat-status-voice" }
      : voice.voiceState === "processing"
        ? { text: "Thinking...", cls: "chat-status-voice" }
        : voice.voiceState === "recording"
          ? { text: "Listening to you...", cls: "chat-status-recording" }
          : voice.voiceState === "wake_detected"
            ? { text: "Wake word detected!", cls: "chat-status-wake" }
            : voice.voiceState === "error"
              ? { text: "Voice error — retrying", cls: "chat-status-voice-error" }
              : voice.isMicAvailable
                ? { text: voice.isWakeWordReady ? "Say \u201cHey Sam\u201d or click the mic" : "Click the mic to speak", cls: "chat-status-idle" }
                : null
    : null;

  return (
    <div className="chat-page">
      {/* Atmosphere — Three-layer living background */}
      <div className="chat-atmos">
        {/* Layer 1: Aurora gradients */}
        <div className="chat-atmos-aurora" />

        {/* Layer 2: Constellation dots + SVG connectors */}
        <div className="chat-atmos-constellation">
          <div className="chat-const-node drift" style={{ width: 3, height: 3, background: "rgba(139,92,246,0.15)", top: "12%", left: "18%", "--dur": "12s", "--delay": "0s" } as React.CSSProperties} />
          <div className="chat-const-node drift" style={{ width: 2, height: 2, background: "rgba(96,165,250,0.12)", top: "28%", left: "72%", "--dur": "15s", "--delay": "2s" } as React.CSSProperties} />
          <div className="chat-const-node drift" style={{ width: 2, height: 2, background: "rgba(52,211,153,0.10)", top: "65%", left: "35%", "--dur": "18s", "--delay": "4s" } as React.CSSProperties} />
          <div className="chat-const-node drift" style={{ width: 3, height: 3, background: "rgba(139,92,246,0.12)", top: "80%", left: "82%", "--dur": "14s", "--delay": "1s" } as React.CSSProperties} />
          <div className="chat-const-node" style={{ width: 2, height: 2, background: "rgba(96,165,250,0.08)", top: "45%", left: "55%" }} />

          <svg className="chat-const-svg">
            <line x1="18%" y1="12%" x2="72%" y2="28%" stroke="rgba(139,92,246,0.03)" strokeWidth="1" strokeDasharray="4 8" style={{ animation: "chat-flowPulse 4s linear infinite" }} />
            <line x1="35%" y1="65%" x2="82%" y2="80%" stroke="rgba(52,211,153,0.02)" strokeWidth="1" strokeDasharray="4 8" style={{ animation: "chat-flowPulse 5s linear infinite" }} />
          </svg>
        </div>

        {/* Layer 3: Data stream particles */}
        <div className="chat-stream-channel" style={{ left: "22%" }}>
          <div className="chat-stream-particle" style={{ background: "rgba(139,92,246,0.18)", "--dur": "8s", "--delay": "0s" } as React.CSSProperties} />
          <div className="chat-stream-particle" style={{ background: "rgba(139,92,246,0.12)", "--dur": "12s", "--delay": "3s" } as React.CSSProperties} />
        </div>
        <div className="chat-stream-channel" style={{ left: "68%" }}>
          <div className="chat-stream-particle" style={{ background: "rgba(96,165,250,0.14)", "--dur": "10s", "--delay": "1s" } as React.CSSProperties} />
          <div className="chat-stream-particle" style={{ background: "rgba(52,211,153,0.10)", "--dur": "14s", "--delay": "5s" } as React.CSSProperties} />
        </div>
        <div className="chat-stream-channel" style={{ left: "45%" }}>
          <div className="chat-stream-particle" style={{ background: "rgba(139,92,246,0.10)", "--dur": "11s", "--delay": "2s" } as React.CSSProperties} />
        </div>
      </div>

      {/* Connection status bar */}
      {!isConnected && (
        <div className="chat-status-bar chat-status-disconnected">
          <span className="chat-status-dot chat-status-dot-recording" />
          Disconnected from Sam. Reconnecting...
        </div>
      )}

      {/* Voice status bar — always visible when mic available */}
      {voiceStatus && (
        <div className={`chat-status-bar ${voiceStatus.cls}`}>
          <span className={`chat-status-dot ${
            voice?.voiceState === "recording" ? "chat-status-dot-recording"
            : voice?.voiceState === "wake_detected" ? "chat-status-dot-wake"
            : voice?.voiceState === "error" ? "chat-status-dot-recording"
            : voice?.voiceState === "idle" ? "chat-status-dot-idle"
            : "chat-status-dot-voice"
          }`} />
          {voiceStatus.text}
        </div>
      )}

      {/* Takeover mode banner */}
      {takeoverState?.active && (
        <div className="chat-takeover-banner">
          <div className="chat-takeover-orb" />
          <div className="chat-takeover-info">
            <span className="chat-takeover-title">Sam is in control</span>
            {takeoverState.task && (
              <span className="chat-takeover-task">{takeoverState.task}</span>
            )}
            {takeoverState.stepNarration && (
              <span className="chat-takeover-step">{takeoverState.stepNarration}</span>
            )}
          </div>
          <button className="chat-takeover-cancel" onClick={cancelTakeover}>
            Cancel
          </button>
        </div>
      )}

      {/* Messages */}
      <MessageList messages={messages} />

      {/* Input */}
      <ChatInput
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
