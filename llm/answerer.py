# LLM calls for final answer generation from retrieved graph context
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

# ── system prompt (exact wording from the guide) ──────────────────────────────
_SYSTEM_PROMPT = """\
You are NodeRAG, an intelligent database assistant that reasons over a \
knowledge graph of the Northwind business database. You have been provided \
with structured context retrieved from a heterogeneous graph containing \
entities, relationships, business insights, and schema information.

Answer the user's question by:
1. Identifying the relevant entities and relationships in the context
2. Following the relationship chains (multi-hop reasoning)
3. Synthesizing a direct, accurate answer
4. Citing the specific pieces of context you relied on

Always reason step by step before giving your final answer.
If the context doesn't contain enough information, say so clearly.\
"""


class AnswerResult(BaseModel):
    answer:               str
    reasoning_steps:      list[str]
    cited_nodes:          list[str]
    confidence:           Literal["high", "medium", "low"]
    suggested_follow_ups: list[str]


def _safe(text: str) -> str:
    """Replace characters that can't be encoded in cp1252 (Windows legacy terminal)."""
    replacements = {"→": "->", "←": "<-", "✓": "OK", "✗": "X", "·": "-", "…": "..."}
    for ch, rep in replacements.items():
        text = text.replace(ch, rep)
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _extract_json(raw: str) -> str:
    """Strip markdown code fences and return the inner JSON string."""
    raw = raw.strip()
    # remove ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        return match.group(1).strip()
    # if it starts with { assume it's already bare JSON
    if raw.startswith("{"):
        return raw
    return raw


class NodeRAGAnswerer:
    def __init__(self):
        import anthropic
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def answer(
        self,
        query: str,
        context: str,
        retrieval_path: list[str],
    ) -> AnswerResult:
        path_block = "\n".join(retrieval_path)

        user_message = (
            "## Retrieval Path (how I found this context)\n"
            f"{path_block}\n\n"
            "## Retrieved Context\n"
            f"{context}\n\n"
            "## Question\n"
            f"{query}\n\n"
            "Respond in this exact JSON format:\n"
            "{\n"
            '  "answer": "...",\n'
            '  "reasoning_steps": ["step 1", "step 2", ...],\n'
            '  "cited_nodes": ["node_id_1", "node_id_2", ...],\n'
            '  "confidence": "high|medium|low",\n'
            '  "suggested_follow_ups": ["...", "...", "..."]\n'
            "}"
        )

        resp = self._client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=1024,
            # cache the static system prompt across calls
            system=[{
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": [
                    # cache the (potentially large) context block
                    {
                        "type": "text",
                        "text": user_message,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }],
        )

        raw = resp.content[0].text.strip()

        try:
            data = json.loads(_extract_json(raw))
            # normalise confidence in case the LLM adds extra text
            conf = str(data.get("confidence", "low")).lower()
            if conf not in ("high", "medium", "low"):
                conf = "low"
            data["confidence"] = conf
            return AnswerResult(**data)
        except Exception:
            return AnswerResult(
                answer=raw,
                reasoning_steps=["(JSON parse failed — raw LLM response returned as answer)"],
                cited_nodes=[],
                confidence="low",
                suggested_follow_ups=[],
            )

    def format_answer_rich(self, result: AnswerResult) -> None:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        console = Console()

        # answer panel
        console.print(Panel(_safe(result.answer), title="Answer", border_style="green"))

        # reasoning steps
        steps_text = "\n".join(f"{i}. {_safe(s)}" for i, s in enumerate(result.reasoning_steps, 1))
        console.print(Panel(steps_text or "(none)", title="Reasoning Steps", border_style="blue"))

        # confidence badge
        colour = {"high": "green", "medium": "yellow", "low": "red"}.get(result.confidence, "white")
        conf_text = Text(f"  Confidence: {result.confidence.upper()}  ", style=f"bold {colour}")
        console.print(conf_text)

        # cited nodes
        if result.cited_nodes:
            cited_tbl = Table(title="Cited Nodes", show_lines=True)
            cited_tbl.add_column("node_id", style="cyan")
            for nid in result.cited_nodes:
                cited_tbl.add_row(nid)
            console.print(cited_tbl)

        # follow-ups
        if result.suggested_follow_ups:
            fu_text = "\n".join(f"- {_safe(q)}" for q in result.suggested_follow_ups)
            console.print(Panel(fu_text, title="Suggested Follow-ups", border_style="dim"))


# ── __main__ ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from rich.console import Console

    console = Console()

    if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY == "your_key_here":
        console.print("[red]ANTHROPIC_API_KEY not set — skipping live test.[/red]")
        console.print("[dim]Copy .env.example to .env and add your key.[/dim]")
        raise SystemExit(0)

    mock_context = """\
## Business Insights
- [insight_top_categories_by_revenue] The top 3 revenue-generating product categories are: \
Confections ($3,424), Condiments ($2,891), Beverages ($2,150).

## Entities
- [entity_Categories_1] Category: Beverages. Soft drinks, coffees, teas, beers, and ales
- [entity_Categories_3] Category: Confections. Desserts, candies, and sweet breads
- [entity_Categories_2] Category: Condiments. Sweet and savory sauces, relishes, spreads.

## Semantic Groups
- [su_Products_category_1] There are 3 products in the Beverages category. \
They include: Chai, Chang, Guarana Fantastica. Price range: $4.50 - $19.00.
- [su_Products_category_3] There are 7 products in the Confections category. \
They include: Pavlova, Sir Rodney's Marmalade, NuNuCa Nuss-Nougat-Creme. \
Price range: $9.20 - $81.00.
"""

    query = "What are the top selling product categories?"
    retrieval_path = [
        "Retrieved via: insight_top_categories_by_revenue --[INSIGHT_ABOUT]--> entity_Categories_1",
        "Retrieved via: su_Products_category_1 --[CONTAINS_ENTITY]--> entity_Products_1",
    ]

    console.print(f"[bold cyan]Query:[/bold cyan] {query}\n")
    answerer = NodeRAGAnswerer()
    result   = answerer.answer(query, mock_context, retrieval_path)
    answerer.format_answer_rich(result)
