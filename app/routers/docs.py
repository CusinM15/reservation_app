from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pathlib import Path
import markdown
from fpdf import FPDF, FontFace
import re

router = APIRouter(tags=["docs"])

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "documentation"

ALLOWED = {
    "navodila-ucitelji": "navodila-ucitelji.md",
    "navodila-vodstvo": "navodila-vodstvo.md",
}

DOC_LABELS = {
    "navodila-ucitelji": "Navodila za učitelje",
    "navodila-vodstvo": "Navodila za vodstvo",
}


class DocPDF(FPDF):
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


def _make_pdf(content: str, title: str) -> bytes:
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

    # Popravi relativne poti slik
    docs_dir_abs = str(DOCS_DIR.resolve())
    html = re.sub(r'src="(?!https?://)([^"]+)"', lambda m: f'src="{docs_dir_abs}/{m.group(1)}"', html)

    pdf = DocPDF()
    pdf.alias_nb_pages()
    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True)
    pdf.add_font("DejaVu", "I", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf", uni=True)
    pdf.add_font("DejaVu", "BI", "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf", uni=True)
    pdf.add_font("DejaVuMono", "", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", uni=True)
    pdf.add_font("DejaVuMono", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", uni=True)
    pdf.add_font("DejaVuMono", "I", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Oblique.ttf", uni=True)
    pdf.add_font("DejaVuMono", "BI", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-BoldOblique.ttf", uni=True)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

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


@router.get("/docs/{name}")
async def get_doc(name: str):
    if name not in ALLOWED:
        return JSONResponse({"error": "Dokument ne obstaja"}, status_code=404)
    filepath = DOCS_DIR / ALLOWED[name]
    if not filepath.exists():
        return JSONResponse({"error": "Datoteka ne obstaja"}, status_code=404)
    content = filepath.read_text(encoding="utf-8")
    return {
        "content": content,
        "label": DOC_LABELS.get(name, name),
        "name": name,
    }


@router.get("/docs/download/{name}")
async def download_doc(name: str):
    if name not in ALLOWED:
        return JSONResponse({"error": "Dokument ne obstaja"}, status_code=404)
    filepath = DOCS_DIR / ALLOWED[name]
    if not filepath.exists():
        return JSONResponse({"error": "Datoteka ne obstaja"}, status_code=404)

    content = filepath.read_text(encoding="utf-8")
    title = DOC_LABELS.get(name, name)
    try:
        pdf_bytes = _make_pdf(content, title)
    except Exception as e:
        return JSONResponse({"error": f"Napaka pri generiranju PDF: {str(e)}"}, status_code=500)

    safe_name = ALLOWED[name].replace(".md", ".pdf")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
