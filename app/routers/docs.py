from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, HTMLResponse
from pathlib import Path
import markdown
from fpdf import FPDF
import re
import os
import html as html_mod

router = APIRouter(tags=["docs"])

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "documentation"

ALLOWED = {
    "navodila-ucitelji": ["navodila-ucitelji.md"],
    "navodila-vodstvo": ["navodila-vodstvo.md", "admin-devops-navodila.md"],
}

DOC_LABELS = {
    "navodila-ucitelji": "Navodila za učitelje",
    "navodila-vodstvo": "Navodila za vodstvo in admin",
}


# ═══════════════════════════════════════════════════════════════════════════
# PDF generator — ročni parser za lep izpis
# ═══════════════════════════════════════════════════════════════════════════

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
        return os.path.join("/usr/share/fonts/truetype/dejavu", fname)

    def _add_font_safe(self, family, style, fname, fallback=None):
        path = self._font_path(fname)
        if os.path.exists(path):
            self.add_font(family, style, path, uni=True)
        elif fallback:
            fb_path = self._font_path(fallback)
            if os.path.exists(fb_path):
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


def _render_md_to_pdf(pdf: DocPDF, md: str):
    """
    Ročni parser markdown → PDF.
    Vsak element obdela ločeno za poln nadzor nad izgledom.
    """
    # Odstrani metapodatke na začetku
    md = re.sub(r'^🌐.*?\n---\s*\n', '', md, count=1, flags=re.DOTALL)
    md = re.sub(r'^---\s*\n.*?\n---\s*\n', '', md, count=1, flags=re.DOTALL)
    md = re.sub(r'^> ⚠️.*?\n---\s*\n', '', md, count=0, flags=re.DOTALL)

    lines = md.split("\n")
    i = 0
    n = len(lines)
    in_code = False
    code_buf = []
    in_bullet = False
    bullet_items = []

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # ── Code block ──
        if stripped.startswith("```"):
            if in_code:
                _pdf_code_block(pdf, code_buf)
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(stripped)
            i += 1
            continue

        # ── Prazna → zaključi sezname ──
        if not stripped:
            if in_bullet and bullet_items:
                _pdf_bullet_list(pdf, bullet_items)
                bullet_items = []
                in_bullet = False
            i += 1
            continue

        # ── Horizontal rule ──
        if re.match(r"^-{3,}$", stripped):
            if bullet_items:
                _pdf_bullet_list(pdf, bullet_items); bullet_items = []; in_bullet = False
            _pdf_hr(pdf)
            i += 1
            continue

        # ── Heading H1-H4 ──
        h = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if h:
            if bullet_items:
                _pdf_bullet_list(pdf, bullet_items); bullet_items = []; in_bullet = False
            level = len(h.group(1))
            text = _strip_inline(h.group(2))
            _pdf_heading(pdf, text, level)
            i += 1
            continue

        # ── Blockquote ──
        bq = re.match(r"^> ?(.*)$", stripped)
        if bq:
            if bullet_items:
                _pdf_bullet_list(pdf, bullet_items); bullet_items = []; in_bullet = False
            _pdf_blockquote(pdf, _strip_inline(bq.group(1)))
            i += 1
            continue

        # ── Bullet list ──
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

        # ── Numbered list ──
        nl = re.match(r"^\d+\.\s(.+)$", stripped)
        if nl:
            if bullet_items:
                _pdf_bullet_list(pdf, bullet_items); bullet_items = []; in_bullet = False
            # For now, numbered lists render as bullet
            in_bullet = True
            bullet_items.append(_strip_inline(nl.group(1)))
            i += 1
            continue

        # ── Table ──
        if "|" in stripped and re.match(r"^\|", stripped):
            # Check if next line is separator row
            if i + 1 < n and re.match(r"^\|[-:| ]+\|", lines[i + 1].strip()):
                rows = []
                rows.append(_parse_table_row(stripped))
                i += 1
                while i < n and "|" in lines[i] and re.match(r"^\|", lines[i].strip()):
                    rows.append(_parse_table_row(lines[i].strip()))
                    i += 1
                if bullet_items:
                    _pdf_bullet_list(pdf, bullet_items); bullet_items = []; in_bullet = False
                _pdf_table(pdf, rows)
                continue

        # ── Navaden paragraf ──
        if bullet_items:
            _pdf_bullet_list(pdf, bullet_items); bullet_items = []; in_bullet = False
        _pdf_paragraph(pdf, stripped)
        i += 1

    if bullet_items:
        _pdf_bullet_list(pdf, bullet_items)
    if code_buf:
        _pdf_code_block(pdf, code_buf)


