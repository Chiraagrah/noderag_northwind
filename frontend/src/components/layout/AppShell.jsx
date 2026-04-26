import { AnimatePresence } from "framer-motion";
import useGraphStore from "../../store/graphStore";
import GraphCanvas from "../graph/GraphCanvas";
import NodeInspector from "../graph/NodeInspector";
import QueryConsole from "../query/QueryConsole";
import ErrorBoundary from "../ErrorBoundary";

export default function AppShell() {
  const selectedNodeId = useGraphStore(s => s.selectedNodeId);

  return (
    <div
      className="app-shell"
      style={{
        display:    "flex",
        height:     "calc(100vh - 40px)",
        marginTop:  40,
        overflow:   "hidden",
      }}
    >
      {/* left — graph canvas */}
      <div
        className="graph-panel"
        style={{ position: "relative", flex: "65 1 0", minWidth: 0 }}
      >
        <ErrorBoundary>
          <GraphCanvas />
          <AnimatePresence>
            {selectedNodeId && <NodeInspector key={selectedNodeId} />}
          </AnimatePresence>
        </ErrorBoundary>
      </div>

      {/* divider */}
      <div style={{ width: 1, background: "var(--border)", flexShrink: 0 }} />

      {/* right — query console */}
      <div
        className="console-panel"
        style={{ flex: "35 1 0", minWidth: 0, display: "flex", flexDirection: "column" }}
      >
        <ErrorBoundary>
          <QueryConsole />
        </ErrorBoundary>
      </div>
    </div>
  );
}
