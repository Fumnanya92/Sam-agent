import React, { useMemo, useState } from "react";
import type {
  ChatMessage,
  ToolCall,
  AgentActivityEvent,
} from "../hooks/useWebSocket";
import { SamFace, type SamFaceState } from "./SamFace";

type Tab = "trace" | "memory" | "artifacts";

type Props = {
  messages: ChatMessage[];
  agentActivity?: AgentActivityEvent[];
  faceState: SamFaceState;
  faceCaption?: string;
};

type ArtifactItem = {
  key: string;
  name: string;
  kind: string;
  ts: number;
};

function deriveArtifacts(messages: ChatMessage[]): ArtifactItem[] {
  const out: ArtifactItem[] = [];
  for (const m of messages) {
    if (m.testResult) {
      out.push({ key: m.id + ":test", name: m.testResult.testName, kind: "TEST", ts: m.timestamp });
    }
    if (m.tutorialStep) {
      out.push({ key: m.id + ":tut", name: `Tutorial step ${m.tutorialStep.stepIndex + 1}`, kind: "TUTORIAL", ts: m.timestamp });
    }
    if (m.screenView) {
      out.push({ key: m.id + ":scr", name: m.screenView.label || "Screen view", kind: "VISION", ts: m.timestamp });
    }
    if (m.toolCalls?.length) {
      for (const tc of m.toolCalls) {
        const args = tc.arguments || {};
        const path = (args as any).path || (args as any).file || (args as any).filename;
        if (typeof path === "string") {
          out.push({ key: m.id + ":" + tc.name + ":" + path, name: String(path).split("/").pop()!, kind: "FILE", ts: m.timestamp });
        }
      }
    }
  }
  // dedupe last 30
  const seen = new Set<string>();
  return out.filter(a => {
    if (seen.has(a.key)) return false;
    seen.add(a.key);
    return true;
  }).slice(-30).reverse();
}

function fmtTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function ContextRail({ messages, agentActivity, faceState, faceCaption }: Props) {
  const [tab, setTab] = useState<Tab>("trace");

  // Live trace = recent tool calls & sub-agent events
  const trace = useMemo(() => {
    const events: { id: string; kind: string; name: string; meta?: string; ts: number }[] = [];

    // tool calls from messages (latest first)
    [...messages].slice(-20).reverse().forEach((m) => {
      if (m.toolCalls?.length) {
        m.toolCalls.forEach((tc, i) => {
          events.push({
            id: m.id + ":tc:" + i,
            kind: "TOOL",
            name: tc.name,
            meta: tc.arguments ? JSON.stringify(tc.arguments).slice(0, 80) : undefined,
            ts: m.timestamp,
          });
        });
      }
      if (m.subAgentEvents?.length) {
        m.subAgentEvents.forEach((evt, i) => {
          events.push({
            id: m.id + ":sa:" + i,
            kind: evt.type === "tool_call" ? "AGENT/TOOL" : evt.type === "done" ? "AGENT/DONE" : "AGENT",
            name: evt.agentName,
            ts: m.timestamp,
          });
        });
      }
    });

    // recent agentActivity events (already most-recent-first)
    (agentActivity ?? []).slice(0, 12).forEach((e) => {
      events.push({
        id: e.id,
        kind: e.eventType === "tool_call" ? "AGENT/TOOL" : e.eventType === "done" ? "AGENT/DONE" : "AGENT",
        name: e.agentName,
        ts: e.timestamp,
      });
    });

    return events.slice(0, 40);
  }, [messages, agentActivity]);

  const artifacts = useMemo(() => deriveArtifacts(messages), [messages]);

  return (
    <aside className="bsh-rail" aria-label="Context rail">
      {/* Sam face on top */}
      <div className="bsh-rail-face">
        <SamFace state={faceState} size={120} caption={faceCaption} />
      </div>

      <div className="bsh-rail-head">
        <button className={`bsh-rail-tab ${tab === "trace" ? "active" : ""}`} onClick={() => setTab("trace")}>
          Trace
        </button>
        <button className={`bsh-rail-tab ${tab === "memory" ? "active" : ""}`} onClick={() => setTab("memory")}>
          Memory
        </button>
        <button className={`bsh-rail-tab ${tab === "artifacts" ? "active" : ""}`} onClick={() => setTab("artifacts")}>
          Artifacts
        </button>
      </div>

      <div className="bsh-rail-body">
        {tab === "trace" && (
          trace.length === 0 ? (
            <div className="bsh-rail-empty">
              No tool activity yet.
              <br />Agent events will stream here.
            </div>
          ) : (
            <>
              <div className="bsh-rail-section">Live</div>
              {trace.map((e) => (
                <div key={e.id} className="bsh-trace-evt">
                  <span className="bsh-trace-evt-tick">▸</span>
                  <div>
                    <div className="bsh-trace-evt-name">{e.kind} · {e.name}</div>
                    <div className="bsh-trace-evt-meta">
                      {fmtTime(e.ts)}{e.meta ? ` · ${e.meta}` : ""}
                    </div>
                  </div>
                </div>
              ))}
            </>
          )
        )}

        {tab === "memory" && (
          <div className="bsh-rail-empty">
            Memory recall stream<br />
            wiring not yet connected.
            <br /><br />
            Hook a memory feed into ContextRail to surface live recalls here.
          </div>
        )}

        {tab === "artifacts" && (
          artifacts.length === 0 ? (
            <div className="bsh-rail-empty">
              No artifacts yet.
              <br />Files, tests and screenshots from the conversation will appear here.
            </div>
          ) : (
            <>
              <div className="bsh-rail-section">Generated</div>
              {artifacts.map((a) => (
                <div key={a.key} className="bsh-art">
                  <div className="bsh-art-name">{a.name}</div>
                  <div className="bsh-art-meta">{a.kind} · {fmtTime(a.ts)}</div>
                </div>
              ))}
            </>
          )
        )}
      </div>
    </aside>
  );
}
