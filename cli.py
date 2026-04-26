# Click-based CLI entry point: ingest, ask, interactive, stats, and demo commands
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))

console = Console()

_HELP = """\
NodeRAG - Structural Intelligence over Relational Databases

Builds a heterogeneous knowledge graph from the Northwind SQLite database
and answers multi-hop questions using Shallow PPR + K-core retrieval
backed by the Anthropic Claude API.

Typical workflow:

  noderag ingest          # build graph + index (first time)
  noderag ask "..."       # ask a single question
  noderag interactive     # start a question-answering REPL
  noderag stats           # inspect the graph
  noderag demo            # run 5 showcase multi-hop queries
"""

_DEMO_QUERIES = [
    "Which suppliers from the UK supply products that were ordered by customers in Germany?",
    "What is the total revenue from orders handled by employees who report to the same manager as Janet Leverling?",
    "Which product categories have the highest average discount rate?",
    "Which customers have ordered products that are now discontinued?",
    "What is the shipping profile of our top 3 revenue-generating customers?",
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_pipeline():
    from pipeline.query import QueryPipeline
    p = QueryPipeline()
    p.load()
    return p


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group(help=_HELP)
def cli():
    pass


# ── noderag ingest ────────────────────────────────────────────────────────────

@cli.command()
@click.option("--db-path",       default=None,  help="Path to northwind.db (default from .env)")
@click.option("--enrich/--no-enrich", default=False,
              help="Enable LLM enrichment of attribute/semantic/insight nodes")
def ingest(db_path, enrich):
    """Build the heterogeneous graph, embed all nodes, and save the FAISS index."""
    from pipeline.ingest import IngestionPipeline
    pipeline = IngestionPipeline(db_path=db_path)
    pipeline.run(enrich_with_llm=enrich)


# ── noderag ask ───────────────────────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.option("--top-k",          default=None, type=int,
              help="Number of nodes to retrieve (default from .env)")
@click.option("--verbose/--quiet", default=False,
              help="Show retrieval details, scores, and context window")
def ask(query, top_k, verbose):
    """Ask a single natural-language question about the Northwind database."""
    pipeline = _load_pipeline()
    answer   = pipeline.ask(query, top_k=top_k, verbose=verbose)
    pipeline._answerer.format_answer_rich(answer)


# ── noderag interactive ───────────────────────────────────────────────────────

@cli.command()
def interactive():
    """Start an interactive question-answering REPL (type 'exit' to quit)."""
    pipeline = _load_pipeline()
    pipeline.interactive()


# ── noderag stats ─────────────────────────────────────────────────────────────

@cli.command()
def stats():
    """Load the saved graph and print node/edge counts broken down by type."""
    import json
    from pathlib import Path

    import networkx as nx
    from graph.node_types import node_from_dict

    root       = Path(__file__).parent
    graph_path = root / "data" / "northwind_graph.json"

    if not graph_path.exists():
        console.print("[red]Graph not found. Run 'noderag ingest' first.[/red]")
        raise SystemExit(1)

    console.print("[cyan]Loading graph...[/cyan]")
    with open(graph_path, encoding="utf-8") as f:
        raw = json.load(f)
    for n in raw["nodes"]:
        if "data" in n and isinstance(n["data"], dict):
            n["data"] = node_from_dict(n["data"])
    G = nx.node_link_graph(raw, directed=True, multigraph=True)

    from collections import defaultdict
    node_counts: dict[str, int] = defaultdict(int)
    for _, d in G.nodes(data=True):
        nd = d.get("data")
        if nd:
            node_counts[nd.node_type] += 1

    edge_counts: dict[str, int] = defaultdict(int)
    for _, _, d in G.edges(data=True):
        edge_counts[d.get("relation", "unknown")] += 1

    node_tbl = Table(title="Node Counts by Type", show_lines=True)
    node_tbl.add_column("Node Type", style="cyan")
    node_tbl.add_column("Code", style="dim")
    node_tbl.add_column("Count", justify="right", style="green")
    _codes = {
        "text_chunk": "N1", "entity": "N2", "semantic_unit": "N3",
        "relationship": "N4", "attribute": "N5",
        "high_level_insight": "N6", "community": "N7",
    }
    for ntype, cnt in sorted(node_counts.items()):
        node_tbl.add_row(ntype, _codes.get(ntype, ""), str(cnt))
    node_tbl.add_row(
        "[bold]TOTAL[/bold]", "",
        f"[bold]{G.number_of_nodes()}[/bold]"
    )
    console.print(node_tbl)

    edge_tbl = Table(title="Edge Counts by Relation", show_lines=True)
    edge_tbl.add_column("Relation", style="yellow")
    edge_tbl.add_column("Count", justify="right", style="green")
    for rel, cnt in sorted(edge_counts.items()):
        edge_tbl.add_row(rel, str(cnt))
    edge_tbl.add_row("[bold]TOTAL[/bold]", f"[bold]{G.number_of_edges()}[/bold]")
    console.print(edge_tbl)


# ── noderag demo ──────────────────────────────────────────────────────────────

@cli.command()
def demo():
    """Run 5 pre-set multi-hop queries that showcase NodeRAG's reasoning capability."""
    console.print(Panel(
        "[bold]NodeRAG Demo — 5 Multi-Hop Queries[/bold]\n"
        "Each query requires at least 2 relationship hops to answer correctly.\n"
        "Standard RAG over flat text would miss these cross-table connections.",
        border_style="cyan",
    ))

    pipeline = _load_pipeline()

    for i, query in enumerate(_DEMO_QUERIES, 1):
        console.print(Panel(
            f"[bold yellow]Query {i} of {len(_DEMO_QUERIES)}[/bold yellow]\n{query}",
            border_style="yellow",
        ))
        try:
            answer = pipeline.ask(query)
            pipeline._answerer.format_answer_rich(answer)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

        if i < len(_DEMO_QUERIES):
            click.pause(info="\nPress any key for the next query...")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
