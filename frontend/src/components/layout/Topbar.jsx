import { useState, useEffect } from "react";
import { api } from "../../utils/api";
import useGraphStore from "../../store/graphStore";

function StatPill({ value, label }) {
  return (
    <div style={{
      background:  "transparent",
      border:      "1px solid var(--border)",
      padding:     "2px 8px",
      fontFamily:  "JetBrains Mono",
      fontSize:    10,
      display:     "flex",
      gap:         4,
      alignItems:  "center",
    }}>
      <span style={{ color: "var(--primary)" }}>{value}</span>
      <span style={{ color: "var(--muted)" }}>{label}</span>
    </div>
  );
}

export default function Topbar() {
  const fetchGraph = useGraphStore(s => s.fetchGraph);

  const [stats,     setStats]     = useState(null);
  const [apiOnline, setApiOnline] = useState(true);
  const [reloading, setReloading] = useState(false);

  // load stats once on mount
  useEffect(() => {
    api.getStats().then(setStats).catch(() => {});
  }, []);

  // poll api status every 15 s
  useEffect(() => {
    const check = () => api.ping().then(setApiOnline);
    check();
    const id = setInterval(check, 15_000);
    return () => clearInterval(id);
  }, []);

  const handleReload = async () => {
    setReloading(true);
    try {
      await api.reload();
      const s = await api.getStats();
      setStats(s);
      await fetchGraph();
    } catch {}
    setReloading(false);
  };

  const DASH = "—";

  return (
    <div style={{
      position:      "fixed",
      top:           0,
      left:          0,
      right:         0,
      height:        40,
      zIndex:        50,
      background:    "var(--panel)",
      borderBottom:  "1px solid var(--border)",
      display:       "flex",
      alignItems:    "center",
      padding:       "0 16px",
      gap:           16,
    }}>
      {/* left — wordmark */}
      <div style={{ display: "flex", alignItems: "center", gap: 0, flexShrink: 0 }}>
        <span style={{ fontFamily: "var(--font-ui)", fontWeight: 500, fontSize: 15, color: "var(--primary)" }}>
          NODE
        </span>
        <span style={{ fontFamily: "var(--font-ui)", fontWeight: 300, fontSize: 15, color: "var(--muted)" }}>
          RAG
        </span>
        <div style={{
          width:      1,
          height:     14,
          background: "var(--border)",
          margin:     "0 12px",
          flexShrink: 0,
        }} />
        <span style={{ fontFamily: "JetBrains Mono", fontSize: 9, color: "var(--muted)" }}>
          northwind · knowledge graph
        </span>
      </div>

      {/* center — stat pills */}
      <div style={{ flex: 1, display: "flex", justifyContent: "center", gap: 6 }}>
        <StatPill value={stats?.node_count       ?? DASH} label="nodes" />
        <StatPill value={stats?.edge_count       ?? DASH} label="edges" />
        <StatPill value={stats?.node_type_count  ?? DASH} label="types" />
      </div>

      {/* right — controls + status + shortcuts */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
        <span style={{ fontFamily: "JetBrains Mono", fontSize: 9, color: "var(--muted)" }}>
          / query&nbsp;&nbsp;esc clear
        </span>

        <button
          onClick={handleReload}
          disabled={reloading}
          style={{
            fontFamily:  "JetBrains Mono",
            fontSize:    10,
            color:       "var(--muted)",
            background:  "none",
            border:      "none",
            cursor:      "pointer",
            padding:     0,
            transition:  "color 150ms",
          }}
          onMouseEnter={e => e.currentTarget.style.color = "var(--primary)"}
          onMouseLeave={e => e.currentTarget.style.color = "var(--muted)"}
        >
          {reloading ? "reloading..." : "reload"}
        </button>

        <span style={{
          fontFamily: "JetBrains Mono",
          fontSize:   10,
          color:      apiOnline ? "var(--n2)" : "#E05C5C",
          transition: "color 300ms",
        }}>
          {apiOnline ? "api online" : "api offline"}
        </span>
      </div>
    </div>
  );
}
