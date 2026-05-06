import React, { useState, useCallback } from "react";
import { useApiData } from "../hooks/useApi";
import { PageHelp } from "../components/PageHelp";

type Skill = {
  name: string;
  description: string;
  intents: string[];
  trigger_phrases: string[];
  enabled: boolean;
  last_activated: string;
};

type ApiResponse = {
  skills: Skill[];
};

function formatRelative(iso: string): string {
  if (!iso) return "never";
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch {
    return iso;
  }
}

function SkillCard({
  skill,
  onToggle,
}: {
  skill: Skill;
  onToggle: (name: string) => Promise<void>;
}) {
  const [toggling, setToggling] = useState(false);
  const [expanded, setExpanded] = useState(false);

  async function handleToggle(e: React.MouseEvent) {
    e.stopPropagation();
    setToggling(true);
    try {
      await onToggle(skill.name);
    } finally {
      setToggling(false);
    }
  }

  return (
    <div
      style={{
        border: "1px solid",
        borderColor: skill.enabled ? "rgba(52,211,153,0.2)" : "rgba(255,255,255,0.07)",
        borderRadius: "10px",
        background: skill.enabled ? "rgba(52,211,153,0.04)" : "rgba(255,255,255,0.02)",
        overflow: "hidden",
        transition: "border-color 0.2s, background 0.2s",
      }}
    >
      {/* Card header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          padding: "14px 16px",
          cursor: "pointer",
        }}
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Enable dot */}
        <div style={{
          width: "8px", height: "8px", borderRadius: "50%", flexShrink: 0,
          background: skill.enabled ? "#34D399" : "rgba(255,255,255,0.2)",
          boxShadow: skill.enabled ? "0 0 6px #34D39966" : "none",
          transition: "background 0.2s, box-shadow 0.2s",
        }} />

        {/* Name + description */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: "13px",
            fontWeight: 700,
            color: skill.enabled ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.4)",
            letterSpacing: "-0.01em",
          }}>
            {skill.name}
          </div>
          <div style={{
            fontSize: "11px",
            color: "rgba(255,255,255,0.4)",
            marginTop: "2px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}>
            {skill.description}
          </div>
        </div>

        {/* Last activated */}
        <div style={{
          fontSize: "11px",
          color: "rgba(255,255,255,0.3)",
          flexShrink: 0,
          minWidth: "60px",
          textAlign: "right",
        }}>
          {formatRelative(skill.last_activated)}
        </div>

        {/* Toggle */}
        <button
          onClick={handleToggle}
          disabled={toggling}
          style={{
            width: "40px",
            height: "22px",
            borderRadius: "11px",
            border: "none",
            background: skill.enabled ? "#34D399" : "rgba(255,255,255,0.12)",
            cursor: "pointer",
            position: "relative",
            flexShrink: 0,
            transition: "background 0.2s",
            outline: "none",
          }}
          title={skill.enabled ? "Disable skill" : "Enable skill"}
        >
          <div style={{
            position: "absolute",
            top: "3px",
            left: skill.enabled ? "21px" : "3px",
            width: "16px", height: "16px",
            borderRadius: "50%",
            background: "white",
            transition: "left 0.15s",
            boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
          }} />
        </button>

        {/* Expand chevron */}
        <div style={{
          fontSize: "10px",
          color: "rgba(255,255,255,0.25)",
          transform: expanded ? "rotate(180deg)" : "none",
          transition: "transform 0.15s",
        }}>▼</div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{
          padding: "0 16px 14px 36px",
          fontSize: "11px",
          color: "rgba(255,255,255,0.5)",
          borderTop: "1px solid rgba(255,255,255,0.05)",
          paddingTop: "10px",
        }}>
          {skill.intents.length > 0 && (
            <div style={{ marginBottom: "6px" }}>
              <span style={{ color: "rgba(255,255,255,0.3)", marginRight: "6px" }}>intents</span>
              {skill.intents.map((i) => (
                <code key={i} style={{
                  marginRight: "5px",
                  padding: "1px 5px",
                  background: "rgba(255,255,255,0.07)",
                  borderRadius: "3px",
                  fontSize: "10px",
                }}>{i}</code>
              ))}
            </div>
          )}
          {skill.trigger_phrases.length > 0 && (
            <div>
              <span style={{ color: "rgba(255,255,255,0.3)", marginRight: "6px" }}>triggers</span>
              {skill.trigger_phrases.slice(0, 4).map((p) => (
                <span key={p} style={{
                  marginRight: "8px",
                  color: "rgba(255,255,255,0.45)",
                  fontStyle: "italic",
                }}>"{p}"</span>
              ))}
              {skill.trigger_phrases.length > 4 && (
                <span style={{ color: "rgba(255,255,255,0.2)" }}>+{skill.trigger_phrases.length - 4} more</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SkillsPage() {
  const { data, loading, error, refetch } = useApiData<ApiResponse>("/api/skills", []);
  const [skills, setSkills] = useState<Skill[] | null>(null);

  // Use local state for optimistic toggle — fall back to fetched data
  const displayed = skills ?? data?.skills ?? [];

  const handleToggle = useCallback(async (name: string) => {
    // Optimistic update
    setSkills((prev) => {
      const base = prev ?? data?.skills ?? [];
      return base.map((s) => s.name === name ? { ...s, enabled: !s.enabled } : s);
    });
    try {
      const res = await fetch(`/api/skills/${encodeURIComponent(name)}/toggle`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json() as { name: string; enabled: boolean };
      // Sync server truth
      setSkills((prev) => {
        const base = prev ?? data?.skills ?? [];
        return base.map((s) => s.name === name ? { ...s, enabled: json.enabled } : s);
      });
    } catch {
      // Revert on error
      setSkills((prev) => {
        const base = prev ?? data?.skills ?? [];
        return base.map((s) => s.name === name ? { ...s, enabled: !s.enabled } : s);
      });
    }
  }, [data]);

  const enabledCount = displayed.filter((s) => s.enabled).length;

  return (
    <div style={{
      height: "100%",
      overflow: "auto",
      padding: "24px",
      color: "rgba(255,255,255,0.85)",
      fontFamily: "inherit",
    }}>
      {/* Header */}
      <div style={{ marginBottom: "20px" }}>
        <h1 style={{ fontSize: "18px", fontWeight: 700, margin: 0, letterSpacing: "-0.01em" }}>
          Skills
        </h1>
        <p style={{ fontSize: "12px", color: "rgba(255,255,255,0.4)", margin: "4px 0 0" }}>
          {loading ? "Loading…" : `${enabledCount} of ${displayed.length} skills enabled · injected live into Sam's prompt`}
        </p>
      </div>
      <PageHelp
        title="Skills — specialist knowledge modules"
        what="Antigravity skills extend Sam with domain expertise. They are injected into the LLM prompt when relevant."
        how={[
          "Toggle a skill on/off — disabled skills are never injected.",
          "Last activated shows when Sam last reached for that skill.",
          "Skills are auto-matched by task description — you rarely need to enable manually.",
          "Voice: Sam, what skills do you have? — reads the enabled list.",
        ]}
      />


      {/* How-to hint */}
      <div style={{
        marginBottom: "20px",
        padding: "10px 14px",
        borderRadius: "8px",
        background: "rgba(96,165,250,0.08)",
        border: "1px solid rgba(96,165,250,0.2)",
        fontSize: "12px",
        color: "rgba(96,165,250,0.85)",
        lineHeight: 1.5,
      }}>
        Skills are mini-plugins that extend what Sam can do. Toggling one off removes it from the
        live prompt immediately — Sam won't offer or respond to it until re-enabled.
        Trigger phrases show what you can say to activate each skill.
      </div>

      {error && (
        <div style={{ color: "#F87171", fontSize: "13px", marginBottom: "16px" }}>
          Failed to load skills — is the daemon running?
        </div>
      )}

      {/* Skill grid */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {displayed.map((skill) => (
          <SkillCard key={skill.name} skill={skill} onToggle={handleToggle} />
        ))}
        {!loading && displayed.length === 0 && (
          <div style={{
            padding: "40px",
            textAlign: "center",
            color: "rgba(255,255,255,0.3)",
            fontSize: "13px",
          }}>
            No skills found. Skills are loaded from the <code>skills/</code> directory.
          </div>
        )}
      </div>
    </div>
  );
}
