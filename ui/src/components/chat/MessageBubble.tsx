import React from "react";
import type { ChatMessage } from "../../hooks/useWebSocket";
import { ToolCallBadge } from "./ToolCallBadge";
import { SubAgentTag } from "./SubAgentTag";
import { MarkdownContent } from "./MarkdownContent";
import { TutorialStepCard } from "./TutorialStepCard";
import { TestResultCard } from "./TestResultCard";

type Props = {
  message: ChatMessage;
};

function getSystemType(message: ChatMessage): "heartbeat" | "error" | "workflow" | "default" {
  if (message.source === "error" || message.priority === "urgent") return "error";
  if (message.source === "heartbeat") return "heartbeat";
  if (message.source === "workflow") return "workflow";
  return "default";
}

function getSystemIcon(type: string): string {
  switch (type) {
    case "heartbeat": return "\u2661"; // heart
    case "error": return "\u26A0";     // warning
    case "workflow": return "\u25B6";   // play
    default: return "\u25C7";           // diamond
  }
}

function getSystemLabel(type: string, message: ChatMessage): string {
  switch (type) {
    case "heartbeat": return "Heartbeat";
    case "error": return "Error";
    case "workflow": return "Workflow";
    default: return message.source || "System";
  }
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const timestamp = new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  // System messages — notification cards
  if (isSystem) {
    // Live screen view panel
    if (message.source === "screen_view" && message.screenView) {
      const sv = message.screenView;
      if (!sv.imageBase64) return null;
      return (
        <div className="chat-msg chat-msg-system">
          <div className="chat-screen-view-panel">
            <div className="chat-screen-view-header">
              <span className={`chat-screen-view-dot${sv.active ? " chat-screen-view-dot-live" : ""}`} />
              <span className="chat-screen-view-title">
                Sam Vision{sv.label ? ` — ${sv.label}` : ""}{sv.active ? "" : " (paused)"}
              </span>
            </div>
            <img
              className="chat-screen-view-img"
              src={`data:image/png;base64,${sv.imageBase64}`}
              alt="Sam screen view"
            />
          </div>
        </div>
      );
    }

    // Tutorial step card
    if (message.source === "tutorial_step" && message.tutorialStep) {
      return (
        <div className="chat-msg chat-msg-system">
          <TutorialStepCard step={message.tutorialStep} />
        </div>
      );
    }

    // Test result card
    if (message.source === "test_result" && message.testResult) {
      return (
        <div className="chat-msg chat-msg-system">
          <TestResultCard result={message.testResult} />
        </div>
      );
    }

    const type = getSystemType(message);

    return (
      <div className="chat-msg chat-msg-system">
        <div className="chat-system-card">
          <div className={`chat-system-icon chat-system-icon-${type}`}>
            {getSystemIcon(type)}
          </div>
          <div className="chat-system-body">
            <div className={`chat-system-label chat-system-label-${type}`}>
              {getSystemLabel(type, message)}
            </div>
            <div className={`chat-system-text ${type === "error" ? "chat-system-text-error" : ""}`}>
              <MarkdownContent content={message.content} />
            </div>
            <div className="chat-system-ts">{timestamp}</div>
          </div>
        </div>
      </div>
    );
  }

  // User / Sam messages
  return (
    <div className={`chat-msg ${isUser ? "chat-msg-user" : "chat-msg-sam"}`}>
      {/* Sam sender row */}
      {!isUser && (
        <div className="chat-sender">
          <div className="chat-sender-orb" />
          <span className="chat-sender-name">Sam</span>
          <span className="chat-sender-ts">{timestamp}</span>
        </div>
      )}

      {/* Sub-agent tags */}
      {message.subAgentEvents && message.subAgentEvents.length > 0 && (
        <div className="chat-sa-row">
          {message.subAgentEvents.map((evt, i) => (
            <SubAgentTag key={i} event={evt} />
          ))}
        </div>
      )}

      {/* Bubble */}
      <div className={`chat-bubble ${isUser ? "chat-bubble-user" : "chat-bubble-sam"}`}>
        {isUser ? message.content : <MarkdownContent content={message.content} />}
        {message.isStreaming && <span className="chat-cursor" />}
      </div>

      {/* Tool calls */}
      {message.toolCalls && message.toolCalls.length > 0 && (
        <div className="chat-tools-row">
          {message.toolCalls.map((tc, i) => (
            <ToolCallBadge key={i} toolCall={tc} />
          ))}
        </div>
      )}

      {/* Timestamp for user messages */}
      {isUser && <div className="chat-ts chat-ts-right">{timestamp}</div>}
    </div>
  );
}
