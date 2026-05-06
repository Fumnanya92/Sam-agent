import React, { useState, useRef, useEffect } from "react";
import type { VoiceState, ActiveWakeEngine } from "../../hooks/useVoice";

type VoiceProps = {
  voiceState: VoiceState;
  startRecording: () => void;
  stopRecording: () => void;
  isMicAvailable: boolean;
  isWakeWordReady: boolean;
  ttsAudioPlaying: boolean;
  micLevel: number;
  cancelTTS: () => void;
  activeWakeEngine: ActiveWakeEngine;
};

type Props = {
  onSend: (text: string) => void;
  disabled?: boolean;
  voice?: VoiceProps;
};

export function BrutalistChatInput({ onSend, disabled, voice }: Props) {
  const [text, setText] = useState("");
  const ta = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { ta.current?.focus(); }, []);

  const submit = () => {
    const v = text.trim();
    if (!v || disabled) return;
    onSend(v);
    setText("");
    if (ta.current) ta.current.style.height = "auto";
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const onInput = () => {
    if (!ta.current) return;
    ta.current.style.height = "auto";
    ta.current.style.height = Math.min(ta.current.scrollHeight, 180) + "px";
  };

  const recording = voice?.voiceState === "recording";
  const speaking = voice?.ttsAudioPlaying;

  const onMic = () => {
    if (!voice) return;
    if (speaking) { voice.cancelTTS(); return; }
    if (recording) { voice.stopRecording(); return; }
    voice.startRecording();
  };

  return (
    <div className="bch-dock">
      <div className="bch-dock-inner">
        <div className="bch-dock-prompt">
          <span className="bch-dock-prompt-caret">▌</span>
          <span>{disabled ? "channel offline" : recording ? "listening — speak now" : speaking ? "playback active — click stop" : "input"}</span>
        </div>

        <div className="bch-dock-row">
          <textarea
            ref={ta}
            className="bch-dock-textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKey}
            onInput={onInput}
            placeholder="> type a message, or /command…"
            disabled={disabled}
            rows={1}
          />

          {recording && voice && (
            <div className="bch-mic-meter" aria-hidden="true">
              {[0.4, 0.7, 1.0, 0.7, 0.4].map((s, i) => (
                <div
                  key={i}
                  className="bch-mic-meter-bar"
                  style={{ height: `${Math.max(4, Math.round((voice.micLevel / 100) * 22 * s))}px` }}
                />
              ))}
            </div>
          )}

          {voice?.isMicAvailable && (
            <button
              className={`bch-dock-btn ${recording ? "rec" : ""}`}
              onClick={onMic}
              title={speaking ? "Stop playback" : recording ? "Stop & send" : "Start voice input"}
              disabled={voice.voiceState === "processing"}
            >
              {speaking ? "■" : recording ? "●" : "🎙"}
            </button>
          )}

          <button
            className="bch-dock-btn bch-dock-btn-send"
            onClick={submit}
            disabled={!text.trim() || disabled}
          >
            SEND ↵
          </button>
        </div>

        <div className="bch-dock-foot">
          <div className="bch-dock-foot-keys">
            <kbd>↵</kbd> send · <kbd>⇧</kbd>+<kbd>↵</kbd> newline · <kbd>/</kbd> commands
          </div>
          <div>
            {voice?.isWakeWordReady ? "WAKE: HEY SAM · ON" : voice?.isMicAvailable ? "VOICE: READY" : ""}
          </div>
        </div>
      </div>
    </div>
  );
}