def _strip_inline(text):
    """Odstrani markdown inline formatiranje (bold, italic, code, link)."""
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = html_mod.unescape(text)
    return text


def _parse_table_row(line):
    """Razčleni vrstico tabele v seznam celic."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def _needs_page_break(pdf, needed_mm=25):
    """Če ni dovolj prostora, dodaj novo stran."""
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


def _pdf_blockquote(pdf, text):
    _needs_page_break(pdf, 12)
    # Siva ozadja z barvno črto na levi
    y_start = pdf.get_y()
    pdf.set_fill_color(248, 249, 250)
    pdf.set_text_color(80, 80, 80)
    pdf.set_font("DejaVu", "I", 9)
    w = 190
    pdf.multi_cell(w, 4.5, text, fill=True, new_x="LMARGIN", new_y="NEXT")
    y_end = pdf.get_y()
    pdf.set_draw_color(74, 108, 247)
    pdf.set_line_width(0.8)
    pdf.line(10, y_start, 10, y_end)
    pdf.ln(2)


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


def _pdf_code_block(pdf, lines):
    _needs_page_break(pdf, 4 * len(lines) + 8)
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("DejaVuMono", "", 7.5)
    pdf.set_text_color(50, 50, 50)
    for line in lines:
        if line.startswith("```"):
            continue
        pdf.cell(0, 4.5, "  " + line, new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(2)


def _pdf_hr(pdf):
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    y = pdf.get_y()
    pdf.line(10, y, 200, y)
    pdf.ln(4)


def _pdf_table(pdf, rows):
    """Tabela z vsemi robovi in sivo glavo."""
    if not rows:
        return
    _needs_page_break(pdf, 12 * len(rows) + 10)

    ncols = max(len(r) for r in rows)
    col_w = 180 / ncols
    lh = 5.5  # line height
    header_color = (240, 242, 245)
    border_color = (200, 200, 200)

    for r_idx, row in enumerate(rows):
        # Izračunaj višino vrstice
        max_lines = 1
        for c in row:
            text_w = pdf.get_string_width(c)
            lines_needed = max(1, int(text_w / col_w) + 1)
            max_lines = max(max_lines, lines_needed)
        row_h = lh * max_lines

        # Preveri prelom strani za celo vrstico
        if pdf.get_y() + row_h > 297 - 20:
            pdf.add_page()
            # Ponovi glavo (prvo vrstico)
            if r_idx > 0:
                first_row = rows[0]
                for c_idx, cell in enumerate(first_row):
                    pdf.set_fill_color(*header_color)
                    pdf.set_font("DejaVu", "B", 8)
                    pdf.set_text_color(50, 50, 50)
                    x = 10 + c_idx * col_w
                    pdf.rect(x, pdf.get_y(), col_w, lh, style="DF")
                    pdf.set_xy(x + 1, pdf.get_y() + 0.5)
                    pdf.cell(col_w - 2, lh - 1, cell[:40])
                pdf.set_y(pdf.get_y() + lh)

        for c_idx, cell in enumerate(row):
            x = 10 + c_idx * col_w
            y = pdf.get_y()

            if r_idx == 0:
                # Header row
                pdf.set_fill_color(*header_color)
                pdf.set_font("DejaVu", "B", 8)
                pdf.set_text_color(50, 50, 50)
            else:
                pdf.set_fill_color(255, 255, 255)
                pdf.set_font("DejaVu", "", 8)
                pdf.set_text_color(60, 60, 60)

            # Nariši celico
            pdf.rect(x, y, col_w, row_h, style="DF")
            pdf.set_xy(x + 1, y + 0.5)
            pdf.cell(col_w - 2, lh - 1, cell[:int(col_w / 4)])

        pdf.set_y(pdf.get_y() + row_h)

    pdf.ln(3)


def _make_pdf(md_content: str, title: str) -> bytes:
    """Pretvori markdown v lep PDF z ročnim parserjem."""
    pdf = DocPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # → Naslovna stran
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

    # → Vsebina
    _render_md_to_pdf(pdf, md_content)

    return bytes(pdf.output(dest="S"))


# ═══════════════════════════════════════════════════════════════════════════
# Bralnik dokumentov
# ═══════════════════════════════════════════════════════════════════════════

def _read_docs(name: str) -> tuple[str, str]:
    """Prebere dokumentacijo. Vrne (vsebina, naslov)."""
    if name not in ALLOWED:
        raise ValueError(f"Dokument '{name}' ne obstaja")

    files = ALLOWED[name]
    content_parts = []
    for i, fname in enumerate(files):
        filepath = DOCS_DIR / fname
        if not filepath.exists():
            filepath = DOCS_DIR / "en" / fname
        if not filepath.exists():
            raise ValueError(f"Datoteka '{fname}' ne obstaja")

        text = filepath.read_text(encoding="utf-8")
        content_parts.append(text)

    # Združi: če je več datotek, dodaj ločilo
    full_content = content_parts[0]
    for part in content_parts[1:]:
        full_content += "\n\n---\n\n" + part

    return full_content, DOC_LABELS.get(name, name)


# ═══════════════════════════════════════════════════════════════════════════
# API endpoints
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/docs/{name}")
async def get_doc(name: str):
    """JSON preview (za klice iz appa)."""
    try:
        content, label = _read_docs(name)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    return {"content": content, "label": label, "name": name}


@router.get("/docs/html/{name}", response_class=HTMLResponse)
async def get_doc_html(name: str):
    """HTML preview s slikami (za hover popup v appu)."""
    try:
        content, label = _read_docs(name)
    except ValueError as e:
        return HTMLResponse(f"<p style='color:red;'>{e}</p>")

    html = markdown.markdown(content, extensions=["fenced_code", "tables"])
    # Popravi relativne poti slik za browser
    html = re.sub(r'src="slike/([^"]+)"', r'src="/slike/\1"', html)
    html = re.sub(r'src="\.\./slike/([^"]+)"', r'src="/slike/\1"', html)

    full_html = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{label}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 1.5rem; line-height: 1.6; color: #333; font-size: 14px; }}
    h1, h2, h3 {{ color: #1a1a2e; }}
    h2 {{ border-bottom: 2px solid #4a6cf7; padding-bottom: 0.3rem; }}
    img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 6px; margin: 10px 0; }}
    pre {{ background: #f5f5f5; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.85rem; }}
    code {{ background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85rem; }}
    blockquote {{ border-left: 4px solid #4a6cf7; margin: 1rem 0; padding: 0.5rem 1rem; background: #f8f9fa; color: #555; }}
    hr {{ border: none; border-top: 1px solid #ddd; margin: 1.5rem 0; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
    th {{ background: #f0f2f5; font-weight: 600; }}
    ul, ol {{ padding-left: 1.5rem; }}
    li {{ margin-bottom: 0.3rem; }}
  </style>
</head>
<body>
  {html}
</body>
</html>"""
    return HTMLResponse(full_html)


@router.get("/docs/download/{name}")
async def download_doc(name: str):
    """PDF download."""
    try:
        content, title = _read_docs(name)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)

    try:
        pdf_bytes = _make_pdf(content, title)
    except Exception as e:
        return JSONResponse({"error": f"Napaka: {str(e)}"}, status_code=500)

    safe_name = f"{name.replace('navodila-', 'navodila_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
