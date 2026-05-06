import React, { useState, useMemo } from "react";
import { useApiData } from "../hooks/useApi";
import { PageHelp } from "../components/PageHelp";

type Capability = {
  name: string;
  description: string;
  intents: string[];
  handler: string;
  status: "working" | "broken" | "wip" | "planned";
  last_verified: string;
  test: string;
  dependencies: string[];
  tags: string[];
};

type ApiResponse = {
  capabilities: Capability[];
  total: number;
};

type TestResult = {
  name: string;
  result: "pass" | "fail" | "timeout" | "error" | "no_test" | "running";
  output: string;
};

const STATUS_COLORS: Record<string, string> = {
  working: "#34D399",
  broken: "#F87171",
  wip: "#FBBF24",
  planned: "#60A5FA",
};

const STATUS_LABELS: Record<string, string> = {
  working: "working",
  broken: "broken",
  wip: "wip",
  planned: "planned",
};

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? "rgba(255,255,255,0.4)";
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 8px",
      borderRadius: "4px",
      fontSize: "11px",
      fontWeight: 600,
      letterSpacing: "0.04em",
      textTransform: "uppercase",
      color,
      background: `${color}18`,
      border: `1px solid ${color}44`,
    }}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function CapabilityRow({
  cap,
  testResult,
  onRunTest,
}: {
  cap: Capability;
  testResult?: TestResult;
  onRunTest: (name: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const running = testResult?.result === "running";

  return (
    <div style={{
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      transition: "background 0.1s",
    }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 110px 130px 110px",
          alignItems: "center",
          padding: "10px 16px",
          gap: "12px",
          cursor: "pointer",
          background: expanded ? "rgba(255,255,255,0.03)" : "transparent",
        }}
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Name + description */}
        <div>
          <div style={{ fontSize: "13px", fontWeight: 600, color: "rgba(255,255,255,0.9)" }}>
            {cap.name}
          </div>
          <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.45)", marginTop: "2px" }}>
            {cap.description}
          </div>
        </div>

        {/* Status */}
        <div><StatusBadge status={cap.status} /></div>

        {/* Tags */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
          {cap.tags.slice(0, 3).map((t) => (
            <span key={t} style={{
              fontSize: "10px",
              padding: "1px 6px",
              borderRadius: "3px",
              background: "rgba(255,255,255,0.07)",
              color: "rgba(255,255,255,0.5)",
            }}>{t}</span>
          ))}
        </div>

        {/* Run test */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", alignItems: "center" }}>
          {testResult && testResult.result !== "running" && (
            <span style={{
              fontSize: "11px",
              fontWeight: 600,
              color: testResult.result === "pass" ? "#34D399" : "#F87171",
            }}>
              {testResult.result === "pass" ? "✓ pass" : `✗ ${testResult.result}`}
            </span>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onRunTest(cap.name); }}
            disabled={running || !cap.test}
            title={cap.test ? "Run test" : "No test defined"}
            style={{
              padding: "4px 10px",
              fontSize: "11px",
              fontWeight: 600,
              borderRadius: "5px",
              border: "1px solid rgba(255,255,255,0.15)",
              background: running ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.08)",
              color: cap.test ? "rgba(255,255,255,0.75)" : "rgba(255,255,255,0.25)",
              cursor: cap.test && !running ? "pointer" : "default",
            }}
          >
            {running ? "…" : "Run"}
          </button>
        </div>
      </div>

      {expanded && (
        <div style={{
          padding: "0 16px 14px 16px",
          fontSize: "12px",
          color: "rgba(255,255,255,0.55)",
          background: "rgba(255,255,255,0.02)",
        }}>
          <div style={{ marginBottom: "6px" }}>
            <span style={{ color: "rgba(255,255,255,0.35)", marginRight: "6px" }}>intents</span>
            {cap.intents.map((i) => (
              <code key={i} style={{
                marginRight: "6px",
                padding: "1px 5px",
                background: "rgba(255,255,255,0.07)",
                borderRadius: "3px",
                fontSize: "11px",
              }}>{i}</code>
            ))}
          </div>
          {cap.handler && (
            <div style={{ marginBottom: "6px" }}>
              <span style={{ color: "rgba(255,255,255,0.35)", marginRight: "6px" }}>handler</span>
              <code style={{ fontSize: "11px" }}>{cap.handler}</code>
            </div>
          )}
          {cap.dependencies.length > 0 && (
            <div style={{ marginBottom: "6px" }}>
              <span style={{ color: "rgba(255,255,255,0.35)", marginRight: "6px" }}>deps</span>
              {cap.dependencies.map((d) => (
                <span key={d} style={{ marginRight: "6px", color: "#FBBF24" }}>{d}</span>
              ))}
            </div>
          )}
          {cap.last_verified && (
            <div style={{ marginBottom: "6px" }}>
              <span style={{ color: "rgba(255,255,255,0.35)", marginRight: "6px" }}>verified</span>
              {cap.last_verified}
            </div>
          )}
          {testResult && testResult.result !== "running" && testResult.output && (
            <pre style={{
              marginTop: "8px",
              padding: "8px",
              background: "rgba(0,0,0,0.4)",
              borderRadius: "5px",
              fontSize: "11px",
              overflowX: "auto",
              color: testResult.result === "pass" ? "#34D399" : "#F87171",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
            }}>
              {testResult.output}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function CapabilitiesPage() {
  const { data, loading, error } = useApiData<ApiResponse>("/api/capabilities", []);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [tagFilter, setTagFilter] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});

  const allTags = useMemo(() => {
    if (!data?.capabilities) return [];
    const set = new Set<string>();
    data.capabilities.forEach((c) => c.tags.forEach((t) => set.add(t)));
    return Array.from(set).sort();
  }, [data]);

  const counts = useMemo(() => {
    const r: Record<string, number> = { all: 0, working: 0, broken: 0, wip: 0, planned: 0 };
    (data?.capabilities ?? []).forEach((c) => {
      r["all"]!++;
      if (c.status in r) r[c.status]!++;
    });
    return r;
  }, [data]);

  const filtered = useMemo(() => {
    let caps = data?.capabilities ?? [];
    if (statusFilter !== "all") caps = caps.filter((c) => c.status === statusFilter);
    if (tagFilter) caps = caps.filter((c) => c.tags.includes(tagFilter));
    if (search.trim()) {
      const q = search.toLowerCase();
      caps = caps.filter(
        (c) =>
          c.name.includes(q) ||
          c.description.toLowerCase().includes(q) ||
          c.intents.some((i) => i.includes(q)) ||
          c.tags.some((t) => t.includes(q))
      );
    }
    return caps;
  }, [data, statusFilter, tagFilter, search]);

  async function runTest(name: string) {
    setTestResults((prev) => ({ ...prev, [name]: { name, result: "running", output: "" } }));
    try {
      const res = await fetch(`/api/capabilities/${name}/test`, { method: "POST" });
      const json: TestResult = await res.json();
      setTestResults((prev) => ({ ...prev, [name]: json }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [name]: { name, result: "error", output: String(err) },
      }));
    }
  }

  const STATUS_TABS = ["all", "working", "broken", "wip", "planned"] as const;

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
          Capabilities
        </h1>
        <p style={{ fontSize: "12px", color: "rgba(255,255,255,0.4)", margin: "4px 0 0" }}>
          {data?.total ?? 0} capabilities · single source of truth
        </p>
      </div>
      <PageHelp
        title="Capabilities — what Sam can do"
        what="Every action Sam knows, with live working/broken/wip status. Single source of truth."
        how={[
          "Filter by status tab (working / broken / wip / planned) or search by name.",
          "Expand a row to see the intents that trigger it and its dependencies.",
          "Click Run test to verify a capability is working right now.",
          "Voice: Sam, what can you do? — speaks from this list.",
        ]}
      />


      {/* Status filter tabs */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "14px", flexWrap: "wrap" }}>
        {STATUS_TABS.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            style={{
              padding: "5px 12px",
              borderRadius: "6px",
              border: "1px solid",
              borderColor: statusFilter === s ? (STATUS_COLORS[s] ?? "rgba(255,255,255,0.3)") : "rgba(255,255,255,0.1)",
              background: statusFilter === s ? `${(STATUS_COLORS[s] ?? "#ffffff")}18` : "transparent",
              color: statusFilter === s ? (STATUS_COLORS[s] ?? "rgba(255,255,255,0.85)") : "rgba(255,255,255,0.45)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {s === "all" ? "all" : STATUS_LABELS[s]}
            <span style={{ marginLeft: "5px", opacity: 0.6 }}>{counts[s] ?? 0}</span>
          </button>
        ))}
      </div>

      {/* Search + tag filter row */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "14px" }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name, intent, description…"
          style={{
            flex: 1,
            padding: "7px 12px",
            borderRadius: "7px",
            border: "1px solid rgba(255,255,255,0.1)",
            background: "rgba(255,255,255,0.05)",
            color: "rgba(255,255,255,0.85)",
            fontSize: "13px",
            outline: "none",
          }}
        />
        <select
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
          style={{
            padding: "7px 10px",
            borderRadius: "7px",
            border: "1px solid rgba(255,255,255,0.1)",
            background: "#0f0f14",
            color: "rgba(255,255,255,0.7)",
            fontSize: "12px",
            cursor: "pointer",
            minWidth: "130px",
          }}
        >
          <option value="">All tags</option>
          {allTags.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.07)",
        borderRadius: "10px",
        overflow: "hidden",
      }}>
        {/* Column headers */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 110px 130px 110px",
          padding: "8px 16px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          gap: "12px",
        }}>
          {["Capability", "Status", "Tags", "Test"].map((h) => (
            <div key={h} style={{
              fontSize: "10px",
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.3)",
              textAlign: h === "Test" ? "right" : "left",
            }}>{h}</div>
          ))}
        </div>

        {loading && (
          <div style={{ padding: "32px", textAlign: "center", color: "rgba(255,255,255,0.3)", fontSize: "13px" }}>
            Loading…
          </div>
        )}
        {error && (
          <div style={{ padding: "32px", textAlign: "center", color: "#F87171", fontSize: "13px" }}>
            Failed to load capabilities
          </div>
        )}
        {!loading && !error && filtered.length === 0 && (
          <div style={{ padding: "32px", textAlign: "center", color: "rgba(255,255,255,0.3)", fontSize: "13px" }}>
            No capabilities match
          </div>
        )}
        {filtered.map((cap) => (
          <CapabilityRow
            key={cap.name}
            cap={cap}
            testResult={testResults[cap.name]}
            onRunTest={runTest}
          />
        ))}
      </div>
    </div>
  );
}
