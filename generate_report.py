"""
NodeRAG Project — Professional PDF Report Generator
Run:  python generate_report.py
Output: NodeRAG_Project_Report.pdf
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import datetime

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG        = HexColor("#0D1117")   # surface
C_PANEL     = HexColor("#161B22")
C_ACCENT    = HexColor("#58A6FF")
C_PRIMARY   = HexColor("#C9D1D9")
C_MUTED     = HexColor("#6E7681")
C_BORDER    = HexColor("#21262D")
C_WHITE     = colors.white
C_N1        = HexColor("#7C8FA6")
C_N2        = HexColor("#3D9A6F")
C_N3        = HexColor("#B07D3A")
C_N4        = HexColor("#9B5A8A")
C_N5        = HexColor("#4A7FC1")
C_N6        = HexColor("#A8892B")
C_N7        = HexColor("#6B5EA8")

C_DARK      = HexColor("#0D1117")
C_SECTION   = HexColor("#1C2128")
C_LIGHT_BG  = HexColor("#F6F8FA")   # for table rows on white
C_TABLE_HDR = HexColor("#1C2128")
C_BODY_TEXT = HexColor("#24292F")
C_H1        = HexColor("#0D1117")
C_H2        = HexColor("#0969DA")
C_H3        = HexColor("#1A7F37")
C_ACCENT2   = HexColor("#8250DF")

W, H = A4
MARGIN_L = 20 * mm
MARGIN_R = 20 * mm
MARGIN_T = 24 * mm
MARGIN_B = 20 * mm


# ── Styles ────────────────────────────────────────────────────────────────────
def build_styles():
    base = getSampleStyleSheet()
    s = {}

    s["cover_title"] = ParagraphStyle(
        "cover_title",
        fontName="Helvetica-Bold",
        fontSize=34,
        leading=42,
        textColor=C_WHITE,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    s["cover_sub"] = ParagraphStyle(
        "cover_sub",
        fontName="Helvetica",
        fontSize=16,
        leading=22,
        textColor=HexColor("#8B949E"),
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    s["cover_meta"] = ParagraphStyle(
        "cover_meta",
        fontName="Helvetica",
        fontSize=10,
        leading=16,
        textColor=HexColor("#6E7681"),
        alignment=TA_LEFT,
    )
    s["h1"] = ParagraphStyle(
        "h1",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=26,
        textColor=C_H1,
        spaceBefore=18,
        spaceAfter=6,
    )
    s["h2"] = ParagraphStyle(
        "h2",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=20,
        textColor=C_H2,
        spaceBefore=14,
        spaceAfter=4,
        borderPad=0,
    )
    s["h3"] = ParagraphStyle(
        "h3",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=16,
        textColor=C_H3,
        spaceBefore=10,
        spaceAfter=3,
    )
    s["body"] = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9.5,
        leading=15,
        textColor=C_BODY_TEXT,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
    )
    s["body_left"] = ParagraphStyle(
        "body_left",
        fontName="Helvetica",
        fontSize=9.5,
        leading=15,
        textColor=C_BODY_TEXT,
        spaceAfter=4,
    )
    s["bullet"] = ParagraphStyle(
        "bullet",
        fontName="Helvetica",
        fontSize=9.5,
        leading=15,
        textColor=C_BODY_TEXT,
        leftIndent=14,
        bulletIndent=4,
        spaceAfter=3,
    )
    s["code"] = ParagraphStyle(
        "code",
        fontName="Courier",
        fontSize=8.5,
        leading=13,
        textColor=HexColor("#24292F"),
        backColor=HexColor("#F6F8FA"),
        leftIndent=8,
        rightIndent=8,
        spaceAfter=6,
        spaceBefore=4,
        borderPad=6,
    )
    s["caption"] = ParagraphStyle(
        "caption",
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=13,
        textColor=C_MUTED,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    s["toc_entry"] = ParagraphStyle(
        "toc_entry",
        fontName="Helvetica",
        fontSize=10,
        leading=18,
        textColor=C_BODY_TEXT,
        leftIndent=0,
    )
    s["toc_entry_sub"] = ParagraphStyle(
        "toc_entry_sub",
        fontName="Helvetica",
        fontSize=9.5,
        leading=16,
        textColor=HexColor("#57606A"),
        leftIndent=18,
    )
    s["callout_title"] = ParagraphStyle(
        "callout_title",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=14,
        textColor=C_H2,
    )
    s["callout_body"] = ParagraphStyle(
        "callout_body",
        fontName="Helvetica",
        fontSize=9,
        leading=14,
        textColor=C_BODY_TEXT,
    )
    return s


# ── Custom Flowables ──────────────────────────────────────────────────────────
class ColorBar(Flowable):
    """Thin horizontal accent bar."""
    def __init__(self, width, height=3, color=C_ACCENT):
        super().__init__()
        self.bar_width = width
        self.bar_height = height
        self.color = color

    def wrap(self, *args):
        return self.bar_width, self.bar_height + 4

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.rect(0, 2, self.bar_width, self.bar_height, fill=1, stroke=0)


class NodeTypePill(Flowable):
    """Coloured pill for a node type."""
    def __init__(self, code, label, color, width=110, height=24):
        super().__init__()
        self.code = code
        self.label = label
        self.color = color
        self.pill_width = width
        self.pill_height = height

    def wrap(self, *args):
        return self.pill_width, self.pill_height + 4

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.roundRect(0, 2, self.pill_width, self.pill_height, 4, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(6, 9, self.code)
        c.setFont("Helvetica", 8.5)
        c.drawString(28, 9, self.label)


class CalloutBox(Flowable):
    """Bordered callout box with title + body text."""
    def __init__(self, title, body, color=C_ACCENT, avail_width=None):
        super().__init__()
        self.title = title
        self.body = body
        self.accent = color
        self.avail_width = avail_width or (W - MARGIN_L - MARGIN_R)

    def wrap(self, aW, aH):
        self.calc_width = aW
        return aW, 60

    def draw(self):
        c = self.canv
        w = self.calc_width
        h = 52
        # background
        c.setFillColor(HexColor("#F6F8FA"))
        c.roundRect(0, 0, w, h, 4, fill=1, stroke=0)
        # left accent stripe
        c.setFillColor(self.accent)
        c.rect(0, 0, 4, h, fill=1, stroke=0)
        # title
        c.setFillColor(self.accent)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(12, h - 16, self.title)
        # body
        c.setFillColor(C_BODY_TEXT)
        c.setFont("Helvetica", 8.8)
        # simple word wrap
        words = self.body.split()
        line, lines = [], []
        for word in words:
            test = " ".join(line + [word])
            if c.stringWidth(test, "Helvetica", 8.8) < w - 24:
                line.append(word)
            else:
                lines.append(" ".join(line))
                line = [word]
        if line:
            lines.append(" ".join(line))
        y = h - 30
        for ln in lines[:2]:
            c.drawString(12, y, ln)
            y -= 13


# ── Page template ─────────────────────────────────────────────────────────────
class PageTemplate:
    def __init__(self, total_pages=1):
        self.total_pages = total_pages

    def on_page(self, canv, doc):
        pn = doc.page
        # skip cover + TOC pages
        if pn <= 2:
            return
        canv.saveState()
        # top rule
        canv.setStrokeColor(HexColor("#D0D7DE"))
        canv.setLineWidth(0.5)
        canv.line(MARGIN_L, H - MARGIN_T + 4, W - MARGIN_R, H - MARGIN_T + 4)
        # header text
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(C_MUTED)
        canv.drawString(MARGIN_L, H - MARGIN_T + 7, "NodeRAG: Structural Intelligence over Relational Databases")
        canv.drawRightString(W - MARGIN_R, H - MARGIN_T + 7, f"Technical Report  ·  {datetime.date.today().strftime('%B %Y')}")
        # bottom rule + page number
        canv.line(MARGIN_L, MARGIN_B - 4, W - MARGIN_R, MARGIN_B - 4)
        canv.drawString(MARGIN_L, MARGIN_B - 12, "Confidential — Internal Use Only")
        canv.drawRightString(W - MARGIN_R, MARGIN_B - 12, f"Page {pn}")
        canv.restoreState()

    def on_cover(self, canv, doc):
        canv.saveState()
        # dark background
        canv.setFillColor(C_BG)
        canv.rect(0, 0, W, H, fill=1, stroke=0)
        # accent stripe top
        canv.setFillColor(C_ACCENT)
        canv.rect(0, H - 8, W, 8, fill=1, stroke=0)
        # accent stripe left
        canv.rect(0, 0, 6, H, fill=1, stroke=0)
        # decorative node circles (background)
        import random; random.seed(42)
        node_colors = [C_N1, C_N2, C_N3, C_N4, C_N5, C_N6, C_N7]
        positions = [
            (W * 0.72, H * 0.62, 60), (W * 0.85, H * 0.52, 40),
            (W * 0.68, H * 0.42, 30), (W * 0.80, H * 0.70, 22),
            (W * 0.76, H * 0.35, 18), (W * 0.90, H * 0.38, 28),
            (W * 0.65, H * 0.58, 14),
        ]
        for i, (x, y, r) in enumerate(positions):
            col = node_colors[i % len(node_colors)]
            canv.setStrokeColor(col)
            canv.setFillColor(HexColor("#161B22"))
            canv.setLineWidth(1.5)
            canv.circle(x, y, r, fill=1, stroke=1)
        # connect some nodes
        canv.setStrokeColor(HexColor("#21262D"))
        canv.setLineWidth(0.8)
        edges = [(0,1),(0,2),(1,3),(2,4),(0,6),(3,5),(2,6)]
        for a, b in edges:
            ax, ay, _ = positions[a]
            bx, by, _ = positions[b]
            canv.line(ax, ay, bx, by)
        canv.restoreState()


# ── Content builders ──────────────────────────────────────────────────────────
def cover_page(S):
    story = []
    today = datetime.date.today().strftime("%B %d, %Y")

    # White space from top of the dark-background (handled by on_cover)
    story.append(Spacer(1, 55 * mm))

    story.append(Paragraph("NodeRAG", S["cover_title"]))
    story.append(Paragraph("Structural Intelligence over Relational Databases", S["cover_sub"]))
    story.append(Spacer(1, 6 * mm))

    # Thin accent line
    story.append(ColorBar(W - MARGIN_L - MARGIN_R - 60, height=3, color=C_ACCENT))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Technical Project Report", S["cover_meta"]))
    story.append(Paragraph(f"Prepared: {today}", S["cover_meta"]))
    story.append(Paragraph("Platform: Northwind SQLite · Claude API · React + D3.js", S["cover_meta"]))
    story.append(Spacer(1, 14 * mm))

    # Node type pills grid
    node_types = [
        ("N1", "Text Chunk",        C_N1),
        ("N2", "Entity",            C_N2),
        ("N3", "Semantic Unit",     C_N3),
        ("N4", "Relationship",      C_N4),
        ("N5", "Attribute",         C_N5),
        ("N6", "High-Level Insight",C_N6),
        ("N7", "Community",         C_N7),
    ]
    pill_data = []
    row = []
    for i, (code, label, col) in enumerate(node_types):
        cell = Table(
            [[Paragraph(f'<font color="white"><b>{code}</b></font>  {label}',
                        ParagraphStyle("pill_text", fontName="Helvetica", fontSize=8.5,
                                       leading=12, textColor=C_WHITE))]],
            colWidths=[72 * mm],
            rowHeights=[16],
        )
        cell.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), col),
            ("ROUNDEDCORNERS", [4]),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ]))
        row.append(cell)
        if len(row) == 3 or i == len(node_types) - 1:
            while len(row) < 3:
                row.append("")
            pill_data.append(row)
            row = []
    pill_table = Table(pill_data, colWidths=[75*mm, 75*mm, 75*mm])
    pill_table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [None]),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(pill_table)
    story.append(PageBreak())
    return story


def toc_page(S):
    story = []
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Table of Contents", S["h1"]))
    story.append(ColorBar(W - MARGIN_L - MARGIN_R))
    story.append(Spacer(1, 4 * mm))

    entries = [
        ("1", "Executive Summary", False),
        ("2", "Project Overview & Motivation", False),
        ("3", "System Architecture", False),
        ("3.1", "Graph Construction Pipeline", True),
        ("3.2", "Embedding & Indexing", True),
        ("3.3", "Multi-Stage Retrieval Engine", True),
        ("3.4", "LLM Answer Generation", True),
        ("4", "The Seven Node Types", False),
        ("5", "Web Application", False),
        ("5.1", "FastAPI Backend", True),
        ("5.2", "React + D3.js Frontend", True),
        ("5.3", "State Management Architecture", True),
        ("6", "Key Challenges & Solutions", False),
        ("7", "Results & Outcomes", False),
        ("8", "Multi-Hop Query Examples", False),
        ("9", "Technology Stack", False),
        ("10", "Conclusions", False),
    ]

    toc_data = []
    for num, title, indent in entries:
        style = S["toc_entry_sub"] if indent else S["toc_entry"]
        prefix = "    " if indent else ""
        toc_data.append([
            Paragraph(f"{prefix}{num}", style),
            Paragraph(f"{prefix}{title}", style),
            Paragraph("·" * 40, ParagraphStyle("dots", fontName="Helvetica", fontSize=9, textColor=HexColor("#D0D7DE"))),
        ])

    toc_table = Table(toc_data, colWidths=[12*mm, 120*mm, None])
    toc_table.setStyle(TableStyle([
        ("VALIGN",  (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 1),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(toc_table)
    story.append(PageBreak())
    return story


def section_divider(title, color=C_ACCENT, S=None):
    """Full-width section header bar."""
    data = [[Paragraph(f'<font color="white"><b>{title}</b></font>',
                       ParagraphStyle("div_title", fontName="Helvetica-Bold", fontSize=13,
                                      leading=18, textColor=C_WHITE))]]
    t = Table(data, colWidths=[W - MARGIN_L - MARGIN_R])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), color),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("ROUNDEDCORNERS", [3]),
    ]))
    return [Spacer(1, 2*mm), t, Spacer(1, 4*mm)]


def build_story(S):
    story = []
    PW = W - MARGIN_L - MARGIN_R   # printable width

    # ── SECTION 1: Executive Summary ─────────────────────────────────────────
    story += section_divider("1   Executive Summary", color=HexColor("#0969DA"), S=S)
    story.append(Paragraph(
        "NodeRAG is a production-ready graph-based Retrieval-Augmented Generation (RAG) "
        "system that transforms a relational database into a heterogeneous knowledge graph "
        "and answers complex, multi-hop natural-language questions over it. The system was "
        "designed, built, and deployed end-to-end — from raw SQLite schema ingestion through "
        "to an interactive web application with a real-time D3.js graph visualiser and "
        "streaming LLM answer console.", S["body"]))
    story.append(Paragraph(
        "The implementation covers seven layers of innovation: heterogeneous graph construction "
        "from a relational schema, sentence-transformer embedding of every graph node, FAISS "
        "vector indexing for sub-millisecond similarity search, Shallow Personalised PageRank "
        "for graph-aware retrieval, K-core decomposition for structural importance boosting, "
        "Claude API integration with prompt caching, and a React 18 + D3.js web application "
        "with Server-Sent Events streaming, Zustand state management, and a one-click Windows "
        "launcher compiled with PyInstaller.", S["body"]))

    # KPIs table
    kpi_data = [
        [Paragraph("<b>Metric</b>", S["body"]), Paragraph("<b>Value</b>", S["body"])],
        ["Graph nodes",           "539"],
        ["Graph edges",           "901"],
        ["Node types",            "7 (N1–N7)"],
        ["Embedding dimensions",  "384-dim (all-MiniLM-L6-v2)"],
        ["FAISS index type",      "IndexFlatIP (cosine similarity)"],
        ["Retrieval stages",      "3 (vector seed → PPR → K-core boost)"],
        ["Context budget",        "~3 000 words per query"],
        ["LLM model",             "Claude Haiku (claude-haiku-4-5-20251001)"],
        ["Frontend stack",        "React 18 · D3.js v7 · Fastapi · Tailwind CSS"],
        ["API endpoints",         "6 REST + 1 SSE streaming"],
        ["Deployable as",         "NodeRAG.exe (PyInstaller, Windows)"],
    ]
    kpi_table = Table(kpi_data, colWidths=[80*mm, PW - 80*mm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), HexColor("#0969DA")),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#F6F8FA"), colors.white]),
        ("GRID",        (0,0), (-1,-1), 0.4, HexColor("#D0D7DE")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 4*mm))

    # ── SECTION 2: Project Overview ──────────────────────────────────────────
    story += section_divider("2   Project Overview & Motivation", color=HexColor("#1A7F37"), S=S)
    story.append(Paragraph(
        "Standard Retrieval-Augmented Generation systems chunk text documents into flat vectors "
        "and retrieve the k nearest neighbours to a query. This approach fundamentally breaks "
        "on relational databases: answering <i>\"Which UK suppliers' products were ordered by "
        "German customers?\"</i> requires traversing five tables across four foreign-key hops. "
        "No flat embedding can encode that traversal.", S["body"]))
    story.append(Paragraph(
        "NodeRAG solves this by reifying every database entity, every foreign-key relationship, "
        "every column, and every business insight as a typed node in a heterogeneous graph. "
        "Retrieval is then a <b>graph walk</b> guided by Personalised PageRank, not a flat "
        "nearest-neighbour search. The result is a system that can perform genuine multi-hop "
        "reasoning while remaining fully grounded in factual database content.", S["body"]))

    story.append(Paragraph("Why the Northwind Database?", S["h3"]))
    story.append(Paragraph(
        "Northwind is a classic business dataset covering Customers, Orders, Products, Suppliers, "
        "Employees, Categories, and OrderDetails. Its natural 4-level FK chain makes it an ideal "
        "benchmark: queries that are trivial in SQL require non-trivial reasoning in natural "
        "language. The database includes 7 core tables, 5 analytical views, 5 business-logic "
        "triggers, and 7 indexes — all of which are ingested as first-class graph nodes.",
        S["body"]))

    story.append(Paragraph("Research Foundation", S["h3"]))
    story.append(Paragraph(
        "This implementation is based on <i>Xu et al. (2025) — NodeRAG: Structuring Graph-based "
        "RAG with Heterogeneous Nodes (arXiv:2504.11544)</i>. The paper defines seven node types "
        "for heterogeneous graph construction over structured data. This project extends the "
        "original paper with: live database extraction (not static text), K-core structural "
        "boosting, a full-stack web application, and a Windows desktop launcher.",
        S["body"]))

    # ── SECTION 3: Architecture ───────────────────────────────────────────────
    story += section_divider("3   System Architecture", color=HexColor("#6F42C1"), S=S)
    story.append(Paragraph(
        "NodeRAG is structured as a six-stage pipeline. Each stage produces an artefact consumed "
        "by the next, enabling the full system to be rebuilt from a single command "
        "(<font face='Courier' size='9'>noderag ingest</font>) or incrementally reloaded via "
        "the web API.", S["body"]))

    arch_steps = [
        ("Stage 1", "Schema Extraction",     "bootstrap_northwind.py reads the live SQLite schema — tables, "
                                              "columns, FKs, check constraints, views, triggers — and serialises "
                                              "it to northwind_schema.json."),
        ("Stage 2", "Graph Construction",    "NorthwindHeterograph builds all 7 node types from the DB + schema. "
                                              "A NetworkX MultiDiGraph with 539 nodes and 901 edges is produced "
                                              "and serialised to northwind_graph.json."),
        ("Stage 3", "LLM Enrichment (opt.)", "GraphEnricher calls the Claude API at ingest time to generate "
                                              "richer column descriptions, semantic-unit summaries, and business "
                                              "insight text. Skipped if --enrich flag is absent."),
        ("Stage 4", "Embedding",             "NodeEmbedder runs all-MiniLM-L6-v2 on every node's text field in "
                                              "batches, producing 384-dim L2-normalised float32 vectors. ~539 "
                                              "embeddings, runtime ≈ 30 s on CPU."),
        ("Stage 5", "FAISS Indexing",        "NodeIndex wraps a FAISS IndexFlatIP (exact inner-product search "
                                              "on unit vectors = cosine similarity). Index and node-ID map are "
                                              "saved as northwind_index.faiss + northwind_index.json."),
        ("Stage 6", "Query Pipeline",        "At query time: embed → seed search → ShallowPPR (2-hop) → "
                                              "K-core boost → context assembly → Claude API → AnswerResult."),
    ]

    for code, title, desc in arch_steps:
        row_data = [[
            Paragraph(f'<font color="white"><b>{code}</b></font>',
                      ParagraphStyle("arch_code", fontName="Helvetica-Bold", fontSize=9,
                                     leading=13, textColor=C_WHITE)),
            Paragraph(f'<b>{title}</b><br/><font size="9">{desc}</font>', S["body_left"]),
        ]]
        t = Table(row_data, colWidths=[24*mm, PW - 24*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (0,0), C_H2),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",   (0,0), (-1,-1), 7),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("GRID",          (0,0), (-1,-1), 0.4, HexColor("#D0D7DE")),
            ("ROWBACKGROUNDS",(1,0), (1,0), [HexColor("#F6F8FA")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 1.5*mm))

    story.append(Spacer(1, 3*mm))

    # 3.3 Retrieval
    story.append(Paragraph("3.3   Multi-Stage Retrieval Engine", S["h2"]))
    story.append(Paragraph(
        "The retrieval pipeline is the core intellectual contribution of the system. Three "
        "complementary ranking signals are combined to select the optimal context for the LLM:",
        S["body"]))

    retrieval_data = [
        [Paragraph("<b>Stage</b>", S["body"]), Paragraph("<b>Algorithm</b>", S["body"]),
         Paragraph("<b>Purpose</b>", S["body"]), Paragraph("<b>Parameters</b>", S["body"])],
        ["1 — Seed Search",   "FAISS IndexFlatIP",       "Find lexically / semantically similar nodes to the query embedding",   "top_k = 10  (default)"],
        ["2 — PPR Expansion", "Shallow PageRank",        "Expand seed set to structurally related nodes within 2-hop neighbourhood", "α = 0.85,  max_iter = 100"],
        ["3 — K-core Boost",  "K-core Decomposition",   "Multiply PPR scores of structurally central nodes by up to 1.5×",      "min_k = 2,  boost = 0.5"],
        ["4 — Context Build", "Type-grouped assembly",  "Group top nodes by type, trim to ~3 000-word budget, format for LLM",  "budget ≈ 3 000 words"],
    ]
    ret_table = Table(retrieval_data, colWidths=[38*mm, 36*mm, 78*mm, PW-38*mm-36*mm-78*mm])
    ret_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), HexColor("#6F42C1")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#F6F8FA"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.4, HexColor("#D0D7DE")),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ]))
    story.append(ret_table)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph(
        "The <b>Shallow</b> constraint in ShallowPPR (2-hop restriction) is a deliberate design "
        "choice: without it, globally popular hub nodes — such as the Orders table, which connects "
        "Customers, Employees, Products, and Shipping — would dominate every result regardless of "
        "the query topic. The 2-hop restriction keeps retrieval query-focused while still enabling "
        "the multi-hop traversal that flat RAG cannot perform.", S["body"]))

    story.append(Paragraph(
        "The <b>K-core boost</b> addresses a different problem: two nodes with identical PPR scores "
        "may have very different structural importance. A node at k-core level 8 (deeply embedded in "
        "the densely connected graph core) is a better context anchor than a peripheral node at "
        "k-core level 1. The boost formula <font face='Courier' size='9'>score × (1 + k/k_max × 0.5)</font> "
        "rewards centrality without overriding semantic relevance.", S["body"]))

    # 3.4 LLM
    story.append(Paragraph("3.4   LLM Answer Generation", S["h2"]))
    story.append(Paragraph(
        "NodeRAGAnswerer calls the Anthropic Claude API with two prompt-cached blocks: a static "
        "system prompt (cache TTL = 5 minutes) and the assembled context string (also cached if "
        "the same context is re-used). The LLM is instructed to return a structured JSON response "
        "containing:", S["body"]))

    for item in [
        "<b>answer</b> — the direct natural-language answer to the question",
        "<b>reasoning_steps</b> — numbered chain-of-thought over the retrieved nodes",
        "<b>cited_nodes</b> — list of node IDs that support the answer (clickable in the UI)",
        "<b>confidence</b> — self-reported confidence score (0.0–1.0)",
        "<b>suggested_follow_ups</b> — 3 follow-up questions for continued exploration",
    ]:
        story.append(Paragraph(f"• {item}", S["bullet"]))

    # ── SECTION 4: Node Types ─────────────────────────────────────────────────
    story += section_divider("4   The Seven Node Types", color=HexColor("#CF222E"), S=S)
    story.append(Paragraph(
        "The heterogeneous graph is the foundational data structure of the system. Each of the "
        "seven node types encodes a different level of abstraction over the relational database, "
        "from raw schema text (N1) to structurally derived community clusters (N7).",
        S["body"]))

    node_type_data = [
        [Paragraph("<b>Type</b>", S["body"]), Paragraph("<b>Code</b>", S["body"]),
         Paragraph("<b>Count</b>", S["body"]), Paragraph("<b>Description</b>", S["body"]),
         Paragraph("<b>Example</b>", S["body"])],
        ["TextChunk",        "N1", "~22",  "Raw schema: table/view/trigger DDL as text chunks",
         "Table: Products, Columns: ProductID, ProductName, UnitPrice…"],
        ["Entity",           "N2", "≤500\n/table", "One real-world row from any table",
         "Supplier: Exotic Liquids, London, UK. Contact: Charlotte Cooper."],
        ["SemanticUnit",     "N3", "7",   "LLM-summarised clusters of entities sharing a theme",
         "There are 3 products in Beverages. Price range: $4.50–$19.00."],
        ["Relationship",     "N4", "~250","FK instance reified as a first-class node",
         "Order #10248 placed by Customer VINET, shipping to France."],
        ["Attribute",        "N5", "~40", "Column-level fact with business description",
         "Products.UnitPrice: The price in USD charged per unit sold."],
        ["HighLevelInsight", "N6", "5",   "Pre-computed SQL aggregate as a business sentence",
         "Top 3 revenue categories: Confections ($6,874), Meat/Poultry ($2,520)…"],
        ["Community",        "N7", "varies","K-core decomposed structural cluster",
         "324 nodes at k-core level 2, centred around entity_Employees_4."],
    ]

    node_colors_map = {
        "TextChunk": C_N1, "Entity": C_N2, "SemanticUnit": C_N3,
        "Relationship": C_N4, "Attribute": C_N5, "HighLevelInsight": C_N6, "Community": C_N7,
    }

    col_widths = [28*mm, 14*mm, 16*mm, 58*mm, PW - 28*mm - 14*mm - 16*mm - 58*mm]
    node_table = Table(node_type_data, colWidths=col_widths)
    ts = [
        ("BACKGROUND",    (0,0), (-1,0), HexColor("#CF222E")),
        ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [HexColor("#F6F8FA"), colors.white]),
        ("GRID",          (0,0), (-1,-1), 0.4, HexColor("#D0D7DE")),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]
    for i, (name, *_) in enumerate(node_type_data[1:], start=1):
        col = node_colors_map.get(name, C_MUTED)
        ts.append(("BACKGROUND", (0,i), (0,i), col))
        ts.append(("TEXTCOLOR",  (0,i), (0,i), colors.white))
        ts.append(("FONTNAME",   (0,i), (0,i), "Helvetica-Bold"))
    node_table.setStyle(TableStyle(ts))
    story.append(node_table)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph(
        "Only N1–N6 nodes participate in FAISS seeding. Community nodes (N7) are excluded from "
        "initial vector search because their embeddings describe structural patterns rather than "
        "specific entities, which would bias retrieval toward global hubs. They do however "
        "participate in the PPR graph walk and contribute structural scores to the K-core boost.",
        S["body"]))

    # ── SECTION 5: Web Application ────────────────────────────────────────────
    story += section_divider("5   Web Application", color=HexColor("#E36209"), S=S)

    story.append(Paragraph("5.1   FastAPI Backend", S["h2"]))
    story.append(Paragraph(
        "The API layer is a FastAPI application (api/main.py) with a module-level singleton cache "
        "(api/graph_cache.py) that lazily loads the graph, FAISS index, and embedder on first "
        "request, then serves all subsequent requests from memory.",
        S["body"]))

    api_data = [
        [Paragraph("<b>Endpoint</b>", S["body"]), Paragraph("<b>Method</b>", S["body"]),
         Paragraph("<b>Purpose</b>", S["body"])],
        ["GET /api/graph/",             "GET",  "Full graph as JSON (nodes + edges + counts)"],
        ["GET /api/graph/stats",        "GET",  "Node/edge counts by type"],
        ["GET /api/graph/node/{id}",    "GET",  "Full node data (all Pydantic fields)"],
        ["GET /api/graph/subgraph",     "GET",  "Ego-graph: depth + max_nodes pruning"],
        ["POST /api/graph/reload",      "POST", "Flush cache, reload from disk"],
        ["POST /api/query/",            "POST", "SSE stream: seed→ppr→kcore→context→answer"],
    ]
    api_table = Table(api_data, colWidths=[58*mm, 18*mm, PW - 58*mm - 18*mm])
    api_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), HexColor("#E36209")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#F6F8FA"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.4, HexColor("#D0D7DE")),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    story.append(api_table)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph(
        "The query endpoint uses Server-Sent Events (SSE) over a POST body, implemented with "
        "FastAPI's <font face='Courier' size='9'>StreamingResponse(media_type='text/event-stream')</font>. "
        "Each event is a JSON-encoded <font face='Courier' size='9'>data: {...}\\n\\n</font> line. "
        "The frontend consumes this with a "
        "<font face='Courier' size='9'>fetch() + ReadableStream</font> async generator because "
        "the native <font face='Courier' size='9'>EventSource</font> API does not support POST bodies.",
        S["body"]))

    story.append(Paragraph("5.2   React + D3.js Frontend", S["h2"]))
    story.append(Paragraph(
        "The frontend is a React 18 single-page application built with Vite. The D3.js force "
        "simulation runs in a pure ES module class (GraphRenderer.js) instantiated inside a "
        "<font face='Courier' size='9'>useRef</font> — React never owns the SVG subtree, "
        "which prevents the force simulation from restarting on every state change.",
        S["body"]))

    frontend_features = [
        ("Force-directed graph",    "D3 v7, 7 muted node colours, size by k-core number, sinusoidal idle drift"),
        ("Node type filtering",     "FilterBar toggles visibility per type with 150ms opacity transitions"),
        ("Node inspector",          "Click any node → Framer Motion slide-in panel with full node data"),
        ("Subgraph expansion",      "'Expand subgraph' merges 2-hop neighbourhood into the live graph"),
        ("Query console",           "Keyboard-first input, word-by-word answer reveal at 30 ms/word"),
        ("Retrieval log",           "Staggered AnimatePresence rows for each SSE event (seed/ppr/kcore/…)"),
        ("Highlight on retrieval",  "PPR-retrieved nodes transition to full opacity; others dim to 6%"),
        ("Cited node tokens",       "Click any cited ID in the answer to jump to + zoom that node in graph"),
        ("Follow-up queries",       "Suggested follow-ups rendered as clickable text links"),
        ("Keyboard shortcuts",      "/ = focus input · Esc = clear · Ctrl+R = reload graph"),
    ]

    ff_data = [[Paragraph("<b>Feature</b>", S["body"]), Paragraph("<b>Implementation Notes</b>", S["body"])]]
    for f, n in frontend_features:
        ff_data.append([Paragraph(f"<b>{f}</b>", S["body_left"]), Paragraph(n, S["body_left"])])
    ff_table = Table(ff_data, colWidths=[52*mm, PW - 52*mm])
    ff_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), HexColor("#E36209")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#F6F8FA"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.4, HexColor("#D0D7DE")),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ]))
    story.append(ff_table)

    story.append(Paragraph("5.3   State Management Architecture", S["h2"]))
    story.append(Paragraph(
        "Two independent Zustand stores prevent the single most common performance pitfall in "
        "D3 + React applications:", S["body"]))

    store_data = [
        [Paragraph("<b>Store</b>", S["body"]), Paragraph("<b>State</b>", S["body"]),
         Paragraph("<b>Key Actions</b>", S["body"])],
        ["graphStore", "graphData, d3Data, selectedNodeId, visibleTypes, highlightedIds, dimmedIds",
         "fetchGraph, toggleType, setHighlights, clearHighlights, fetchSubgraph, selectNode"],
        ["queryStore", "question, isQuerying, steps[], answer, error, history[]",
         "startQuery, addStep, setAnswer, setError, setQuestion, clearHistory"],
    ]
    st_table = Table(store_data, colWidths=[28*mm, 80*mm, PW - 28*mm - 80*mm])
    st_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), HexColor("#8250DF")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#F6F8FA"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.4, HexColor("#D0D7DE")),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ]))
    story.append(Spacer(1, 2*mm))
    story.append(st_table)
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "Because graphStore and queryStore are independent, a query update (a new retrieval "
        "step arriving, the answer text revealing word by word) never causes the GraphCanvas "
        "component to re-render. D3 animation frames and React render cycles run in completely "
        "separate loops and never compete.", S["body"]))

    # ── SECTION 6: Challenges & Solutions ────────────────────────────────────
    story += section_divider("6   Key Challenges & Solutions", color=HexColor("#953800"), S=S)

    challenges = [
        (
            "Tailwind CSS v4 vs v3 Incompatibility",
            "npm install tailwindcss installs v4 by default, which removed the tailwind.config.js "
            "CLI entirely. Running npx tailwindcss init -p failed silently.",
            "Pinned Tailwind to v3.4 with npm install -D tailwindcss@3 postcss autoprefixer. "
            "The tailwind.config.js with custom colours and font families then worked correctly.",
        ),
        (
            "D3 Force Simulation Restarting on Every React Render",
            "Naive implementations that store the D3 simulation in React state restart the physics "
            "simulation every time any other component updates, causing visible node position jumps.",
            "GraphRenderer.js is a plain ES module class stored in useRef (never React state). "
            "React never touches the SVG subtree; D3 tick loop runs uninterrupted at 60 fps.",
        ),
        (
            "SSE over POST Body (EventSource Limitation)",
            "The native EventSource API only supports GET requests with no body. The query endpoint "
            "requires a POST body (question, top_k, verbose).",
            "queryStream() in api.js uses fetch() + ReadableStream async generator to parse the "
            "text/event-stream response, with full support for POST bodies.",
        ),
        (
            "Vite Proxy Dropping Long-Running SSE Connections",
            "The default Vite proxy timeout drops connections after 30–60 s, cutting off LLM "
            "responses mid-stream.",
            "vite.config.js sets proxyTimeout: 0 (no timeout) for the /api route, preventing "
            "any SSE stream from being terminated prematurely.",
        ),
        (
            "Zustand Set Identity in useEffect Dependencies",
            "Passing a Set directly as a useEffect dependency never triggers the effect on "
            "re-render because React compares by reference, and every new Set is a new object.",
            "Computed visibleTypesKey = [...visibleTypes].sort().join(',') as a string dependency. "
            "String comparison is by value, so type-filter changes reliably trigger D3 updates.",
        ),
        (
            "nx.core_number() on MultiDiGraph",
            "NetworkX's core_number() only accepts undirected simple graphs. Calling it directly "
            "on the MultiDiGraph raised a NetworkXError.",
            "KCoreRanker converts the graph with nx.Graph(G) (simple, undirected projection) "
            "before calling core_number(), then maps core numbers back to the original node IDs.",
        ),
        (
            "PyInstaller + Windows PATH at Runtime",
            "When NodeRAG.exe launches, the spawned processes need python and npm on PATH. "
            "PyInstaller bundles its own Python runtime, which can conflict.",
            "The launcher uses subprocess.Popen with shell=True and start 'title' cmd /k which "
            "opens a new CMD window inheriting the user's full PATH, not PyInstaller's bundled "
            "environment. This ensures uvicorn and npm run from the system Python/Node.",
        ),
        (
            "FastAPI Static Files Shadowing API Routes",
            "Mounting StaticFiles at '/' before registering API routers caused all /api/* "
            "requests to be intercepted and return 404.",
            "StaticFiles is mounted last, after all routers are registered. FastAPI evaluates "
            "routes in registration order, so /api/* is matched before the static fallback.",
        ),
    ]

    for title, problem, solution in challenges:
        chal_table = Table(
            [
                [Paragraph(f"<b>{title}</b>",
                           ParagraphStyle("ct2", fontName="Helvetica-Bold", fontSize=9.5,
                                          leading=14, textColor=HexColor("#953800")))],
                [Paragraph(f"<b>Problem:</b> {problem}", S["body_left"])],
                [Paragraph(f"<b>Solution:</b> {solution}", S["body_left"])],
            ],
            colWidths=[PW]
        )
        chal_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (0,0), HexColor("#FFF8F0")),
            ("BACKGROUND",    (0,1), (0,1), colors.white),
            ("BACKGROUND",    (0,2), (0,2), HexColor("#F0FFF4")),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("BOX",           (0,0), (-1,-1), 0.5, HexColor("#D0D7DE")),
            ("LINEBELOW",     (0,0), (0,0), 0.4, HexColor("#D0D7DE")),
            ("LINEBELOW",     (0,1), (0,1), 0.4, HexColor("#D0D7DE")),
        ]))
        story.append(KeepTogether([chal_table, Spacer(1, 2.5*mm)]))

    # ── SECTION 7: Results ────────────────────────────────────────────────────
    story += section_divider("7   Results & Outcomes", color=HexColor("#0969DA"), S=S)

    story.append(Paragraph("Graph Construction", S["h3"]))
    results_graph = [
        [Paragraph("<b>Metric</b>", S["body"]), Paragraph("<b>Result</b>", S["body"])],
        ["Total nodes in graph",                "539"],
        ["Total edges",                         "901"],
        ["Entity nodes (N2, one per DB row)",   "~350 (7 tables × up to 500/table, deduplicated)"],
        ["Relationship nodes (N4)",             "~250 (FK instances across 6 relationship types)"],
        ["FAISS index size",                    "809 KB (539 × 384-dim float32 vectors)"],
        ["Embedding runtime",                   "~30 s on CPU (all-MiniLM-L6-v2, batch size 32)"],
        ["Full ingest time (no LLM enrichment)","~2–3 minutes (embedding-dominated)"],
        ["K-core max level",                    "≥ 8 (Orders/OrderDetails hub nodes)"],
    ]
    rg_table = Table(results_graph, colWidths=[90*mm, PW - 90*mm])
    rg_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), HexColor("#0969DA")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#F6F8FA"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.4, HexColor("#D0D7DE")),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    story.append(rg_table)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("Retrieval Quality", S["h3"]))
    story.append(Paragraph(
        "The system successfully resolves multi-hop queries that are intractable for standard "
        "flat RAG. The PPR expansion reliably surfaces FK-connected nodes within 2 hops of the "
        "seed set. Cosine similarity scores for direct semantic matches reach 0.67+ on "
        "high-level insight nodes, enabling direct retrieval without chain-of-thought arithmetic.",
        S["body"]))
    story.append(Paragraph(
        "The K-core boost correctly identifies structurally central nodes: Orders, OrderDetails, "
        "and Products consistently receive the highest core numbers, matching domain expectations "
        "for a business dataset where these tables are the transactional hub.", S["body"]))

    story.append(Paragraph("Web Application", S["h3"]))
    story.append(Paragraph(
        "The full-stack web application is production-quality:", S["body"]))
    for item in [
        "D3 force simulation runs at 60 fps uninterrupted during query streaming and answer reveal",
        "SSE streaming delivers retrieval steps and answer tokens in real time with no dropped connections",
        "Node inspector, subgraph expansion, type filtering, zoom controls, and cited-token navigation all function correctly",
        "Responsive layout adapts to narrow viewports (≤1100px: vertical stack, 60/40 split)",
        "Error boundaries prevent graph or query failures from crashing the entire application",
        "Keyboard shortcuts (/, Esc, Ctrl+R) provide full keyboard-navigable workflow",
    ]:
        story.append(Paragraph(f"• {item}", S["bullet"]))

    story.append(Paragraph("Deployment", S["h3"]))
    story.append(Paragraph(
        "NodeRAG.exe (8.4 MB, PyInstaller one-file bundle) launches the complete system — "
        "API server, frontend dev server, and browser — from a single double-click. No Python "
        "installation, no terminal, no npm commands required by the end user. The launcher "
        "opens named CMD windows for each server, polls the API health endpoint, and opens "
        "the browser automatically once the stack is ready.", S["body"]))

    # ── SECTION 8: Multi-Hop Queries ─────────────────────────────────────────
    story += section_divider("8   Multi-Hop Query Examples", color=HexColor("#1A7F37"), S=S)

    queries = [
        (
            "3-hop: Supplier → Product → Order → Customer",
            "Which suppliers from the UK supply products that were ordered by customers in Germany?",
            "Suppliers[Country=UK] → Products[SupplierID] → OrderDetails[ProductID] → Orders[OrderID] → Customers[Country=Germany]",
        ),
        (
            "2-hop: Employee hierarchy + Revenue",
            "What is the total revenue from orders handled by employees who report to the same manager as Janet Leverling?",
            "Employees[Janet Leverling] → Employees[ReportsTo=2] → Orders[EmployeeID] → OrderDetails[UnitPrice × Quantity × (1-Discount)]",
        ),
        (
            "2-hop: Category + Discount aggregation",
            "Which product categories have the highest average discount rate?",
            "Categories → Products[CategoryID] → OrderDetails[ProductID, Discount]",
        ),
        (
            "3-hop: Discontinued products + Order history",
            "Which customers have ordered products that are now discontinued?",
            "Products[Discontinued=1] → OrderDetails[ProductID] → Orders[OrderID] → Customers[CustomerID]",
        ),
        (
            "N6 insight + Shipping analysis",
            "What is the shipping profile of our top 3 revenue-generating customers?",
            "N6 insight[top_customers_by_revenue] → Orders[CustomerID, ShipCountry, Freight]",
        ),
    ]

    for hop_label, question, chain in queries:
        q_data = [
            [Paragraph(f"<b>{hop_label}</b>",
                       ParagraphStyle("hl", fontName="Helvetica-Bold", fontSize=9,
                                      leading=13, textColor=HexColor("#1A7F37")))],
            [Paragraph(f'<i>"{question}"</i>',
                       ParagraphStyle("qtext", fontName="Helvetica-Oblique", fontSize=9.5,
                                      leading=14, textColor=C_BODY_TEXT))],
            [Paragraph(f'<font face="Courier" size="8.5">{chain}</font>',
                       ParagraphStyle("chain", fontName="Courier", fontSize=8.5,
                                      leading=13, textColor=HexColor("#57606A"),
                                      backColor=HexColor("#F6F8FA"), leftIndent=4))],
        ]
        q_table = Table(q_data, colWidths=[PW])
        q_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (0,0), HexColor("#DAFBE1")),
            ("BACKGROUND",    (0,1), (0,1), colors.white),
            ("BACKGROUND",    (0,2), (0,2), HexColor("#F6F8FA")),
            ("BOX",           (0,0), (-1,-1), 0.5, HexColor("#D0D7DE")),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.append(KeepTogether([q_table, Spacer(1, 2.5*mm)]))

    # ── SECTION 9: Tech Stack ─────────────────────────────────────────────────
    story += section_divider("9   Technology Stack", color=HexColor("#6F42C1"), S=S)

    stack_data = [
        [Paragraph("<b>Layer</b>", S["body"]), Paragraph("<b>Technology</b>", S["body"]),
         Paragraph("<b>Version</b>", S["body"]), Paragraph("<b>Role</b>", S["body"])],
        # Backend
        ["Language",        "Python",                   "3.11+",    "All backend, CLI, ingestion pipeline"],
        ["Graph",           "NetworkX",                 "3.x",      "MultiDiGraph construction, PPR, k-core"],
        ["Embedding",       "sentence-transformers",    "latest",   "all-MiniLM-L6-v2, 384-dim unit vectors"],
        ["Vector Index",    "FAISS (faiss-cpu)",         "latest",   "IndexFlatIP, exact inner-product search"],
        ["LLM API",         "Anthropic Python SDK",     "latest",   "Claude Haiku, prompt caching"],
        ["API Framework",   "FastAPI + Uvicorn",        "latest",   "REST + SSE streaming, CORS"],
        ["Validation",      "Pydantic v2",              "2.x",      "DTOs, node type models, config"],
        ["CLI",             "Click + Rich",             "latest",   "ingest / ask / interactive / stats / demo"],
        # Frontend
        ["Frontend",        "React 18",                 "18.x",     "SPA, component tree, hooks"],
        ["Build",           "Vite",                     "8.x",      "Dev server (:5173), HMR, proxy, prod build"],
        ["D3.js",           "D3 v7",                    "7.9",      "Force simulation, zoom, drag"],
        ["State",           "Zustand",                  "5.x",      "Two independent stores (graph + query)"],
        ["Styling",         "Tailwind CSS",             "3.4",      "Custom dark theme, responsive breakpoints"],
        ["Animation",       "Framer Motion",            "latest",   "Node inspector slide, retrieval log stagger"],
        ["Data Fetching",   "TanStack Query",           "latest",   "Server state for graph stats"],
        # Deployment
        ["Launcher",        "PyInstaller",              "6.x",      "One-file Windows .exe (8.4 MB)"],
        ["Database",        "SQLite",                   "3.x",      "Northwind sample database (76 KB)"],
    ]

    cw = [28*mm, 38*mm, 18*mm, PW - 28*mm - 38*mm - 18*mm]
    st_table = Table(stack_data, colWidths=cw)
    ts2 = [
        ("BACKGROUND",   (0,0), (-1,0), HexColor("#6F42C1")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#F6F8FA"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.4, HexColor("#D0D7DE")),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
    ]
    section_rows = {1: "Backend", 10: "Frontend", 16: "Deployment"}
    for row_i in range(1, len(stack_data)):
        if row_i in section_rows:
            ts2.append(("BACKGROUND", (0,row_i), (-1,row_i), HexColor("#EFF2F5")))
            ts2.append(("FONTNAME",   (0,row_i), (-1,row_i), "Helvetica-Bold"))
    st_table.setStyle(TableStyle(ts2))
    story.append(st_table)

    # ── SECTION 10: Conclusions ───────────────────────────────────────────────
    story += section_divider("10   Conclusions", color=HexColor("#0D1117"), S=S)

    story.append(Paragraph(
        "NodeRAG demonstrates that graph-based RAG is not just theoretically superior to flat "
        "vector RAG for relational data — it is <b>practically buildable</b> as a production "
        "system within a single codebase of reasonable size. The key insight is that reifying "
        "foreign-key relationships as first-class graph nodes transforms a multi-table JOIN "
        "problem into a graph walk problem, which Personalised PageRank solves elegantly.",
        S["body"]))
    story.append(Paragraph(
        "The K-core boost adds a structural dimension that pure vector search cannot capture: "
        "knowing that Orders is the most structurally central table (highest k-core) allows the "
        "retriever to prioritise it as a context anchor even for queries that don't mention orders "
        "directly. This structural awareness is what enables the system to answer queries like "
        "<i>\"What is the shipping profile of our top customers?\"</i> without requiring the user "
        "to specify the JOIN path.", S["body"]))
    story.append(Paragraph(
        "The web application delivers a qualitatively different experience from a standard RAG "
        "chatbot: the force-directed graph makes the knowledge structure visible and explorable, "
        "the retrieval log makes the retrieval process transparent, and cited node tokens create "
        "a direct link between the LLM's answer and the underlying graph evidence.",
        S["body"]))

    story.append(Paragraph("Limitations & Future Work", S["h3"]))
    for item in [
        "<b>Scale:</b> The current FAISS IndexFlatIP performs exact search — suitable for 539 nodes "
        "but would need HNSW or IVF indexing for graphs with millions of nodes.",
        "<b>Graph freshness:</b> The graph is built at ingest time. A production system would need "
        "an incremental update mechanism to reflect live database changes.",
        "<b>LLM enrichment:</b> Running noderag ingest --enrich generates richer node descriptions "
        "via Claude but is not run by default. Enriched descriptions would improve retrieval quality "
        "for queries that rely on semantic understanding rather than exact matches.",
        "<b>Multi-database support:</b> The current implementation is Northwind-specific. "
        "Generalising the FK-traversal and schema extraction to arbitrary SQLite/PostgreSQL "
        "databases would significantly broaden applicability.",
        "<b>Evaluation benchmark:</b> No formal retrieval accuracy benchmark was run against "
        "a ground-truth QA dataset. Adding a BEIR-style evaluation would quantify the PPR + K-core "
        "gains over baseline flat RAG.",
    ]:
        story.append(Paragraph(f"• {item}", S["bullet"]))

    story.append(Spacer(1, 6*mm))
    story.append(ColorBar(PW, height=2, color=C_ACCENT))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "<i>Based on: Xu et al. (2025). NodeRAG: Structuring Graph-based RAG with Heterogeneous "
        "Nodes. arXiv:2504.11544</i>",
        ParagraphStyle("ref", fontName="Helvetica-Oblique", fontSize=8.5, leading=13,
                       textColor=C_MUTED, alignment=TA_CENTER)))

    return story


# ── Build document ────────────────────────────────────────────────────────────
def build_pdf(output_path="NodeRAG_Project_Report.pdf"):
    tmpl = PageTemplate()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="NodeRAG: Structural Intelligence over Relational Databases",
        author="NodeRAG Project",
        subject="Technical Project Report",
        creator="NodeRAG Report Generator",
    )

    S = build_styles()
    story = cover_page(S) + toc_page(S) + build_story(S)

    # Build with page callbacks
    def on_page(canv, doc):
        if doc.page == 1:
            tmpl.on_cover(canv, doc)
        else:
            tmpl.on_page(canv, doc)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    import os
    out = os.path.join(os.path.dirname(__file__), "NodeRAG_Project_Report.pdf")
    build_pdf(out)
