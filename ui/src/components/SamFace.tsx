import React from "react";
import type { VoiceState } from "../hooks/useVoice";
import "../styles/sam-face.css";

export type SamFaceState =
  | "idle"
  | "thinking"
  | "listening"
  | "speaking"
  | "happy"
  | "error";

type Props = {
  state: SamFaceState;
  size?: number;            // px, square. Default 96
  caption?: string | false; // show status caption
  showFrame?: boolean;      // CRT frame, default true
  onClick?: () => void;
  className?: string;
};

const STATE_LABEL: Record<SamFaceState, string> = {
  idle: "Online",
  thinking: "Processing",
  listening: "Listening",
  speaking: "Speaking",
  happy: "Ready",
  error: "Fault",
};

/**
 * Map the existing VoiceState (or any external signal) to a SamFace state.
 * Exported so callers can keep a single source of truth.
 */
export function voiceStateToFace(
  vs: VoiceState | undefined,
  opts: { ttsPlaying?: boolean; hasError?: boolean } = {},
): SamFaceState {
  if (opts.hasError || vs === "error") return "error";
  if (opts.ttsPlaying || vs === "speaking") return "speaking";
  if (vs === "processing") return "thinking";
  if (vs === "recording" || vs === "wake_detected") return "listening";
  return "idle";
}

export function SamFace({
  state,
  size = 96,
  caption,
  showFrame = true,
  onClick,
  className = "",
}: Props) {
  // Geometry — viewBox 100x100 centered
  // Eye y-position varies by state (happy = lower, raised arc above for "smile")
  return (
    <div className={`sam-face-wrap ${className}`} style={{ display: "inline-flex", flexDirection: "column", alignItems: "center" }}>
      <div
        className="sam-face"
        data-state={state}
        onClick={onClick}
        role={onClick ? "button" : "img"}
        aria-label={`Sam — ${STATE_LABEL[state]}`}
        tabIndex={onClick ? 0 : undefined}
        style={{ width: size, height: size, cursor: onClick ? "pointer" : "default" }}
      >
        <div className={showFrame ? "sam-face-frame" : ""} style={{ width: "100%", height: "100%" }}>
            <svg
              className="sam-face-svg"
              viewBox="0 0 100 100"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              {/* Listening rings (only animate in listening state) */}
              <circle className="sam-listen-ring" cx="32" cy="42" r="10" fill="none" stroke="currentColor" strokeWidth="1" style={{ color: "var(--bt-accent)" }} />
              <circle className="sam-listen-ring" cx="68" cy="42" r="10" fill="none" stroke="currentColor" strokeWidth="1" style={{ color: "var(--bt-accent)" }} />

              {/* Eye sockets — square brackets to keep brutalist feel */}
              <EyeSocket x={22} y={32} state={state} side="left" />
              <EyeSocket x={62} y={32} state={state} side="right" />

              {/* Thinking scanner bar */}
              <rect className="sam-think-scanner" x="36" y="48" width="28" height="2" />

              {/* Mouth — different shape per state */}
              <Mouth state={state} />

              {/* Tiny brand crosshair top-left */}
              <line x1="3" y1="3" x2="9" y2="3" stroke="var(--bt-line-hot)" strokeWidth="1" />
              <line x1="3" y1="3" x2="3" y2="9" stroke="var(--bt-line-hot)" strokeWidth="1" />
              <line x1="97" y1="97" x2="91" y2="97" stroke="var(--bt-line-hot)" strokeWidth="1" />
              <line x1="97" y1="97" x2="97" y2="91" stroke="var(--bt-line-hot)" strokeWidth="1" />
            </svg>
        </div>
      </div>
      {caption !== false && (
        <div className="sam-face-caption">
          <span className="sam-face-caption-dot" />
          <span>{caption ?? STATE_LABEL[state]}</span>
        </div>
      )}
    </div>
  );
}

/* ---------- Sub-elements ---------- */

