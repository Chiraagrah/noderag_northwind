# NetworkX heterograph builder: constructs the 7-type heterogeneous graph from Northwind DB
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx
from rich.console import Console
from rich.table import Table

# allow running as __main__ from any cwd
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.node_types import (
    AnyNode, Attribute, Community, Entity, HighLevelInsight,
    Relationship, SemanticUnit, TextChunk, node_from_dict,
)
import config

console = Console()

# ── business-meaning lookup for ~20 important Northwind columns ────────────────
_BDESCS: dict[tuple[str, str], str] = {
    ("Products",     "ProductID"):    "Unique identifier for each product in the catalog.",
    ("Products",     "ProductName"):  "The commercial name of the product as sold to customers.",
    ("Products",     "UnitPrice"):    "The price in USD charged per unit of product sold to customers.",
    ("Products",     "UnitsInStock"): "Current inventory count of units available for sale.",
    ("Products",     "Discontinued"): "Flag indicating whether this product is no longer sold (1=discontinued).",
    ("Orders",       "OrderID"):      "Unique identifier for each customer order.",
    ("Orders",       "OrderDate"):    "The date on which the order was placed by the customer.",
    ("Orders",       "ShipCountry"):  "The destination country to which the order is shipped.",
    ("Orders",       "Freight"):      "The shipping cost in USD charged for delivering the order.",
    ("OrderDetails", "Quantity"):     "Number of units of the product included in this order line.",
    ("OrderDetails", "UnitPrice"):    "The price per unit at the time the order was placed.",
    ("OrderDetails", "Discount"):     "Fractional discount applied to this line (0.0=none, 0.25=25% off).",
    ("Customers",    "CustomerID"):   "Unique five-character code identifying the customer.",
    ("Customers",    "CompanyName"):  "The official registered company name of the customer.",
    ("Customers",    "Country"):      "The country where the customer's business is located.",
    ("Employees",    "Title"):        "The employee's job title within the sales organization.",
    ("Employees",    "ReportsTo"):    "The EmployeeID of this employee's direct manager.",
    ("Suppliers",    "CompanyName"):  "The name of the company that supplies products to Northwind.",
    ("Suppliers",    "Country"):      "The country where the supplier's headquarters is located.",
    ("Categories",   "CategoryName"): "The product category grouping (e.g., Beverages, Seafood).",
    ("Categories",   "Description"):  "A brief description of the types of products in this category.",
}

_PK_COL: dict[str, str] = {
    "Customers":  "CustomerID",
    "Suppliers":  "SupplierID",
    "Categories": "CategoryID",
    "Products":   "ProductID",
    "Employees":  "EmployeeID",
    "Orders":     "OrderID",
}


def _pk(table: str, row: dict) -> str:
    if table == "OrderDetails":
        return f"{row['OrderID']}_{row['ProductID']}"
    return str(row[_PK_COL[table]])


def _entity_text(table: str, row: dict) -> str:
    if table == "Customers":
        return (
            f"Customer: {row.get('CompanyName','?')}, located in "
            f"{row.get('City','?')}, {row.get('Country','?')}. "
            f"Contact: {row.get('ContactName','?')}. Phone: {row.get('Phone','?')}."
        )
    if table == "Suppliers":
        return (
            f"Supplier: {row.get('CompanyName','?')}, based in "
            f"{row.get('City','?')}, {row.get('Country','?')}. "
            f"Contact: {row.get('ContactName','?')}. Phone: {row.get('Phone','?')}."
        )
    if table == "Categories":
        return f"Category: {row.get('CategoryName','?')}. {row.get('Description','')}"
    if table == "Products":
        disc = "Discontinued." if row.get("Discontinued") else "Active."
        return (
            f"Product: {row.get('ProductName','?')}, priced at "
            f"${row.get('UnitPrice', 0):.2f} per unit. "
            f"{row.get('UnitsInStock', 0)} units in stock. {disc}"
        )
    if table == "Employees":
        return (
            f"Employee: {row.get('FirstName','?')} {row.get('LastName','?')}, "
            f"{row.get('Title','?')}, based in {row.get('City','?')}, {row.get('Country','?')}."
        )
    if table == "Orders":
        return (
            f"Order #{row.get('OrderID','?')} placed by customer {row.get('CustomerID','?')} "
            f"on {row.get('OrderDate','?')}, shipping to {row.get('ShipCountry','?')}. "
            f"Freight: ${row.get('Freight', 0):.2f}."
        )
    if table == "OrderDetails":
        disc_pct = int((row.get("Discount") or 0) * 100)
        return (
            f"Order #{row.get('OrderID','?')} includes {row.get('Quantity','?')} units of "
            f"product #{row.get('ProductID','?')} at ${row.get('UnitPrice', 0):.2f} each "
            f"({disc_pct}% discount)."
        )
    return str(row)


