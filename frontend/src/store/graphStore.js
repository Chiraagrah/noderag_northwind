import { create } from "zustand";
import { api } from "../utils/api";
import { transformGraphResponse } from "../utils/graphTransform";

const ALL_TYPES = new Set([
  "text_chunk", "entity", "semantic_unit",
  "relationship", "attribute", "high_level_insight", "community",
]);

const useGraphStore = create((set, get) => ({
  graphData:      null,
  d3Data:         null,
  isLoading:      false,
  error:          null,
  selectedNodeId: null,
  hoveredNodeId:  null,
  visibleTypes:   new Set(ALL_TYPES),
  highlightedIds: new Set(),
  dimmedIds:      new Set(),

  fetchGraph: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await api.getGraph();
      set({
        graphData: data,
        d3Data:    transformGraphResponse(data),
        isLoading: false,
      });
    } catch (err) {
      set({ error: err.message ?? "Failed to load graph", isLoading: false });
    }
  },

  selectNode: (id) => set({ selectedNodeId: id }),

  hoverNode: (id) => set({ hoveredNodeId: id }),

  toggleType: (type) => {
    const current = get().visibleTypes;
    if (current.has(type)) {
      if (current.size <= 1) return; // refuse if it would empty the set
      const next = new Set(current);
      next.delete(type);
      set({ visibleTypes: next });
    } else {
      set({ visibleTypes: new Set([...current, type]) });
    }
  },

  setHighlights: (ids) => {
    const allIds = get().d3Data?.nodes.map(n => n.id) ?? [];
    const dimmed = new Set(allIds.filter(id => !ids.has(id)));
    set({ highlightedIds: ids, dimmedIds: dimmed });
  },

  clearHighlights: () => set({ highlightedIds: new Set(), dimmedIds: new Set() }),

  setVisibleTypes: (types) => set({ visibleTypes: new Set(types) }),

  fetchSubgraph: async (nodeId) => {
    try {
      const data = await api.getSubgraph(nodeId);
      const incoming = transformGraphResponse(data);
      const existing = get().d3Data;
      if (!existing) {
        set({ d3Data: incoming });
        return;
      }
      const existingNodeIds = new Set(existing.nodes.map(n => n.id));
      const existingLinkKeys = new Set(
        existing.links.map(l => `${l.source}-${l.target}-${l.relation}`)
      );
      const newNodes = incoming.nodes.filter(n => !existingNodeIds.has(n.id));
      const newLinks = incoming.links.filter(
        l => !existingLinkKeys.has(`${l.source}-${l.target}-${l.relation}`)
      );
      set({
        d3Data: {
          ...existing,
          nodes: [...existing.nodes, ...newNodes],
          links: [...existing.links, ...newLinks],
        },
      });
    } catch (err) {
      console.error("fetchSubgraph failed:", err);
    }
  },
}));

export default useGraphStore;
