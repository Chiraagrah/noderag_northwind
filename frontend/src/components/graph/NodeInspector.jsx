import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import useGraphStore from "../../store/graphStore";
import { api } from "../../utils/api";
import { NODE_CONFIG } from "../../utils/nodeColors";

function SectionLabel({ children }) {
  return (
    <div style={{
      fontFamily:    "JetBrains Mono",
      fontSize:      10,
      color:         "var(--muted)",
      textTransform: "lowercase",
      marginBottom:  4,
      marginTop:     16,
    }}>
      {children}
    </div>
  );
}

export default function NodeInspector() {
  const selectedNodeId = useGraphStore(s => s.selectedNodeId);
  const selectNode     = useGraphStore(s => s.selectNode);
  const d3Data         = useGraphStore(s => s.d3Data);
  const fetchSubgraph  = useGraphStore(s => s.fetchSubgraph);

  const [nodeDetail, setNodeDetail] = useState(null);

  useEffect(() => {
    if (!selectedNodeId) { setNodeDetail(null); return; }
    api.getNode(selectedNodeId)
      .then(setNodeDetail)
      .catch(() => setNodeDetail(null));
  }, [selectedNodeId]);

  if (!selectedNodeId) return null;

  const cfg  = NODE_CONFIG[nodeDetail?.node_type] ?? { code: "?", label: "Unknown", color: "var(--muted)" };
  const links = d3Data?.links ?? [];
  const outgoing = links.filter(l => {
    const s = typeof l.source === "object" ? l.source.id : l.source;
    return s === selectedNodeId;
  }).length;
  const incoming = links.filter(l => {
    const t = typeof l.target === "object" ? l.target.id : l.target;
    return t === selectedNodeId;
  }).length;

  return (
    <motion.div
      key={selectedNodeId}
      initial={{ x: 300, opacity: 0 }}
      animate={{ x: 0,   opacity: 1 }}
      exit={{    x: 300, opacity: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      style={{
        position:    "absolute",
        top:         0,
        right:       0,
        bottom:      0,
        width:       300,
        background:  "var(--panel)",
        borderLeft:  "1px solid var(--border)",
        display:     "flex",
        flexDirection: "column",
        zIndex:      10,
      }}
    >
      {/* Header */}
      <div style={{
        height:        40,
        borderBottom:  "1px solid var(--border)",
        padding:       "0 12px",
        display:       "flex",
        alignItems:    "center",
        justifyContent: "space-between",
        flexShrink:    0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontFamily: "JetBrains Mono", fontSize: 10, color: cfg.color }}>
            {cfg.code}
          </span>
          <span style={{ fontFamily: "var(--font-ui)", fontSize: 12, color: "var(--primary)" }}>
            {cfg.label}
          </span>
        </div>
        <button
          onClick={() => selectNode(null)}
          style={{
            width:      20,
            height:     20,
            background: "none",
            border:     "none",
            color:      "var(--muted)",
            fontSize:   16,
            cursor:     "pointer",
            lineHeight: "20px",
            padding:    0,
          }}
          onMouseEnter={e => e.currentTarget.style.color = "var(--primary)"}
          onMouseLeave={e => e.currentTarget.style.color = "var(--muted)"}
        >
          ×
        </button>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
        <SectionLabel>node id</SectionLabel>
        <div style={{
          fontFamily:  "JetBrains Mono",
          fontSize:    10,
          color:       "var(--muted)",
          userSelect:  "all",
          wordBreak:   "break-all",
        }}>
          {selectedNodeId}
        </div>

        {nodeDetail && (
          <>
            <SectionLabel>description</SectionLabel>
            <div style={{
              fontFamily:  "var(--font-ui)",
              fontSize:    12,
              color:       "var(--primary)",
              lineHeight:  1.6,
            }}>
              {nodeDetail.text}
            </div>

            <Properties nodeDetail={nodeDetail} selectNode={selectNode} />
          </>
        )}

        <SectionLabel>connections</SectionLabel>
        <div style={{ fontFamily: "JetBrains Mono", fontSize: 10, color: "var(--muted)", display: "flex", gap: 16 }}>
          <span>→ {outgoing} out</span>
          <span>← {incoming} in</span>
        </div>
      </div>

      {/* Footer */}
      <div style={{
        height:       36,
        borderTop:    "1px solid var(--border)",
        padding:      "0 8px",
        display:      "flex",
        alignItems:   "center",
        flexShrink:   0,
      }}>
        <ExpandButton nodeId={selectedNodeId} fetchSubgraph={fetchSubgraph} />
      </div>
    </motion.div>
  );
}

function Properties({ nodeDetail, selectNode }) {
  const type = nodeDetail.node_type;

  if (type === "entity" && nodeDetail.attributes && Object.keys(nodeDetail.attributes).length > 0) {
    return (
      <>
        <SectionLabel>properties</SectionLabel>
        <PropList entries={Object.entries(nodeDetail.attributes)} />
      </>
    );
  }

  if (type === "relationship") {
    return (
      <>
        <SectionLabel>properties</SectionLabel>
        <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "2px 12px" }}>
          <dt style={dtStyle}>from</dt>
          <dd style={ddStyle}>
            <button onClick={() => selectNode(nodeDetail.from_entity_id)} style={linkBtnStyle}>
              {nodeDetail.from_entity_id}
            </button>
          </dd>
          <dt style={dtStyle}>to</dt>
          <dd style={ddStyle}>
            <button onClick={() => selectNode(nodeDetail.to_entity_id)} style={linkBtnStyle}>
              {nodeDetail.to_entity_id}
            </button>
          </dd>
          <dt style={dtStyle}>label</dt>
          <dd style={ddStyle}>{nodeDetail.relation_label}</dd>
        </dl>
      </>
    );
  }

  if (type === "community") {
    return (
      <>
        <SectionLabel>properties</SectionLabel>
        <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "2px 12px" }}>
          <dt style={dtStyle}>k-core</dt>
          <dd style={ddStyle}>{nodeDetail.core_number}</dd>
          <dt style={dtStyle}>members</dt>
          <dd style={ddStyle}>{nodeDetail.member_node_ids?.length ?? 0}</dd>
        </dl>
      </>
    );
  }

  if (type === "high_level_insight") {
    return (
      <>
        <SectionLabel>properties</SectionLabel>
        <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "2px 12px" }}>
          <dt style={dtStyle}>confidence</dt>
          <dd style={ddStyle}>{nodeDetail.confidence}</dd>
          <dt style={dtStyle}>type</dt>
          <dd style={ddStyle}>{nodeDetail.insight_type}</dd>
        </dl>
      </>
    );
  }

  return null;
}

