#!/usr/bin/env python3
"""
Pre-build test: validira PDF generacijo za vse dokumente v obeh jezikih.
Poženi pred `docker build` s `python3 tests/test_pdf.py`.
Če karkoli pade → exit code 1 → ne buildaj.
"""
import sys
import re
from pathlib import Path

# Add app to path so we can import the PDF generator directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

# ── Minimalni PDF generator (kopiran iz docs.py, brez FastAPI odvisnosti) ──
from fpdf import FPDF

class DocPDF(FPDF):
    def __init__(self):
        super().__init__()
        self._add_font_safe("DejaVu", "", "DejaVuSans.ttf")
        self._add_font_safe("DejaVu", "B", "DejaVuSans-Bold.ttf")
        self._add_font_safe("DejaVu", "I", "DejaVuSans-Oblique.ttf", "DejaVuSans.ttf")
        self._add_font_safe("DejaVu", "BI", "DejaVuSans-BoldOblique.ttf", "DejaVuSans-Bold.ttf")
        self._add_font_safe("DejaVuMono", "", "DejaVuSansMono.ttf")
        self._add_font_safe("DejaVuMono", "B", "DejaVuSansMono-Bold.ttf")

    @staticmethod
    def _font_path(fname: str) -> str:
        return f"/usr/share/fonts/truetype/dejavu/{fname}"

    def _add_font_safe(self, family, style, fname, fallback=None):
        path = self._font_path(fname)
        if Path(path).exists():
            self.add_font(family, style, path, uni=True)
        elif fallback:
            fb_path = self._font_path(fallback)
            if Path(fb_path).exists():
                self.add_font(family, style, fb_path, uni=True)

    def header(self):
        if self.page_no() > 1:
            self.set_font("DejaVu", "I", 7)
            self.set_text_color(150, 150, 150)
            self.cell(0, 5, "ostc-app — Dokumentacija", align="L")
            self.cell(0, 5, f"Str. {self.page_no()}/{{nb}}", align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(200, 200, 200)
            self.line(10, 12, 200, 12)
            self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "I", 7)
        self.set_text_color(180, 180, 180)
        self.cell(0, 10, "OŠ Toneta Čufarja Jesenice", align="C")


def _strip_inline(text):
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    return text


def _needs_page_break(pdf, needed_mm=25):
    if pdf.get_y() + needed_mm > 297 - 20:
        pdf.add_page()
        return True
    return False


def _pdf_heading(pdf, text, level):
    _needs_page_break(pdf, 20)
    sizes = {1: 16, 2: 13, 3: 11, 4: 10}
    colors = {1: (26, 26, 46), 2: (26, 26, 46), 3: (74, 108, 247), 4: (50, 50, 50)}
    pdf.set_font("DejaVu", "B", sizes.get(level, 11))
    pdf.set_text_color(*colors.get(level, (50, 50, 50)))
    pdf.multi_cell(0, sizes.get(level, 11) * 0.5, text, new_x="LMARGIN", new_y="NEXT")
    if level <= 2:
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.3)
        pdf.line(10, pdf.get_y() + 1, 200, pdf.get_y() + 1)
    pdf.ln(2 + max(0, 2 - level))


def _pdf_paragraph(pdf, text):
    _needs_page_break(pdf, 8)
    pdf.set_font("DejaVu", "", 9.5)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)


def _pdf_bullet_list(pdf, items):
    for item in items:
        _needs_page_break(pdf, 6)
        pdf.set_font("DejaVu", "", 9.5)
        pdf.set_text_color(50, 50, 50)
        x0 = pdf.get_x()
        pdf.cell(6, 5, "•")
        pdf.multi_cell(0, 5, item, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x0 + 6)
    pdf.ln(1.5)


def _pdf_hr(pdf):
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    y = pdf.get_y()
    pdf.line(10, y, 200, y)
    pdf.ln(4)


