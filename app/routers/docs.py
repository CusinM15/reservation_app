from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, HTMLResponse
from pathlib import Path
import markdown
from fpdf import FPDF, FontFace
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

    def _add_font_safe(self, family: str, style: str, fname: str, fallback: str = None):
        path = self._font_path(fname)
        if os.path.exists(path):
            self.add_font(family, style, path, uni=True)
        elif fallback:
            fb_path = self._font_path(fallback)
            if os.path.exists(fb_path):
                self.add_font(family, style, fb_path, uni=True)

    def header(self):
        if self.page_no() > 1:
            self.set_font("DejaVu", "B", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 5, "ostc-app — Dokumentacija", align="C")
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Stran {self.page_no()}/{{nb}}", align="C")


def _make_pdf(md_content: str, title: str) -> bytes:
    """Pretvori markdown v PDF z uporabo markdown → HTML → fpdf2 write_html."""
    # Odstrani YAML frontmatter in jezikovne povezave
    lines = md_content.split("\n")
    cleaned = []
    skip_frontmatter = False
    in_frontmatter = False
    for line in lines:
        if line.strip() == "---" and not in_frontmatter:
            in_frontmatter = True
            skip_frontmatter = True
            continue
        if in_frontmatter and line.strip() == "---":
            in_frontmatter = False
            continue
        if in_frontmatter:
            continue
        # Preskoci jezikovne povezave (🌐 ...)
        if line.strip().startswith("🌐"):
            skip_frontmatter = True
            continue
        if skip_frontmatter and line.strip() == "---":
            skip_frontmatter = False
            continue
        if skip_frontmatter:
            continue
        cleaned.append(line)

    content = "\n".join(cleaned)

    # Markdown → HTML
    html = markdown.markdown(
        content,
        extensions=["fenced_code", "tables", "nl2br"],
    )

    # fpdf2 write_html ne podpira gnezdenih tagov v <td> — počistimo jih
    def _strip_nested_in_td(m):
        inner = m.group(1)
        inner = re.sub(r'<[^>]+>', '', inner)
        return f'<td>{inner}</td>'
    html = re.sub(r'<td>(.*?)</td>', _strip_nested_in_td, html, flags=re.DOTALL)
    html = re.sub(r'<th>(.*?)</th>', lambda m: f'<th>{re.sub(r"<[^>]+>", "", m.group(1))}</th>', html, flags=re.DOTALL)

    # Slike: relative → absolute filesystem path za fpdf2
    def _fix_img_src(m):
        src = m.group(1)
        if src.startswith(("http://", "https://", "/")):
            return f'src="{src}"'
        # Relativna pot → absolutna filesystem pot za write_html
        abs_path = str((DOCS_DIR / src).resolve())
        if os.path.exists(abs_path):
            return f'src="{abs_path}"'
        return f'src="{src}"'
    html = re.sub(r'src="([^"]+)"', _fix_img_src, html)

    pdf = DocPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title
    pdf.set_font("DejaVu", "B", 16)
    pdf.set_text_color(26, 26, 46)
    pdf.multi_cell(0, 8, title)
    pdf.set_draw_color(74, 108, 247)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    pdf.set_text_color(34, 34, 34)
    pdf.write_html(html, tag_styles={
        "code": FontFace(family="DejaVuMono", size_pt=8),
        "pre": FontFace(family="DejaVuMono", size_pt=8),
    })

    return bytes(pdf.output(dest="S"))


def _read_docs(name: str) -> tuple[str, str]:
    """Prebere dokumentacijo. Vrne (vsebina, naslov)."""
    if name not in ALLOWED:
        raise ValueError(f"Dokument '{name}' ne obstaja")

    files = ALLOWED[name]
    content_parts = []
    for i, fname in enumerate(files):
        filepath = DOCS_DIR / fname
        if not filepath.exists():
            # Poskusi EN
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


def _strip_markdown_images(md: str) -> str:
    """Pretvori slike v alt text za HTML preview (brez /slike/ mounta)."""
    # Zamenjaj slike z alt tekstom v HTML
    md = re.sub(r'!\[([^\]]*)\]\(slike/([^)]+)\)', r'<em>[Slika: \1]</em>', md)
    md = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<em>[Slika: \1]</em>', md)
    return md


@router.get("/docs/{name}")
async def get_doc(name: str):
    """JSON preview dokumentacije (za hover popup v appu)."""
    try:
        content, label = _read_docs(name)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)

    return {
        "content": content,
        "label": label,
        "name": name,
    }


@router.get("/docs/html/{name}", response_class=HTMLResponse)
async def get_doc_html(name: str):
    """HTML preview dokumentacije s slikami."""
    try:
        content, label = _read_docs(name)
    except ValueError as e:
        return HTMLResponse(f"<p style='color:red;'>{e}</p>")

    # Markdown → HTML
    html = markdown.markdown(
        content,
        extensions=["fenced_code", "tables"],
    )

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
    """PDF download dokumentacije."""
    try:
        content, title = _read_docs(name)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)

    try:
        pdf_bytes = _make_pdf(content, title)
    except Exception as e:
        return JSONResponse({"error": f"Napaka pri generiranju PDF: {str(e)}"}, status_code=500)

    safe_name = f"{name.replace('navodila-', 'navodila_')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
