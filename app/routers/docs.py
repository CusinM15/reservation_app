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
from app.templating import make_templates
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
from html.parser import HTMLParser

from app.emoji_pdf import replace_emojis
from app.audit import log_audit
from app.models import User, AppSetting, UIString

router = APIRouter(tags=["docs"])

OBRAZCI_TEMPLATES = make_templates(str(Path(__file__).resolve().parent.parent / "templates"))

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
    "dpa": ["dpa.md"],
    "obvestilo-ucitelji": ["obvestilo-ucitelji.md"],
    "obvestilo-starsi": ["obvestilo-starsi.md"],
    "reklama-sola": ["reklama-sola.md"],
    "main": ["main.md"],
    "main-en": ["en/main.md"],
    "aplikacija-rezervacije": ["aplikacija-rezervacije.md"],
    "aplikacija-rezervacije-en": ["en/aplikacija-rezervacije.md"],
    "govorilne-ure": ["govorilne-ure.md"],
    "admin-devops-navodila": ["admin-devops-navodila.md"],
    "admin-devops-navodila-en": ["en/admin-devops-navodila.md"],
    "postavi-lokalni-app": ["postavi-lokalni-app.md"],
    "postavi-lokalni-app-en": ["en/postavi-lokalni-app.md"],
}

DOC_LABELS = {
    "navodila-ucitelji": "Navodila za učitelje",
    "navodila-ucitelji-en": "Teacher Instructions",
    "navodila-vodstvo": "Navodila za vodstvo",
    "navodila-vodstvo-en": "Management Guide",
    "navodila-admin": "Navodila za administratorja",
    "navodila-admin-en": "Administrator Guide",
    "pogoji-uporabe": "Pogoji uporabe",
    "dpa": "Pogodba o obdelavi osebnih podatkov (DPA)",
    "obvestilo-ucitelji": "Obvestilo za učitelje — govorilne ure",
    "obvestilo-starsi": "Obvestilo za starše — najava na govorilne ure",
    "reklama-sola": "Predstavitev aplikacije (reklama)",
    "main": "Glavna dokumentacija",
    "main-en": "Main Documentation",
    "aplikacija-rezervacije": "Aplikacija — rezervacije in ocenjevanja",
    "aplikacija-rezervacije-en": "Application Guide",
    "govorilne-ure": "Govorilne ure",
    "admin-devops-navodila": "Administrator / DevOps — tehnična navodila",
    "admin-devops-navodila-en": "Admin / DevOps Guide",
    "postavi-lokalni-app": "Postavitev lokalnega okolja",
    "postavi-lokalni-app-en": "Setting up a local environment",
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



def _doc_to_html(content: str, label: str, govorilne_url: str | None = None) -> str:
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
    if govorilne_url:
        html = html.replace("{{GOVORILNE_URL}}", govorilne_url)
    return html


def _make_pdf(md_content: str, title: str, obvestilo: bool = False, govorilne_url: str | None = None) -> bytes:
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
    if govorilne_url:
        body_html = body_html.replace("{{GOVORILNE_URL}}", govorilne_url)

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


def _govorilne_url(db: Session, request: Request) -> str:
    """Javni URL govorilnih ur za šolo iz ?skola (kratica) — fallback privzeta.

    Vrne absolutni URL (host iz zahtevka) + /govorilne_<kratica>. Kratica pride
    iz query parametra ?skola= (npr. ostcj ali zgled); če manjka/napačna → privzeta
    šola. Tako je obvestilo za starše per-šola, ne trdo na ostcj.
    """
    from app.config import settings
    from app.models import School
    slug = request.query_params.get("skola")
    if slug:
        sch = db.query(School).filter(School.slug == slug).first()
        if sch is None:
            slug = None
    if not slug:
        sch = db.query(School).filter(School.slug == settings.DEFAULT_SCHOOL_SLUG).first()
        slug = sch.slug if sch else settings.DEFAULT_SCHOOL_SLUG
    return str(request.base_url).rstrip("/") + f"/govorilne_{slug}"

@router.get("/docs/{name}")
async def get_doc(name: str, db: Session = Depends(get_db)):
    """Lepa HTML stran namesto belega JSON-a — preusmeri na /docs/html/{name}.

    Nekoč je tu bil JSON preview; frontend danes uporablja /docs/html/ in
    /api/navodila/docs/ (JSON), zato vsaka neposredna pot /docs/<dokument>
    (npr. pogoji uporabe v nogi javne strani) prikaže oblikovano stran.
    """
    return RedirectResponse(url=f"/docs/html/{name}", status_code=302)


@router.get("/docs/html/{name}", response_class=HTMLResponse)
async def get_doc_html(name: str, request: Request, db: Session = Depends(get_db)):
    """HTML preview s slikami (za hover popup v appu).
    
    Vključuje celoten HTML dokument s CSS oblikovanjem, primernim za
    prikaz v popup oknu. Cache-Control: no-cache zagotavlja, da se
    spremembe dokumentacije takoj pokažejo.
    """
    try:
        content, label = _read_docs(name, db)
    except ValueError as e:
        return HTMLResponse(f"<p style='color:red;'>{e}</p>")

    gov_url = _govorilne_url(db, request)
    body_html = _doc_to_html(content, label, gov_url)

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

    # DPA: za prijavljene (admin/vodstvo) dodaj ploščo s statusom, vpogledom,
    # prenosom in ponastavitvijo podpisane pogodbe.
    if name == "dpa":
        dpa_panel = _dpa_panel_html(request, db)
        if dpa_panel:
            full_html = full_html.replace("<body>", "<body>" + dpa_panel, 1)

    return HTMLResponse(
        content=full_html,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def _dpa_panel_html(request: Request, db: Session) -> str:
    """Plošča za DPA stran: status podpisa + gumba Prenesi in Ponastavi."""
    from app.dpa import get_agreement
    from app.tenancy import resolve_school_context

    user = get_request_user(request, db)
    if user is None:
        return ""
    try:
        school_id, school = resolve_school_context(request, db)
    except Exception:
        return ""
    if school is None:
        return ""

    from app.tenancy import is_main_admin, is_school_admin

    is_admin = is_school_admin(user) or is_main_admin(user)
    is_vodstvo = (not is_admin) and user.role == "vodstvo"
    agreement = get_agreement(db, school.id)
    is_teacher = (not is_admin) and (not is_vodstvo)

    if agreement is not None:
        when = agreement.signed_at.strftime("%d. %m. %Y ob %H:%M") if agreement.signed_at else "?"
        sha = agreement.sha256[:16] + "…" if agreement.sha256 else ""
        btns = [
            f'<a class="dpa-btn" href="/settings/dpa/pdf" download style="background:#4a6cf7;color:#fff;">⬇ Prenesi podpisan PDF</a>',
        ]
        if is_admin:
            btns.append(
                '<button class="dpa-btn" style="background:#e11d48;color:#fff;" '
                'onclick="if(confirm(\'Ponastaviti DPA? Podatke boste lahko spremenili in podpisali znova.\')){fetch(\'/settings/dpa/reset\',{method:\'POST\'}).then(r=>r.json()).then(()=>location.reload());}">↺ Ponastavi</button>'
            )
        inner = (f'<p><b>✔ Podpisano:</b> {when} · različica {agreement.version} · '
                 f'SHA-256 {sha}</p>'
                 + " ".join(btns)
                 + f'<iframe src="/settings/dpa/pdf" style="width:100%;height:60vh;border:1px solid #ccc;border-radius:6px;" title="Podpisana DPA"></iframe>')
    elif is_admin:
        inner = ('<p><b>DPA še ni podpisana.</b> Izpolnite podatke v '
                 '<a href="/settings">Nastavitvah šole → DPA</a> in kliknite »Podpiši«.</p>')
    elif is_vodstvo:
        inner = "<p><b>DPA še ni podpisana.</b></p>"
    elif is_teacher:
        inner = ('<p><b>⚠ DPA še ni podpisana.</b> Šola mora najprej podpisati pogodbo '
                 'o obdelavi osebnih podatkov — aplikacija za učitelje zato trenutno ni '
                 'odprta. Obrnite se na šolskega administratorja.</p>')
    else:
        return ""

    return (
        '<div style="border:2px solid #4a6cf7;border-radius:10px;padding:1rem 1.2rem;'
        'margin-bottom:1.5rem;background:#f6f8ff;">'
        f"<h3 style='margin-top:0;color:#1a1a2e;'>📄 Pogodba o obdelavi osebnih podatkov — {html_mod.escape(school.name)}</h3>"
        f"{inner}</div>"
    )


@router.get("/docs/download/{name}")
async def download_doc(name: str, request: Request, db: Session = Depends(get_db)):
    """PDF download z weasyprint.
    
    Generira PDF iz Markdown dokumentacije. Če weasyprint ni nameščen
    (npr. v Docker sliki), vrne 500 napako.
    """
    try:
        content, title = _read_docs(name, db)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)

    try:
        gov_url = _govorilne_url(db, request)
        pdf_bytes = _make_pdf(content, title, obvestilo=name.startswith("obvestilo"), govorilne_url=gov_url)

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
    skola = None
    if user and user.school_id:
        from app.models import School
        sch = db.query(School).filter(School.id == user.school_id).first()
        skola = sch.slug if sch else None
    return tmpl.TemplateResponse(request, "obrazci.html", {"role": role, "skola": skola})


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
    """Urejevalni dokumenti = VSE dokumentacijske strani (vključno EN različice)."""
    return list(ALLOWED.keys())


def _shown_docs() -> list[str]:
    """Dokumenti, ki se pokažejo na /navodila strani.

    Ostanejo SAMO tisti, ki so v produkciji na reservationapp.site dejansko
    prikazani: navodila za učitelje/vodstvo/admin (dropdown v aplikaciji +
    login link) in obvestila učitelji/starši (stran Obrazci). Ostale kopije
    (EN) in notranji/dev dokumenti (main, postavi-lokalni-app, admin-devops,
    aplikacija-rezervacije, govorilne-ure, pogoji, reklama-sola) se tu NE
    prikažejo in NE urejajo — backend /docs/html{...} pa ostane nedotaknjen.
    """
    SHOWN = {
        "navodila-ucitelji",
        "navodila-vodstvo",
        "navodila-admin",
        "obvestilo-ucitelji",
        "obvestilo-starsi",
        "pogoji-uporabe",  # javni dokument (povezava na /govorilne) — urejamo na /navodila
        "dpa",              # DPA — viden adminu/vodstvu, urejamo na /navodila
    }
    return [k for k in _editable_docs() if k in SHOWN]


@router.get("/navodila", response_class=HTMLResponse)
def navodila_main_page(request: Request, db: Session = Depends(get_db)):
    """Stran 'Navodila' — samo glavni admin.

    Pokaže pregled vseh strani, ki so dostopne prek UI-ja, ter urejevalnik
    .md navodil/obvestil (shranjevanje v DB kot override).
    """
    user = _require_main_admin(request, db)
    docs = [
        {"name": k, "label": DOC_LABELS.get(k, k), "overridden": bool(_get_override(db, k))}
        for k in _shown_docs()
    ]
    return OBRAZCI_TEMPLATES.TemplateResponse("navodila_main.html", {
        "request": request,
        "user": user,
        "docs": docs,
        "all_preview": [{"name": k, "label": DOC_LABELS.get(k, k)} for k in _shown_docs()],
    })


@router.get("/api/navodila/docs")
def navodila_list_docs(request: Request, db: Session = Depends(get_db)):
    _require_main_admin(request, db)
    return {"docs": [
        {"name": k, "label": DOC_LABELS.get(k, k), "overridden": bool(_get_override(db, k))}
        for k in _shown_docs()
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
    if name not in _shown_docs():
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
    if name not in _shown_docs():
        raise HTTPException(status_code=400, detail="Ta dokument ni urejevalen")
    _clear_override(db, name)
    log_audit(db, user.id, user.username, "reset_doc", name)
    return {"ok": True, "name": name, "overridden": False}

# ═══════════════════════════════════════════════════════════════════════
# Urejanje strani (predloge HTML/CSS/JS) — univerzalni editor
# Glavni admin prek /navodila preglasi HTML predlogo poljubne strani.
# Override = AppSetting "TEMPLATE_OVERRIDE:<ime>"; uporablja ga
# app/template_override.OverrideLoader ob vsakem renderju. Backend .py
# se tu NE ureja.
# ═══════════════════════════════════════════════════════════════════════

TEMPLATE_FILES = sorted([
    "index.html", "login.html", "registracija.html", "registracija_uspeh.html",
    "admin_users.html", "audit_log.html", "global_settings.html", "schools.html",
    "school_settings.html", "nastavitev.html", "narocnina.html", "nakup.html",
    "obrazci.html", "dejavnosti.html", "govorilne.html", "govorilne_ure.html",
    "govorilne_prijave.html", "zasloni.html", "eracun_izdajatelj.html", "navodila_main.html",
])


def _page_label(name: str) -> str:
    base = name[:-5] if name.endswith(".html") else name
    return base.replace("_", " ").strip().title()


@router.get("/api/pages/list")
def pages_list(request: Request, db: Session = Depends(get_db)):
    _require_main_admin(request, db)
    from app import template_override as tov
    return {"templates": [
        {"name": n, "label": _page_label(n), "overridden": bool(tov.read_override(db, n))}
        for n in TEMPLATE_FILES
    ]}


@router.get("/api/pages/{name}")
def pages_get(name: str, request: Request, db: Session = Depends(get_db)):
    _require_main_admin(request, db)
    if name not in TEMPLATE_FILES:
        raise HTTPException(status_code=404, detail="Predloga ne obstaja")
    from app import template_override as tov
    ov = tov.read_override(db, name)
    content = ov if ov is not None else tov.read_builtin(name)
    if content is None:
        raise HTTPException(status_code=404, detail="Predloge ni mogoče prebrati")
    return {
        "name": name,
        "label": _page_label(name),
        "content": content,
        "overridden": ov is not None,
        "history": len(tov.list_history(db, name)),
    }


@router.post("/api/pages/{name}", status_code=200)
async def pages_save(name: str, request: Request, db: Session = Depends(get_db)):
    user = _require_main_admin(request, db)
    if name not in TEMPLATE_FILES:
        raise HTTPException(status_code=400, detail="Predloga ne obstaja")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")
    content = str(body.get("content", "")) or ""
    from app import template_override as tov
    tov.save_override(db, name, content)
    log_audit(db, user.id, user.username, "edit_page", name)
    return {"ok": True, "name": name, "overridden": True}


@router.post("/api/pages/{name}/reset", status_code=200)
def pages_reset(name: str, request: Request, db: Session = Depends(get_db)):
    user = _require_main_admin(request, db)
    if name not in TEMPLATE_FILES:
        raise HTTPException(status_code=400, detail="Predloga ne obstaja")
    from app import template_override as tov
    tov.clear_override(db, name)
    log_audit(db, user.id, user.username, "reset_page", name)
    return {"ok": True, "name": name, "overridden": False}


@router.post("/api/pages/{name}/revert", status_code=200)
def pages_revert(name: str, request: Request, db: Session = Depends(get_db)):
    user = _require_main_admin(request, db)
    if name not in TEMPLATE_FILES:
        raise HTTPException(status_code=400, detail="Predloga ne obstaja")
    from app import template_override as tov
    prev = tov.revert_override(db, name)
    if prev is None:
        return {"ok": False, "name": name, "reason": "Ni prejšnje verzije v zgodovini."}
    log_audit(db, user.id, user.username, "revert_page", name)
    return {"ok": True, "name": name, "reverted": True}

# ═══════════════════════════════════════════════════════════════════════
# Urejevalnik besedil (ui_strings SL/EN) — za /navodila
# ═══════════════════════════════════════════════════════════════════════

_PAGE_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _string_pages_map() -> dict[str, list[str]]:
    """Kljuc napisa -> strani (.html), kjer nastopa kot t('kljuc', ...)."""
    m: dict[str, list[str]] = {}
    try:
        import re as _re
        for p in _PAGE_TEMPLATE_DIR.glob("*.html"):
            txt = p.read_text(encoding="utf-8")
            keys = set(_re.findall(r"\bt\('([^']+)'", txt)).union(
                    set(_re.findall(r'\bt\("([^"]+)"', txt)))
            for key in keys:
                m.setdefault(key, []).append(p.name)
        for k in m:
            m[k] = sorted(set(m[k]))
    except Exception:
        m = {}
    return m


@router.get("/api/strings")
def strings_list(request: Request, db: Session = Depends(get_db)):
    """Seznam vseh napisov (SL/EN) + na katerih straneh se pojavi."""
    _require_main_admin(request, db)
    pages = _string_pages_map()
    rows = db.query(UIString).order_by(UIString.key).all()
    q = (request.query_params.get("q") or "").strip().lower()
    page_filter = (request.query_params.get("page") or "").strip()

    items = []
    for r in rows:
        sl = r.sl or ""
        en = r.en or ""
        rpages = pages.get(r.key, [])
        if page_filter and page_filter not in rpages:
            continue
        if q and (q not in r.key.lower()) and (q not in sl.lower()) and (q not in en.lower()):
            continue
        items.append({"key": r.key, "sl": sl, "en": en, "pages": rpages})
    all_pages = sorted({p for ps in pages.values() for p in ps})
    return {"strings": items, "pages": all_pages, "total": len(items)}


@router.post("/api/strings/{key}", status_code=200)
async def strings_save(key: str, request: Request, db: Session = Depends(get_db)):
    """Shrani napis (SL in/ali EN) v bazo; takoj velja (i18n cache se izprazni)."""
    user = _require_main_admin(request, db)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")
    row = db.query(UIString).filter(UIString.key == key).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Napisa ni v bazi")
    if "sl" in body:
        row.sl = str(body.get("sl") or "")
    if "en" in body:
        row.en = str(body.get("en") or "")
    db.commit()
    from app.i18n import invalidate_cache
    invalidate_cache()
    log_audit(db, user.id, user.username, "edit_string", key)
    return {"ok": True, "key": key, "sl": row.sl, "en": row.en}

# ═══════════════════════════════════════════════════════════════════════
# Urejanje strani BREZ kode — BLOKI besedila (GET/POST /api/pages/.../text)
# ═══════════════════════════════════════════════════════════════════════
# Predlogo razrežemo na BLOKE vidnega besedila: en_blok = odstavek / naslov /
# seznam-postavka / celica / gumb/label — kot CELOTA (za urejanje velikega
# besedila v enem kosu). Blok, ki vsebuje Jinja ({{ }} / {% %} / {# #}) ali
# script/style, NIJE urejevan tukaj — označen kot 'jinja' (večjezični napis
# / gumb), ki se ureja v Urejevalniku besedil. Ostala koda (HTML oznake) ostane
# nedotaknjena; ob shranitvi se v blok vstavi zgoj novo besedilo.

_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
              "link", "meta", "param", "source", "track", "wbr"}

# Elementi, katerih BESEDILO je ena urejevalna enota (blok).
_BLOCK_TAGS = {
    "P", "H1", "H2", "H3", "H4", "H5", "H6", "LI", "TD", "TH", "DT", "DD",
    "CAPTION", "SUMMARY", "FIGCAPTION", "BLOCKQUOTE", "LABEL", "LEGEND",
    "BUTTON", "TITLE", "OPTION", "ADDRESS", "PRE",
}

_ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "a", "ul", "ol", "li", "br",
                 "code", "span", "del", "sub", "sup"}
_ALLOWED_ATTRS = {"a": {"href", "target"}}


def _extract_passages(tpl: str):
    """Predlogo razreže na bloke besedila.

    Vrne (passages, code_regions):
      passage: {"start","end","name","text","jinja"}   (jinja=True => neurejevan,
               ureja se prek Urejevalnika besedil)
      code:    {"start","end","kind"}  (za prikaz strukture, po potrebi)
    Prazen/nepomeneben blok (le whitespace) se izpusti.
    """
    n = len(tpl)
    i = 0
    state = "text"
    buf_start = 0
    tag_start = -1
    passages: list[dict] = []
    codes: list[dict] = []
    elem_stack: list[str] = []
    pass_stack: list[dict] = []   # open block frames {"name","start","jinja"}

    def finalize(end: int) -> None:
        if not pass_stack:
            return
        fr = pass_stack[-1]
        if end > fr["start"] and tpl[fr["start"]:end].strip():
            passages.append({
                "start": fr["start"], "end": end,
                "name": fr["name"].lower(),
                "jinja": fr["jinja"],
            })
        pass_stack.pop()

    def handle_tag_close(gt: int) -> None:
        nonlocal state
        raw = tpl[tag_start:gt + 1]
        m = re.match(r"<\s*(/?)([A-Za-z][A-Za-z0-9]*)", raw)
        if m:
            closing = m.group(1) == "/"
            name = m.group(2).upper()
            if closing:
                if elem_stack and elem_stack[-1] == name:
                    elem_stack.pop()
                    if name in _BLOCK_TAGS:
                        finalize(tag_start)
            else:
                if name not in _VOID_TAGS:
                    elem_stack.append(name)
                    if name in _BLOCK_TAGS:
                        finalize(tag_start)  # končaj trenutni blok pred gnezdenim
                        pass_stack.append({"name": name, "start": gt + 1, "jinja": False})
        state = "text"

    while i < n:
        c = tpl[i]
        if state == "text":
            if c == "<":
                if tpl.startswith("<!--", i):
                    if pass_stack:
                        pass_stack[-1]["jinja"] = True
                    state = "comment"; tag_start = i; i += 4
                elif tpl[i:i+8].lower().startswith("<script"):
                    if pass_stack:
                        pass_stack[-1]["jinja"] = True
                    state = "script"; tag_start = i; i += 1
                elif tpl[i:i+7].lower().startswith("<style"):
                    if pass_stack:
                        pass_stack[-1]["jinja"] = True
                    state = "style"; tag_start = i; i += 1
                else:
                    state = "tag"; tag_start = i; i += 1
            elif tpl.startswith("{{", i) or tpl.startswith("{%", i) or tpl.startswith("{#", i):
                if pass_stack:
                    pass_stack[-1]["jinja"] = True
                codes.append({"start": i, "kind": "jinja"})
                state = "jinja_end"; i += 2
            else:
                i += 1
        elif state == "tag":
            if c == ">":
                handle_tag_close(i)
                buf_start = i + 1
                i += 1
            elif c in "\"'":
                q = c
                j = tpl.find(q, i + 1)
                i = (j + 1) if j != -1 else n
            else:
                i += 1
        elif state == "jinja_end":
            if tpl.startswith("}}", i) or tpl.startswith("%}", i) or tpl.startswith("#}", i):
                codes[-1]["end"] = i + 2
                state = "text"; buf_start = i + 2; i += 2
            else:
                i += 1
        elif state == "comment":
            if tpl.startswith("-->", i):
                state = "text"; buf_start = i + 3; i += 3
            else:
                i += 1
        elif state in ("script", "style"):
            end_marker = "</script" if state == "script" else "</style"
            j = tpl.find(end_marker, i)
            if j == -1:
                i = n
            else:
                gt = tpl.find(">", j)
                end = (gt + 1) if gt != -1 else j + len(end_marker) + 1
                # odstrani script/style s sklada (bil dodan kot element)
                if elem_stack and elem_stack[-1].lower() == ("script" if state == "script" else "style"):
                    elem_stack.pop()
                state = "text"; buf_start = end; i = end
    if state == "text" and pass_stack:
        finalize(n)

    for p in passages:
        inner = tpl[p["start"]:p["end"]]
        p["text"] = _resolve_edit_text(inner)
        p["dynamic"] = _is_dynamic(inner)
    codes = [c for c in codes if "end" in c]
    return passages, codes


def _sanitize_fragment(markup: str) -> str:
    """Dovoljene oznake (krepko/link/seznam) + escapano besedilo; vse drugo daj stran."""
    allowed = _ALLOWED_TAGS
    out: list[str] = []

    class _P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.drop = 0
        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag in ("script", "style"):
                self.drop += 1
                return
            if tag == "br" and tag in allowed:
                out.append("<br>")
                return
            if tag not in allowed:
                return
            a = ""
            if tag in _ALLOWED_ATTRS:
                for k, v in attrs:
                    k = k.lower()
                    if k in _ALLOWED_ATTRS[tag]:
                        v = (v or "").strip()
                        if k == "href" and v.startswith(("http://", "https://", "mailto:", "tel:", "/", "#", "?")):
                            a += f' href="{html_mod.escape(v, quote=True)}"'
                        elif k == "target" and v in ("_blank", "_self"):
                            a += f' target="{v}"'
            out.append(f"<{tag}{a}>")
        def handle_startendtag(self, tag, attrs):
            if tag.lower() == "br":
                out.append("<br>")
        def handle_endtag(self, tag):
            tag = tag.lower()
            if tag in ("script", "style"):
                self.drop = max(0, self.drop - 1)
                return
            if self.drop:
                return
            if tag != "br" and tag in allowed:
                out.append(f"</{tag}>")
        def handle_data(self, data):
            if self.drop:
                return
            out.append(html_mod.escape(data))
        def handle_comment(self, data):
            pass

    _P().feed(markup)
    return "".join(out)


def _is_dynamic(inner: str) -> bool:
    """Dinamično (bere iz nastavitev/kode) — ni za urejati tukaj."""
    if "{%" in inner:
        return True
    for m in re.finditer(r"\{\{(.*?)\}\}", inner, re.DOTALL):
        expr = " ".join(m.group(1).split())
        if not expr.startswith("t(") and not expr.startswith("t ("):
            return True
    return False


def _resolve_edit_text(inner: str) -> str:
    """Vidno besedilo za urejanje: default iz t('key','default'), Jinja oskubljena,
    oznake odstranjene — uporabnik vidi čist tekst (ne {{ }}/<tags>)."""
    txt = re.sub(r"\{\{\s*t\('[^']*'\s*,\s*'([^']*)'[^}]*?\}\}", r"\1", inner, flags=re.DOTALL)
    txt = re.sub(r"\{[{%][\s\S]*?[}%]\}", "", txt)
    txt = re.sub(r"<[^>]+>", "", txt)
    return " ".join(html_mod.unescape(txt).split())


def _visible_text(markup: str) -> str:
    """Vidna besedila (brez oznak), normalizirano — za primerjavo 'ali se je spremenilo'."""
    txt = re.sub(r"<[^>]+>", "", markup or "")
    return " ".join(html_mod.unescape(txt).split())


def _rebuild_passages(tpl: str, passages: list[dict], edits: dict) -> str:
    """Nova predloga: urejene (ne-jinja) bloke nadomesti z novim besedilom.

    Nespremenjen blok (enako vidno besedilo) ostane POVSEM nedotaknjen, da se
    ohranijo npr. class="brand" in druge oznake; spremenjen se sanitizira."""

    out: list[str] = []
    pos = 0
    for idx, p in enumerate(passages):
        if p["start"] > pos:
            out.append(tpl[pos:p["start"]])
        orig = tpl[p["start"]:p["end"]]
        new = edits.get(str(idx))
        if p["dynamic"] or new is None:
            out.append(orig)
        elif _visible_text(new) == _resolve_edit_text(orig):
            out.append(orig)          # nič spremenil -> ohrani vse (tudi Jinja)
        else:
            out.append(_sanitize_fragment(new))  # spremenil -> postane navadno besedilo
        pos = p["end"]
    out.append(tpl[pos:])
    return "".join(out)


@router.get("/api/pages/{name}/text")
def pages_text(name: str, request: Request, db: Session = Depends(get_db)):
    """Bloki besedila strani za urejevalnik brez kode."""
    _require_main_admin(request, db)
    if name not in TEMPLATE_FILES:
        raise HTTPException(status_code=404, detail="Predloga ne obstaja")
    from app import template_override as tov
    ov = tov.read_override(db, name)
    content = ov if ov is not None else tov.read_builtin(name)
    if content is None:
        raise HTTPException(status_code=404, detail="Predloge ni mogoče prebrati")
    passages, codes = _extract_passages(content)
    items = []
    for idx, p in enumerate(passages):
        items.append({"type": "text", "id": idx, "tag": p["name"],
                      "dynamic": p["dynamic"], "text": p["text"]})
    return {"name": name, "items": items, "overridden": ov is not None,
            "history": len(tov.list_history(db, name))}


@router.post("/api/pages/{name}/text", status_code=200)
async def pages_text_save(name: str, request: Request, db: Session = Depends(get_db)):
    """Shrani urejeno besedilo: vstavi nazaj v predlogo (koda + večjezični ostanejo)."""
    user = _require_main_admin(request, db)
    if name not in TEMPLATE_FILES:
        raise HTTPException(status_code=400, detail="Predloga ne obstaja")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")
    from app import template_override as tov
    ov = tov.read_override(db, name)
    content = ov if ov is not None else tov.read_builtin(name)
    if content is None:
        raise HTTPException(status_code=404, detail="Predloge ni mogoče prebrati")
    passages, _codes = _extract_passages(content)
    edits = body.get("fragments") or {}
    rebuilt = _rebuild_passages(content, passages, edits)
    tov.save_override(db, name, rebuilt)
    log_audit(db, user.id, user.username, "edit_page", f"{name} (besedilo)")
    return {"ok": True, "name": name, "overridden": True}
