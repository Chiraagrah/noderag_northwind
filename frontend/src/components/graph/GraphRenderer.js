import * as d3 from "d3";
import { getNodeColor, getNodeRadius } from "../../utils/nodeColors";

export class GraphRenderer {
  constructor(svgEl, containerEl) {
    this.svg       = d3.select(svgEl);
    this.container = d3.select(containerEl);
    this.sim       = null;
    this.zoom      = null;
    this._driftTimers = [];
    this._nodeSel  = null;
    this._linkSel  = null;
    this._width    = 0;
    this._height   = 0;
  }

  init(d3Data, { onNodeClick, onNodeHover, onNodeLeave }) {
    const rect   = this.svg.node().getBoundingClientRect();
    this._width  = rect.width  || 800;
    this._height = rect.height || 600;
    const { _width: W, _height: H } = this;

    // deep-copy so D3 can mutate positions without touching the store
    const nodes = d3Data.nodes.map(d => ({ ...d }));
    const links = d3Data.links.map(d => ({ ...d }));

    // ── zoom / pan ────────────────────────────────────────────────────────────
    this.zoom = d3.zoom()
      .scaleExtent([0.15, 5])
      .on("zoom", (event) => {
        this.container.attr("transform", event.transform);
      });
    this.svg.call(this.zoom);

    // click on svg background → deselect
    this.svg.on("click.bg", () => onNodeClick(null));

    // ── edges ─────────────────────────────────────────────────────────────────
    const edgeG = this.container.append("g").attr("class", "edges");
    this._linkSel = edgeG.selectAll("line")
      .data(links)
      .join("line")
        .attr("stroke", "var(--border)")
        .attr("stroke-width", 1)
        .attr("stroke-opacity", 0.5)
        .attr("marker-end", "url(#arrow)");

    // ── nodes ─────────────────────────────────────────────────────────────────
    const nodeG = this.container.append("g").attr("class", "nodes");
    this._nodeSel = nodeG.selectAll("g.node")
      .data(nodes, d => d.id)
      .join("g")
        .attr("class", "node")
        .call(
          d3.drag()
            .on("start", (event, d) => {
              if (!event.active) this.sim.alphaTarget(0.3).restart();
              d.fx = d.x;
              d.fy = d.y;
            })
            .on("drag", (event, d) => {
              d.fx = event.x;
              d.fy = event.y;
            })
            .on("end", (event, d) => {
              if (!event.active) this.sim.alphaTarget(0);
              d.fx = null;
              d.fy = null;
            })
        );

    // circles
    this._nodeSel.append("circle")
      .attr("r",             d => getNodeRadius(d.node_type, d.core_number))
      .attr("fill",          d => getNodeColor(d.node_type))
      .attr("fill-opacity",  0.15)
      .attr("stroke",        d => getNodeColor(d.node_type))
      .attr("stroke-width",  1.5)
      .style("cursor",       "pointer")
      .on("click.node",      (event, d) => { event.stopPropagation(); onNodeClick(d.id); })
      .on("mouseenter",      (event, d) => onNodeHover(d.id))
      .on("mouseleave",      ()         => onNodeLeave());

    // labels
    this._nodeSel.append("text")
      .text(d => (d.label || d.id).slice(0, 22))
      .attr("dy",           d => getNodeRadius(d.node_type, d.core_number) + 12)
      .attr("text-anchor",  "middle")
      .attr("font-family",  "JetBrains Mono")
      .attr("font-size",    9)
      .attr("fill",         "var(--muted)")
      .style("pointer-events", "none");

    // ── force simulation ──────────────────────────────────────────────────────
    this.sim = d3.forceSimulation(nodes)
      .alphaDecay(0.028)
      .velocityDecay(0.45)
      .force("link",    d3.forceLink(links).id(d => d.id)
                          .distance(d => 55 + (1 - (d.weight ?? 1)) * 40))
      .force("charge",  d3.forceManyBody().strength(-130))
      .force("center",  d3.forceCenter(W / 2, H / 2))
      .force("collide", d3.forceCollide()
                          .radius(d => getNodeRadius(d.node_type, d.core_number) + 3))
      .on("tick", () => {
        this._linkSel
          .attr("x1", d => d.source.x)
          .attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x)
          .attr("y2", d => d.target.y);
        this._nodeSel.attr("transform", d => `translate(${d.x ?? 0},${d.y ?? 0})`);
      })
      .on("end", () => this._startDrift(nodes));
  }

  // ── idle drift ───────────────────────────────────────────────────────────────
  _startDrift(nodes) {
    const nodeEls = this._nodeSel ? this._nodeSel.nodes() : [];
    const timer = d3.timer((elapsed) => {
      nodes.forEach((d, i) => {
        if (d.fx != null) return;                        // skip pinned nodes
        if (!nodeEls[i])  return;
        const ox = Math.sin(elapsed / 8000 + i * 0.7) * 2.5;
        const oy = Math.cos(elapsed / 9000 + i * 1.1) * 2.5;
        d3.select(nodeEls[i])
          .attr("transform", `translate(${(d.x ?? 0) + ox},${(d.y ?? 0) + oy})`);
      });
    });
    this._driftTimers.push(timer);
  }

  // ── highlight update ─────────────────────────────────────────────────────────
  update(highlightedIds, dimmedIds) {
    if (!this._nodeSel || !this._linkSel) return;

    if (highlightedIds.size > 0) {
      // stop drift while highlighting
      this._driftTimers.forEach(t => t.stop());
      this._driftTimers = [];

      this._nodeSel.select("circle")
        .transition().duration(200)
        .attr("fill-opacity",   d => dimmedIds.has(d.id) ? 0.06 : 0.25)
        .attr("stroke-opacity", d => dimmedIds.has(d.id) ? 0.2  : 1.0)
        .attr("stroke-width",   d => dimmedIds.has(d.id) ? 1.5  : 2.5);

      this._nodeSel.select("text")
        .transition().duration(200)
        .attr("opacity", d => dimmedIds.has(d.id) ? 0.15 : 1.0);

      this._linkSel
        .transition().duration(200)
        .attr("stroke-opacity", d => {
          const s = typeof d.source === "object" ? d.source.id : d.source;
          const t = typeof d.target === "object" ? d.target.id : d.target;
          return (highlightedIds.has(s) || highlightedIds.has(t)) ? 0.8 : 0.1;
        })
        .attr("stroke-width", d => {
          const s = typeof d.source === "object" ? d.source.id : d.source;
          const t = typeof d.target === "object" ? d.target.id : d.target;
          return (highlightedIds.has(s) || highlightedIds.has(t)) ? 1.5 : 1;
        });
    } else {
      // restore defaults
      this._nodeSel.select("circle")
        .transition().duration(200)
        .attr("fill-opacity",   0.15)
        .attr("stroke-opacity", 1.0)
        .attr("stroke-width",   1.5);

      this._nodeSel.select("text")
        .transition().duration(200)
        .attr("opacity", 1.0);

      this._linkSel
        .transition().duration(200)
        .attr("stroke-opacity", 0.5)
        .attr("stroke-width",   1);
    }
  }

  // ── type filter ───────────────────────────────────────────────────────────────
  filter(visibleTypes) {
    if (!this._nodeSel || !this._linkSel) return;

    this._nodeSel
      .transition().duration(150)
      .attr("opacity", d => visibleTypes.has(d.node_type) ? 1 : 0)
      .style("pointer-events", d => visibleTypes.has(d.node_type) ? "auto" : "none");

    this._linkSel
      .transition().duration(150)
      .attr("stroke-opacity", d => {
        const sType = typeof d.source === "object" ? d.source.node_type : null;
        const tType = typeof d.target === "object" ? d.target.node_type : null;
        if (sType && !visibleTypes.has(sType)) return 0;
        if (tType && !visibleTypes.has(tType)) return 0;
        return 0.5;
      });
  }

  // ── zoom to node ──────────────────────────────────────────────────────────────
  zoomToNode(nodeId, width, height) {
    if (!this.sim || !this.zoom) return;
    const node = this.sim.nodes().find(n => n.id === nodeId);
    if (!node) return;
    const scale = 2;
    const tx    = width  / 2 - scale * (node.x ?? 0);
    const ty    = height / 2 - scale * (node.y ?? 0);
    this.svg.transition().duration(600)
      .call(this.zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  }

  zoomBy(factor) {
    if (!this.zoom) return;
    this.svg.transition().duration(250).call(this.zoom.scaleBy, factor);
  }

  resetZoom() {
    if (!this.zoom) return;
    this.svg.transition().duration(400).call(this.zoom.transform, d3.zoomIdentity);
  }

  // ── cleanup ───────────────────────────────────────────────────────────────────
  destroy() {
    if (this.sim) { this.sim.stop(); this.sim = null; }
    this._driftTimers.forEach(t => t.stop());
    this._driftTimers = [];
    this.container.selectAll("*").remove();
    this.svg.on(".zoom",  null);
    this.svg.on("click.bg", null);
  }
}
