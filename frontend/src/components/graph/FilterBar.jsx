import useGraphStore from "../../store/graphStore";
import { NODE_CONFIG } from "../../utils/nodeColors";

export default function FilterBar() {
  const visibleTypes = useGraphStore(s => s.visibleTypes);
  const toggleType   = useGraphStore(s => s.toggleType);

  return (
    <div style={{
      position:   "absolute",
      top:        12,
      left:       12,
      display:    "flex",
      gap:        4,
      flexWrap:   "wrap",
    }}>
      {Object.entries(NODE_CONFIG).map(([type, cfg]) => {
        const active = visibleTypes.has(type);
        return (
          <button
            key={type}
            onClick={() => toggleType(type)}
            title={cfg.label}
            style={{
              height:          22,
              padding:         "0 8px",
              borderRadius:    0,
              border:          "1px solid var(--border)",
              borderLeft:      `3px solid ${active ? cfg.color : "var(--border)"}`,
              background:      active ? "var(--overlay)" : "transparent",
              color:           active ? "var(--primary)" : "var(--muted)",
              fontFamily:      "JetBrains Mono",
              fontSize:        10,
              cursor:          "pointer",
              lineHeight:      "22px",
              transition:      "all 150ms",
            }}
          >
            {cfg.code}
          </button>
        );
      })}
    </div>
  );
}
