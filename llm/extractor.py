# LLM calls for entity/relationship extraction and graph enrichment during ingestion
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class GraphEnricher:
    """Enriches graph nodes with LLM-generated business descriptions and summaries."""

    def __init__(self):
        import anthropic
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self._cache: dict[str, str] = {}

    def generate_business_description(
        self,
        table: str,
        column: str,
        data_type: str,
        sample_values: list,
    ) -> str:
        key = f"{table}.{column}"
        if key in self._cache:
            return self._cache[key]

        resp = self._client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=60,
            system=(
                "You are a database documentation expert. "
                "Write exactly one concise sentence (max 20 words) describing "
                "the business meaning of this database column."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Table: {table}, Column: {column}, "
                    f"Type: {data_type}, Sample values: {sample_values}"
                ),
            }],
        )
        result = resp.content[0].text.strip()
        self._cache[key] = result
        return result

    def synthesize_semantic_unit_summary(
        self,
        theme: str,
        entity_texts: list[str],
    ) -> str:
        sample = entity_texts[:10]
        bullets = "\n".join(f"- {t}" for t in sample)

        resp = self._client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=120,
            system=(
                "You are a data analyst. Write a 2-sentence summary of this group "
                "of database records. Focus on business meaning, not technical details."
            ),
            messages=[{
                "role": "user",
                "content": f"Theme: {theme}\nRecords:\n{bullets}",
            }],
        )
        return resp.content[0].text.strip()

    def generate_insight(self, insight_type: str, sql_result: str) -> str:
        resp = self._client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=80,
            system=(
                "Convert this database query result into one clear business insight "
                "sentence. Be specific with numbers."
            ),
            messages=[{
                "role": "user",
                "content": f"Query type: {insight_type}\nResult: {sql_result}",
            }],
        )
        return resp.content[0].text.strip()


if __name__ == "__main__":
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY == "your_key_here":
        console.print("[red]ANTHROPIC_API_KEY not set — skipping live test.[/red]")
        console.print("[dim]Copy .env.example to .env and add your key.[/dim]")
    else:
        enricher = GraphEnricher()

        desc = enricher.generate_business_description(
            "Products", "UnitPrice", "REAL", [18.0, 19.0, 10.0]
        )
        console.print(Panel(desc, title="generate_business_description: Products.UnitPrice"))

        summary = enricher.synthesize_semantic_unit_summary(
            theme="Products in Beverages category",
            entity_texts=[
                "Product: Chai, priced at $18.00 per unit. 39 units in stock. Active.",
                "Product: Chang, priced at $19.00 per unit. 17 units in stock. Active.",
                "Product: Guarana Fantastica, priced at $4.50 per unit. 20 units in stock. Discontinued.",
            ],
        )
        console.print(Panel(summary, title="synthesize_semantic_unit_summary: Beverages"))

        insight = enricher.generate_insight(
            insight_type="top_customers_by_revenue",
            sql_result="Ernst Handel $2,000 | Rattlesnake Canyon $1,800 | QUICK-Stop $1,600",
        )
        console.print(Panel(insight, title="generate_insight: top_customers_by_revenue"))
