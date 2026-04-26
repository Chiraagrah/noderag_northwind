export function transformGraphResponse(apiData) {
  return {
    nodes: apiData.nodes.map(n => ({ ...n, id: n.node_id })),
    links: apiData.edges.map(e => ({
      source:   e.source,
      target:   e.target,
      relation: e.relation,
      weight:   e.weight ?? 1,
    })),
    nodeCounts: apiData.node_counts,
    edgeCounts: apiData.edge_counts,
  };
}
