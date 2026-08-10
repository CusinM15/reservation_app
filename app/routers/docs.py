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

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, HTMLResponse
from pathlib import Path
import markdown
import re
import os
import html as html_mod

from app.emoji_pdf import replace_emojis

router = APIRouter(tags=["docs"])

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "documentation"

# Dovoljeni dokumenti — preslikava v datotečni sistem.
# Zakaj whitelist? Preprečuje directory traversal napade.
ALLOWED = {
    "navodila-ucitelji": ["navodila-ucitelji.md"],
    "navodila-ucitelji-en": ["en/navodila-ucitelji.md"],
    "navodila-vodstvo": ["navodila-vodstvo.md"],
    "navodila-vodstvo-en": ["en/navodila-vodstvo.md"],
}

DOC_LABELS = {
    "navodila-ucitelji": "Navodila za učitelje",
    "navodila-ucitelji-en": "Teacher Instructions (English)",
    "navodila-vodstvo": "Navodila za vodstvo in admin",
    "navodila-vodstvo-en": "Management Guide (English)",
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
# Strani so A4 z marginami 2cm, z nogo "OŠ Toneta Čufarja Jesenice".

_PDF_CSS = """
@page { margin: 1.8cm 2cm; @bottom-center { content: "OŠ Toneta Čufarja Jesenice"; font-size: 8pt; color: #999; } }
body { font-family: 'Noto Sans', 'DejaVu Sans', 'Noto Color Emoji', sans-serif; font-size: 11pt; line-height: 1.6; color: #333; }
h1 { font-size: 19pt; color: #1a1a2e; border-bottom: 2px solid #4a6cf7; padding-bottom: 4pt; margin-top: 20pt; font-family: 'Noto Sans', 'DejaVu Sans', 'Noto Color Emoji', sans-serif; }
h2 { font-size: 15pt; color: #1a1a2e; border-bottom: 2px solid #4a6cf7; padding-bottom: 3pt; margin-top: 16pt; font-family: 'Noto Sans', 'DejaVu Sans', 'Noto Color Emoji', sans-serif; }
h3 { font-size: 12.5pt; color: #4a6cf7; margin-top: 12pt; font-family: 'Noto Sans', 'DejaVu Sans', 'Noto Color Emoji', sans-serif; }
h4 { font-size: 11pt; color: #333; margin-top: 8pt; font-family: 'Noto Sans', 'DejaVu Sans', 'Noto Color Emoji', sans-serif; }
p { margin: 5pt 0; text-align: justify; }
img { max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4pt; margin: 10pt 0; display: block; }
img.emoji { display: inline; height: 1.15em; width: auto; border: none; border-radius: 0; margin: 0 0.05em; vertical-align: -0.2em; }
pre { background: #f5f5f5; padding: 10pt 12pt; border-radius: 4pt; font-size: 9pt; font-family: 'DejaVu Sans Mono', 'Noto Color Emoji', monospace; overflow-x: auto; page-break-inside: avoid; }
code { background: #f0f0f0; padding: 1pt 3pt; border-radius: 2pt; font-size: 9.5pt; font-family: 'DejaVu Sans Mono', 'Noto Color Emoji', monospace; }
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


# Emoji regex — pokrije barvne emoji (U+1F000–U+1FAFF), simbole (U+2600–U+27BF),
# dodatne simbole (U+2B00–U+2BFF), skupaj z VS16 (U+FE0F), ZWJ sekvencami
# (U+200D) in regionalnimi indikatorji (zastave, U+1F1E6–U+1F1FF).
_EMOJI_RE = re.compile(
    r'[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]'
    r'(?:\uFE0F|\u200D[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F])*'
    r'[\U0001F1E6-\U0001F1FF]*',
    re.UNICODE,
)

_EMOJI_DIR = DOCS_DIR / "slike" / "emoji"


def _emoji_to_images(html: str) -> str:
    """Zamenja emoji znake v HTML-ju z <img> tagi na lokalne PNG datoteke.

    WeasyPrint ne zna pravilno skalirati bitmap emoji fontov (CBDT/CBLC)
    pri majhnih velikostih — izriše jih kot 2×2 pt pike. Zato v PDF-ju
    emoji nadomestimo s pravimi slikami iz slike/emoji/ (Google Noto
    emoji, 512×512). Če PNG za določen emoji ne obstaja, pustimo znak
    (fallback na font).

    Primer: 👩🏫 (U+1F469 U+200D U+1F3EB) → emoji_u1f469_200d_1f3eb.png
    """

    def _replace(m: re.Match) -> str:
        seq = m.group(0)
        if not seq or seq in ("\ufe0f", "\u200d"):
            return seq
        cp = "_".join(f"{ord(c):x}" for c in seq)
        png = _EMOJI_DIR / f"emoji_u{cp}.png"
        if png.exists():
            return f'<img class="emoji" src="file://{png}" alt="{seq}">'
        return seq

    return _EMOJI_RE.sub(_replace, html)


def _make_pdf(md_content: str, title: str) -> bytes:
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

    # Emoji → slike (PNG iz slike/emoji/). WeasyPrint ne zna pravilno
    # skalirati bitmap emoji fontov (CBDT) pri majhnih velikostih — izriše
    # jih kot 2×2 pt pike. Zato emoji zamenjamo z <img> tagi, ki kažejo
    # na lokalne PNG datoteke (Google Noto emoji, 512×512).
    body_html = _emoji_to_images(body_html)

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{_PDF_CSS}</style>
</head>
<body>
<div class="title-page">
  <h1>{html_mod.escape(title)}</h1>
  <p class="sub">OŠ Toneta Čufarja Jesenice</p>
  <hr>
</div>
{body_html}
</body>
</html>"""

    from weasyprint import HTML as WP_HTML

    pdf_bytes = WP_HTML(string=full_html, base_url=str(DOCS_DIR)).write_pdf()
    return pdf_bytes


# ═══════════════════════════════════════════════════════════════════════
# Bralnik dokumentov
# ═══════════════════════════════════════════════════════════════════════


def _read_docs(name: str) -> tuple[str, str]:
    """Prebere dokumentacijo. Vrne (vsebina, naslov).
    
    Uporablja whitelist (ALLOWED) za preprečevanje directory traversal.
    Če datoteka ne obstaja, vrne ValueError.
    """
    if name not in ALLOWED:
        raise ValueError(f"Dokument '{name}' ne obstaja")

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
async def get_doc(name: str):
    """JSON preview (za klice iz appa)."""
    try:
        content, label = _read_docs(name)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    return {"content": content, "label": label, "name": name}


@router.get("/docs/html/{name}", response_class=HTMLResponse)
async def get_doc_html(name: str):
    """HTML preview s slikami (za hover popup v appu).
    
    Vključuje celoten HTML dokument s CSS oblikovanjem, primernim za
    prikaz v popup oknu. Cache-Control: no-cache zagotavlja, da se
    spremembe dokumentacije takoj pokažejo.
    """
    try:
        content, label = _read_docs(name)
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
    return HTMLResponse(
        content=full_html,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/docs/download/{name}")
async def download_doc(name: str):
    """PDF download z weasyprint.
    
    Generira PDF iz Markdown dokumentacije. Če weasyprint ni nameščen
    (npr. v Docker sliki), vrne 500 napako.
    """
    try:
        content, title = _read_docs(name)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)

    try:
        pdf_bytes = _make_pdf(content, title)
    except Exception as e:
        return JSONResponse({"error": f"Napaka: {str(e)}"}, status_code=500)

    safe_name = f"instrukcije_{name.replace('navodila-', '').replace('-', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
