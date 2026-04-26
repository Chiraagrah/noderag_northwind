import { useRef, useEffect, useState } from "react";
import useGraphStore from "../../store/graphStore";
import { useD3Graph } from "../../hooks/useD3Graph";
import FilterBar from "./FilterBar";
import TypeLegend from "./TypeLegend";

const LARGE_GRAPH_THRESHOLD = 600;
const LARGE_GRAPH_TYPES = ["entity", "relationship", "high_level_insight", "community"];

// ── sub-components ────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div style={{
      position:       "absolute",
      inset:          0,
      display:        "flex",
      alignItems:     "center",
      justifyContent: "center",
      background:     "var(--surface)",
      zIndex:         5,
    }}>
      {/* Static skeleton — 10 circles, 8 lines */}
      <svg width="300" height="220" style={{ opacity: 0.5 }}>
        {[
          [150,110],[80,60],[220,60],[50,140],[250,140],
          [120,180],[180,180],[90,100],[210,100],[150,40],
        ].map(([cx,cy],i) => (
          <circle key={i} cx={cx} cy={cy} r={10}
            fill="var(--overlay)" stroke="var(--border)" strokeWidth={1} />
        ))}
        {[[150,110,80,60],[150,110,220,60],[150,110,50,140],[150,110,250,140],
          [80,60,90,100],[220,60,210,100],[50,140,120,180],[250,140,180,180]
        ].map(([x1,y1,x2,y2],i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke="var(--border)" strokeWidth={1} />
        ))}
      </svg>
      <div style={{
        position:   "absolute",
        fontFamily: "JetBrains Mono",
        fontSize:   11,
        color:      "var(--muted)",
      }}>
        loading graph...
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div style={{
      position:       "absolute",
      inset:          0,
      display:        "flex",
      flexDirection:  "column",
      alignItems:     "center",
      justifyContent: "center",
      background:     "var(--surface)",
      gap:            8,
      zIndex:         5,
    }}>
      <div style={{ fontFamily: "JetBrains Mono", fontSize: 11, color: "#E05C5C" }}>
        {message}
      </div>
      <button
        onClick={onRetry}
        style={{
          fontFamily:  "JetBrains Mono",
          fontSize:    11,
          color:       "var(--primary)",
          background:  "none",
          border:      "1px solid var(--border)",
          padding:     "4px 12px",
          cursor:      "pointer",
          borderRadius: 0,
        }}
      >
        retry
      </button>
    </div>
  );
}

function ZoomControls({ onZoomIn, onZoomOut, onReset }) {
  const btnStyle = {
    width:        28,
    height:       28,
    background:   "var(--panel)",
    border:       "1px solid var(--border)",
    color:        "var(--primary)",
    fontSize:     16,
    cursor:       "pointer",
    borderRadius: 0,
    display:      "flex",
    alignItems:   "center",
    justifyContent: "center",
    fontFamily:   "JetBrains Mono",
  };

  return (
    <div style={{
      position:      "absolute",
      bottom:        12,
      right:         12,
      display:       "flex",
      flexDirection: "column",
      gap:           2,
    }}>
      <button style={btnStyle} onClick={onZoomIn}>+</button>
      <button style={btnStyle} onClick={onZoomOut}>−</button>
      <button style={{ ...btnStyle, fontSize: 9 }} onClick={onReset}>1:1</button>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export default function GraphCanvas() {
  const svgRef       = useRef(null);
  const containerRef = useRef(null);
  const [largeGraph, setLargeGraph] = useState(false);

  const isLoading      = useGraphStore(s => s.isLoading);
  const error          = useGraphStore(s => s.error);
  const d3Data         = useGraphStore(s => s.d3Data);
  const highlightedIds = useGraphStore(s => s.highlightedIds);
  const dimmedIds      = useGraphStore(s => s.dimmedIds);
  const visibleTypes   = useGraphStore(s => s.visibleTypes);
  const fetchGraph     = useGraphStore(s => s.fetchGraph);
  const selectNode     = useGraphStore(s => s.selectNode);
  const hoverNode      = useGraphStore(s => s.hoverNode);
  const setVisibleTypes = useGraphStore(s => s.setVisibleTypes);

  // fetch on mount
  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  // large graph: auto-filter to key types if > threshold
  useEffect(() => {
    if (!d3Data) return;
    if (d3Data.nodes.length > LARGE_GRAPH_THRESHOLD) {
      setVisibleTypes(LARGE_GRAPH_TYPES);
      setLargeGraph(true);
    } else {
      setLargeGraph(false);
    }
  }, [d3Data, setVisibleTypes]);

  const { zoomToNode, resetZoom, zoomBy } = useD3Graph(
    svgRef, containerRef, d3Data,
    {
      onNodeClick:   selectNode,
      onNodeHover:   hoverNode,
      onNodeLeave:   () => hoverNode(null),
      highlightedIds,
      dimmedIds,
      visibleTypes,
    }
  );

  // expose zoomToNode on store for cited-node click (wired in later steps)
  useEffect(() => {
    window.__noderagZoomToNode = zoomToNode;
  }, [zoomToNode]);

  return (
    <div
      className="relative w-full h-full"
      style={{ background: "var(--surface)" }}
    >
      {isLoading && <LoadingState />}
      {error     && <ErrorState message={error} onRetry={fetchGraph} />}

      <svg
        ref={svgRef}
        className="w-full h-full"
        style={{ display: isLoading ? "none" : "block" }}
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 -4 8 8"
            refX="16"
            refY="0"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path d="M0,-4L8,0L0,4" fill="var(--border)" />
          </marker>
        </defs>
        <g ref={containerRef} />
      </svg>

      {!isLoading && (
        <>
          <FilterBar />
          {largeGraph && (
            <div style={{
              position:   "absolute",
              top:        40,
              left:       12,
              fontFamily: "JetBrains Mono",
              fontSize:   10,
              color:      "var(--muted)",
            }}>
              large graph — showing key types only (use filters to reveal all)
            </div>
          )}
          <TypeLegend />
          <ZoomControls
            onZoomIn={() => zoomBy(1.4)}
            onZoomOut={() => zoomBy(1 / 1.4)}
            onReset={resetZoom}
          />
        </>
      )}
    </div>
  );
}
