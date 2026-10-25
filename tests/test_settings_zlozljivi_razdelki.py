# ─────────────────────────────────────────────────────────────────────────
# tests/test_settings_zlozljivi_razdelki.py
#
# 25.10.2026 — nastavitve šole (/settings) dobijo zložljiva poglavja
# (»▸ več / ▾ manj«), enako kot /govorilne/ure, in popravek: Zaslon JS blok
# je bil zunaj <script> → surova koda na dnu strani + mrtvi gumbi.
# ─────────────────────────────────────────────────────────────────────────

import re

from app.config import settings
from tests.conftest import login


def _get_settings_html(client) -> str:
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    return client.get("/settings").text


def test_settings_razdelki_so_zlozljivi(client):
    """Vsak razdelek (h3) je zdaj details.collapsible s summary + toggle-hint.

    'Naročnina šole' je pogojen razdelek (izriše se le, če je prodaja
    omogočena) — v testnem okolju ga ni, zato preverimo vedno-prisotne.
    """
    html = _get_settings_html(client)
    for naslov in ("Osnovno", "Pravila ocenjevanja", "E-pošta (SMTP)",
                   "Digitalni zaslon (nadomeščanja)", "Navodila",
                   "Varnostna kopija šole", "Obnova iz varnostne kopije"):
        # naslov mora biti znotraj summary-ja razdelka
        assert f"<summary><h3>{naslov}</h3>" in html, f"manjka summary za: {naslov}"
    # pogojni razdelek, če je izrisan, mora biti prav tako zložljiv
    if "Naročnina šole" in html:
        assert "<summary><h3>Naročnina šole</h3>" in html
    assert html.count("details class=\"collapsible\"") >= 7


def test_settings_osnovno_odprto_ostali_zaprti(client):
    """'Osnovno' ostane privzeto odprto (open), ostali razdelki zaprti."""
    html = _get_settings_html(client)
    assert '<details class="collapsible" open>' in html


def test_settings_brez_surove_kode_na_dnu(client):
    """Zaslon JS blok mora biti znotraj <script> — brez surovega teksta na dnu."""
    html = _get_settings_html(client)
    opens = [m.start() for m in re.finditer(r"<script>", html)]
    closes = [m.start() for m in re.finditer(r"</script>", html)]
    # uravnovešeno: prej je bil osamljen </script> na dnu (4 odprtja, 1 več zaprtij)
    assert len(opens) == len(closes), "neuravnovešeni <script>/</script> tagi"
    zp = html.find("async function zasloniFetch")
    assert zp != -1, "zasloniFetch manjka"
    prev_open = max((o for o in opens if o < zp), default=-1)
    next_close = min((cl for cl in closes if cl > zp), default=-1)
    assert prev_open < zp < next_close, \
        "zasloniFetch je zunaj <script> — surova koda na dnu!"


def test_settings_toggle_hint_js_obstaja(client):
    """JS posodobi oznako ▸ več / ▾ manj ob odpiranju/zapiranju."""
    html = _get_settings_html(client)
    assert "d.addEventListener('toggle'" in html
    assert "h.textContent = d.open ? ' ▾ manj' : ' ▸ več';" in html
