import { useState, useEffect } from "react";
import useQueryStore from "../../store/queryStore";
import useGraphStore from "../../store/graphStore";
import { NODE_CONFIG } from "../../utils/nodeColors";

const CONFIDENCE_COLORS = {
  high:   "var(--n2)",
  medium: "var(--n3)",
  low:    "#E05C5C",
};

// derive node type from node_id prefix heuristic
function guessNodeType(nodeId) {
  if (!nodeId) return null;
  const id = nodeId.toLowerCase();
  if (id.startsWith("entity_"))   return "entity";
  if (id.startsWith("rel_"))      return "relationship";
  if (id.startsWith("su_"))       return "semantic_unit";
  if (id.startsWith("attr_"))     return "attribute";
  if (id.startsWith("insight_"))  return "high_level_insight";
  if (id.startsWith("community")) return "community";
  if (id.startsWith("tc_") || id.startsWith("chunk_")) return "text_chunk";
  return null;
}

function CitedToken({ nodeId }) {
  const selectNode  = useGraphStore(s => s.selectNode);
  const nodeType    = guessNodeType(nodeId);
  const color       = NODE_CONFIG[nodeType]?.color ?? "var(--border)";

  const handleClick = () => {
    selectNode(nodeId);
    window.__noderagZoomToNode?.(nodeId);
  };

  return (
    <button
      onClick={handleClick}
      title={nodeId}
      style={{
        fontFamily:  "JetBrains Mono",
        fontSize:    10,
        background:  "var(--overlay)",
        border:      "1px solid var(--border)",
        borderLeft:  `3px solid ${color}`,
        padding:     "2px 6px",
        color:       "var(--primary)",
        cursor:      "pointer",
        borderRadius: 0,
        transition:  "border-color 150ms",
        whiteSpace:  "nowrap",
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = color}
      onMouseLeave={e => {
        e.currentTarget.style.borderLeftColor = color;
        e.currentTarget.style.borderTopColor  = "var(--border)";
        e.currentTarget.style.borderRightColor = "var(--border)";
        e.currentTarget.style.borderBottomColor = "var(--border)";
      }}
    >
      {nodeId}
    </button>
  );
}

export default function AnswerPane() {
  const answer = useQueryStore(s => s.answer);
  const [revealedCount, setRevealedCount] = useState(0);
  const [showReasoning, setShowReasoning] = useState(false);

  const words = answer?.answer?.split(" ") ?? [];

  useEffect(() => {
    if (!answer) { setRevealedCount(0); setShowReasoning(false); return; }
    setRevealedCount(0);
    setShowReasoning(false);
    const allWords = answer.answer.split(" ");
    let i = 0;
    const iv = setInterval(() => {
      i++;
      setRevealedCount(i);
      if (i >= allWords.length) clearInterval(iv);
    }, 30);
    return () => clearInterval(iv);
  }, [answer]);

  if (!answer) return null;

  const visibleText = words.slice(0, revealedCount).join(" ");
  const confidence  = answer.confidence ?? "low";
  const steps       = answer.reasoning_steps ?? [];
  const cited       = answer.cited_nodes ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* confidence */}
      <div style={{
        fontFamily: "JetBrains Mono",
        fontSize:   10,
        color:      CONFIDENCE_COLORS[confidence] ?? "var(--muted)",
      }}>
        confidence: {confidence}
      </div>

      {/* answer text — word-by-word reveal */}
      <div style={{
        fontFamily:   "var(--font-ui)",
        fontSize:     13,
        color:        "var(--primary)",
        lineHeight:   1.7,
        borderLeft:   "2px solid var(--border)",
        paddingLeft:  12,
      }}>
        {visibleText}
      </div>

      {/* reasoning steps — collapsible */}
      {steps.length > 0 && (
        <div>
          <button
            onClick={() => setShowReasoning(v => !v)}
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
            {showReasoning ? "hide reasoning" : `show reasoning (${steps.length} steps)`}
          </button>
          {showReasoning && (
            <ol style={{
              marginTop:   8,
              paddingLeft: 16,
              listStyle:   "decimal",
              display:     "flex",
              flexDirection: "column",
              gap:         0,
            }}>
              {steps.map((s, i) => (
                <li key={i} style={{
                  fontFamily:  "var(--font-ui)",
                  fontSize:    12,
                  color:       "var(--muted)",
                  padding:     "4px 0",
                  lineHeight:  1.5,
                }}>
                  {s}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {/* cited nodes */}
      {cited.length > 0 && (
        <div>
          <div style={{
            fontFamily:   "JetBrains Mono",
            fontSize:     10,
            color:        "var(--muted)",
            marginBottom: 6,
          }}>
            cited nodes
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {cited.map(id => <CitedToken key={id} nodeId={id} />)}
          </div>
        </div>
      )}
    </div>
  );
}
