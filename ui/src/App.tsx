import React, { useState, useEffect, useMemo } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { useVoice, type WakeEngineChoice } from "./hooks/useVoice";
import { useApiData } from "./hooks/useApi";
import { SamFace, voiceStateToFace } from "./components/SamFace";
import { ContextRail } from "./components/ContextRail";
import BrutalistChatPage from "./pages/BrutalistChatPage";

type PublicConfig = {
  voice?: { wake_engine?: WakeEngineChoice };
};

// Lazy page imports
const TasksPage = React.lazy(() => import("./pages/TasksPage"));
const PipelinePage = React.lazy(() => import("./pages/PipelinePage"));
const KnowledgePage = React.lazy(() => import("./pages/KnowledgePage"));
const MemoryPage = React.lazy(() => import("./pages/MemoryPage"));
const CalendarPage = React.lazy(() => import("./pages/CalendarPage"));
const OfficePage = React.lazy(() => import("./pages/OfficePage"));
const CommandPage = React.lazy(() => import("./pages/CommandPage"));
const AuthorityPage = React.lazy(() => import("./pages/AuthorityPage"));
const SettingsPage = React.lazy(() => import("./pages/SettingsPage"));
const AwarenessPage = React.lazy(() => import("./pages/AwarenessPage"));
const WorkflowsPage = React.lazy(() => import("./pages/WorkflowsPage"));
const GoalsPage = React.lazy(() => import("./pages/GoalsPage"));
const DashboardPage = React.lazy(() => import("./pages/DashboardPage"));
const SitesPage = React.lazy(() => import("./pages/SitesPage"));
const CapabilitiesPage = React.lazy(() => import("./pages/CapabilitiesPage"));
const SkillsPage = React.lazy(() => import("./pages/SkillsPage"));

type Route =
  | "dashboard" | "chat" | "tasks" | "pipeline" | "memory" | "calendar"
  | "office" | "knowledge" | "command" | "authority" | "awareness"
  | "workflows" | "goals" | "sites" | "capabilities" | "skills" | "settings";

export type SettingsSection = "general" | "profile" | "llm" | "channels" | "integrations" | "sidecar";
const SETTINGS_SECTIONS: SettingsSection[] = ["general", "profile", "llm", "channels", "integrations", "sidecar"];

const ALL_ROUTES: Route[] = [
  "dashboard","chat","tasks","pipeline","memory","calendar","office",
  "knowledge","command","authority","awareness","workflows","goals",
  "sites","capabilities","skills","settings",
];

function getRoute(): Route {
  const hash = window.location.hash.replace("#/", "");
  if (hash.startsWith("settings")) return "settings";
  if (ALL_ROUTES.includes(hash as Route)) return hash as Route;
  return "chat";
}

function getSettingsSection(): SettingsSection {
  const hash = window.location.hash.replace("#/", "");
  if (hash.startsWith("settings/")) {
    const s = hash.replace("settings/", "");
    if (SETTINGS_SECTIONS.includes(s as SettingsSection)) return s as SettingsSection;
  }
  return "general";
}

/* ================================================================
   NAV CONFIG — grouped categories
   ================================================================ */
type NavEntry = { glyph: string; label: string; route: Route };

const NAV_GROUPS: { title: string; items: NavEntry[] }[] = [
  {
    title: "Workspace",
    items: [
      { glyph: "▣", label: "Chat",      route: "chat" },
      { glyph: "◇", label: "Dashboard", route: "dashboard" },
      { glyph: "✦", label: "Tasks",     route: "tasks" },
      { glyph: "◆", label: "Goals",     route: "goals" },
      { glyph: "▶", label: "Pipeline",  route: "pipeline" },
      { glyph: "□", label: "Calendar",  route: "calendar" },
    ],
  },
  {
    title: "Brain",
    items: [
      { glyph: "◈", label: "Memory",       route: "memory" },
      { glyph: "○", label: "Knowledge",    route: "knowledge" },
      { glyph: "◎", label: "Awareness",    route: "awareness" },
      { glyph: "✱", label: "Capabilities", route: "capabilities" },
      { glyph: "★", label: "Skills",        route: "skills" },
    ],
  },
  {
    title: "Build",
    items: [
      { glyph: "△", label: "Agents",    route: "office" },
      { glyph: "⬡", label: "Workflows", route: "workflows" },
      { glyph: "■", label: "Sites",     route: "sites" },
      { glyph: "▣", label: "Authority", route: "authority" },
      { glyph: "▣", label: "Command",   route: "command" },
    ],
  },
];

const ROUTE_LABEL: Record<Route, string> = {
  dashboard: "DASHBOARD", chat: "CHAT", tasks: "TASKS", pipeline: "PIPELINE",
  memory: "MEMORY", calendar: "CALENDAR", office: "AGENTS", knowledge: "KNOWLEDGE",
  command: "COMMAND", authority: "AUTHORITY", awareness: "AWARENESS",
  workflows: "WORKFLOWS", goals: "GOALS", sites: "SITES",
  capabilities: "CAPABILITIES", skills: "SKILLS", settings: "SETTINGS",
};