def _render_md_to_pdf(pdf, md):
    """Simplified render — tests that nothing crashes and output looks reasonable."""
    md = re.sub(r'^🌐.*?\n---\s*\n', '', md, count=1, flags=re.DOTALL)
    md = re.sub(r'^---\s*\n.*?\n---\s*\n', '', md, count=1, flags=re.DOTALL)

    lines = md.split("\n")
    i, n = 0, len(lines)
    in_bullet, bullet_items = False, []

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            if in_bullet and bullet_items:
                _pdf_bullet_list(pdf, bullet_items)
                bullet_items = []
                in_bullet = False
            i += 1
            continue

        if re.match(r"^-{3,}$", stripped):
            if bullet_items:
                _pdf_bullet_list(pdf, bullet_items)
                bullet_items = []
                in_bullet = False
            _pdf_hr(pdf)
            i += 1
            continue

        h = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if h:
            if bullet_items:
                _pdf_bullet_list(pdf, bullet_items)
                bullet_items = []
                in_bullet = False
            level = len(h.group(1))
            _pdf_heading(pdf, _strip_inline(h.group(2)), level)
            i += 1
            continue

        bl = re.match(r"^- (.+)$", stripped)
        if bl:
            in_bullet = True
            bullet_items.append(_strip_inline(bl.group(1)))
            i += 1
            continue
        if in_bullet and stripped.startswith(("  ", "\t")):
            if bullet_items:
                bullet_items[-1] += " " + _strip_inline(stripped)
            i += 1
            continue

        nl = re.match(r"^\d+\.\s(.+)$", stripped)
        if nl:
            if bullet_items:
                _pdf_bullet_list(pdf, bullet_items)
                bullet_items = []
                in_bullet = False
            in_bullet = True
            bullet_items.append(_strip_inline(nl.group(1)))
            i += 1
            continue

        if bullet_items:
            _pdf_bullet_list(pdf, bullet_items)
            bullet_items = []
            in_bullet = False
        _pdf_paragraph(pdf, stripped)
        i += 1

    if bullet_items:
        _pdf_bullet_list(pdf, bullet_items)


def make_pdf(md_content: str, title: str) -> bytes:
    pdf = DocPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 20)
    pdf.set_text_color(26, 26, 46)
    pdf.cell(0, 14, title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("DejaVu", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "OŠ Toneta Čufarja Jesenice", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_draw_color(74, 108, 247)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    _render_md_to_pdf(pdf, md_content)
    return bytes(pdf.output(dest="S"))


# ══════════════════════════════════════
# TESTS
# ══════════════════════════════════════

DOCS_DIR = Path(__file__).resolve().parent.parent / "documentation"

TESTS = [
    # (name, lang)
    ("navodila-ucitelji", "sl"),
    ("navodila-ucitelji", "en"),
    ("navodila-vodstvo", "sl"),
    ("navodila-vodstvo", "en"),
]


def test_pdfs():
    failures = 0

    for name, lang in TESTS:
        # Read the right file
        fnames = {
            "navodila-ucitelji": ["navodila-ucitelji.md"],
            "navodila-vodstvo": ["navodila-vodstvo.md", "admin-devops-navodila.md"],
        }
        files = fnames[name]
        content_parts = []
        for fname in files:
            if lang == "en":
                fp = DOCS_DIR / "en" / fname
                if not fp.exists():
                    fp = DOCS_DIR / fname
            else:
                fp = DOCS_DIR / fname
                if not fp.exists():
                    fp = DOCS_DIR / "en" / fname
            content_parts.append(fp.read_text(encoding="utf-8"))

        full_content = content_parts[0]
        for part in content_parts[1:]:
            full_content += "\n\n---\n\n" + part

        labels = {
            "navodila-ucitelji": {"sl": "Navodila za učitelje", "en": "Teacher Instructions"},
            "navodila-vodstvo": {"sl": "Navodila za vodstvo in admin", "en": "Management & Admin Guide"},
        }
        title = labels[name][lang]

        # Generate PDF
        pdf_bytes = make_pdf(full_content, title)

        # ── Validacije ──
        test_id = f"{name} ({lang})"

        # 1. Velikost
        size_ok = 10000 <= len(pdf_bytes) <= 500000
        if not size_ok:
            print(f"❌ {test_id}: velikost {len(pdf_bytes)}B (izven 10k–500k)")
            failures += 1
        else:
            print(f"✅ {test_id}: {len(pdf_bytes)} bytes")

        # 2. %PDF header
        if not pdf_bytes.startswith(b"%PDF"):
            print(f"❌ {test_id}: ne začne se z %PDF")
            failures += 1

        # 3. Preverimo, da PDF vsebuje /Type /Catalog (veljaven PDF)
        #    in da ima več kot 1 stran
        page_count = pdf_bytes.count(b"/Type /Page")
        has_catalog = b"/Type /Catalog" in pdf_bytes
        if not has_catalog:
            print(f"❌ {test_id}: neveljaven PDF (manjka /Catalog)")
            failures += 1
        if page_count < 2:
            print(f"  ⚠️  {test_id}: samo {page_count} strani")
        else:
            print(f"  ✓ {page_count} strani, veljaven PDF")

    return failures


if __name__ == "__main__":
    print("═" * 56)
    print("  Pre-build PDF testi")
    print("═" * 56)
    failures = test_pdfs()
    print("─" * 56)
    if failures:
        print(f"\n❌ NEUSPELO: {failures} testov padlo")
        sys.exit(1)
    else:
        print("\n✅ Vsi testi uspešni!")