function PropList({ entries }) {
  return (
    <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "2px 12px" }}>
      {entries.map(([k, v]) => (
        <span key={k} style={{ display: "contents" }}>
          <dt style={dtStyle}>{k}</dt>
          <dd style={ddStyle}>{String(v)}</dd>
        </span>
      ))}
    </dl>
  );
}

function ExpandButton({ nodeId, fetchSubgraph }) {
  const [loading, setLoading] = useState(false);
  const handle = async () => {
    setLoading(true);
    await fetchSubgraph(nodeId);
    setLoading(false);
  };
  return (
    <button
      onClick={handle}
      disabled={loading}
      style={{
        width:       "100%",
        background:  "transparent",
        border:      "1px solid var(--border)",
        color:       "var(--primary)",
        fontFamily:  "var(--font-ui)",
        fontSize:    11,
        cursor:      "pointer",
        height:      24,
        borderRadius: 0,
        transition:  "border-color 150ms, color 150ms",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = "var(--accent)";
        e.currentTarget.style.color       = "var(--accent)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = "var(--border)";
        e.currentTarget.style.color       = "var(--primary)";
      }}
    >
      {loading ? "loading..." : "expand subgraph"}
    </button>
  );
}

const dtStyle = {
  fontFamily: "JetBrains Mono",
  fontSize:   10,
  color:      "var(--muted)",
  paddingTop: 2,
};
const ddStyle = {
  fontFamily: "var(--font-ui)",
  fontSize:   12,
  color:      "var(--primary)",
  margin:     0,
  wordBreak:  "break-word",
};
const linkBtnStyle = {
  fontFamily:  "JetBrains Mono",
  fontSize:    10,
  color:       "var(--accent)",
  background:  "none",
  border:      "none",
  cursor:      "pointer",
  padding:     0,
  textAlign:   "left",
  wordBreak:   "break-all",
};
