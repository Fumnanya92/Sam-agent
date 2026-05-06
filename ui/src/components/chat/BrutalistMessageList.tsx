import React, { useEffect, useRef } from "react";
import type { ChatMessage } from "../../hooks/useWebSocket";
import { MarkdownContent } from "./MarkdownContent";
import { SubAgentTag } from "./SubAgentTag";
import { ToolCallBadge } from "./ToolCallBadge";

type Props = {
  messages: ChatMessage[];
  onPromptClick?: (text: string) => void;
};

const PROMPTS = [
  "Show today's open tasks",
  "Summarize my pipeline status",
  "What's on the calendar this week?",
  "Run a quick health check",
];

function fmtTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function fmtDay(ts: number) {
  const d = new Date(ts);
  const today = new Date();
  const yest = new Date(); yest.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "TODAY";
  if (d.toDateString() === yest.toDateString()) return "YESTERDAY";
  return d.toLocaleDateString([], { month: "short", day: "numeric" }).toUpperCase();
}

export function BrutalistMessageList({ messages, onPromptClick }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="bch-empty">
        <div className="bch-empty-title">SAM // READY</div>
        <div className="bch-empty-sub">
          Channel open. Type a directive or invoke voice.
          <br />Wake-word, slash commands, and tool routing are live.
        </div>
        {onPromptClick && (
          <div className="bch-empty-prompts">
            {PROMPTS.map((p) => (
              <button key={p} className="bch-empty-prompt" onClick={() => onPromptClick(p)}>
                {p}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bch-scroll">
      <div className="bch-stream">
        {messages.map((m, i) => {
          const prev = messages[i - 1];
          const showDay =
            !prev || fmtDay(m.timestamp) !== fmtDay(prev.timestamp);
          return (
            <React.Fragment key={m.id}>
              {showDay && <div className="bch-time">{fmtDay(m.timestamp)}</div>}
              <BrutalistMessage msg={m} />
            </React.Fragment>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function BrutalistMessage({ msg }: { msg: ChatMessage }) {
  const ts = fmtTime(msg.timestamp);

  if (msg.role === "system") {
    const variant =
      msg.source === "error" || msg.priority === "urgent" ? "err" :
      msg.source === "heartbeat" ? "ok" :
      msg.source === "workflow" ? "warn" : "";
    const tag =
      msg.source === "error" ? "ERROR" :
      msg.source === "heartbeat" ? "PULSE" :
      msg.source === "workflow" ? "WORKFLOW" :
      (msg.source || "SYS").toUpperCase();
    return (
      <div className={`bch-msg bch-msg-system`}>
        <div className={`bch-system ${variant}`}>
          <span className="bch-system-tag">{tag}</span>
          <div className="bch-system-body">
            <MarkdownContent content={msg.content} />
          </div>
          <span className="bch-system-ts">{ts}</span>
        </div>
      </div>
    );
  }

  const isUser = msg.role === "user";
  return (
    <div className={`bch-msg ${isUser ? "bch-msg-user" : "bch-msg-sam"}`}>
      <div className="bch-sender">
        <span className="bch-sender-bracket">{isUser ? "[USR]" : "[SAM]"}</span>
        <span className={`bch-sender-name ${isUser ? "user" : ""}`}>
          {isUser ? "operator" : "sam.core"}
        </span>
        <span className="bch-sender-ts">{ts}</span>
      </div>

      {msg.subAgentEvents && msg.subAgentEvents.length > 0 && (
        <div className="bch-sa-row">
          {msg.subAgentEvents.map((e, i) => <SubAgentTag key={i} event={e} />)}
        </div>
      )}

      <div className={`bch-bubble ${isUser ? "bch-bubble-user" : "bch-bubble-sam"}`}>
        {isUser ? msg.content : <MarkdownContent content={msg.content} />}
        {msg.isStreaming && <span className="bch-cursor" />}
      </div>

      {msg.toolCalls && msg.toolCalls.length > 0 && (
        <div className="bch-tools">
          {msg.toolCalls.map((tc, i) => <ToolCallBadge key={i} toolCall={tc} />)}
        </div>
      )}
    </div>
  );
}
