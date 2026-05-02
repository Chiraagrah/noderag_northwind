# End-to-end query pipeline: question -> retrieval -> LLM -> structured answer
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


class QueryPipeline:
    """Loads the pre-built graph + index and answers natural-language questions."""

    def __init__(
        self,
        graph_path: str = "data/northwind_graph.json",
        index_path: str = "data/northwind_index",
    ):
        root = Path(__file__).parent.parent
        self.graph_path = str(root / graph_path)
        self.index_path = str(root / index_path)

        self._retriever = None
        self._answerer  = None

    # ── loading ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        import networkx as nx
        from graph.embedder import NodeEmbedder
        from graph.indexer import NodeIndex
        from graph.node_types import node_from_dict
        from llm.answerer import NodeRAGAnswerer
        from retrieval.kcore import KCoreRanker
        from retrieval.retriever import NodeRAGRetriever

        # graph
        console.print("[cyan]Loading graph...[/cyan]")
        with open(self.graph_path, encoding="utf-8") as f:
            raw = json.load(f)
        for n in raw["nodes"]:
            if "data" in n and isinstance(n["data"], dict):
                n["data"] = node_from_dict(n["data"])
        G = nx.node_link_graph(raw, directed=True, multigraph=True)
        console.print(
            f"  [green]OK[/green]  {G.number_of_nodes()} nodes, "
            f"{G.number_of_edges()} edges"
        )

        # index
        console.print("[cyan]Loading FAISS index...[/cyan]")
        index = NodeIndex()
        index.load(self.index_path)
        console.print(f"  [green]OK[/green]  {len(index.node_ids)} vectors")

        # build pipeline components
        embedder  = NodeEmbedder()
        kcore     = KCoreRanker()

        self._retriever = NodeRAGRetriever(G, index, embedder, kcore)
        self._answerer  = NodeRAGAnswerer()
        console.print("[green]Pipeline ready.[/green]")

    # ── query ─────────────────────────────────────────────────────────────────

    def ask(
        self,
        query: str,
        top_k: int | None = None,
        verbose: bool = False,
    ):
        from llm.answerer import AnswerResult

        if self._retriever is None or self._answerer is None:
            raise RuntimeError("Call load() before ask().")

        result = self._retriever.retrieve(query, top_k=top_k)

        if verbose:
            self._print_retrieval_stats(result)
            console.print(Panel(
                result.context_text,
                title="Context sent to LLM",
                border_style="dim",
            ))

        answer = self._answerer.answer(
            query=query,
            context=result.context_text,
            retrieval_path=result.retrieval_path,
        )
        return answer

    # ── interactive REPL ──────────────────────────────────────────────────────

    def interactive(self) -> None:
        from rich.prompt import Prompt

        console.print(Panel(
            "[bold]NodeRAG Interactive Mode[/bold]\n"
            "Ask questions about the Northwind database.\n"
            "Type [bold]exit[/bold] or [bold]quit[/bold] to stop.",
            border_style="cyan",
        ))

        last_follow_ups: list[str] = []

        while True:
            # surface follow-up suggestions from previous answer
            if last_follow_ups:
                console.print("\n[dim]Suggested follow-ups:[/dim]")
                for i, q in enumerate(last_follow_ups, 1):
                    console.print(f"  [dim]{i}. {q}[/dim]")

            try:
                query = Prompt.ask("\n[bold cyan]Question[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                break

            if query.strip().lower() in ("exit", "quit", ""):
                break

            try:
                answer = self.ask(query)
                self._answerer.format_answer_rich(answer)
                last_follow_ups = answer.suggested_follow_ups
            except Exception as exc:
                console.print(f"[red]Error: {exc}[/red]")

        console.print("[dim]Goodbye.[/dim]")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _print_retrieval_stats(self, result) -> None:
        seed_tbl = Table(title="Seed Nodes", show_lines=True)
        seed_tbl.add_column("node_id",   style="dim",   no_wrap=True)
        seed_tbl.add_column("node_type", style="cyan",  no_wrap=True)
        seed_tbl.add_column("score",     justify="right", style="green")
        for s in result.seed_nodes[:5]:
            seed_tbl.add_row(s["node_id"][:45], s["node_type"], f"{s['score']:.4f}")
        console.print(seed_tbl)

        ret_tbl = Table(title="Retrieved Nodes (GNN + K-core)", show_lines=True)
        ret_tbl.add_column("rank",       justify="right", style="dim")
        ret_tbl.add_column("node_type",  style="cyan",    no_wrap=True)
        ret_tbl.add_column("score",      justify="right", style="green")
        ret_tbl.add_column("text",       style="white")
        for i, r in enumerate(result.retrieved_nodes, 1):
            ret_tbl.add_row(str(i), r["node_type"], f"{r['score']:.4f}", r["text"][:65])
        console.print(ret_tbl)

        console.print(Panel(
            "\n".join(result.retrieval_path),
            title="Retrieval Path",
            border_style="dim",
        ))


if __name__ == "__main__":
    pipeline = QueryPipeline()
    pipeline.load()

    queries = [
        "Which UK suppliers provide products in the Beverages category?",
        "Who are the top customers by revenue and which countries are they from?",
    ]

    for query in queries:
        console.rule(f"[bold yellow]{query}[/bold yellow]")
        answer = pipeline.ask(query, verbose=True)
        pipeline._answerer.format_answer_rich(answer)
        console.print()
