# ─────────────────────────────────────────────────────────────────────────
# app/routers/docs.py — Bralnik dokumentacije (Markdown → HTML/PDF)
#
# Namen: Servira dokumentacijo v treh formatih:
# - JSON (za API klic iz aplikacije)
# - HTML (za hover popup v brskalniku)
# - PDF (za prenos s weasyprint)
#
# Dokumentacija je shranjena v /documentation/ mapi kot Markdown (.md)
# datoteke. Slike so v /documentation/slike/ in se servirajo kot
# statične datoteke preko main.py.
#
# Zakaj lastni bralnik namesto zunanje storitve?
# Dokumentacija je namenjena učiteljem, ki pogosto nimajo dostopa do
# zunanjih storitev (omejen internet). Prav tako želimo, da je PDF
# generiran z isto obliko (CSS) kot HTML predogled.
#
# Cloudflare workaround: '@' v emailih zakodiramo kot HTML entiteto,
# da Cloudflare ne sproži email obfuscation, ki bi pokvaril popup okno.
# ─────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database import get_db
from app.tenancy import role_value, get_request_user, is_main_admin
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse, Response, HTMLResponse
from pathlib import Path
import markdown
import re
import os
import html as html_mod

from app.emoji_pdf import replace_emojis
from app.audit import log_audit
from app.models import User, AppSetting

router = APIRouter(tags=["docs"])

OBRAZCI_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "documentation"

# Dovoljeni dokumenti — preslikava v datotečni sistem.
# Zakaj whitelist? Preprečuje directory traversal napade.
ALLOWED = {
    "navodila-ucitelji": ["navodila-ucitelji.md"],
    "navodila-ucitelji-en": ["en/navodila-ucitelji.md"],
    "navodila-vodstvo": ["navodila-vodstvo.md"],
    "navodila-vodstvo-en": ["en/navodila-vodstvo.md"],
    "navodila-admin": ["navodila-admin.md"],
    "navodila-admin-en": ["en/navodila-admin.md"],
    "pogoji-uporabe": ["pogoji-uporabe.md"],
    "obvestilo-ucitelji": ["obvestilo-ucitelji.md"],
    "obvestilo-starsi": ["obvestilo-starsi.md"],
    "reklama-sola": ["reklama-sola.md"],
}

DOC_LABELS = {
    "navodila-ucitelji": "Navodila za učitelje",
    "navodila-ucitelji-en": "Teacher Instructions",
    "navodila-vodstvo": "Navodila za vodstvo",
    "navodila-vodstvo-en": "Management Guide",
    "navodila-admin": "Navodila za administratorja",
    "navodila-admin-en": "Administrator Guide",
    "pogoji-uporabe": "Pogoji uporabe",
    "obvestilo-ucitelji": "Obvestilo za učitelje — govorilne ure",
    "obvestilo-starsi": "Obvestilo za starše — najava na govorilne ure",
    "reklama-sola": "Predstavitev aplikacije (reklama)",
}


# ═══════════════════════════════════════════════════════════════════════
# PDF generator — weasyprint (HTML → lep PDF)
# ═══════════════════════════════════════════════════════════════════════
#
# CSS je definiran inline za samostojen PDF. Uporablja Noto Sans
# (moderen font, vizualno blizu Segoe UI/Roboto iz HTML previewja) +
# Noto Color Emoji (barvni emojiji — brez njega bi bili tofu kvadratki).
# Stil namerno posnema /docs/html/{name} preview: iste barve (#1a1a2e,
# #4a6cf7, #f8f9fa), iste oblike (rounded vogali, podčrtani naslovi).
# Strani so A4 z marginami 2cm, z nevtralno nogo "Šolska rezervacijska aplikacija"
# (BREZ imena posamezne šole — navodila so splošna in uporabna za vsako šolo).

