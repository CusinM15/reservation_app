from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pathlib import Path
import markdown
import weasyprint

router = APIRouter(tags=["docs"])

# Map logical names to actual files
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "documentation"

ALLOWED = {
    "navodila-ucitelji": "navodila-ucitelji.md",
    "navodila-vodstvo": "navodila-vodstvo.md",
    "admin-devops-navodila": "admin-devops-navodila.md",
}

DOC_LABELS = {
    "navodila-ucitelji": "Navodila za učitelje",
    "navodila-vodstvo": "Navodila za vodstvo",
    "admin-devops-navodila": "Admin navodila",
}

PDF_STYLES = """
<style>
  body { font-family: sans-serif; font-size: 11pt; line-height: 1.6; color: #333; padding: 1.5cm; }
  h1 { font-size: 16pt; color: #1a1a2e; margin-top: 1em; }
  h2 { font-size: 14pt; color: #1a1a2e; margin-top: 1em; }
  h3 { font-size: 12pt; color: #1a1a2e; }
  code { background: #f0f0f0; padding: 1px 4px; font-size: 10pt; border-radius: 3px; }
  pre { background: #f4f4f4; padding: 8px; border-radius: 4px; font-size: 9pt; overflow-x: auto; white-space: pre-wrap; }
  blockquote { border-left: 3px solid #4a6cf7; padding-left: 10px; margin: 0.5em 0; color: #555; }
  table { border-collapse: collapse; width: 100%; margin: 0.5em 0; }
  th, td { border: 1px solid #bbb; padding: 4px 8px; font-size: 10pt; text-align: left; }
  th { background: #f0f2f5; }
  img { max-width: 100%; height: auto; }
  hr { border: none; border-top: 1px solid #ddd; margin: 1em 0; }
  p { margin: 0.3em 0; }
  ul, ol { margin: 0.3em 0; padding-left: 1.5em; }
  li { margin: 0.1em 0; }
  a { color: #4a6cf7; }
  strong { color: #1a1a2e; }
</style>
"""


def _md_to_pdf_bytes(md_content: str) -> bytes:
    """Convert markdown content to PDF bytes."""
    html_body = markdown.markdown(md_content, extensions=["extra"])
    html_doc = (
        f"<!DOCTYPE html><html><head><meta charset=\"utf-8\">{PDF_STYLES}</head>"
        f"<body>{html_body}</body></html>"
    )
    return weasyprint.HTML(string=html_doc).write_pdf()


@router.get("/docs/{name}")
async def get_doc(name: str):
    """Return markdown content as JSON (used for hover preview)."""
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
    """Download instructions as PDF."""
    if name not in ALLOWED:
        return JSONResponse({"error": "Dokument ne obstaja"}, status_code=404)
    filepath = DOCS_DIR / ALLOWED[name]
    if not filepath.exists():
        return JSONResponse({"error": "Datoteka ne obstaja"}, status_code=404)
    md_content = filepath.read_text(encoding="utf-8")
    pdf_bytes = _md_to_pdf_bytes(md_content)
    pdf_name = ALLOWED[name].replace(".md", ".pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={pdf_name}"},
    )
