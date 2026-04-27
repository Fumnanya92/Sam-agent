import React, { useRef, useEffect } from "react";
import type { TutorialStepPayload } from "../../hooks/useWebSocket";

type Props = {
  step: TutorialStepPayload;
};

export function TutorialStepCard({ step }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !step.imageBase64) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0);

      if (step.highlight) {
        const { x, y, width, height, label } = step.highlight;

        // Amber fill overlay
        ctx.fillStyle = "rgba(251,191,36,0.15)";
        ctx.fillRect(x, y, width, height);

        // Amber border
        ctx.strokeStyle = "#FBBF24";
        ctx.lineWidth = Math.max(2, Math.round(img.naturalWidth / 400));
        ctx.strokeRect(x, y, width, height);

        // Corner accents
        const corner = Math.min(12, width / 4, height / 4);
        ctx.strokeStyle = "#F59E0B";
        ctx.lineWidth = ctx.lineWidth + 1;
        // top-left
        ctx.beginPath(); ctx.moveTo(x, y + corner); ctx.lineTo(x, y); ctx.lineTo(x + corner, y); ctx.stroke();
        // top-right
        ctx.beginPath(); ctx.moveTo(x + width - corner, y); ctx.lineTo(x + width, y); ctx.lineTo(x + width, y + corner); ctx.stroke();
        // bottom-left
        ctx.beginPath(); ctx.moveTo(x, y + height - corner); ctx.lineTo(x, y + height); ctx.lineTo(x + corner, y + height); ctx.stroke();
        // bottom-right
        ctx.beginPath(); ctx.moveTo(x + width - corner, y + height); ctx.lineTo(x + width, y + height); ctx.lineTo(x + width, y + height - corner); ctx.stroke();

        // Label badge
        if (label) {
          const fontSize = Math.max(12, Math.round(img.naturalWidth / 80));
          ctx.font = `600 ${fontSize}px Inter, sans-serif`;
          const textW = ctx.measureText(label).width;
          const padH = 4, padV = 3;
          const bx = x, by = y > fontSize + padV * 2 + 4 ? y - fontSize - padV * 2 - 4 : y + height + 4;
          ctx.fillStyle = "#F59E0B";
          ctx.fillRect(bx, by, textW + padH * 2, fontSize + padV * 2);
          ctx.fillStyle = "#000";
          ctx.fillText(label, bx + padH, by + padV + fontSize - 2);
        }
      }
    };
    img.src = `data:image/png;base64,${step.imageBase64}`;
  }, [step]);

  const isComplete = step.complete;

  return (
    <div className="chat-tutorial-card">
      <div className="chat-tutorial-header">
        <span className="chat-tutorial-step-badge">
          Step {step.stepIndex}{step.totalSteps ? ` of ${step.totalSteps}` : ""}
        </span>
        {isComplete && <span className="chat-tutorial-done">✓ Complete</span>}
      </div>

      <p className="chat-tutorial-instruction">{step.instruction}</p>

      {step.imageBase64 && (
        <div className="chat-tutorial-canvas-wrap">
          <canvas ref={canvasRef} className="chat-tutorial-canvas" />
        </div>
      )}
    </div>
  );
}