_PDF_CSS = """
@page { margin: 1.8cm 2cm; @bottom-center { content: "Šolska rezervacijska aplikacija"; font-size: 8pt; color: #999; } }
body { font-family: 'Noto Sans', 'DejaVu Sans', sans-serif; font-size: 11pt; line-height: 1.6; color: #333; }
h1 { font-size: 19pt; color: #1a1a2e; border-bottom: 2px solid #4a6cf7; padding-bottom: 4pt; margin-top: 20pt; font-family: 'Noto Sans', 'DejaVu Sans', sans-serif; }
h2 { font-size: 15pt; color: #1a1a2e; border-bottom: 2px solid #4a6cf7; padding-bottom: 3pt; margin-top: 16pt; font-family: 'Noto Sans', 'DejaVu Sans', sans-serif; }
h3 { font-size: 12.5pt; color: #4a6cf7; margin-top: 12pt; font-family: 'Noto Sans', 'DejaVu Sans', sans-serif; }
h4 { font-size: 11pt; color: #333; margin-top: 8pt; font-family: 'Noto Sans', 'DejaVu Sans', sans-serif; }
p { margin: 5pt 0; text-align: justify; }
img { max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4pt; margin: 10pt 0; display: block; }
img.emoji { display: inline; height: 1.15em; width: auto; border: none; border-radius: 0; margin: 0 0.05em; vertical-align: -0.2em; }
pre { background: #f5f5f5; padding: 10pt 12pt; border-radius: 4pt; font-size: 9pt; font-family: 'DejaVu Sans Mono', monospace; overflow-x: auto; page-break-inside: avoid; }
code { background: #f0f0f0; padding: 1pt 3pt; border-radius: 2pt; font-size: 9.5pt; font-family: 'DejaVu Sans Mono', monospace; }
blockquote { border-left: 4pt solid #4a6cf7; margin: 10pt 0; padding: 6pt 12pt; background: #f8f9fa; color: #555; page-break-inside: avoid; }
hr { border: none; border-top: 1pt solid #ddd; margin: 16pt 0; }
table { border-collapse: collapse; width: 100%; margin: 10pt 0; font-size: 10pt; page-break-inside: avoid; }
th, td { border: 1px solid #ddd; padding: 5pt 9pt; text-align: left; }
th { background: #f0f2f5; font-weight: 600; }
ul, ol { padding-left: 22pt; margin: 5pt 0; }
li { margin-bottom: 3pt; }
.title-page { text-align: center; padding-top: 60pt; }
.title-page h1 { font-size: 24pt; border: none; margin-bottom: 0; }
.title-page .sub { font-size: 11pt; color: #888; margin-top: 4pt; }
.title-page hr { width: 60%; margin: 22pt auto; border-top: 2px solid #4a6cf7; }
.page-break { page-break-before: always; }
"""
_OBVESTILA_CSS = """
/* ===== Obvestila: eleganten A4 dokument (obvestilo-*) ===== */
/* Na zaslonu (HTML preview) izgleda kot bel A4 list na sivem ozadju; */
/* v PDF (weasyprint, print media) pa ostane na @page A4 — čist brez linij. */
@media screen {
  html { background: #e8eef4; }
  body {
    max-width: 794px;           /* ~21 cm A4 širina */
    box-sizing: border-box;      /* 794 = skupna širina s paddingom */
    margin: 40px auto;
    background: #ffffff;
    box-shadow: 0 12px 48px rgba(15,40,65,.20);
    padding: 56px 64px 72px;
    border-radius: 6px;
  }
}
h1 {
  background: linear-gradient(135deg, #0b3b5c, #14608c);
  color: #ffffff !important;
  padding: 26px 36px;
  border-radius: 14px;
  margin: 0 0 26px;
  font-size: 21pt;
  text-align: center;
  box-shadow: 0 6px 22px rgba(11,59,92,.30);
  border: none !important;
}
h2 {
  color: #0b3b5c;
  font-size: 15pt;
  margin-top: 22px;
  padding-bottom: 6px;
  border-left: 5px solid #14608c;
  padding-left: 14px;
}
p { font-size: 11.5pt; color: #28323c; }
ol, ul { padding-left: 24px; }
li { margin-bottom: 5px; font-size: 11.5pt; color: #28323c; }
hr { border: none; margin: 18px 0; }          /* brez vidnih linij */
blockquote {
  background: #f0f6fc;
  border: 1px solid #cfe0ee;
  border-left: 6px solid #14608c;
  border-radius: 12px;
  padding: 14px 18px;
  font-size: 11.5pt;
  color: #344c5c;
  page-break-inside: avoid;
}
blockquote a, blockquote a:visited {
  display: inline-block;
  margin-top: 14px;
  background: linear-gradient(135deg,#0b3b5c,#14608c);
  color: #ffffff !important;
  padding: 12px 28px;
  border-radius: 30px;
  text-decoration: none;
  font-weight: 700;
  font-size: 12pt;
  box-shadow: 0 4px 12px rgba(11,59,92,.25);
}
blockquote a:hover { background: #14608c; }
"""



