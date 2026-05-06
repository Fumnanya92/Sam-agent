import React from "react";
import type { VoiceState } from "../hooks/useVoice";
import "../styles/orb.css";

type OrbSize = "full" | "mini";

type Props = {
  voiceState: VoiceState;
  size?: OrbSize;
  lastUtterance?: string;
  onClick?: () => void;
};

function stateLabel(s: VoiceState): string {
  switch (s) {
    case "idle":          return "Online";
    case "wake_detected": return "Waking…";
    case "recording":     return "Listening";
    case "processing":    return "Thinking…";
    case "speaking":      return "Speaking";
    default:              return "Online";
  }
}

function orbClass(s: VoiceState): string {
  switch (s) {
    case "idle":          return "orb-idle";
    case "wake_detected": return "orb-wake";
    case "recording":     return "orb-listening";
    case "processing":    return "orb-thinking";
    case "speaking":      return "orb-speaking";
    default:              return "orb-idle";
  }
}

export function SamOrb({ voiceState, size = "full", lastUtterance, onClick }: Props) {
  const isMini = size === "mini";
  const label = stateLabel(voiceState);
  const cls = orbClass(voiceState);

  if (isMini) {
    return (
      <button
        className={`sam-orb-mini ${cls}`}
        onClick={onClick}
        title={`Sam — ${label}`}
        aria-label={`Sam is ${label}. Click to open.`}
      >
        <div className="orb-mini-core" />
        <div className="orb-mini-ring" />
      </button>
    );
  }

  return (
    <div className={`sam-orb-wrapper ${cls}`} onClick={onClick} role={onClick ? "button" : undefined} aria-label={`Sam — ${label}`}>
      {/* Visual container — rings + core live here, absolutely positioned */}
      <div className="orb-visual" aria-hidden="true">
        <div className={`orb-ring orb-ring-3 ${cls}`} />
        <div className={`orb-ring orb-ring-2 ${cls}`} />
        <div className={`orb-ring orb-ring-1 ${cls}`} />
        <div className={`orb-core ${cls}`}>
          <div className="orb-core-inner" />
        </div>
      </div>

      {/* Labels — flow below visual in flex column */}
      <div className="orb-state-label" aria-live="polite">{label}</div>
      {lastUtterance && (
        <div className="orb-utterance" aria-live="polite">
          {lastUtterance.length > 80 ? lastUtterance.slice(0, 80) + "…" : lastUtterance}
        </div>
      )}
    </div>
  );
}
