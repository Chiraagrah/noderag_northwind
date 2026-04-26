const BASE = "/api";

export const api = {
  getGraph:    ()          => fetch(`${BASE}/graph/`).then(r => r.json()),
  getSubgraph: (id, d = 2) => fetch(`${BASE}/graph/subgraph?center_node_id=${encodeURIComponent(id)}&depth=${d}`).then(r => r.json()),
  getStats:    ()          => fetch(`${BASE}/graph/stats`).then(r => r.json()),
  getNode:     (id)        => fetch(`${BASE}/graph/node/${encodeURIComponent(id)}`).then(r => r.json()),
  ping:        ()          => fetch(`${BASE}/`).then(r => r.ok).catch(() => false),
  reload:      ()          => fetch(`${BASE}/graph/reload`, { method: "POST" }).then(r => r.json()),
};

/* Async generator for SSE over POST */
export async function* queryStream(question, top_k = 10) {
  const res = await fetch(`${BASE}/query/`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ question, top_k }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer    = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      const line = part.trim();
      if (line.startsWith("data: ")) {
        try { yield JSON.parse(line.slice(6)); } catch { /* skip malformed */ }
      }
    }
  }
}