def _doc_to_html(content: str, label: str) -> str:
    """Pretvori markdown v lep HTML (brez ovoja <html><body> — samo vsebina).
    
    Popravi relativne poti slik za browser/slike/ in zakodira @ za Cloudflare.
    """
    html = markdown.markdown(content, extensions=["fenced_code", "tables"])
    # Popravi relativne poti slik za browser/slike/
    html = re.sub(r'src="slike/([^"]+)"', r'src="/slike/\1"', html)
    html = re.sub(r'src="\.\./slike/([^"]+)"', r'src="/slike/\1"', html)
    # Zakodiraj @ kot HTML entiteto, da Cloudflare ne prepozna emaila in ga ne obfuscates
    # (Cloudflare email obfuscation pokvari email v popupu, ker innerHTML ne poganja JS)
    html = html.replace("@", "&#64;")
    return html


def _make_pdf(md_content: str, title: str, obvestilo: bool = False) -> bytes:
    """Pretvori markdown v lep PDF s pomočjo weasyprint (HTML+CSS → PDF).
    
    Odstrani morebitni YAML frontmatter (--- ... ---) in doda naslovno
    stran z imenom šole. Relativne poti slik pretvori v absolutne
    (file://) za weasyprint.
    """
    # Odstrani morebitni frontmatter
    md_clean = re.sub(r'^---\s*\n.*?\n---\s*\n', '', md_content, count=1, flags=re.DOTALL)

    # Pretvori v HTML
    body_html = markdown.markdown(md_clean, extensions=["fenced_code", "tables"])
    # Relativne slike → absolutne za weasyprint
    body_html = re.sub(r'src="slike/([^"]+)"', r'src="file://' + str(DOCS_DIR) + r'/slike/\1"', body_html)
    body_html = re.sub(r'src="\.\./slike/([^"]+)"', r'src="file://' + str(DOCS_DIR) + r'/slike/\1"', body_html)

    # Emojiji → <img> (weasyprint 69 ne izriše CBDT barvnih emoji — vidi app/emoji_pdf.py)
    body_html = replace_emojis(body_html)

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{_PDF_CSS + (_OBVESTILA_CSS if obvestilo else '')}</style>
</head>
<body>
{f'''<div class="title-page">
  <h1>{html_mod.escape(title)}</h1>
  <p class="sub">Navodila za uporabo</p>
  <hr>
</div>
''' if not obvestilo else ''}{body_html}
</body>
</html>"""

    from weasyprint import HTML as WP_HTML

    pdf_bytes = WP_HTML(string=full_html, base_url=str(DOCS_DIR)).write_pdf()
    return pdf_bytes


# ═══════════════════════════════════════════════════════════════════════
# Bralnik dokumentov
# ═══════════════════════════════════════════════════════════════════════


# Predpona ključev v AppSetting za shranjene .md predloge (glavni admin override).
# Glavni admin v /navodila shrani svojo .md verzijo navodila; ta se prikaže
# namesto vgrajene datoteke v dokumentaciji/ (za učitelje/vodstvo/admina,
# v HTML predogledu in v PDF).
DOC_OVERRIDE_PREFIX = "DOC_OVERRIDE:"


def _get_override(db: Session | None, name: str) -> str | None:
    """Vrni shranjeno .md predlogo (glavni admin override) ali None."""
    if db is None:
        return None
    row = db.query(AppSetting).filter(AppSetting.key == DOC_OVERRIDE_PREFIX + name).first()
    if row is None or not row.value:
        return None
    return row.value


def _save_override(db: Session, name: str, content: str) -> None:
    """Shrani/posodobi .md override (glavni admin)."""
    row = db.query(AppSetting).filter(AppSetting.key == DOC_OVERRIDE_PREFIX + name).first()
    if row is None:
        db.add(AppSetting(key=DOC_OVERRIDE_PREFIX + name, value=content))
    else:
        row.value = content
    db.commit()


def _clear_override(db: Session, name: str) -> None:
    """Ponastavi dokument na vgrajeno .md datoteko (pobriše override)."""
    row = db.query(AppSetting).filter(AppSetting.key == DOC_OVERRIDE_PREFIX + name).first()
    if row is not None:
        db.delete(row)
        db.commit()


def _read_docs(name: str, db: Session | None = None) -> tuple[str, str]:
    """Prebere dokumentacijo. Vrne (vsebina, naslov).

    Če ima glavni admin shranjen override (.md v DB), se ta prikaže namesto
    vgrajene datoteke. Uporablja whitelist (ALLOWED) za preprečevanje directory
    traversal. Če datoteka ne obstaja, vrne ValueError.
    """
    if name not in ALLOWED:
        raise ValueError(f"Dokument '{name}' ne obstaja")

    override = _get_override(db, name)
    if override:
        return override, DOC_LABELS.get(name, name)

    files = ALLOWED[name]
    content_parts = []
    for fname in files:
        filepath = DOCS_DIR / fname
        if not filepath.exists():
            raise ValueError(f"Datoteka '{fname}' ne obstaja")
        text = filepath.read_text(encoding="utf-8")
        content_parts.append(text)

    full_content = content_parts[0]
    for part in content_parts[1:]:
        full_content += "\n\n---\n\n" + part

    return full_content, DOC_LABELS.get(name, name)


# ═══════════════════════════════════════════════════════════════════════
# API endpoints
# ═══════════════════════════════════════════════════════════════════════


@router.get("/docs/{name}")
async def get_doc(name: str, db: Session = Depends(get_db)):
    """JSON preview (za klice iz appa)."""
    try:
        content, label = _read_docs(name, db)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    return {"content": content, "label": label, "name": name}


@router.get("/docs/html/{name}", response_class=HTMLResponse)
async def get_doc_html(name: str, db: Session = Depends(get_db)):
    """HTML preview s slikami (za hover popup v appu).
    
    Vključuje celoten HTML dokument s CSS oblikovanjem, primernim za
    prikaz v popup oknu. Cache-Control: no-cache zagotavlja, da se
    spremembe dokumentacije takoj pokažejo.
    """
    try:
        content, label = _read_docs(name, db)
    except ValueError as e:
        return HTMLResponse(f"<p style='color:red;'>{e}</p>")

    body_html = _doc_to_html(content, label)

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
  {body_html}
</body>
</html>"""
    if name.startswith("obvestilo"):
        full_html = full_html.replace("</style>", _OBVESTILA_CSS + "</style>", 1)
    return HTMLResponse(
        content=full_html,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/docs/download/{name}")
async def download_doc(name: str, db: Session = Depends(get_db)):
    """PDF download z weasyprint.
    
    Generira PDF iz Markdown dokumentacije. Če weasyprint ni nameščen
    (npr. v Docker sliki), vrne 500 napako.
    """
    try:
        content, title = _read_docs(name, db)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)

    try:
        pdf_bytes = _make_pdf(content, title, obvestilo=name.startswith("obvestilo"))
    except Exception as e:
        return JSONResponse({"error": f"Napaka: {str(e)}"}, status_code=500)

    safe_name = f"instrukcije_{name.replace('navodila-', '').replace('-', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )

