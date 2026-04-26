export const NODE_CONFIG = {
  text_chunk:         { color: "#7C8FA6", code: "N1", label: "Text Chunk"   },
  entity:             { color: "#3D9A6F", code: "N2", label: "Entity"       },
  semantic_unit:      { color: "#B07D3A", code: "N3", label: "Semantic Unit"},
  relationship:       { color: "#9B5A8A", code: "N4", label: "Relationship" },
  attribute:          { color: "#4A7FC1", code: "N5", label: "Attribute"    },
  high_level_insight: { color: "#A8892B", code: "N6", label: "Insight"      },
  community:          { color: "#6B5EA8", code: "N7", label: "Community"    },
};

export const getNodeColor = (node_type) =>
  NODE_CONFIG[node_type]?.color ?? "#4a5568";

export const getNodeRadius = (node_type, core_number = 0) => {
  const base = {
    community:          16,
    high_level_insight: 13,
    semantic_unit:      11,
    entity:             9,
    relationship:       8,
    text_chunk:         6,
    attribute:          5,
  };
  return (base[node_type] ?? 8) + Math.min(core_number ?? 0, 6) * 0.5;
};
