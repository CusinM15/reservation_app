from fastapi import APIRouter
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import html

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
    """Download markdown file."""
    if name not in ALLOWED:
        return JSONResponse({"error": "Dokument ne obstaja"}, status_code=404)
    filepath = DOCS_DIR / ALLOWED[name]
    if not filepath.exists():
        return JSONResponse({"error": "Datoteka ne obstaja"}, status_code=404)
    return FileResponse(
        str(filepath),
        filename=ALLOWED[name],
        media_type="text/markdown",
    )