# ═══════════════════════════════════════════════════════════════
# Obvestila / Obrazci (za vodstvo in admina)
# ═══════════════════════════════════════════════════════════════
@router.get("/obrazci", response_class=HTMLResponse)
def obrazci_stran(request: Request, db: Session = Depends(get_db)):
    """Zaščitena stran Obvestila/Obrazci — samo vodstvo in admin.

    Pokaže seznam obvestil (učitelji + starši), vsako s prikazom in
    PDF prenosom (via /docs/html in /docs/download).
    """
    tmpl = OBRAZCI_TEMPLATES
    user = get_request_user(request, db)
    if user is None:
        return RedirectResponse(url="/auth/login")
    role = role_value(user)
    if role not in ("admin", "vodstvo", "main_admin"):
        raise HTTPException(status_code=403, detail="Ni dostopa")
    return tmpl.TemplateResponse(request, "obrazci.html", {"role": role})

# ═══════════════════════════════════════════════════════════════
# Navodila (glavni admin) — sitemap UI strani + urejanje .md
# ═══════════════════════════════════════════════════════════════
def _require_main_admin(request: Request, db: Session) -> User:
    """Vrni prijavljenega glavnega admina ali 403/redirect."""
    from app.security import get_current_user_id
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not is_main_admin(user):
        raise HTTPException(status_code=403, detail="Dostop samo za glavnega admina")
    return user


