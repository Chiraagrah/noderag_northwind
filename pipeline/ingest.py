# End-to-end ingestion pipeline: DB -> heterograph -> embeddings -> FAISS index
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


class IngestionPipeline:
    def __init__(
        self,
        db_path: str | None = None,
        schema_path: str | None = None,
        graph_output: str = "data/northwind_graph.json",
        index_output: str = "data/northwind_index",
    ):
        root = Path(__file__).parent.parent
        self.db_path      = db_path      or str(root / config.DB_PATH)
        self.schema_path  = schema_path  or str(root / "data" / "northwind_schema.json")
        self.graph_output = str(root / graph_output)
        self.index_output = str(root / index_output)

    # ── public entry point ────────────────────────────────────────────────────

    def run(self, enrich_with_llm: bool = False) -> dict:
        console.print(Panel(
            f"[bold]NodeRAG Ingestion Pipeline[/bold]\n"
            f"DB:     {self.db_path}\n"
            f"Schema: {self.schema_path}\n"
            f"LLM enrichment: {'ON' if enrich_with_llm else 'OFF'}",
            border_style="cyan",
        ))
        t_total = time.time()
        summary: dict = {}

        # ── Step 1: load schema ───────────────────────────────────────────────
        self._step("1", "Load schema")
        with open(self.schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        n_tables   = len(schema.get("tables", {}))
        n_views    = len(schema.get("views", {}))
        n_triggers = len(schema.get("triggers", {}))
        console.print(
            f"  [green]OK[/green]  {n_tables} tables, {n_views} views, {n_triggers} triggers"
        )
        summary["schema"] = {"tables": n_tables, "views": n_views, "triggers": n_triggers}

        # ── Step 2: build heterograph ─────────────────────────────────────────
        self._step("2", "Build heterograph")
        from graph.heterograph import NorthwindHeterograph
        t0 = time.time()
        hg = NorthwindHeterograph(self.db_path, self.schema_path)
        G  = hg.build()
        stats = hg.stats()
        elapsed = time.time() - t0

        self._print_stats(stats)
        console.print(f"  Built in {elapsed:.1f}s")
        summary["graph"] = stats

        # ── Step 3 (optional): LLM enrichment ────────────────────────────────
        if enrich_with_llm:
            self._step("3", "LLM enrichment")
            enriched = self._enrich(G)
            summary["enrichment"] = enriched
        else:
            console.print("[dim]  Step 3 skipped (pass --enrich to enable)[/dim]")

        # ── Step 4: embed nodes ───────────────────────────────────────────────
        self._step("4", "Embed nodes")
        from graph.embedder import NodeEmbedder
        t0 = time.time()
        embedder   = NodeEmbedder()
        embeddings = embedder.embed_graph(G)
        elapsed    = time.time() - t0
        dim = next(iter(embeddings.values())).shape[0] if embeddings else 0
        console.print(
            f"  [green]OK[/green]  {len(embeddings)} nodes embedded  "
            f"| dim={dim} | {elapsed:.1f}s"
        )
        summary["embeddings"] = {"count": len(embeddings), "dim": dim, "seconds": round(elapsed, 1)}

        # ── Step 4.5: GNN — train on graph topology, save embeddings separately ─
        # IMPORTANT: FAISS is built from sentence-transformer embeddings (base_embeddings)
        # so that query vectors (also sentence-transformer) remain in the same space.
        # GNN embeddings are saved separately and used for neighbourhood expansion
        # at retrieval time, replacing the PPR graph-walk step.
        self._step("4.5", "GNN topology training (GraphSAGE — saved separately)")
        import numpy as np
        from pathlib import Path
        from graph.gnn_embedder import GNNEmbedder
        t0  = time.time()
        gnn = GNNEmbedder(
            hidden_dim = config.GNN_HIDDEN_DIM,
            out_dim    = config.GNN_OUT_DIM,
            epochs     = config.GNN_EPOCHS,
            lr         = config.GNN_LR,
            neg_ratio  = config.GNN_NEG_RATIO,
        )
        gnn_embeddings = gnn.fit_transform(G, embeddings, verbose=True)
        elapsed = time.time() - t0

        # Save GNN embeddings to a separate .npz file (not the FAISS index)
        gnn_path = str(Path(self.index_output).parent / "northwind_gnn_embeddings.npz")
        np.savez_compressed(
            gnn_path,
            node_ids=np.array(list(gnn_embeddings.keys())),
            embeddings=np.stack(list(gnn_embeddings.values())).astype(np.float32),
        )
        console.print(
            f"  [green]OK[/green]  GNN embeddings saved to {gnn_path}  "
            f"| dim={config.GNN_OUT_DIM} | {elapsed:.1f}s"
        )
        summary["gnn"] = {"dim": config.GNN_OUT_DIM, "path": gnn_path, "seconds": round(elapsed, 1)}

        # ── Step 5: build and save FAISS index from sentence-transformer embeddings ─
        self._step("5", "Build & save FAISS index (sentence-transformer embeddings)")
        from graph.indexer import NodeIndex
        node_data = {
            nid: G.nodes[nid]["data"]
            for nid in embeddings          # <— base sentence-transformer embeddings
            if G.nodes[nid].get("data") is not None
        }
        idx = NodeIndex()
        idx.build(embeddings, node_data)   # <— NOT gnn_embeddings
        idx.save(self.index_output)
        console.print(
            f"  [green]OK[/green]  Saved to {self.index_output}.faiss + .json"
        )
        summary["index"] = {"path": self.index_output}

        # ── Step 6: save graph ────────────────────────────────────────────────
        self._step("6", "Save graph")
        hg.save(self.graph_output)
        console.print(f"  [green]OK[/green]  Saved to {self.graph_output}")
        summary["graph_path"] = self.graph_output

        total_elapsed = time.time() - t_total
        console.print(Panel(
            f"[bold green]Ingestion complete[/bold green] in {total_elapsed:.1f}s\n"
            f"Nodes: {stats['total_nodes']}  |  Edges: {stats['total_edges']}  |  "
            f"Vectors: {len(embeddings)}",
            border_style="green",
        ))
        return summary

    # ── LLM enrichment ────────────────────────────────────────────────────────

    def _enrich(self, G) -> dict:
        from graph.embedder import NodeEmbedder
        from llm.extractor import GraphEnricher

        enricher = GraphEnricher()
        embedder = NodeEmbedder()
        counts   = {"attributes": 0, "semantic_units": 0, "insights": 0}

        # N5 Attribute nodes
        console.print("  Enriching Attribute nodes (N5)...")
        for nid, data in G.nodes(data=True):
            nd = data.get("data")
            if nd is None or nd.node_type != "attribute":
                continue
            try:
                desc = enricher.generate_business_description(
                    nd.table_name, nd.column_name, nd.data_type,
                    []  # sample values not stored on node; pass empty
                )
                nd.business_description = desc
                nd.text = f"{nd.table_name}.{nd.column_name}: {desc}"
                G.nodes[nid]["data"] = nd
                counts["attributes"] += 1
            except Exception as exc:
                console.print(f"  [yellow]  skip {nid}: {exc}[/yellow]")

        # N3 SemanticUnit nodes
        console.print("  Enriching SemanticUnit nodes (N3)...")
        for nid, data in G.nodes(data=True):
            nd = data.get("data")
            if nd is None or nd.node_type != "semantic_unit":
                continue
            try:
                member_texts = []
                for mid in nd.member_entity_ids[:10]:
                    if mid in G:
                        md = G.nodes[mid].get("data")
                        if md:
                            member_texts.append(md.text)
                summary = enricher.synthesize_semantic_unit_summary(nd.theme, member_texts)
                nd.summary = summary
                nd.text    = summary
                G.nodes[nid]["data"] = nd
                counts["semantic_units"] += 1
            except Exception as exc:
                console.print(f"  [yellow]  skip {nid}: {exc}[/yellow]")

        # N6 HighLevelInsight nodes
        console.print("  Enriching HighLevelInsight nodes (N6)...")
        for nid, data in G.nodes(data=True):
            nd = data.get("data")
            if nd is None or nd.node_type != "high_level_insight":
                continue
            try:
                enriched_text = enricher.generate_insight(nd.insight_type, nd.text)
                nd.text = enriched_text
                G.nodes[nid]["data"] = nd
                counts["insights"] += 1
            except Exception as exc:
                console.print(f"  [yellow]  skip {nid}: {exc}[/yellow]")

        console.print(
            f"  [green]OK[/green]  Enriched: "
            f"{counts['attributes']} attributes, "
            f"{counts['semantic_units']} semantic units, "
            f"{counts['insights']} insights"
        )
        return counts

    # ── helpers ───────────────────────────────────────────────────────────────

    def _step(self, num: str, label: str) -> None:
        console.rule(f"[bold cyan]Step {num}: {label}[/bold cyan]")

    def _print_stats(self, stats: dict) -> None:
        tbl = Table(show_lines=True, title="Graph Stats")
        tbl.add_column("Node Type",  style="cyan")
        tbl.add_column("Count", justify="right", style="green")
        for ntype, cnt in sorted(stats["nodes_by_type"].items()):
            tbl.add_row(ntype, str(cnt))
        tbl.add_row("[bold]TOTAL nodes[/bold]",  f"[bold]{stats['total_nodes']}[/bold]")
        tbl.add_row("[bold]TOTAL edges[/bold]",  f"[bold]{stats['total_edges']}[/bold]")
        console.print(tbl)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run NodeRAG ingestion pipeline")
    parser.add_argument("--enrich", action="store_true", help="Enable LLM enrichment")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    pipeline = IngestionPipeline(db_path=args.db_path)
    pipeline.run(enrich_with_llm=args.enrich)
