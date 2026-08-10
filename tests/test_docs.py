"""Testi za dokumentacijo: PDF download, HTML predogled, emoji → Twemoji PNG slike."""
import pytest
from conftest import make_client

from app.routers.docs import _emoji_to_images, _doc_to_html


# ═══ Enotni testi za emoji → slike (PDF) ═══
def test_emoji_converted_to_twemoji_image():
    """✅ (U+2705) se spremeni v <img> s Twemoji PNG-jem."""
    out = _emoji_to_images("<li>✅ Vsaj 5 znakov</li>")
    assert 'class="emoji"' in out
    assert "2705.png" in out


def test_teacher_zwj_emoji_single_image():
    """👩🏫 (U+1F469 ZWJ U+1F3EB) mora biti ENA slika (1f469-200d-1f3eb.png)."""
    out = _emoji_to_images("<p>\U0001F469\u200d\U0001F3EB Navodila</p>")
    assert "1f469-200d-1f3eb.png" in out
    assert out.count('class="emoji"') == 1


def test_vs16_emoji_falls_back_to_base_png():
    """⚠️ (U+26A0 + VS16) se pretvori v 26a0.png (če 26a0-fe0f.png ne obstaja)."""
    out = _emoji_to_images("<p>\u26a0\ufe0f Opozorilo</p>")
    assert "26a0.png" in out
    assert out.count('class="emoji"') == 1


def test_unsupported_symbols_stay_as_text():
    """✕ (U+2715, brez PNG-ja, DejaVu-safe) ostane tekst."""
    out = _emoji_to_images("<p>✕ Opozorilo</p>")
    assert "✕" in out
    assert 'class="emoji"' not in out


def test_code_blocks_preserved():
    """Koda v <pre>/<code> se ne sme spreminjati (niti emoji)."""
    assert _emoji_to_images("<pre>👩🏫  koda   ostane</pre>") == "<pre>👩🏫  koda   ostane</pre>"
    assert _emoji_to_images("<code>print('😊')</code>") == "<code>print('😊')</code>"


# ═══ HTML predogled (brskalnik) ═══
def test_html_preview_keeps_emoji_and_fixes_images():
    out = _doc_to_html("# 👩🏫 Navodila\n\n- ✅ stvar\n\n![s](slike/x.png)", "test")
    assert "✅" in out and "👩" in out      # emoji ostanejo
    assert 'src="/slike/x.png"' in out      # relativne poti -> /slike/
    assert "&#64;" in out                    # @ zakodiran za Cloudflare


# ═══ API: predogled in PDF download ═══
def test_docs_html_endpoint(app_ready):
    c = make_client()  # /docs/ je javno — ni potrebna prijava
    r = c.get("/docs/html/navodila-ucitelji")
    assert r.status_code == 200
    assert "Navodila" in r.text


def test_docs_download_pdf(app_ready):
    c = make_client()
    r = c.get("/docs/download/navodila-ucitelji")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_docs_unknown_document_404(app_ready):
    c = make_client()
    r = c.get("/docs/neobstaja")
    assert r.status_code == 404
    assert "ne obstaja" in r.json()["error"]