function EyeSocket({ x, y, state, side }: { x: number; y: number; state: SamFaceState; side: "left" | "right" }) {
  // Happy = upward arc (^), Error = X, default = filled rectangle pupil
  if (state === "happy") {
    // Curved arc representing closed-up smiling eye
    const d = `M ${x} ${y + 10} Q ${x + 8} ${y - 2}, ${x + 16} ${y + 10}`;
    return (
      <path
        className="sam-eye"
        d={d}
        fill="none"
        stroke="var(--bt-accent)"
        strokeWidth="3"
        strokeLinecap="square"
      />
    );
  }
  if (state === "error") {
    return (
      <g className="sam-eye" stroke="var(--bt-err)" strokeWidth="3" strokeLinecap="square">
        <line x1={x} y1={y + 2} x2={x + 16} y2={y + 14} />
        <line x1={x + 16} y1={y + 2} x2={x} y2={y + 14} />
      </g>
    );
  }
  // Default eye — bracketed pupil
  return (
    <g>
      {/* bracket frame */}
      <polyline
        points={`${x},${y - 1} ${x},${y + 16} ${x + 16},${y + 16} ${x + 16},${y - 1}`}
        fill="none"
        stroke="var(--bt-line-hot)"
        strokeWidth="1"
      />
      {/* pupil */}
      <rect className="sam-eye" x={x + 3} y={y + 3} width={10} height={10} />
      {/* highlight */}
      <rect className="sam-eye-glow" x={x + 4} y={y + 4} width={3} height={3} />
      {/* lid for blink */}
      <rect className="sam-eye-lid" x={x + 2} y={y + 2} width={12} height={12} />
    </g>
  );
}

function Mouth({ state }: { state: SamFaceState }) {
  const cx = 50;
  const baseY = 70;

  if (state === "speaking") {
    // 7 vertical bars — waveform
    const bars = Array.from({ length: 7 }, (_, i) => i);
    return (
      <g transform={`translate(${cx - 18}, ${baseY})`}>
        {bars.map((i) => (
          <rect
            key={i}
            className="sam-mouth-bar"
            x={i * 5.5}
            y={-6}
            width={3}
            height={12}
            rx={0.5}
          />
        ))}
      </g>
    );
  }

  if (state === "listening") {
    // small open circle / dot — "i'm receiving"
    return (
      <g>
        <rect x={cx - 2} y={baseY - 2} width={4} height={4} fill="var(--bt-accent)" />
        <line x1={cx - 10} y1={baseY} x2={cx - 5} y2={baseY} stroke="var(--bt-text-3)" strokeWidth="1" />
        <line x1={cx + 5} y1={baseY} x2={cx + 10} y2={baseY} stroke="var(--bt-text-3)" strokeWidth="1" />
      </g>
    );
  }

  if (state === "thinking") {
    // dotted line — processing
    return (
      <line
        x1={cx - 14} y1={baseY} x2={cx + 14} y2={baseY}
        stroke="var(--bt-accent)"
        strokeWidth="2"
        strokeDasharray="2 3"
        strokeLinecap="square"
      />
    );
  }

  if (state === "happy") {
    // upward smile arc
    return (
      <path
        d={`M ${cx - 14} ${baseY - 2} Q ${cx} ${baseY + 10}, ${cx + 14} ${baseY - 2}`}
        fill="none"
        stroke="var(--bt-ok)"
        strokeWidth="3"
        strokeLinecap="square"
      />
    );
  }

  if (state === "error") {
    // squiggle
    return (
      <polyline
        points={`${cx - 14},${baseY} ${cx - 7},${baseY - 4} ${cx},${baseY + 4} ${cx + 7},${baseY - 4} ${cx + 14},${baseY}`}
        fill="none"
        stroke="var(--bt-err)"
        strokeWidth="2"
        strokeLinecap="square"
      />
    );
  }

  // idle — closed neutral line
  return (
    <line
      x1={cx - 12} y1={baseY} x2={cx + 12} y2={baseY}
      stroke="var(--bt-text-2)"
      strokeWidth="2"
      strokeLinecap="square"
    />
  );
}