class NorthwindHeterograph:
    def __init__(self, db_path: str, schema_path: str):
        self.db_path = db_path
        self.schema_path = schema_path
        self.G: nx.MultiDiGraph = nx.MultiDiGraph()
        with open(schema_path, encoding="utf-8") as f:
            self.schema = json.load(f)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _add_node(self, node: AnyNode) -> None:
        self.G.add_node(node.node_id, data=node)

    def _add_edge(self, src: str, dst: str, relation: str, weight: float = 1.0) -> None:
        # only add if both endpoints already exist as nodes
        if src in self.G and dst in self.G:
            self.G.add_edge(src, dst, relation=relation, weight=weight)

    # ── public API ────────────────────────────────────────────────────────────

    def build(self) -> nx.MultiDiGraph:
        steps = [
            ("N5  Attribute nodes",       self._build_attribute_nodes),
            ("N2  Entity nodes",          self._build_entity_nodes),
            ("N4  Relationship nodes",    self._build_relationship_nodes),
            ("N1  Text chunk nodes",      self._build_text_chunk_nodes),
            ("N3  Semantic unit nodes",   self._build_semantic_unit_nodes),
            ("N6  High-level insights",   self._build_high_level_insight_nodes),
            ("N7  Community nodes",       self._build_community_nodes),
        ]
        for label, fn in steps:
            console.print(f"[cyan]Building {label}...[/cyan]")
            fn()
            s = self.stats()
            console.print(
                f"  [dim]>> {s['total_nodes']} nodes, {s['total_edges']} edges so far[/dim]"
            )
        return self.G

    def save(self, path: str) -> None:
        data = nx.node_link_data(self.G)
        for n in data["nodes"]:
            if "data" in n and hasattr(n["data"], "model_dump"):
                n["data"] = n["data"].model_dump()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def load(self, path: str) -> None:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for n in data["nodes"]:
            if "data" in n and isinstance(n["data"], dict):
                n["data"] = node_from_dict(n["data"])
        self.G = nx.node_link_graph(data, directed=True, multigraph=True)

    def stats(self) -> dict:
        node_counts: dict[str, int] = defaultdict(int)
        for _, d in self.G.nodes(data=True):
            nd = d.get("data")
            if nd:
                node_counts[nd.node_type] += 1

        edge_counts: dict[str, int] = defaultdict(int)
        for _, _, d in self.G.edges(data=True):
            edge_counts[d.get("relation", "unknown")] += 1

        return {
            "total_nodes":       self.G.number_of_nodes(),
            "total_edges":       self.G.number_of_edges(),
            "nodes_by_type":     dict(node_counts),
            "edges_by_relation": dict(edge_counts),
        }

    # ── N5: Attribute nodes ───────────────────────────────────────────────────

    def _build_attribute_nodes(self) -> None:
        for table, info in self.schema["tables"].items():
            for col in info["columns"]:
                desc = _BDESCS.get(
                    (table, col["name"]),
                    f"Column {col['name']} of type {col['type']} in table {table}.",
                )
                node_id = f"attr_{table}_{col['name']}"
                self._add_node(Attribute(
                    node_id=node_id,
                    text=f"{table}.{col['name']}: {desc}",
                    table_name=table,
                    column_name=col["name"],
                    data_type=col["type"],
                    business_description=desc,
                ))

    # ── N2: Entity nodes ──────────────────────────────────────────────────────

    def _build_entity_nodes(self) -> None:
        with self._conn() as conn:
            for table in self.schema["tables"]:
                cur = conn.execute(f"SELECT * FROM '{table}' LIMIT 500")
                for row in cur.fetchall():
                    row = dict(row)
                    pk_val = _pk(table, row)
                    self._add_node(Entity(
                        node_id=f"entity_{table}_{pk_val}",
                        text=_entity_text(table, row),
                        table_name=table,
                        primary_key=pk_val,
                        attributes=row,
                    ))

    # ── N4: Relationship nodes ────────────────────────────────────────────────

    def _build_relationship_nodes(self) -> None:
        with self._conn() as conn:
            self._rel_orders_customers(conn)
            self._rel_orders_employees(conn)
            self._rel_products_suppliers(conn)
            self._rel_products_categories(conn)
            self._rel_orderdetails_orders(conn)
            self._rel_employees_manager(conn)

    def _rel_orders_customers(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT o.OrderID, o.OrderDate, o.ShipCountry,
                   c.CustomerID, c.CompanyName
            FROM Orders o
            LEFT JOIN Customers c ON o.CustomerID = c.CustomerID
        """).fetchall()
        for r in (dict(r) for r in rows):
            nid = f"rel_orders_{r['OrderID']}_customer_{r['CustomerID']}"
            self._add_node(Relationship(
                node_id=nid,
                text=(
                    f"Order #{r['OrderID']} was placed by Customer {r['CustomerID']} "
                    f"({r['CompanyName'] or 'Unknown'}) on {r['OrderDate']}, "
                    f"shipping to {r['ShipCountry']}."
                ),
                from_entity_id=f"entity_Orders_{r['OrderID']}",
                to_entity_id=f"entity_Customers_{r['CustomerID']}",
                relation_label="PLACED_BY",
                from_table="Orders",
                to_table="Customers",
            ))
            self._add_edge(nid, f"entity_Orders_{r['OrderID']}",       "HAS_SOURCE")
            self._add_edge(nid, f"entity_Customers_{r['CustomerID']}", "HAS_TARGET")

    def _rel_orders_employees(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT o.OrderID,
                   e.EmployeeID,
                   e.FirstName || ' ' || e.LastName AS EmployeeName
            FROM Orders o
            LEFT JOIN Employees e ON o.EmployeeID = e.EmployeeID
        """).fetchall()
        for r in (dict(r) for r in rows):
            nid = f"rel_orders_{r['OrderID']}_employee_{r['EmployeeID']}"
            self._add_node(Relationship(
                node_id=nid,
                text=(
                    f"Order #{r['OrderID']} was processed by Employee "
                    f"{r['EmployeeName'] or 'Unknown'}."
                ),
                from_entity_id=f"entity_Orders_{r['OrderID']}",
                to_entity_id=f"entity_Employees_{r['EmployeeID']}",
                relation_label="PROCESSED_BY",
                from_table="Orders",
                to_table="Employees",
            ))
            self._add_edge(nid, f"entity_Orders_{r['OrderID']}",       "HAS_SOURCE")
            self._add_edge(nid, f"entity_Employees_{r['EmployeeID']}", "HAS_TARGET")

    def _rel_products_suppliers(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT p.ProductID, p.ProductName,
                   s.SupplierID, s.CompanyName AS SupplierName
            FROM Products p
            LEFT JOIN Suppliers s ON p.SupplierID = s.SupplierID
        """).fetchall()
        for r in (dict(r) for r in rows):
            nid = f"rel_products_{r['ProductID']}_supplier_{r['SupplierID']}"
            self._add_node(Relationship(
                node_id=nid,
                text=(
                    f"Product '{r['ProductName']}' is supplied by "
                    f"{r['SupplierName'] or 'Unknown'} (Supplier #{r['SupplierID']})."
                ),
                from_entity_id=f"entity_Products_{r['ProductID']}",
                to_entity_id=f"entity_Suppliers_{r['SupplierID']}",
                relation_label="SUPPLIED_BY",
                from_table="Products",
                to_table="Suppliers",
            ))
            self._add_edge(nid, f"entity_Products_{r['ProductID']}",  "HAS_SOURCE")
            self._add_edge(nid, f"entity_Suppliers_{r['SupplierID']}", "HAS_TARGET")

    def _rel_products_categories(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT p.ProductID, p.ProductName,
                   c.CategoryID, c.CategoryName
            FROM Products p
            LEFT JOIN Categories c ON p.CategoryID = c.CategoryID
        """).fetchall()
        for r in (dict(r) for r in rows):
            nid = f"rel_products_{r['ProductID']}_category_{r['CategoryID']}"
            self._add_node(Relationship(
                node_id=nid,
                text=(
                    f"Product '{r['ProductName']}' belongs to the "
                    f"'{r['CategoryName']}' category."
                ),
                from_entity_id=f"entity_Products_{r['ProductID']}",
                to_entity_id=f"entity_Categories_{r['CategoryID']}",
                relation_label="BELONGS_TO_CATEGORY",
                from_table="Products",
                to_table="Categories",
            ))
            self._add_edge(nid, f"entity_Products_{r['ProductID']}",   "HAS_SOURCE")
            self._add_edge(nid, f"entity_Categories_{r['CategoryID']}", "HAS_TARGET")

    def _rel_orderdetails_orders(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT od.OrderID, od.ProductID, od.Quantity, od.UnitPrice, od.Discount,
                   p.ProductName
            FROM OrderDetails od
            LEFT JOIN Products p ON od.ProductID = p.ProductID
        """).fetchall()
        for r in (dict(r) for r in rows):
            name = r["ProductName"] or f"Product #{r['ProductID']}"
            disc_pct = int((r["Discount"] or 0) * 100)
            nid = f"rel_orderdetails_{r['OrderID']}_{r['ProductID']}_order"
            self._add_node(Relationship(
                node_id=nid,
                text=(
                    f"Order #{r['OrderID']} contains {r['Quantity']} units of "
                    f"'{name}' at ${r['UnitPrice']:.2f} each ({disc_pct}% discount)."
                ),
                from_entity_id=f"entity_OrderDetails_{r['OrderID']}_{r['ProductID']}",
                to_entity_id=f"entity_Orders_{r['OrderID']}",
                relation_label="PART_OF_ORDER",
                from_table="OrderDetails",
                to_table="Orders",
            ))
            self._add_edge(nid, f"entity_OrderDetails_{r['OrderID']}_{r['ProductID']}", "HAS_SOURCE")
            self._add_edge(nid, f"entity_Orders_{r['OrderID']}",                        "HAS_TARGET")
            # Wire product→orderdetail so supplier→product→order chain is traversable
            self._add_edge(nid, f"entity_Products_{r['ProductID']}",                   "INVOLVES_PRODUCT")

    def _rel_employees_manager(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT e.EmployeeID,
                   e.FirstName || ' ' || e.LastName AS EmpName,
                   m.EmployeeID AS ManagerID,
                   m.FirstName || ' ' || m.LastName AS ManagerName
            FROM Employees e
            JOIN Employees m ON e.ReportsTo = m.EmployeeID
        """).fetchall()
        for r in (dict(r) for r in rows):
            nid = f"rel_employees_{r['EmployeeID']}_reports_to_{r['ManagerID']}"
            self._add_node(Relationship(
                node_id=nid,
                text=(
                    f"Employee {r['EmpName']} reports to "
                    f"{r['ManagerName']} (Employee #{r['ManagerID']})."
                ),
                from_entity_id=f"entity_Employees_{r['EmployeeID']}",
                to_entity_id=f"entity_Employees_{r['ManagerID']}",
                relation_label="REPORTS_TO",
                from_table="Employees",
                to_table="Employees",
            ))
            self._add_edge(nid, f"entity_Employees_{r['EmployeeID']}", "HAS_SOURCE")
            self._add_edge(nid, f"entity_Employees_{r['ManagerID']}",  "HAS_TARGET")

    # ── N1: Text chunk nodes ──────────────────────────────────────────────────

    def _build_text_chunk_nodes(self) -> None:
        # one chunk per table
        for table, info in self.schema["tables"].items():
            col_str = ", ".join(f"{c['name']} ({c['type']})" for c in info["columns"])
            fk_str  = "; ".join(
                f"{fk['from_col']} -> {fk['to_table']}.{fk['to_col']}"
                for fk in info["foreign_keys"]
            ) or "None"
            checks  = "; ".join(info.get("check_constraints", [])) or "None"
            sample  = info["sample_rows"][0] if info["sample_rows"] else {}
            sample_str = ", ".join(f"{k}={v}" for k, v in list(sample.items())[:4])
            text = (
                f"Table: {table}\n"
                f"Columns: {col_str}\n"
                f"Foreign Keys: {fk_str}\n"
                f"Check Constraints: {checks}\n"
                f"Row Count: {info['row_count']}\n"
                f"Sample: {sample_str}"
            )
            words = text.split()
            if len(words) > 400:
                text = " ".join(words[:400])
            self._add_node(TextChunk(
                node_id=f"tc_{table}_0",
                text=text,
                source_table=table,
                chunk_index=0,
                token_count=len(words),
            ))

        # one chunk per view
        for vname, vinfo in self.schema.get("views", {}).items():
            sql  = vinfo.get("sql", "")
            text = f"View: {vname}\nSQL Definition:\n{sql}"
            self._add_node(TextChunk(
                node_id=f"tc_view_{vname}",
                text=text,
                source_table=f"view:{vname}",
                chunk_index=0,
                token_count=len(text.split()),
            ))

        # one chunk per trigger
        for tname, tinfo in self.schema.get("triggers", {}).items():
            sql  = tinfo.get("sql", "")
            text = (
                f"Trigger: {tname} on table {tinfo.get('table','?')}\n"
                f"SQL Definition:\n{sql}"
            )
            self._add_node(TextChunk(
                node_id=f"tc_trigger_{tname}",
                text=text,
                source_table=f"trigger:{tname}",
                chunk_index=0,
                token_count=len(text.split()),
            ))

    # ── N3: Semantic unit nodes ───────────────────────────────────────────────

    def _build_semantic_unit_nodes(self) -> None:
        with self._conn() as conn:
            self._su_products_by_category(conn)
            self._su_orders_by_country(conn)
            self._su_employees_by_city(conn)
            self._su_customers_by_country(conn)
            self._su_suppliers_by_country(conn)
            self._su_orderdetails_by_product(conn)
            self._su_categories_each(conn)

    def _su_products_by_category(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT c.CategoryID, c.CategoryName,
                   COUNT(*) AS n,
                   GROUP_CONCAT(p.ProductName, ', ') AS names,
                   MIN(p.UnitPrice) AS min_p, MAX(p.UnitPrice) AS max_p
            FROM Products p JOIN Categories c ON p.CategoryID = c.CategoryID
            GROUP BY c.CategoryID
        """).fetchall()
        for r in (dict(r) for r in rows):
            summary = (
                f"There are {r['n']} products in the {r['CategoryName']} category. "
                f"They include: {r['names']}. "
                f"Price range: ${r['min_p']:.2f} - ${r['max_p']:.2f}."
            )
            nid = f"su_Products_category_{r['CategoryID']}"
            pids = [
                row[0] for row in conn.execute(
                    "SELECT ProductID FROM Products WHERE CategoryID=?", (r["CategoryID"],)
                ).fetchall()
            ]
            member_ids = [f"entity_Products_{pid}" for pid in pids]
            self._add_node(SemanticUnit(
                node_id=nid, text=summary, member_entity_ids=member_ids,
                theme=f"Products in {r['CategoryName']} category", summary=summary,
            ))
            for mid in member_ids:
                self._add_edge(nid, mid, "CONTAINS_ENTITY")

    def _su_orders_by_country(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT ShipCountry, COUNT(*) AS n,
                   ROUND(SUM(Freight), 2) AS total_freight,
                   GROUP_CONCAT(DISTINCT CustomerID) AS customers
            FROM Orders GROUP BY ShipCountry
        """).fetchall()
        for r in (dict(r) for r in rows):
            summary = (
                f"There are {r['n']} orders shipping to {r['ShipCountry']}. "
                f"Total freight: ${r['total_freight']}. "
                f"Customers: {r['customers']}."
            )
            safe = r["ShipCountry"].replace(" ", "_")
            nid = f"su_Orders_country_{safe}"
            oids = [
                row[0] for row in conn.execute(
                    "SELECT OrderID FROM Orders WHERE ShipCountry=?", (r["ShipCountry"],)
                ).fetchall()
            ]
            member_ids = [f"entity_Orders_{oid}" for oid in oids]
            self._add_node(SemanticUnit(
                node_id=nid, text=summary, member_entity_ids=member_ids,
                theme=f"Orders shipping to {r['ShipCountry']}", summary=summary,
            ))
            for mid in member_ids:
                self._add_edge(nid, mid, "CONTAINS_ENTITY")

    def _su_employees_by_city(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT City, COUNT(*) AS n,
                   GROUP_CONCAT(FirstName || ' ' || LastName, ', ') AS names
            FROM Employees GROUP BY City
        """).fetchall()
        for r in (dict(r) for r in rows):
            summary = (
                f"There are {r['n']} employees based in {r['City']}. "
                f"They are: {r['names']}."
            )
            safe = r["City"].replace(" ", "_")
            nid = f"su_Employees_city_{safe}"
            eids = [
                row[0] for row in conn.execute(
                    "SELECT EmployeeID FROM Employees WHERE City=?", (r["City"],)
                ).fetchall()
            ]
            member_ids = [f"entity_Employees_{eid}" for eid in eids]
            self._add_node(SemanticUnit(
                node_id=nid, text=summary, member_entity_ids=member_ids,
                theme=f"Employees in {r['City']}", summary=summary,
            ))
            for mid in member_ids:
                self._add_edge(nid, mid, "CONTAINS_ENTITY")

    def _su_customers_by_country(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT Country, COUNT(*) AS n,
                   GROUP_CONCAT(CompanyName, ', ') AS names
            FROM Customers GROUP BY Country
        """).fetchall()
        for r in (dict(r) for r in rows):
            summary = (
                f"There are {r['n']} customers in {r['Country']}. "
                f"They include: {r['names']}."
            )
            safe = r["Country"].replace(" ", "_")
            nid = f"su_Customers_country_{safe}"
            cids = [
                row[0] for row in conn.execute(
                    "SELECT CustomerID FROM Customers WHERE Country=?", (r["Country"],)
                ).fetchall()
            ]
            member_ids = [f"entity_Customers_{cid}" for cid in cids]
            self._add_node(SemanticUnit(
                node_id=nid, text=summary, member_entity_ids=member_ids,
                theme=f"Customers in {r['Country']}", summary=summary,
            ))
            for mid in member_ids:
                self._add_edge(nid, mid, "CONTAINS_ENTITY")

    def _su_suppliers_by_country(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT Country, COUNT(*) AS n,
                   GROUP_CONCAT(CompanyName, ', ') AS names
            FROM Suppliers GROUP BY Country
        """).fetchall()
        for r in (dict(r) for r in rows):
            summary = (
                f"There are {r['n']} suppliers from {r['Country']}. "
                f"They include: {r['names']}."
            )
            safe = r["Country"].replace(" ", "_")
            nid = f"su_Suppliers_country_{safe}"
            sids = [
                row[0] for row in conn.execute(
                    "SELECT SupplierID FROM Suppliers WHERE Country=?", (r["Country"],)
                ).fetchall()
            ]
            member_ids = [f"entity_Suppliers_{sid}" for sid in sids]
            self._add_node(SemanticUnit(
                node_id=nid, text=summary, member_entity_ids=member_ids,
                theme=f"Suppliers from {r['Country']}", summary=summary,
            ))
            for mid in member_ids:
                self._add_edge(nid, mid, "CONTAINS_ENTITY")

    def _su_orderdetails_by_product(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT od.ProductID, p.ProductName,
                   COUNT(*) AS n,
                   SUM(od.Quantity) AS total_qty,
                   ROUND(SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)), 2) AS revenue
            FROM OrderDetails od
            LEFT JOIN Products p ON od.ProductID = p.ProductID
            GROUP BY od.ProductID ORDER BY n DESC LIMIT 10
        """).fetchall()
        for r in (dict(r) for r in rows):
            name = r["ProductName"] or f"Product #{r['ProductID']}"
            summary = (
                f"Product #{r['ProductID']} ({name}) appears in {r['n']} orders. "
                f"Total quantity ordered: {r['total_qty']}. "
                f"Total revenue: ${r['revenue']:.2f}."
            )
            nid = f"su_OrderDetails_product_{r['ProductID']}"
            pairs = conn.execute(
                "SELECT OrderID, ProductID FROM OrderDetails WHERE ProductID=?",
                (r["ProductID"],),
            ).fetchall()
            member_ids = [f"entity_OrderDetails_{row[0]}_{row[1]}" for row in pairs]
            self._add_node(SemanticUnit(
                node_id=nid, text=summary, member_entity_ids=member_ids,
                theme=f"Orders containing {name}", summary=summary,
            ))
            for mid in member_ids:
                self._add_edge(nid, mid, "CONTAINS_ENTITY")

    def _su_categories_each(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            "SELECT CategoryID, CategoryName, Description FROM Categories"
        ).fetchall()
        for r in (dict(r) for r in rows):
            summary = (
                f"Category '{r['CategoryName']}': {r['Description']}. "
                f"This group covers all products classified under {r['CategoryName']}."
            )
            nid = f"su_Categories_{r['CategoryID']}"
            member_ids = [f"entity_Categories_{r['CategoryID']}"]
            self._add_node(SemanticUnit(
                node_id=nid, text=summary, member_entity_ids=member_ids,
                theme=r["CategoryName"], summary=summary,
            ))
            for mid in member_ids:
                self._add_edge(nid, mid, "CONTAINS_ENTITY")

    # ── N6: High-level insight nodes ──────────────────────────────────────────

    def _build_high_level_insight_nodes(self) -> None:
        with self._conn() as conn:
            self._insight_top_customers(conn)
            self._insight_top_categories(conn)
            self._insight_most_active_employee(conn)
            self._insight_top_customer_country(conn)
            self._insight_most_expensive_discontinued(conn)

    def _insight_top_customers(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT c.CustomerID, c.CompanyName, c.Country,
                   ROUND(SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)), 2) AS revenue
            FROM Customers c
            JOIN Orders o ON c.CustomerID = o.CustomerID
            JOIN OrderDetails od ON o.OrderID = od.OrderID
            GROUP BY c.CustomerID ORDER BY revenue DESC LIMIT 5
        """).fetchall()
        rows = [dict(r) for r in rows]
        summary = ", ".join(
            f"{r['CompanyName']} ({r['Country']}, ${r['revenue']:.0f})" for r in rows
        )
        node = HighLevelInsight(
            node_id="insight_top_customers_by_revenue",
            text=f"The top 5 customers by total order value are: {summary}.",
            source_entity_ids=[f"entity_Customers_{r['CustomerID']}" for r in rows],
            insight_type="top_customers_by_revenue",
            confidence=1.0,
        )
        self._add_node(node)
        for r in rows:
            self._add_edge(node.node_id, f"entity_Customers_{r['CustomerID']}", "INSIGHT_ABOUT")

    def _insight_top_categories(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("""
            SELECT c.CategoryID, c.CategoryName,
                   ROUND(SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)), 2) AS revenue
            FROM Categories c
            JOIN Products p ON c.CategoryID = p.CategoryID
            JOIN OrderDetails od ON p.ProductID = od.ProductID
            GROUP BY c.CategoryID ORDER BY revenue DESC LIMIT 3
        """).fetchall()
        rows = [dict(r) for r in rows]
        summary = ", ".join(f"{r['CategoryName']} (${r['revenue']:.0f})" for r in rows)
        node = HighLevelInsight(
            node_id="insight_top_categories_by_revenue",
            text=f"The top 3 revenue-generating product categories are: {summary}.",
            source_entity_ids=[f"entity_Categories_{r['CategoryID']}" for r in rows],
            insight_type="top_categories_by_revenue",
            confidence=1.0,
        )
        self._add_node(node)
        for r in rows:
            self._add_edge(node.node_id, f"entity_Categories_{r['CategoryID']}", "INSIGHT_ABOUT")

    def _insight_most_active_employee(self, conn: sqlite3.Connection) -> None:
        r = dict(conn.execute("""
            SELECT e.EmployeeID,
                   e.FirstName || ' ' || e.LastName AS name,
                   e.Title, COUNT(o.OrderID) AS order_count
            FROM Employees e
            JOIN Orders o ON e.EmployeeID = o.EmployeeID
            GROUP BY e.EmployeeID ORDER BY order_count DESC LIMIT 1
        """).fetchone())
        node = HighLevelInsight(
            node_id="insight_most_active_employee",
            text=(
                f"The most active employee is {r['name']} ({r['Title']}), "
                f"who has handled {r['order_count']} orders."
            ),
            source_entity_ids=[f"entity_Employees_{r['EmployeeID']}"],
            insight_type="most_active_employee",
            confidence=1.0,
        )
        self._add_node(node)
        self._add_edge(node.node_id, f"entity_Employees_{r['EmployeeID']}", "INSIGHT_ABOUT")

    def _insight_top_customer_country(self, conn: sqlite3.Connection) -> None:
        r = dict(conn.execute("""
            SELECT Country, COUNT(*) AS cnt
            FROM Customers GROUP BY Country ORDER BY cnt DESC LIMIT 1
        """).fetchone())
        cids = [
            row[0] for row in conn.execute(
                "SELECT CustomerID FROM Customers WHERE Country=?", (r["Country"],)
            ).fetchall()
        ]
        node = HighLevelInsight(
            node_id="insight_top_customer_country",
            text=(
                f"{r['Country']} has the highest number of customers "
                f"with {r['cnt']} registered companies."
            ),
            source_entity_ids=[f"entity_Customers_{cid}" for cid in cids],
            insight_type="top_customer_country",
            confidence=1.0,
        )
        self._add_node(node)
        for cid in cids:
            self._add_edge(node.node_id, f"entity_Customers_{cid}", "INSIGHT_ABOUT")

    def _insight_most_expensive_discontinued(self, conn: sqlite3.Connection) -> None:
        r = dict(conn.execute("""
            SELECT ProductID, ProductName, UnitPrice
            FROM Products WHERE Discontinued=1
            ORDER BY UnitPrice DESC LIMIT 1
        """).fetchone())
        node = HighLevelInsight(
            node_id="insight_most_expensive_discontinued",
            text=(
                f"The most expensive discontinued product is '{r['ProductName']}' "
                f"at ${r['UnitPrice']:.2f} per unit."
            ),
            source_entity_ids=[f"entity_Products_{r['ProductID']}"],
            insight_type="most_expensive_discontinued_product",
            confidence=1.0,
        )
        self._add_node(node)
        self._add_edge(node.node_id, f"entity_Products_{r['ProductID']}", "INSIGHT_ABOUT")

    # ── N7: Community nodes ───────────────────────────────────────────────────

    def _build_community_nodes(self) -> None:
        # core_number requires a simple (non-multi) graph
        G_un = nx.Graph(self.G.to_undirected())
        core_numbers = nx.core_number(G_un)
        min_k = config.KCORE_MIN_K

        by_core: dict[int, list[str]] = defaultdict(list)
        for nid, k in core_numbers.items():
            if k >= min_k:
                by_core[k].append(nid)

        if not by_core:
            console.print("[yellow]No nodes met k-core threshold — skipping.[/yellow]")
            return

        deg_centrality = nx.degree_centrality(G_un)  # G_un is already simple Graph

        for k, members in sorted(by_core.items()):
            central = max(members, key=lambda nid: deg_centrality.get(nid, 0))
            central_data = self.G.nodes[central].get("data")
            central_label = (central_data.text[:60] if central_data else central)

            summary = (
                f"{len(members)} nodes at k-core level {k}, "
                f"centered around {central}. "
                f"Representative context: {central_label}."
            )
            nid = f"community_k{k}"
            self._add_node(Community(
                node_id=nid,
                text=summary,
                member_node_ids=members,
                core_number=k,
                central_entity_id=central,
                community_summary=summary,
            ))
            for mid in members:
                self._add_edge(nid, mid, "HAS_MEMBER")


# ── __main__ ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root        = Path(__file__).parent.parent
    db_path     = str(root / "data" / "northwind.db")
    schema_path = str(root / "data" / "northwind_schema.json")
    graph_path  = str(root / "data" / "northwind_graph.json")

    hg = NorthwindHeterograph(db_path, schema_path)
    hg.build()

    stats = hg.stats()

    node_tbl = Table(title="Node Counts by Type", show_lines=True)
    node_tbl.add_column("Node Type", style="cyan")
    node_tbl.add_column("Count", justify="right", style="green")
    for ntype, cnt in sorted(stats["nodes_by_type"].items()):
        node_tbl.add_row(ntype, str(cnt))
    node_tbl.add_row("[bold]TOTAL[/bold]", f"[bold]{stats['total_nodes']}[/bold]")
    console.print(node_tbl)

    edge_tbl = Table(title="Edge Counts by Relation", show_lines=True)
    edge_tbl.add_column("Relation", style="yellow")
    edge_tbl.add_column("Count", justify="right", style="green")
    for rel, cnt in sorted(stats["edges_by_relation"].items()):
        edge_tbl.add_row(rel, str(cnt))
    edge_tbl.add_row("[bold]TOTAL[/bold]", f"[bold]{stats['total_edges']}[/bold]")
    console.print(edge_tbl)

    hg.save(graph_path)
    console.print(f"\n[green]Graph saved to {graph_path}[/green]")
