import React from "react";
import { useApiData } from "../../hooks/useApi";

type Config = {
  heartbeat: {
    interval_minutes: number;
    active_hours: { start: number; end: number };
    aggressiveness: string;
  };
};

export function HeartbeatPanel() {
  const { data: config, loading } = useApiData<Config>("/api/config", []);

  if (loading || !config) {
    return <div style={cardStyle}><span style={{ color: "var(--j-text-muted)", fontSize: "13px" }}>Loading...</span></div>;
  }

  const hb = config.heartbeat;

  return (
    <div style={cardStyle}>
      <h3 style={headerStyle}>Heartbeat</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "13px" }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "var(--j-text-dim)" }}>Interval</span>
          <span style={{ color: "var(--j-text)" }}>{hb.interval_minutes} min</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "var(--j-text-dim)" }}>Active Hours</span>
          <span style={{ color: "var(--j-text)" }}>{hb.active_hours.start}:00 - {hb.active_hours.end}:00</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "var(--j-text-dim)" }}>Aggressiveness</span>
          <span
            style={{
              color: hb.aggressiveness === "aggressive"
                ? "var(--j-warning)"
                : hb.aggressiveness === "moderate"
                  ? "var(--j-accent)"
                  : "var(--j-text-muted)",
              textTransform: "capitalize",
              fontWeight: 500,
            }}
          >
            {hb.aggressiveness}
          </span>
        </div>
      </div>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  padding: "20px",
  background: "var(--j-surface)",
  border: "1px solid var(--j-border)",
  borderRadius: "8px",
};

const headerStyle: React.CSSProperties = {
  fontSize: "14px",
  fontWeight: 600,
  color: "var(--j-text)",
  marginBottom: "16px",
};
