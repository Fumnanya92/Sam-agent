import React, { useState } from "react";

interface PageHelpProps {
  title: string;
  what: string;
  how: string[];
}

export function PageHelp({ title, what, how }: PageHelpProps) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{
      background: "rgba(255,255,255,0.04)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: "8px",
      padding: "10px 14px",
      marginBottom: "20px",
      fontSize: "12px",
      color: "rgba(255,255,255,0.55)",
    }}>
      <div
        onClick={() => setOpen(o => !o)}
        style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}
      >
        <span style={{ fontWeight: 600, color: "rgba(255,255,255,0.75)" }}>
          {title}
        </span>
        <span style={{ fontSize: "10px", opacity: 0.6 }}>{open ? "▲ hide" : "▼ how to use"}</span>
      </div>
      <div style={{ marginTop: "4px" }}>{what}</div>
      {open && (
        <ul style={{ margin: "8px 0 0 0", paddingLeft: "18px", lineHeight: "1.8" }}>
          {how.map((tip, i) => (
            <li key={i}>{tip}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