def _editable_docs() -> list[str]:
    """Urejevalni dokumenti = slovenske različice navodil/obvestil (brez -en)."""
    return [k for k in ALLOWED if not k.endswith("-en")]


@router.get("/navodila", response_class=HTMLResponse)
def navodila_main_page(request: Request, db: Session = Depends(get_db)):
    """Stran 'Navodila' — samo glavni admin.

    Pokaže pregled vseh strani, ki so dostopne prek UI-ja, ter urejevalnik
    .md navodil/obvestil (shranjevanje v DB kot override).
    """
    user = _require_main_admin(request, db)
    docs = [
        {"name": k, "label": DOC_LABELS.get(k, k), "overridden": bool(_get_override(db, k))}
        for k in _editable_docs()
    ]
    return OBRAZCI_TEMPLATES.TemplateResponse("navodila_main.html", {
        "request": request,
        "user": user,
        "docs": docs,
        "all_preview": [{"name": k, "label": DOC_LABELS.get(k, k)} for k in _editable_docs()],
    })


@router.get("/api/navodila/docs")
def navodila_list_docs(request: Request, db: Session = Depends(get_db)):
    _require_main_admin(request, db)
    return {"docs": [
        {"name": k, "label": DOC_LABELS.get(k, k), "overridden": bool(_get_override(db, k))}
        for k in _editable_docs()
    ]}


@router.get("/api/navodila/docs/{name}")
def navodila_get_doc(name: str, request: Request, db: Session = Depends(get_db)):
    _require_main_admin(request, db)
    if name not in ALLOWED:
        raise HTTPException(status_code=404, detail="Dokument ne obstaja")
    content, label = _read_docs(name, db)
    return {
        "name": name,
        "label": label,
        "content": content,
        "overridden": bool(_get_override(db, name)),
    }


@router.post("/api/navodila/docs/{name}", status_code=200)
async def navodila_save_doc(name: str, request: Request, db: Session = Depends(get_db)):
    user = _require_main_admin(request, db)
    if name not in _editable_docs():
        raise HTTPException(status_code=400, detail="Ta dokument ni urejevalen")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")
    content = str(body.get("content", "")) or ""
    _save_override(db, name, content)
    log_audit(db, user.id, user.username, "edit_doc", name)
    return {"ok": True, "name": name, "label": DOC_LABELS.get(name, name), "overridden": True}


@router.post("/api/navodila/docs/{name}/reset", status_code=200)
def navodila_reset_doc(name: str, request: Request, db: Session = Depends(get_db)):
    user = _require_main_admin(request, db)
    if name not in _editable_docs():
        raise HTTPException(status_code=400, detail="Ta dokument ni urejevalen")
    _clear_override(db, name)
    log_audit(db, user.id, user.username, "reset_doc", name)
    return {"ok": True, "name": name, "overridden": False}
