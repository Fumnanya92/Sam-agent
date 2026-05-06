import React, { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "../hooks/useApi";
import type { ChatMessage, AgentActivityEvent, GoalEvent, WorkflowEvent } from "../hooks/useWebSocket";
import type { UseVoiceReturn } from "../hooks/useVoice";
import "../styles/dashboard-brutalist.css";

/* ================================================================
   TYPES
   ================================================================ */
type AgentInfo = {
  id: string;
  role: { id: string; name: string };
  status: "active" | "idle" | "terminated";
  current_task: string | null;
  created_at: number;
};

type HealthData = {
  uptime: number;
  services: Record<string, string>;
  memory: { heapUsed: number; heapTotal: number; rss: number };
  database: { connected: boolean; size: number };
  startedAt: number;
};

type VaultEntity = {
  id: string;
  type: string;
  name: string;
  description: string;
  created_at: number;
  updated_at: number;
};

type GoalData = {
  id: string;
  title: string;
  score: number;
  status: string;
  health: string;
  level: string;
  deadline: number | null;
};

type WorkflowData = {
  id: string;
  name: string;
  status: string;
};

type DashboardProps = {
  messages: ChatMessage[];
  isConnected: boolean;
  voice: UseVoiceReturn;
  sendMessage: (text: string) => void;
  agentActivity: AgentActivityEvent[];
  goalEvents: GoalEvent[];
  workflowEvents: WorkflowEvent[];
};

/* ================================================================
   HELPERS
   ================================================================ */
function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  if (d > 0) return `${d}d ${h.toString().padStart(2, "0")}h`;
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m.toString().padStart(2, "0")}m` : `${m}m`;
}

function timeAgo(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 10) return "now";
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

function nav(href: string) { window.location.hash = href; }

/* ================================================================
   PRIMITIVES
   ================================================================ */
function StatusDot({ kind }: { kind: "ok" | "warn" | "err" | "idle" }) {
  return <span className={`dbx-dot dbx-dot-${kind}`} />;
}

function StatTile({ label, value, sub, accent, href }: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
  href?: string;
}) {
  return (
    <button
      type="button"
      className={`dbx-tile${accent ? " dbx-tile-accent" : ""}`}
      onClick={() => href && nav(href)}
      tabIndex={href ? 0 : -1}
    >
      <div className="dbx-tile-label">{label}</div>
      <div className="dbx-tile-value">{value}</div>
      {sub && <div className="dbx-tile-sub">{sub}</div>}
    </button>
  );
}

function Panel({ title, count, action, children }: {
  title: string;
  count?: string | number;
  action?: { label: string; href: string };
  children: React.ReactNode;
}) {
  return (
    <section className="dbx-panel">
      <header className="dbx-panel-head">
        <span className="dbx-panel-bracket">[</span>
        <span className="dbx-panel-title">{title}</span>
        <span className="dbx-panel-bracket">]</span>
        {count !== undefined && <span className="dbx-panel-count">{String(count).padStart(3, "0")}</span>}
        <span className="dbx-panel-fill" />
        {action && (
          <button className="dbx-panel-action" onClick={() => nav(action.href)}>
            {action.label} →
          </button>
        )}
      </header>
      <div className="dbx-panel-body">{children}</div>
    </section>
  );
}

/* ================================================================
   ASCII SPARK — minimal terminal sparkline
   ================================================================ */
function Spark({ data, width = 60 }: { data: number[]; width?: number }) {
  const chars = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"];
  const max = Math.max(...data, 1);
  const samples = Array.from({ length: width }, (_, i) => {
    const idx = Math.floor((i / width) * data.length);
    return data[idx] ?? 0;
  });
  return (
    <span className="dbx-spark">
      {samples.map((v, i) => chars[Math.min(7, Math.floor((v / max) * 7))]).join("")}
    </span>
  );
}

/* ================================================================
   SECTIONS
   ================================================================ */
function SystemHeader({ health, isConnected }: { health: HealthData | null; isConnected: boolean }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const ts = now.toISOString().replace("T", " ").slice(0, 19);
  const memPct = health ? Math.round((health.memory.heapUsed / health.memory.heapTotal) * 100) : 0;

  return (
    <div className="dbx-sysbar">
      <span className="dbx-sysbar-label">SAM://</span>
      <span className="dbx-sysbar-path">command/dashboard</span>
      <span className="dbx-sysbar-sep">·</span>
      <span className="dbx-sysbar-ts">{ts} UTC</span>
      <span className="dbx-sysbar-fill" />
      <span className="dbx-sysbar-stat">
        <StatusDot kind={isConnected ? "ok" : "err"} />
        {isConnected ? "LINK UP" : "LINK DOWN"}
      </span>
      <span className="dbx-sysbar-sep">·</span>
      <span className="dbx-sysbar-stat">
        UPTIME {health ? formatUptime(health.uptime) : "--"}
      </span>
      <span className="dbx-sysbar-sep">·</span>
      <span className="dbx-sysbar-stat">
        HEAP {memPct}%
      </span>
      <span className="dbx-sysbar-sep">·</span>
      <span className="dbx-sysbar-stat">
        DB {health?.database.connected ? "OK" : "DOWN"}
      </span>
    </div>
  );
}

function AgentRow({ agent }: { agent: AgentInfo }) {
  const kind: "ok" | "idle" | "err" =
    agent.status === "active" ? "ok" : agent.status === "terminated" ? "err" : "idle";
  const elapsed = Math.floor((Date.now() - agent.created_at) / 1000);
  return (
    <button className="dbx-row" onClick={() => nav("#/office")}>
      <StatusDot kind={kind} />
      <span className="dbx-row-name">{agent.role.name}</span>
      <span className="dbx-row-tag">{agent.role.id}</span>
      <span className="dbx-row-task">
        {agent.current_task ?? (kind === "idle" ? "awaiting" : kind === "err" ? "terminated" : "running")}
      </span>
      <span className="dbx-row-meta">
        {elapsed < 60 ? `${elapsed}s` : elapsed < 3600 ? `${Math.floor(elapsed/60)}m` : `${Math.floor(elapsed/3600)}h`}
      </span>
    </button>
  );
}

function GoalRow({ goal }: { goal: GoalData }) {
  const pct = Math.round(goal.score * 100);
  const blocks = 20;
  const filled = Math.round((pct / 100) * blocks);
  const bar = "█".repeat(filled) + "░".repeat(blocks - filled);
  const tone = goal.health === "critical" || goal.health === "behind"
    ? "err"
    : goal.health === "at_risk" ? "warn" : "ok";
  return (
    <button className="dbx-row" onClick={() => nav("#/goals")}>
      <StatusDot kind={tone} />
      <span className="dbx-row-name">{goal.title}</span>
      <span className="dbx-row-bar">{bar}</span>
      <span className="dbx-row-meta">{pct.toString().padStart(3, " ")}%</span>
    </button>
  );
}

function MemoryRow({ entity }: { entity: VaultEntity }) {
  return (
    <button className="dbx-row" onClick={() => nav("#/memory")}>
      <span className="dbx-row-tag dbx-row-tag-accent">{entity.type.toUpperCase()}</span>
      <span className="dbx-row-name">{entity.name}</span>
      <span className="dbx-row-fill" />
      <span className="dbx-row-meta">{timeAgo(entity.updated_at)}</span>
    </button>
  );
}

function WorkflowRow({ wf }: { wf: WorkflowData }) {
  const kind: "ok" | "idle" | "err" =
    wf.status === "running" || wf.status === "active" ? "ok"
    : wf.status === "failed" || wf.status === "error" ? "err"
    : "idle";
  return (
    <button className="dbx-row" onClick={() => nav("#/workflows")}>
      <StatusDot kind={kind} />
      <span className="dbx-row-name">{wf.name}</span>
      <span className="dbx-row-fill" />
      <span className="dbx-row-tag">{wf.status}</span>
    </button>
  );
}

/* ================================================================
   FILTER BAR
   ================================================================ */
type AgentStatusFilter = "all" | "active" | "idle" | "terminated";
type GoalHealthFilter = "all" | "ok" | "at_risk" | "critical";
type WorkflowStatusFilter = "all" | "running" | "idle" | "failed";

type DashboardFilters = {
  query: string;
  agentStatus: AgentStatusFilter;
  goalHealth: GoalHealthFilter;
  workflowStatus: WorkflowStatusFilter;
  memoryType: string; // "all" or specific entity type
  logKind: string;    // "all" or substring of event type
  live: boolean;
};

function Segmented<T extends string>({ value, options, onChange }: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="dbx-seg" role="radiogroup">
      {options.map(o => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          className={`dbx-seg-btn${value === o.value ? " dbx-seg-on" : ""}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function FilterBar({
  filters, setFilters, memoryTypes, logKinds, onReset,
}: {
  filters: DashboardFilters;
  setFilters: React.Dispatch<React.SetStateAction<DashboardFilters>>;
  memoryTypes: string[];
  logKinds: string[];
  onReset: () => void;
}) {
  const upd = <K extends keyof DashboardFilters>(k: K, v: DashboardFilters[K]) =>
    setFilters(prev => ({ ...prev, [k]: v }));

  return (
    <div className="dbx-filterbar" role="region" aria-label="Dashboard filters">
      <div className="dbx-filter-row">
        <div className="dbx-filter-search">
          <span className="dbx-filter-prompt">/</span>
          <input
            className="dbx-filter-input"
            placeholder="filter agents · logs · goals · memory · workflows…"
            value={filters.query}
            onChange={e => upd("query", e.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
          {filters.query && (
            <button
              className="dbx-filter-clear"
              onClick={() => upd("query", "")}
              aria-label="Clear search"
            >×</button>
          )}
        </div>

        <button
          type="button"
          className={`dbx-live-btn${filters.live ? " dbx-live-on" : " dbx-live-off"}`}
          onClick={() => upd("live", !filters.live)}
          aria-pressed={filters.live}
          title={filters.live ? "Pause real-time updates" : "Resume real-time updates"}
        >
          <span className="dbx-live-dot" />
          {filters.live ? "LIVE" : "PAUSED"}
        </button>

        <button
          type="button"
          className="dbx-reset-btn"
          onClick={onReset}
          title="Reset all filters"
        >RESET</button>
      </div>

      <div className="dbx-filter-row dbx-filter-row-wrap">
        <div className="dbx-filter-group">
          <span className="dbx-filter-label">AGENTS</span>
          <Segmented<AgentStatusFilter>
            value={filters.agentStatus}
            onChange={v => upd("agentStatus", v)}
            options={[
              { value: "all", label: "ALL" },
              { value: "active", label: "ACTIVE" },
              { value: "idle", label: "IDLE" },
              { value: "terminated", label: "TERM" },
            ]}
          />
        </div>

        <div className="dbx-filter-group">
          <span className="dbx-filter-label">GOALS</span>
          <Segmented<GoalHealthFilter>
            value={filters.goalHealth}
            onChange={v => upd("goalHealth", v)}
            options={[
              { value: "all", label: "ALL" },
              { value: "ok", label: "OK" },
              { value: "at_risk", label: "RISK" },
              { value: "critical", label: "CRIT" },
            ]}
          />
        </div>

        <div className="dbx-filter-group">
          <span className="dbx-filter-label">FLOW</span>
          <Segmented<WorkflowStatusFilter>
            value={filters.workflowStatus}
            onChange={v => upd("workflowStatus", v)}
            options={[
              { value: "all", label: "ALL" },
              { value: "running", label: "RUN" },
              { value: "idle", label: "IDLE" },
              { value: "failed", label: "FAIL" },
            ]}
          />
        </div>

        <div className="dbx-filter-group">
          <span className="dbx-filter-label">MEMORY</span>
          <select
            className="dbx-filter-select"
            value={filters.memoryType}
            onChange={e => upd("memoryType", e.target.value)}
          >
            <option value="all">ALL TYPES</option>
            {memoryTypes.map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select>
        </div>

        <div className="dbx-filter-group">
          <span className="dbx-filter-label">LOG</span>
          <select
            className="dbx-filter-select"
            value={filters.logKind}
            onChange={e => upd("logKind", e.target.value)}
          >
            <option value="all">ALL EVENTS</option>
            {logKinds.map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select>
        </div>
      </div>
    </div>
  );
}

function ActivityRow({ ev }: { ev: AgentActivityEvent }) {
  const t = new Date(ev.timestamp ?? Date.now());
  const ts = `${t.getHours().toString().padStart(2,"0")}:${t.getMinutes().toString().padStart(2,"0")}:${t.getSeconds().toString().padStart(2,"0")}`;
  const text = (ev as any).message ?? (ev as any).description ?? (ev as any).type ?? "event";
  return (
    <div className="dbx-log-row">
      <span className="dbx-log-ts">{ts}</span>
      <span className="dbx-log-arrow">›</span>
      <span className="dbx-log-text">{text}</span>
    </div>
  );
}

/* ================================================================
   ROOT
   ================================================================ */
export default function DashboardPage({
  messages, isConnected, voice, agentActivity, goalEvents, workflowEvents,
}: DashboardProps) {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [entities, setEntities] = useState<VaultEntity[]>([]);
  const [entityCount, setEntityCount] = useState(0);
  const [goals, setGoals] = useState<GoalData[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowData[]>([]);

  const DEFAULT_FILTERS: DashboardFilters = {
    query: "",
    agentStatus: "all",
    goalHealth: "all",
    workflowStatus: "all",
    memoryType: "all",
    logKind: "all",
    live: true,
  };
  const [filters, setFilters] = useState<DashboardFilters>(DEFAULT_FILTERS);
  const resetFilters = useCallback(() => setFilters(DEFAULT_FILTERS), []);

  const fetchAgents = useCallback(async () => {
    try { setAgents(await api<AgentInfo[]>("/api/agents")); } catch {}
  }, []);
  const fetchHealth = useCallback(async () => {
    try { setHealth(await api<HealthData>("/api/health")); } catch {}
  }, []);
  const fetchEntities = useCallback(async () => {
    try {
      const data = await api<VaultEntity[]>("/api/vault/entities");
      setEntityCount(data.length);
      setEntities([...data].sort((a, b) => b.updated_at - a.updated_at).slice(0, 50));
    } catch {}
  }, []);
  const fetchGoals = useCallback(async () => {
    try { setGoals(await api<GoalData[]>("/api/goals?status=active&limit=8")); } catch {}
  }, []);
  const fetchWorkflows = useCallback(async () => {
    try { setWorkflows(await api<WorkflowData[]>("/api/workflows")); } catch {}
  }, []);

  useEffect(() => {
    fetchAgents(); fetchHealth(); fetchEntities(); fetchGoals(); fetchWorkflows();
  }, [fetchAgents, fetchHealth, fetchEntities, fetchGoals, fetchWorkflows]);

  useEffect(() => {
    if (!filters.live) return;
    const a = setInterval(fetchAgents, 5000);
    const h = setInterval(fetchHealth, 10000);
    const e = setInterval(fetchEntities, 30000);
    return () => { clearInterval(a); clearInterval(h); clearInterval(e); };
  }, [fetchAgents, fetchHealth, fetchEntities, filters.live]);

  useEffect(() => { if (filters.live && goalEvents.length) fetchGoals(); }, [goalEvents.length, fetchGoals, filters.live]);
  useEffect(() => { if (filters.live && workflowEvents.length) fetchWorkflows(); }, [workflowEvents.length, fetchWorkflows, filters.live]);

  const activeAgents = agents.filter(a => a.status === "active").length;
  const runningWf = workflows.filter(w => w.status === "running" || w.status === "active").length;
  const memPct = health ? Math.round((health.memory.heapUsed / health.memory.heapTotal) * 100) : 0;

  // Available facets for filter selectors
  const memoryTypes = useMemo(
    () => Array.from(new Set(entities.map(e => e.type).filter(Boolean))).sort(),
    [entities],
  );
  const logKinds = useMemo(() => {
    const set = new Set<string>();
    agentActivity.forEach(ev => {
      const t = (ev as any).type ?? (ev as any).kind;
      if (typeof t === "string" && t) set.add(t);
    });
    return Array.from(set).sort();
  }, [agentActivity]);

  const q = filters.query.trim().toLowerCase();
  const matchQ = (...fields: (string | undefined | null)[]) =>
    !q || fields.some(f => (f ?? "").toLowerCase().includes(q));

  const filteredAgents = useMemo(() => agents.filter(a => {
    if (filters.agentStatus !== "all" && a.status !== filters.agentStatus) return false;
    return matchQ(a.role.name, a.role.id, a.current_task ?? "");
  }), [agents, filters.agentStatus, q]);

  const filteredGoals = useMemo(() => goals.filter(g => {
    if (filters.goalHealth !== "all") {
      const tone = g.health === "critical" || g.health === "behind"
        ? "critical"
        : g.health === "at_risk" ? "at_risk" : "ok";
      if (tone !== filters.goalHealth) return false;
    }
    return matchQ(g.title, g.status, g.health, g.level);
  }), [goals, filters.goalHealth, q]);

  const filteredWorkflows = useMemo(() => workflows.filter(w => {
    if (filters.workflowStatus !== "all") {
      const kind = w.status === "running" || w.status === "active" ? "running"
        : w.status === "failed" || w.status === "error" ? "failed" : "idle";
      if (kind !== filters.workflowStatus) return false;
    }
    return matchQ(w.name, w.status);
  }), [workflows, filters.workflowStatus, q]);

  const filteredEntities = useMemo(() => entities.filter(e => {
    if (filters.memoryType !== "all" && e.type !== filters.memoryType) return false;
    return matchQ(e.name, e.description, e.type);
  }), [entities, filters.memoryType, q]);

  const filteredActivity = useMemo(() => {
    return agentActivity.filter(ev => {
      const t = (ev as any).type ?? (ev as any).kind ?? "";
      if (filters.logKind !== "all" && t !== filters.logKind) return false;
      const text = (ev as any).message ?? (ev as any).description ?? t;
      return matchQ(String(text), String(t));
    });
  }, [agentActivity, filters.logKind, q]);

  // Build a fake-ish but stable spark from current values + recent activity counts
  const activitySpark = useMemo(() => {
    const buckets = new Array(40).fill(0);
    filteredActivity.slice(-200).forEach((ev, i) => {
      const idx = Math.floor((i / Math.max(1, Math.min(200, filteredActivity.length))) * 40);
      buckets[idx] = (buckets[idx] ?? 0) + 1;
    });
    if (buckets.every(b => b === 0)) return [1,2,1,3,2,4,3,5,4,6,5,4,3,2,3,4,5,6,7,5,4,3,2,1,2,3,4,5,6,5,4,3,2,1,2,3,2,1,2,3];
    return buckets;
  }, [filteredActivity]);

  const recentActivity = filteredActivity.slice(-12).reverse();

  const filteredServices = useMemo(() => {
    if (!health) return [] as [string, string][];
    return Object.entries(health.services).filter(([name, status]) => matchQ(name, status));
  }, [health, q]);

  return (
    <div className="dbx-root">
      <SystemHeader health={health} isConnected={isConnected} />

      {/* Top stat ribbon */}
      <div className="dbx-tiles">
        <StatTile label="AGENTS·ACTIVE" value={String(activeAgents).padStart(2, "0")} sub={`${agents.length} TOTAL`} href="#/office" accent />
        <StatTile label="WORKFLOWS·LIVE" value={String(runningWf).padStart(2, "0")} sub={`${workflows.length} REGISTERED`} href="#/workflows" />
        <StatTile label="ENTITIES" value={entityCount > 999 ? `${(entityCount / 1000).toFixed(1)}K` : String(entityCount)} sub="MEMORY VAULT" href="#/memory" />
        <StatTile label="GOALS·OPEN" value={String(goals.filter(g => g.status === "active").length).padStart(2, "0")} sub="TRACKED" href="#/goals" />
        <StatTile label="HEAP" value={`${memPct}%`} sub={health ? `${(health.memory.heapUsed/1048576).toFixed(0)}MB` : "--"} />
        <StatTile label="MESSAGES" value={String(messages.length).padStart(4, "0")} sub="THIS SESSION" href="#/chat" />
      </div>

      <FilterBar
        filters={filters}
        setFilters={setFilters}
        memoryTypes={memoryTypes}
        logKinds={logKinds}
        onReset={resetFilters}
      />

      {/* Activity sparkline strip */}
      <div className="dbx-spark-strip">
        <span className="dbx-spark-label">EVENT FLOW · 24H</span>
        <Spark data={activitySpark} width={120} />
        <span className="dbx-spark-meta">{filteredActivity.length} / {agentActivity.length} EVENTS</span>
      </div>

      {/* Main grid */}
      <div className="dbx-grid">
        {/* Agents */}
        <Panel title="AGENT FLEET" count={filteredAgents.length} action={{ label: "TOPOLOGY", href: "#/office" }}>
          {filteredAgents.length === 0
            ? <div className="dbx-empty">// {agents.length === 0 ? "no agents registered" : "no agents match filters"}</div>
            : filteredAgents.slice(0, 8).map(a => <AgentRow key={a.id} agent={a} />)}
        </Panel>

        {/* Activity log */}
        <Panel title="LIVE LOG" count={filteredActivity.length} action={{ label: "FULL", href: "#/awareness" }}>
          {recentActivity.length === 0
            ? <div className="dbx-empty">// {agentActivity.length === 0 ? "awaiting activity" : "no events match filters"}</div>
            : recentActivity.map((ev, i) => <ActivityRow key={i} ev={ev} />)}
        </Panel>

        {/* Goals */}
        <Panel title="GOALS" count={filteredGoals.length} action={{ label: "ALL", href: "#/goals" }}>
          {filteredGoals.length === 0
            ? <div className="dbx-empty">// {goals.length === 0 ? "no active goals" : "no goals match filters"}</div>
            : filteredGoals.slice(0, 6).map(g => <GoalRow key={g.id} goal={g} />)}
        </Panel>

        {/* Memory */}
        <Panel title="MEMORY · RECENT" count={filteredEntities.length} action={{ label: "BROWSE", href: "#/memory" }}>
          {filteredEntities.length === 0
            ? <div className="dbx-empty">// {entities.length === 0 ? "vault empty" : "no entities match filters"}</div>
            : filteredEntities.slice(0, 8).map(e => <MemoryRow key={e.id} entity={e} />)}
        </Panel>

        {/* Workflows */}
        <Panel title="WORKFLOWS" count={filteredWorkflows.length} action={{ label: "DESIGNER", href: "#/workflows" }}>
          {filteredWorkflows.length === 0
            ? <div className="dbx-empty">// {workflows.length === 0 ? "no workflows" : "no workflows match filters"}</div>
            : filteredWorkflows.slice(0, 6).map(w => <WorkflowRow key={w.id} wf={w} />)}
        </Panel>

        {/* Services */}
        <Panel title="SERVICES" count={filteredServices.length}>
          {!health
            ? <div className="dbx-empty">// no health report</div>
            : filteredServices.length === 0
              ? <div className="dbx-empty">// no services match filters</div>
              : filteredServices.map(([name, status]) => {
                const kind: "ok" | "warn" | "err" =
                  status === "ok" || status === "running" || status === "healthy" ? "ok"
                  : status === "degraded" || status === "warning" ? "warn"
                  : "err";
                return (
                  <div className="dbx-row" key={name}>
                    <StatusDot kind={kind} />
                    <span className="dbx-row-name">{name}</span>
                    <span className="dbx-row-fill" />
                    <span className="dbx-row-tag">{status}</span>
                  </div>
                );
              })}
        </Panel>
      </div>

      {/* Footer prompt */}
      <div className="dbx-footer">
        <span className="dbx-prompt">sam@command:~$</span>
        <span className="dbx-prompt-cursor">█</span>
        <span className="dbx-prompt-hint">use the chat panel — voice: "Hey Sam"</span>
      </div>
    </div>
  );
}
