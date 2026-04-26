import { useRef, useEffect, useCallback } from "react";
import { GraphRenderer } from "../components/graph/GraphRenderer";

export function useD3Graph(svgRef, containerRef, d3Data, options) {
  const rendererRef = useRef(null);

  const { onNodeClick, onNodeHover, onNodeLeave, highlightedIds, dimmedIds, visibleTypes } = options;

  // rebuild renderer when d3Data changes
  useEffect(() => {
    if (rendererRef.current) {
      rendererRef.current.destroy();
      rendererRef.current = null;
    }
    if (!d3Data || !svgRef.current || !containerRef.current) return;

    const renderer = new GraphRenderer(svgRef.current, containerRef.current);
    renderer.init(d3Data, { onNodeClick, onNodeHover, onNodeLeave });
    rendererRef.current = renderer;

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d3Data]);

  // update highlights
  useEffect(() => {
    if (rendererRef.current) {
      rendererRef.current.update(highlightedIds, dimmedIds);
    }
  }, [highlightedIds, dimmedIds]);

  // update visible type filter — use stable string key to avoid object identity issues
  const visibleTypesKey = visibleTypes ? [...visibleTypes].sort().join(",") : "";
  useEffect(() => {
    if (rendererRef.current && visibleTypes) {
      rendererRef.current.filter(visibleTypes);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleTypesKey]);

  // cleanup on unmount
  useEffect(() => {
    return () => {
      if (rendererRef.current) {
        rendererRef.current.destroy();
        rendererRef.current = null;
      }
    };
  }, []);

  const zoomToNode = useCallback((id) => {
    if (!rendererRef.current || !svgRef.current) return;
    const { width, height } = svgRef.current.getBoundingClientRect();
    rendererRef.current.zoomToNode(id, width, height);
  }, [svgRef]);

  const resetZoom = useCallback(() => {
    rendererRef.current?.resetZoom();
  }, []);

  const zoomBy = useCallback((factor) => {
    rendererRef.current?.zoomBy(factor);
  }, []);

  return { zoomToNode, resetZoom, zoomBy };
}
