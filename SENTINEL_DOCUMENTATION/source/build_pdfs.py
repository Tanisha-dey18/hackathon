"""Builds the Sentinel documentation set from the Markdown sources in this folder.

Run from the repository root:
    backend/.venv/Scripts/python SENTINEL_DOCUMENTATION/source/build_pdfs.py
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ASSETS = OUT / "assets"
sys.path.insert(0, str(HERE))
from diagrams import DIAGRAMS  # noqa: E402

AUTHOR = "Tanisha Dey"
DOC_DATE = "October 2026"

# ----------------------------------------------------------------------------- fonts
FONT_DIR = Path("C:/Windows/Fonts")
FONTS = {"Body": "segoeui.ttf", "Body-Bold": "segoeuib.ttf", "Body-Italic": "segoeuii.ttf",
         "Body-BoldItalic": "segoeuiz.ttf", "Body-Semi": "seguisb.ttf", "Mono": "consola.ttf", "Mono-Bold": "consolab.ttf"}
FALLBACK = {"Body": "DejaVuSans.ttf", "Body-Bold": "DejaVuSans-Bold.ttf", "Body-Italic": "DejaVuSans-Oblique.ttf",
            "Body-BoldItalic": "DejaVuSans-BoldOblique.ttf", "Body-Semi": "DejaVuSans-Bold.ttf",
            "Mono": "DejaVuSansMono.ttf", "Mono-Bold": "DejaVuSansMono-Bold.ttf"}
for name, fn in FONTS.items():
    path = FONT_DIR / fn
    if not path.exists():
        path = FONT_DIR / FALLBACK[name]
    pdfmetrics.registerFont(TTFont(name, str(path)))  # TrueType fonts are embedded (subset) in the PDF
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic")
pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold", italic="Mono", boldItalic="Mono-Bold")

# ----------------------------------------------------------------------------- palette & styles
NAVY = colors.HexColor("#0B1A33")
NAVY2 = colors.HexColor("#16305A")
CYAN = colors.HexColor("#00A9CC")
CYAN_D = colors.HexColor("#007E99")
INK = colors.HexColor("#1B2433")
MUTED = colors.HexColor("#5B6B82")
RULE = colors.HexColor("#D6E0EC")
SOFT = colors.HexColor("#F3F7FB")
CALLOUT = colors.HexColor("#E8F7FB")

PAGE_W, PAGE_H = A4
MARGIN_X = 20 * mm
FRAME_W = PAGE_W - 2 * MARGIN_X

S = {
    "part": ParagraphStyle("part", fontName="Body-Bold", fontSize=19, leading=24, textColor=NAVY, spaceBefore=2, spaceAfter=4),
    "partno": ParagraphStyle("partno", fontName="Body-Semi", fontSize=9, leading=12, textColor=CYAN_D, spaceAfter=0),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=12.6, leading=16, textColor=NAVY2, spaceBefore=12, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="Body-Bold", fontSize=10.4, leading=14, textColor=CYAN_D, spaceBefore=9, spaceAfter=3),
    "body": ParagraphStyle("body", fontName="Body", fontSize=9.6, leading=14.2, textColor=INK, spaceAfter=5),
    "bullet": ParagraphStyle("bullet", fontName="Body", fontSize=9.6, leading=13.8, textColor=INK, leftIndent=14,
                             bulletIndent=4, spaceAfter=2.5, bulletFontName="Body"),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8, leading=10.4, textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="Body-Bold", fontSize=8, leading=10.4, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.8, leading=10.2, textColor=NAVY),
    "caption": ParagraphStyle("caption", fontName="Body-Italic", fontSize=8.2, leading=11, textColor=MUTED,
                              alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
    "callout": ParagraphStyle("callout", fontName="Body", fontSize=9.4, leading=13.6, textColor=NAVY),
    "toc1": ParagraphStyle("toc1", fontName="Body-Bold", fontSize=9.8, leading=15, textColor=NAVY, leftIndent=0),
    "toc2": ParagraphStyle("toc2", fontName="Body", fontSize=8.8, leading=12.4, textColor=MUTED, leftIndent=14),
}


# ----------------------------------------------------------------------------- inline markdown
def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    codes: list[str] = []

    def keep_code(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: f'<font name="Mono" color="#0A5C70">{codes[int(m.group(1))]}</font>', text)
    return text


# ----------------------------------------------------------------------------- flowables
class PartHeader(Flowable):
    """Navy band used for PART headings; registers itself in the TOC."""

    def __init__(self, number: str, title: str):
        super().__init__()
        self.number, self.title = number, title
        self.width, self.height = FRAME_W, 58

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=0)
        c.setFillColor(CYAN)
        c.rect(0, 0, 5, self.height, fill=1, stroke=0)
        c.setFont("Body-Semi", 8.5)
        c.drawString(18, self.height - 20, self.number.upper())
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 17)
        c.drawString(18, 15, self.title)


class Callout(Flowable):
    def __init__(self, text: str):
        super().__init__()
        self.p = Paragraph(inline(text), S["callout"])

    def wrap(self, aw, ah):
        self.w = aw
        _, h = self.p.wrap(aw - 26, ah)
        self.h = h + 16
        return aw, self.h

    def draw(self):
        c = self.canv
        c.setFillColor(CALLOUT)
        c.roundRect(0, 0, self.w, self.h, 4, fill=1, stroke=0)
        c.setFillColor(CYAN)
        c.rect(0, 0, 3.5, self.h, fill=1, stroke=0)
        self.p.drawOn(c, 16, 8)


def make_table(rows: list[list[str]]) -> Table:
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    from reportlab.pdfbase.pdfmetrics import stringWidth

    def plain(t):
        return re.sub(r"[`*]", "", t)

    mins, weights = [], []
    for j in range(ncol):
        words = [w for r in rows for w in re.split(r"[\s/]+", plain(r[j])) if w]
        longest = max((stringWidth(w, "Body-Bold", 8) for w in words), default=20)
        mins.append(min(longest + 11, 128))
        lengths = [min(len(plain(r[j])), 70) for r in rows]
        weights.append(max(6, sum(lengths) / len(lengths) * 0.6 + max(lengths) * 0.4))
    spare = max(FRAME_W - sum(mins), 0)
    total = sum(weights)
    widths = [m + spare * w / total for m, w in zip(mins, weights)]
    scale = FRAME_W / sum(widths)
    widths = [w * scale for w in widths]
    data = [[Paragraph(inline(c), S["cellh"] if i == 0 else S["cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    return t


class Counter:
    figure = 0


def figure_caption(text: str) -> Paragraph:
    Counter.figure += 1
    return Paragraph(f"Figure {Counter.figure}: {inline(text)}", S["caption"])


def diagram_flowables(key: str):
    fn, caption = DIAGRAMS[key]
    d = fn(FRAME_W)
    return [KeepTogether([Spacer(1, 4), d, figure_caption(caption)])]


def image_flowables(name: str, caption: str):
    path = ASSETS / f"{name}.jpg"
    if not path.exists():
        raise FileNotFoundError(path)
    from reportlab.lib.utils import ImageReader

    iw, ih = ImageReader(str(path)).getSize()
    w = FRAME_W
    h = w * ih / iw
    if h > 120 * mm:
        h = 120 * mm
        w = h * iw / ih
    img = Image(str(path), width=w, height=h)
    frame = Table([[img]], colWidths=[w + 2], hAlign="CENTER")
    frame.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("LEFTPADDING", (0, 0), (-1, -1), 1),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return [KeepTogether([Spacer(1, 3), frame, figure_caption(caption)])]


def md_to_flowables(md: str, part_breaks: bool = True) -> list:
    out: list = []
    lines = md.splitlines()
    i = 0
    first_part = True
    para: list[str] = []

    def flush():
        if para:
            out.append(Paragraph(inline(" ".join(para)), S["body"]))
            para.clear()

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            flush()
            i += 1
            continue
        if s.startswith("```"):
            flush()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(lines[j])
                j += 1
            pre = Preformatted("\n".join(buf), S["code"])
            t = Table([[pre]], colWidths=[FRAME_W])
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
            out += [t, Spacer(1, 6)]
            i = j + 1
            continue
        m = re.match(r"^\[\[(DIAGRAM|IMG):([^|\]]+)(?:\|([^\]]*))?\]\]$", s)
        if m:
            flush()
            figs = diagram_flowables(m.group(2)) if m.group(1) == "DIAGRAM" else image_flowables(m.group(2), m.group(3) or "")
            if len(out) >= 2 and isinstance(out[-1], Paragraph) and out[-1].style.name in ("h2", "h3"):
                head = out.pop()
                if isinstance(out[-1], CondPageBreak):
                    out.pop()
                figs = [KeepTogether([head] + figs[0]._content)]
            out += figs
            i += 1
            continue
        if s.startswith("# "):
            flush()
            title = s[2:].strip()
            pm = re.match(r"PART (\d+):\s*(.+)", title)
            if part_breaks and not first_part:
                out.append(PageBreak())
            first_part = False
            if pm:
                hdr = PartHeader(f"Part {pm.group(1)}", pm.group(2))
                hdr._toc = (0, f"Part {pm.group(1)}: {pm.group(2)}")
            else:
                hdr = PartHeader("Sentinel", title)
                hdr._toc = (0, title)
            out += [hdr, Spacer(1, 10)]
            i += 1
            continue
        if s.startswith("## "):
            flush()
            p = Paragraph(inline(s[3:]), S["h2"])
            p._toc = (1, re.sub(r"<[^>]+>", "", inline(s[3:])))
            out += [CondPageBreak(60), p]
            i += 1
            continue
        if s.startswith("### "):
            flush()
            block = [Paragraph(inline(s[4:]), S["h3"])]
            i += 1
            # Q&A blocks: keep the question with its "**Short answer:**" / "**Deeper explanation:**" lines
            while i < len(lines) and lines[i].strip().startswith("**"):
                block.append(Paragraph(inline(lines[i].strip()), S["body"]))
                i += 1
            out += [CondPageBreak(48), KeepTogether(block) if len(block) > 1 else block[0]]
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            out += [make_table(rows), Spacer(1, 8)]
            continue
        if s.startswith("> "):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out += [Spacer(1, 2), Callout(" ".join(buf)), Spacer(1, 8)]
            continue
        bm = re.match(r"^(- |\d+\. )(.*)$", s)
        if bm:
            flush()
            marker = "•" if bm.group(1) == "- " else bm.group(1).strip()
            out.append(Paragraph(inline(bm.group(2)), S["bullet"], bulletText=marker))
            i += 1
            continue
        if s.startswith("**") and para == []:
            # Q&A label lines ("**Short answer:** ...") render as their own paragraphs
            out.append(Paragraph(inline(s), S["body"]))
            i += 1
            continue
        para.append(s)
        i += 1
    flush()
    return out


# ----------------------------------------------------------------------------- document
class SentinelDoc(BaseDocTemplate):
    def __init__(self, path, doc_title, toc=True, **kw):
        super().__init__(str(path), pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=22 * mm,
                         bottomMargin=20 * mm, title=f"PROJECT SENTINEL: {doc_title}", author=AUTHOR,
                         subject="PayPal AI Hackathon 2026", creator="ReportLab", **kw)
        self.doc_title = doc_title
        frame = Frame(MARGIN_X, 20 * mm, FRAME_W, PAGE_H - 42 * mm, id="body", leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate("cover", frames=[frame], onPage=self._cover),
                               PageTemplate("body", frames=[frame], onPage=self._decor)])

    def afterFlowable(self, f):
        toc = getattr(f, "_toc", None)
        if toc:
            level, text = toc
            key = f"toc{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, text, self.page, key))

    def _decor(self, c, doc):
        c.saveState()
        c.setFillColor(NAVY)
        c.rect(0, PAGE_H - 13 * mm, PAGE_W, 13 * mm, fill=1, stroke=0)
        c.setFillColor(CYAN)
        c.rect(0, PAGE_H - 13.6 * mm, PAGE_W, 0.6 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 8.5)
        c.drawString(MARGIN_X, PAGE_H - 8.3 * mm, "PROJECT SENTINEL")
        c.setFont("Body", 8.5)
        c.drawString(MARGIN_X + 82, PAGE_H - 8.3 * mm, f"·  {self.doc_title}")
        c.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 8.3 * mm, "PayPal AI Hackathon 2026")
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MARGIN_X, 13 * mm, PAGE_W - MARGIN_X, 13 * mm)
        c.setFillColor(MUTED)
        c.setFont("Body", 7.4)
        c.drawString(MARGIN_X, 8.5 * mm, "Hackathon prototype · PayPal Sandbox · synthetic data · not an official PayPal product")
        c.setFont("Body-Bold", 8)
        c.setFillColor(NAVY)
        c.drawRightString(PAGE_W - MARGIN_X, 8.5 * mm, f"Page {doc.page}")
        c.restoreState()

    def _cover(self, c, doc):
        c.saveState()
        c.setFillColor(NAVY)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        # subtle network motif
        c.setStrokeColor(colors.HexColor("#1D3A66"))
        c.setLineWidth(0.7)
        pts = [(380, 760), (470, 700), (520, 790), (430, 640), (540, 610), (330, 690), (500, 520)]
        for a in pts:
            for b in pts:
                if a < b and abs(a[0] - b[0]) + abs(a[1] - b[1]) < 220:
                    c.line(*a, *b)
        for x, y in pts:
            c.setFillColor(CYAN)
            c.circle(x, y, 4.2, fill=1, stroke=0)
        c.setFillColor(CYAN)
        c.rect(MARGIN_X, PAGE_H - 330, 46, 3.2, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#8FB8D8"))
        c.setFont("Body-Semi", 10.5)
        c.drawString(MARGIN_X, PAGE_H - 300, doc.doc_title.upper())
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 38)
        c.drawString(MARGIN_X, PAGE_H - 380, "PROJECT SENTINEL")
        c.setFont("Body-Semi", 15)
        c.drawString(MARGIN_X, PAGE_H - 410, "Autonomous AI-Powered Payment Risk Intelligence")
        c.drawString(MARGIN_X, PAGE_H - 430, "& Protection Platform")
        c.setFillColor(colors.HexColor("#A9C0DA"))
        c.setFont("Body", 10.5)
        c.drawString(MARGIN_X, PAGE_H - 460, "Combining Machine Learning, Graph Intelligence, Agentic AI")
        c.drawString(MARGIN_X, PAGE_H - 475, "and PayPal Payment Infrastructure")
        y = 250
        for label, value in (("PREPARED FOR", "PayPal AI Hackathon 2026"), ("PREPARED BY", AUTHOR), ("DATE", DOC_DATE)):
            c.setFillColor(CYAN)
            c.setFont("Body-Semi", 8)
            c.drawString(MARGIN_X, y, label)
            c.setFillColor(colors.white)
            c.setFont("Body-Bold", 12.5)
            c.drawString(MARGIN_X, y - 16, value)
            y -= 44
        c.setFillColor(colors.HexColor("#122748"))
        c.roundRect(MARGIN_X, 40, FRAME_W, 50, 5, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#C6D5E8"))
        c.setFont("Body", 7.8)
        c.drawString(MARGIN_X + 12, 72, "Disclaimer: Sentinel is a hackathon prototype. It runs on PayPal Sandbox with synthetic data only and is not")
        c.drawString(MARGIN_X + 12, 60, "an official, deployed or endorsed PayPal fraud-prevention product. It does not access PayPal's internal risk systems.")
        c.drawString(MARGIN_X + 12, 48, "Model results describe synthetic data and are not evidence of real-world performance.")
        c.restoreState()


def front_matter(doc_title: str, purpose: str, toc: bool, about: bool = True) -> list:
    flow: list = [NextPageTemplate("body"), PageBreak()]
    if not about:
        return flow
    flow.append(Paragraph("About this document", S["h2"]))
    flow.append(Paragraph(inline(purpose), S["body"]))
    flow.append(Spacer(1, 4))
    flow.append(make_table([
        ["Item", "Detail"],
        ["Project", "PROJECT SENTINEL: Autonomous AI-Powered Payment Risk Intelligence & Protection Platform"],
        ["Prepared for", "PayPal AI Hackathon 2026"],
        ["Prepared by", AUTHOR],
        ["Source of truth", "The repository (backend/, frontend/, docs/). Every metric and test result was taken from the running system or its test suite."],
        ["Repository", "github.com/Tanisha-dey18/hackathon"],
        ["Generated", date.today().isoformat()],
    ]))
    flow.append(Spacer(1, 8))
    flow.append(Callout(
        "**Disclaimer.** Sentinel is a hackathon prototype using PayPal Sandbox and synthetic data. It is not an officially "
        "deployed PayPal fraud prevention product and has no access to PayPal's internal systems. Features that are designed but "
        "not implemented are labelled **Future Scope**, and integrations that are implemented but were not executed live are "
        "labelled as such."))
    if toc:
        flow.append(PageBreak())
        flow.append(Paragraph("Contents", S["part"]))
        flow.append(Spacer(1, 6))
        t = TableOfContents()
        t.levelStyles = [S["toc1"], S["toc2"]]
        t.dotsMinLevel = 0
        flow.append(t)
    flow.append(PageBreak())
    return flow


def split_parts(md: str) -> dict[int, str]:
    parts: dict[int, str] = {}
    chunks = re.split(r"(?m)^(?=# PART \d+:)", md)
    for ch in chunks:
        m = re.match(r"# PART (\d+):", ch)
        if m:
            parts[int(m.group(1))] = ch
    return parts


def build(path: Path, doc_title: str, purpose: str, md: str, toc: bool = True, about: bool = True):
    Counter.figure = 0
    doc = SentinelDoc(path, doc_title)
    story = [Spacer(1, 1)] + front_matter(doc_title, purpose, toc, about) + md_to_flowables(md)
    if toc:
        doc.multiBuild(story)
    else:
        doc.build(story)
    return path


def export_markdown(full_md: str, quick_md: str):
    """Editable Markdown deliverable: diagrams exported as SVG, screenshots linked from assets/."""
    diag_dir = ASSETS / "diagrams"
    diag_dir.mkdir(parents=True, exist_ok=True)
    for key, (fn, _) in DIAGRAMS.items():
        renderSVG.drawToFile(fn(482), str(diag_dir / f"{key}.svg"))

    def repl(m):
        kind, name, cap = m.group(1), m.group(2), m.group(3)
        if kind == "DIAGRAM":
            return f"![{DIAGRAMS[name][1]}](assets/diagrams/{name}.svg)\n\n*{DIAGRAMS[name][1]}*"
        return f"![{cap}](assets/{name}.jpg)\n\n*{cap}*"

    body = re.sub(r"(?m)^\[\[(DIAGRAM|IMG):([^|\]]+)(?:\|([^\]]*))?\]\]$", repl, full_md)
    header = (f"# PROJECT SENTINEL\n\n**Autonomous AI-Powered Payment Risk Intelligence & Protection Platform**\n\n"
              f"*Combining Machine Learning, Graph Intelligence, Agentic AI and PayPal Payment Infrastructure.*\n\n"
              f"Prepared for: PayPal AI Hackathon 2026 · Prepared by: {AUTHOR} · {DOC_DATE}\n\n"
              "> **Disclaimer.** Hackathon prototype using PayPal Sandbox and synthetic data. Not an officially deployed PayPal "
              "fraud prevention product.\n\n"
              "This file is the editable source of the PDF documentation set (regenerate with "
              "`backend/.venv/Scripts/python SENTINEL_DOCUMENTATION/source/build_pdfs.py`).\n\n---\n\n")
    quick = re.sub(r"(?m)^\[\[(DIAGRAM|IMG):([^|\]]+)(?:\|([^\]]*))?\]\]$", repl, quick_md).replace("# Sentinel at a Glance", "# APPENDIX: Quick Overview", 1)
    (OUT / "SENTINEL_Project_Documentation.md").write_text(header + body + "\n\n---\n\n" + quick, encoding="utf-8")


def main():
    srcs = [HERE / f"part_{x}.md" for x in "abcde"]
    full = "\n\n".join(p.read_text(encoding="utf-8") for p in srcs)
    quick = (HERE / "quick_overview.md").read_text(encoding="utf-8")
    parts = split_parts(full)
    assert sorted(parts) == list(range(1, 21)), sorted(parts)

    build(OUT / "SENTINEL_Complete_Project_Report.pdf", "Complete Project Report",
          "The complete technical and non-technical report: problem, solution, architecture, implementation, PayPal "
          "integration, testing, limitations, interview preparation and personal pitches. Parts 1 to 4 are written for "
          "non-technical readers; Parts 5 to 12 for engineers and judges.", full)

    tech = "\n\n".join(parts[n] for n in (5, 6, 7, 8, 9, 10, 11, 12, 15, 17))
    build(OUT / "SENTINEL_Technical_Architecture.pdf", "Technical Architecture",
          "An engineering-focused extract of the complete report: architecture, technology stack, ML pipeline, graph "
          "intelligence, investigation agent, PayPal integration, database and API, security, testing and limitations.", tech)

    build(OUT / "SENTINEL_Project_Quick_Overview.pdf", "Project Quick Overview",
          "A short overview for recruiters and judges. See the Complete Project Report for details.", quick, toc=False,
          about=False)

    viva = parts[19] + "\n\n" + parts[20]
    build(OUT / "SENTINEL_Viva_and_Interview_Guide.pdf", "Viva and Interview Guide",
          "The full question bank (110 questions with short answers, deeper explanations and follow-ups) plus the elevator "
          "pitch, 2-minute and 5-minute explanations, and resume, LinkedIn, GitHub and submission descriptions.", viva)

    export_markdown(full, quick)
    print("built")


if __name__ == "__main__":
    main()