function PageFallback() {
  return (
    <div style={{
      flex: 1,
      display: "grid",
      placeItems: "center",
      color: "var(--bt-text-3)",
      fontFamily: "var(--bt-mono)",
      fontSize: "11px",
      letterSpacing: "0.2em",
      textTransform: "uppercase",
    }}>
      ▸ loading module…
    </div>
  );
}

/* ================================================================
   APP
   ================================================================ */
export function App() {
  const [route, setRoute] = useState<Route>(getRoute);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>(getSettingsSection);
  const [sideOpen, setSideOpen] = useState(true);
  const [railOpen, setRailOpen] = useState(true);

  const ws = useWebSocket();
  const { data: publicConfig } = useApiData<PublicConfig>("/api/config", []);
  const wakeEngine = publicConfig?.voice?.wake_engine ?? "openwakeword";
  const voice = useVoice({ wsRef: ws.wsRef, wakeEngine });

  // Wire voice ↔ WS
  useEffect(() => {
    ws.voiceCallbacksRef.current = {
      onTTSBinary: voice.handleTTSBinary,
      onTTSStart: voice.handleTTSStart,
      onTTSEnd: voice.handleTTSEnd,
      onError: voice.handleError,
    };
  }, [voice.handleTTSBinary, voice.handleTTSStart, voice.handleTTSEnd, voice.handleError]);

  useEffect(() => {
    const onHash = () => {
      setRoute(getRoute());
      setSettingsSection(getSettingsSection());
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!window.location.hash) window.location.hash = "#/chat";
  }, []);

  const navigate = (r: Route) => {
    window.location.hash = r === "settings" ? "#/settings/general" : `#/${r}`;
  };

  // Sessions stub — derived from message activity until backend exposes a list
  const sessions = useMemo(() => {
    const today = new Date().toLocaleDateString([], { month: "short", day: "numeric" });
    return [
      { id: "current", title: "Current session", meta: `${ws.messages.length} msgs · ${today}`, active: true },
    ];
  }, [ws.messages.length]);

  // Derive Sam face state
  const faceState = voiceStateToFace(voice.voiceState, {
    ttsPlaying: voice.ttsAudioPlaying,
    hasError: !ws.isConnected,
  });

  const lastMsg = ws.messages[ws.messages.length - 1];
  const isStreaming = lastMsg?.isStreaming;
  const effectiveFaceState =
    faceState === "idle" && isStreaming ? "thinking" : faceState;

  return (
    <div
      className="bsh-root"
      data-side={sideOpen ? "open" : "closed"}
      data-rail={railOpen ? "open" : "closed"}
    >
      {/* ============= SIDEBAR ============= */}
      <aside className="bsh-side" aria-label="Primary navigation">
        <div className="bsh-side-head">
          <div className="bsh-side-mark">S</div>
          {sideOpen && (
            <div className="bsh-side-brand">
              SAM<span className="bsh-side-brand-sub" style={{ marginLeft: 6 }}>// AGENT</span>
            </div>
          )}
          <button
            className="bsh-side-toggle"
            onClick={() => setSideOpen(!sideOpen)}
            aria-label={sideOpen ? "Collapse sidebar" : "Expand sidebar"}
            title={sideOpen ? "Collapse" : "Expand"}
          >
            {sideOpen ? "‹" : "›"}
          </button>
        </div>

        {/* Sessions / history */}
        {sideOpen && (
          <>
            <div className="bsh-side-section">
              <span className="bsh-side-section-title">Sessions</span>
              <button className="bsh-side-section-action" title="New session" onClick={() => navigate("chat")}>+</button>
            </div>
            <div className="bsh-sessions">
              {sessions.map((s) => (
                <button
                  key={s.id}
                  className={`bsh-session ${s.active ? "active" : ""}`}
                  onClick={() => navigate("chat")}
                >
                  <span className="bsh-session-title">{s.title}</span>
                  <span className="bsh-session-meta">{s.meta}</span>
                </button>
              ))}
            </div>
          </>
        )}

        {/* Nav */}
        <nav className="bsh-nav">
          {NAV_GROUPS.map((g) => (
            <React.Fragment key={g.title}>
              {sideOpen && <div className="bsh-nav-cat">{g.title}</div>}
              {g.items.map((it) => (
                <button
                  key={it.label + it.route}
                  className={`bsh-nav-item ${route === it.route ? "active" : ""}`}
                  onClick={() => navigate(it.route)}
                  title={it.label}
                  aria-current={route === it.route ? "page" : undefined}
                >
                  <span className="bsh-nav-item-icon" aria-hidden="true">{it.glyph}</span>
                  <span>{it.label}</span>
                </button>
              ))}
            </React.Fragment>
          ))}

          {sideOpen && <div className="bsh-nav-cat">System</div>}
          <button
            className={`bsh-nav-item ${route === "settings" ? "active" : ""}`}
            onClick={() => navigate("settings")}
          >
            <span className="bsh-nav-item-icon">⚙</span>
            <span>Settings</span>
          </button>
        </nav>

        <div className="bsh-side-foot">
          <div className={`bsh-side-foot-dot ${ws.isConnected ? "online" : "offline"}`} />
          {sideOpen && (
            <span className="bsh-side-foot-text">
              {ws.isConnected ? "LINK · LIVE" : "LINK · DOWN"}
            </span>
          )}
        </div>
      </aside>

      {/* ============= MAIN ============= */}
      <main className="bsh-main">
        <div className="bsh-topbar">
          <div className="bsh-topbar-route">
            {ROUTE_LABEL[route]}
            {route === "settings" && ` · ${settingsSection.toUpperCase()}`}
          </div>
          <div className="bsh-topbar-spacer" />
          <div className="bsh-topbar-meta">
            {new Date().toLocaleDateString([], { month: "short", day: "numeric" }).toUpperCase()}
          </div>
          <button
            className="bsh-topbar-btn"
            onClick={() => setRailOpen(!railOpen)}
            title={railOpen ? "Hide context rail" : "Show context rail"}
            aria-label={railOpen ? "Hide context rail" : "Show context rail"}
          >
            {railOpen ? "›|" : "|‹"}
          </button>
        </div>

        {/* System notices */}
        {ws.notices.length > 0 && (
          <div style={{ padding: "10px 18px 0" }}>
            {ws.notices.map((n) => (
              <div
                key={n.id}
                style={{
                  display: "flex", alignItems: "flex-start", gap: 12,
                  padding: "10px 14px", marginBottom: 8,
                  border: "1px solid var(--bt-warn)",
                  background: "rgba(245, 166, 35, 0.06)",
                  color: "var(--bt-text)",
                  fontFamily: "var(--bt-mono)",
                  fontSize: 12,
                }}
              >
                <span style={{ color: "var(--bt-warn)", fontWeight: 700, letterSpacing: "0.2em", fontSize: 10 }}>!</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700 }}>{n.title}</div>
                  <div style={{ color: "var(--bt-text-2)", marginTop: 2 }}>{n.text}</div>
                </div>
                <button
                  onClick={() => ws.dismissNotice(n.id)}
                  style={{
                    background: "none", border: "none",
                    color: "var(--bt-text-3)", cursor: "pointer", fontSize: 14,
                  }}
                  aria-label="Dismiss notice"
                >×</button>
              </div>
            ))}
          </div>
        )}

        <div className="bsh-content">
          <React.Suspense fallback={<PageFallback />}>
            {route === "chat" && (
              <BrutalistChatPage
                messages={ws.messages}
                isConnected={ws.isConnected}
                sendMessage={ws.sendMessage}
                voice={voice}
                takeoverState={ws.takeoverState}
                cancelTakeover={ws.cancelTakeover}
                agentActivity={ws.agentActivity}
              />
            )}
            {route === "dashboard" && <DashboardPage messages={ws.messages} isConnected={ws.isConnected} voice={voice} sendMessage={ws.sendMessage} agentActivity={ws.agentActivity} goalEvents={ws.goalEvents} workflowEvents={ws.workflowEvents} />}
            {route === "tasks" && <TasksPage taskEvents={ws.taskEvents} />}
            {route === "pipeline" && <PipelinePage contentEvents={ws.contentEvents} sendMessage={ws.sendMessage} />}
            {route === "memory" && <MemoryPage />}
            {route === "calendar" && <CalendarPage taskEvents={ws.taskEvents} contentEvents={ws.contentEvents} />}
            {route === "office" && <OfficePage agentActivity={ws.agentActivity} />}
            {route === "knowledge" && <KnowledgePage />}
            {route === "command" && <CommandPage />}
            {route === "awareness" && <AwarenessPage />}
            {route === "workflows" && <WorkflowsPage workflowEvents={ws.workflowEvents} sendMessage={ws.sendMessage} />}
            {route === "goals" && <GoalsPage goalEvents={ws.goalEvents} />}
            {route === "sites" && <SitesPage sendMessage={ws.sendMessage} isConnected={ws.isConnected} messages={ws.messages} />}
            {route === "authority" && <AuthorityPage />}
            {route === "capabilities" && <CapabilitiesPage />}
            {route === "skills" && <SkillsPage />}
            {route === "settings" && <SettingsPage section={settingsSection} />}
          </React.Suspense>
        </div>
      </main>

      {/* ============= CONTEXT RAIL ============= */}
      {railOpen && (
        <ContextRail
          messages={ws.messages}
          agentActivity={ws.agentActivity}
          faceState={effectiveFaceState}
        />
      )}
    </div>
  );
}
