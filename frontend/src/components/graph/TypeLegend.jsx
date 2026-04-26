import useGraphStore from "../../store/graphStore";
import { NODE_CONFIG } from "../../utils/nodeColors";

export default function TypeLegend() {
  const nodeCounts = useGraphStore(s => s.graphData?.node_counts ?? {});

  return (
    <div style={{
      position:   "absolute",
      bottom:     12,
      left:       12,
      padding:    12,
      background: "var(--panel)",
      border:     "1px solid var(--border)",
      borderRadius: 0,
    }}>
      <table style={{ borderCollapse: "collapse" }}>
        <tbody>
          {Object.entries(NODE_CONFIG).map(([type, cfg]) => (
            <tr key={type}>
              <td style={{ padding: "2px 8px 2px 0" }}>
                <div style={{
                  width:        10,
                  height:       10,
                  background:   cfg.color,
                  borderRadius: 0,
                  flexShrink:   0,
                }} />
              </td>
              <td style={{
                padding:    "2px 8px 2px 0",
                fontFamily: "JetBrains Mono",
                fontSize:   10,
                color:      "var(--muted)",
              }}>
                {cfg.code}
              </td>
              <td style={{
                padding:    "2px 8px 2px 0",
                fontFamily: "var(--font-ui)",
                fontSize:   11,
                color:      "var(--primary)",
              }}>
                {cfg.label}
              </td>
              <td style={{
                padding:    "2px 0",
                fontFamily: "JetBrains Mono",
                fontSize:   10,
                color:      "var(--muted)",
                textAlign:  "right",
              }}>
                {nodeCounts[type] ?? 0}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
