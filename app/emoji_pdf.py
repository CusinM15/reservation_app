# ─────────────────────────────────────────────────────────────────────────
# app/emoji_pdf.py — Rasterizacija emojijev za PDF (workaround za weasyprint)
#
# Problem: WeasyPrint 69 obarvanih emoji (Noto Color Emoji, CBDT font)
# postavi na 2x2pt — emoji so v PDF praktično nevidni (mikroskopski madeži),
# čeprav so v brskalniku (HTML preview) lepi.
#
# Rešitev: emojije sami rasteriziramo iz fonta (PNG bitmape v CBDT tabeli)
# in jih v HTML-ju zamenjamo z <img> tagi prave velikosti (height:1.15em).
# WeasyPrint vgradi običajne slike brez težav.
#
# Shaping (uharfbuzz) poskrbi za pravilne ZWJ ligature (npr. 👩‍🏫 → en glif).
# ─────────────────────────────────────────────────────────────────────────

import base64
import html as html_mod
import os
import re
import subprocess
from functools import lru_cache

import uharfbuzz as hb
from fontTools.ttLib import TTFont

# Emoji sekvence: osnovni emoji/simbol (vključno z letterlike simboli kot ℹ️)
# + opcijski VS16 + opcijske (VS16? ZWJ emoji) skupine + opcijski VS16.
# Zajame tudi 👩🏫 (ZWJ brez predhodnega VS16) in ⚠️/ℹ️ (VS16).
_EMOJI_RE = re.compile(
    r"(?:"
    r"[\U0001F000-\U0001FAFF\u2100-\u27BF\u2B00-\u2BFF]"
    r"(?:\uFE0F?\u200D[\U0001F000-\U0001FAFF\u2100-\u27BF\u2B00-\u2BFF])*"
    r"\uFE0F?"
    r")"
)

_FONT_PATH: str | None = None
_TT: TTFont | None = None
_HB_FONT: hb.Font | None = None


def _find_font() -> str:
    """Poišči Noto Color Emoji (CBDT). Najprej znane poti, potem fc-match."""
    candidates = [
        os.environ.get("EMOJI_FONT_PATH", ""),
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",  # Debian/Docker
        "/usr/share/fonts/opentype/noto/NotoColorEmoji.ttf",
        os.path.expanduser("~/.fonts/NotoColorEmoji.ttf"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{file}", "Noto Color Emoji"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip() and os.path.exists(out.stdout.strip()):
            return out.stdout.strip()
    except Exception:
        pass
    raise FileNotFoundError(
        "Noto Color Emoji font ni nameščen! (apt: fonts-noto-color-emoji)"
    )


def _load():
    global _FONT_PATH, _TT, _HB_FONT
    if _TT is None:
        _FONT_PATH = _find_font()
        _TT = TTFont(_FONT_PATH)
        blob = hb.Blob.from_file_path(_FONT_PATH)
        _HB_FONT = hb.Font(hb.Face(blob))
    return _TT, _HB_FONT


def _shape_to_glyph(seq: str) -> int | None:
    """Vrne glyph id za emoji sekvenco (uharfbuzz upošteva ZWJ ligature)."""
    _, hb_font = _load()
    buf = hb.Buffer()
    buf.add_str(seq)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf)
    if not buf.glyph_infos:
        return None
    return buf.glyph_infos[0].codepoint


@lru_cache(maxsize=256)
def render_emoji_png(seq: str) -> bytes | None:
    """Vrne PNG bajte (barvni emoji) ali None, če glifa ni mogoče izvleči."""
    tt, _ = _load()
    gid = _shape_to_glyph(seq)
    if gid is None:
        return None
    gname = tt.getGlyphName(gid)
    strike = tt["CBDT"].strikeData[0]  # edini strike v Noto Color Emoji
    rec = strike.get(gname)
    if rec is None:
        return None
    return rec.imageData  # že PNG (format 17 v CBDT)


@lru_cache(maxsize=256)
def emoji_img_tag(seq: str) -> str:
    """<img> tag z data URI za emoji sekvenco (ali original, če ne gre)."""
    png = render_emoji_png(seq)
    if png is None:
        return seq  # fallback: pusti originalni znak
    b64 = base64.b64encode(png).decode("ascii")
    return (
        f'<img src="data:image/png;base64,{b64}" alt="{html_mod.escape(seq)}" '
        'style="height:1.15em;width:auto;vertical-align:-0.18em;'
        'display:inline-block;border:none;margin:0;padding:0;">'
    )


def replace_emojis(html: str) -> str:
    """Zamenja vse emoji sekvence v HTML-ju z <img> tagi (za weasyprint)."""
    return _EMOJI_RE.sub(lambda m: emoji_img_tag(m.group(0)), html)
