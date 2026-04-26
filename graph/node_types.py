# Pydantic dataclass definitions for all 7 NodeRAG heterogeneous node types
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    node_type: Literal["text_chunk"] = "text_chunk"
    node_id: str
    text: str
    source_table: str
    source_column: Optional[str] = None
    chunk_index: int = 0
    token_count: int = 0


class Entity(BaseModel):
    node_type: Literal["entity"] = "entity"
    node_id: str
    text: str                          # human-readable sentence built from row values
    table_name: str
    primary_key: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class SemanticUnit(BaseModel):
    node_type: Literal["semantic_unit"] = "semantic_unit"
    node_id: str
    text: str                          # = summary
    member_entity_ids: list[str] = Field(default_factory=list)
    theme: str
    summary: str


class Relationship(BaseModel):
    node_type: Literal["relationship"] = "relationship"
    node_id: str
    text: str                          # natural-language sentence describing the relationship
    from_entity_id: str
    to_entity_id: str
    relation_label: str
    from_table: str
    to_table: str


class Attribute(BaseModel):
    node_type: Literal["attribute"] = "attribute"
    node_id: str
    text: str                          # e.g. "Products.UnitPrice: The price per unit in USD."
    table_name: str
    column_name: str
    data_type: str
    business_description: Optional[str] = None


class HighLevelInsight(BaseModel):
    node_type: Literal["high_level_insight"] = "high_level_insight"
    node_id: str
    text: str                          # LLM-synthesized business rule or pattern
    source_entity_ids: list[str] = Field(default_factory=list)
    insight_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class Community(BaseModel):
    node_type: Literal["community"] = "community"
    node_id: str
    text: str                          # = community_summary
    member_node_ids: list[str] = Field(default_factory=list)
    core_number: int
    central_entity_id: Optional[str] = None
    community_summary: str


# Discriminated union over node_type — used for serialization / deserialization
AnyNode = Union[
    TextChunk,
    Entity,
    SemanticUnit,
    Relationship,
    Attribute,
    HighLevelInsight,
    Community,
]

_TYPE_MAP: dict[str, type] = {
    "text_chunk":       TextChunk,
    "entity":           Entity,
    "semantic_unit":    SemanticUnit,
    "relationship":     Relationship,
    "attribute":        Attribute,
    "high_level_insight": HighLevelInsight,
    "community":        Community,
}


def node_from_dict(d: dict) -> AnyNode:
    node_type = d.get("node_type")
    cls = _TYPE_MAP.get(node_type)
    if cls is None:
        raise ValueError(f"Unknown node_type: {node_type!r}")
    return cls(**d)


if __name__ == "__main__":
    import json
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    samples: list[AnyNode] = [
        TextChunk(
            node_id="tc_products_0",
            text=(
                "Table: Products\n"
                "Columns: ProductID (INTEGER), ProductName (TEXT), UnitPrice (REAL), UnitsInStock (INTEGER), Discontinued (INTEGER)\n"
                "Foreign Keys: SupplierID -> Suppliers, CategoryID -> Categories\n"
                "Row Count: 30\n"
                "Sample: ProductID=1, ProductName=Chai, UnitPrice=18.0, UnitsInStock=39"
            ),
            source_table="Products",
            chunk_index=0,
            token_count=62,
        ),
        Entity(
            node_id="entity_suppliers_1",
            text="Supplier: Exotic Liquids, based in London, UK. Contact: Charlotte Cooper. Phone: 171-555-2222.",
            table_name="Suppliers",
            primary_key="1",
            attributes={
                "SupplierID": 1,
                "CompanyName": "Exotic Liquids",
                "ContactName": "Charlotte Cooper",
                "Country": "UK",
                "City": "London",
                "Phone": "171-555-2222",
            },
        ),
        SemanticUnit(
            node_id="su_products_category_1",
            text="There are 3 products in the Beverages category. They include: Chai, Chang, Guarana Fantastica. Price range: $4.50 - $19.00.",
            member_entity_ids=["entity_products_1", "entity_products_2", "entity_products_24"],
            theme="Products in Beverages category",
            summary="There are 3 products in the Beverages category. They include: Chai, Chang, Guarana Fantastica. Price range: $4.50 - $19.00.",
        ),
        Relationship(
            node_id="rel_orders_10248_customer_vinet",
            text="Order #10248 was placed by Customer VINET (Vins et alcools Chevalier) on 2023-07-04, shipping to France.",
            from_entity_id="entity_orders_10248",
            to_entity_id="entity_customers_VINET",
            relation_label="PLACED_BY",
            from_table="Orders",
            to_table="Customers",
        ),
        Attribute(
            node_id="attr_products_unitprice",
            text="Products.UnitPrice: The price in USD charged per unit of product sold to customers.",
            table_name="Products",
            column_name="UnitPrice",
            data_type="REAL",
            business_description="The price in USD charged per unit of product sold to customers.",
        ),
        HighLevelInsight(
            node_id="insight_top_customers",
            text="The top 3 revenue-generating customers are Ernst Handel (Austria), Rattlesnake Canyon Grocery (USA), and QUICK-Stop (Germany), together accounting for over 40% of total order value.",
            source_entity_ids=["entity_customers_ERNSH", "entity_customers_RATTC", "entity_customers_QUICK"],
            insight_type="top_customers_by_revenue",
            confidence=0.95,
        ),
        Community(
            node_id="community_k3_0",
            text="12 nodes at k-core level 3, centered around entity_orders_10258. Dense cluster of UK suppliers, Beverage products, and high-value Austrian orders.",
            member_node_ids=[
                "entity_orders_10258", "entity_customers_ERNSH",
                "entity_employees_1", "entity_products_1",
                "rel_orders_10258_customer", "su_products_category_1",
            ],
            core_number=3,
            central_entity_id="entity_orders_10258",
            community_summary="12 nodes at k-core level 3, centered around entity_orders_10258. Dense cluster of UK suppliers, Beverage products, and high-value Austrian orders.",
        ),
    ]

    for node in samples:
        label = f"[bold cyan]{node.node_type.upper()}[/bold cyan]  node_id={node.node_id}"
        body = json.dumps(node.model_dump(), indent=2)
        console.print(Panel(body, title=label, border_style="dim"))

    # round-trip deserialization check
    console.print("\n[bold green]Round-trip node_from_dict check:[/bold green]")
    for node in samples:
        restored = node_from_dict(node.model_dump())
        assert restored == node, f"Round-trip failed for {node.node_id}"
        console.print(f"  [green]OK[/green]  {node.node_type:20s}  {node.node_id}")
