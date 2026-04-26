import { motion, AnimatePresence } from "framer-motion";
import useQueryStore from "../../store/queryStore";
import { NODE_CONFIG } from "../../utils/nodeColors";

const EVENT_COLORS = {
  seed:    "var(--n5)",
  ppr:     "var(--n2)",
  kcore:   "var(--n7)",
  context: "var(--n3)",
  answer:  "var(--primary)",
  error:   "#E05C5C",
};

function getSummary(event, indexInType) {
  const { event_type, data } = event;
  switch (event_type) {
    case "seed":
      if (data.status === "embedding") return "embedding query";
      return `found ${data.nodes?.length ?? 0} seed nodes`;
    case "ppr":
      return `traversed graph · ${data.nodes?.length ?? 0} nodes ranked`;
    case "kcore":
      return "k-core boost applied";
    case "context":
      return `assembled ${data.char_count ?? 0} char context from ${data.node_count ?? 0} nodes`;
    case "answer":
      return `answer generated (${data.confidence ?? "?"} confidence)`;
    case "error":
      return data.message ?? "unknown error";
    default:
      return event_type;
  }
}

function getNodeTypeCode(node) {
  return NODE_CONFIG[node.node_type]?.code ?? "??";
}

function PprSubRow({ nodes }) {
  const top3 = (nodes ?? []).slice(0, 3);
  if (top3.length === 0) return null;
  return (
    <div style={{
      fontFamily: "JetBrains Mono",
      fontSize:   10,
      color:      "var(--muted)",
      paddingLeft: 60,
      marginTop:  2,
    }}>
      {"↳ "}
      {top3.map((n, i) => (
        <span key={n.node_id} style={{ marginRight: 8 }}>
          <span style={{ color: NODE_CONFIG[n.node_type]?.color ?? "var(--muted)" }}>
            [{getNodeTypeCode(n)}]
          </span>
          {" "}{n.node_id}
        </span>
      ))}
    </div>
  );
}

export default function RetrievalLog() {
  const steps = useQueryStore(s => s.steps);

  // track which "seed" event index we're on to distinguish first vs second
  let seedCount = 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <AnimatePresence initial={false}>
        {steps.map((event, i) => {
          const isSeed = event.event_type === "seed";
          const seedIdx = isSeed ? seedCount++ : -1;
          const summary = getSummary(event, seedIdx);
          const elapsed = event._elapsed ?? 0;

          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.12 }}
            >
              <div style={{
                display:    "flex",
                gap:        8,
                alignItems: "baseline",
              }}>
                <span style={{
                  fontFamily:  "JetBrains Mono",
                  fontSize:    10,
                  color:       "var(--muted)",
                  minWidth:    40,
                  textAlign:   "right",
                  flexShrink:  0,
                }}>
                  {elapsed}ms
                </span>
                <span style={{
                  fontFamily: "JetBrains Mono",
                  fontSize:   10,
                  color:      EVENT_COLORS[event.event_type] ?? "var(--muted)",
                  minWidth:   52,
                  flexShrink: 0,
                }}>
                  {event.event_type}
                </span>
                <span style={{
                  fontFamily: "JetBrains Mono",
                  fontSize:   10,
                  color:      "var(--muted)",
                }}>
                  {summary}
                </span>
              </div>

              {event.event_type === "ppr" && (
                <PprSubRow nodes={event.data.nodes} />
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
