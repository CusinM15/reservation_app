# ─────────────────────────────────────────────────────────────────────────
# tests/test_ocenjevanje_razredi.py — izbor razreda in IP/NIP/ID pri ocenjevanjih
#
# Zahteva uporabnika (2026-09-24), dokončna oblika:
#   * »IP/NIP/ID« naj NE bo izbira v spustnem seznamu razredov,
#   * pri razredih 6.a–7.č ter vseh 8. in 9. (črke in številke) in pri skupinah
#     »8. razred (vsi)« / »9. razred (vsi)« ter privzeti »6.–9. razred (vsi)« naj
#     se poleg tega razreda prikažejo TUDI ocenjevanja razreda IP/NIP/ID,
#   * ta ocenjevanja naj bodo v ZELENI znački (skladno z legendo).
#
# Ker gre za odjemalčev JavaScript, preverjamo izrisani HTML strani + odgovor API-ja.
# ─────────────────────────────────────────────────────────────────────────

from datetime import date

from app.database import SessionLocal
from app.models import Assessment
from tests.conftest import default_school_id, login

DAY = date(2026, 12, 10)
MONTH = "2026-12"


def _index_html(client, make_user) -> str:
    user = make_user()
    login(client, user.username)
    r = client.get("/")
    assert r.status_code == 200
    return r.text


def _js(html: str, zacetek: str, konec: str) -> str:
    assert zacetek in html, f"v strani ni {zacetek!r}"
    return html.split(zacetek, 1)[1].split(konec, 1)[0]


def _picker_js(html: str) -> str:
    return _js(html, "function populateOcRazredi", "function populateHours")


def _load_js(html: str) -> str:
    return _js(html, "async function loadAssessments", "function renderMonthlyCalendar")


def _render_js(html: str) -> str:
    return _js(html, "function renderMonthlyCalendar", "document.getElementById('oc-calendar-container')")


# ── 1. IP/NIP/ID: skrit le v filtru, drugje ostane ───────────────────

def test_ip_nip_id_hidden_only_in_filter_dropdown(client, make_user):
    """IP/NIP/ID se NE ponudi v filtru ocenjevanj, drugje (obrazec za novo
    ocenjevanje, izvoz) pa ostane na voljo."""
    funkcija = _picker_js(_index_html(client, make_user))

    # filtriranje velja izključno za filter (oc-razred); izbirni predmet
    # (IP/NIP) se skrije prek nastavitvenega flag-a, ne več trde kode
    assert "id === 'oc-razred'" in funkcija
    assert "jeObicajen(r) && !ipRazrediSet.has(r)" in funkcija
    assert "jeObicajen" in funkcija


def test_form_dropdown_keeps_ip_nip_id(client, make_user):
    """Obrazec za novo ocenjevanje dobi CEL seznam (torej tudi IP/NIP/ID)."""
    telo = _index_html(client, make_user)
    assert "populateOcRazredi('oc-form-razred', razredi)" in telo


def test_export_dropdown_keeps_ip_nip_id(client, make_user):
    """Izvoz ocenjevanj se polni iz celotnega seznama razredov (brez filtra)."""
    telo = _js(_index_html(client, make_user), "function openExportOcModal",
               "async function exportOcenjevanja")
    assert "razredi.map(r => `<option value=\"${r}\">${r}</option>`)" in telo


# ── 2. Skupinska izbira 6.–9. je ODSTRANJENA ─────────────────────────

def test_six_to_nine_group_option_is_removed(client, make_user):
    """Uporabnik je zahteval odstranitev izbire »6.–9. razred (vsi)«."""
    html = _index_html(client, make_user)
    funkcija = _picker_js(html)

    assert "__6_9__" not in funkcija
    assert "6.–9. razred (vsi)" not in funkcija
    assert "sel.value = '__6_9__'" not in funkcija
    # prav tako je ni nikjer drugje na strani (nalaganje, koledar)
    assert "__6_9__" not in html


def test_group_shortcuts_still_exist(client, make_user):
    funkcija = _picker_js(_index_html(client, make_user))
    assert 'value="__8__"' in funkcija and 'value="__9__"' in funkcija


# ── 3. IP/NIP/ID ocenjevanja se PRIKAŽEJO zraven 6.–9. ───────────────

def test_load_includes_ip_for_grades_6_to_9(client, make_user):
    telo = _load_js(_index_html(client, make_user))

    assert "ipRazrediSet" in telo            # flag iz /api/razredi-ip
    assert "jePosebni" in telo               # prepoznavanje posebne skupine
    assert "jeRazpon69" in telo              # le razredi/skupine 6.–9.
    assert "RAZREDI_69" in telo
    # ocenjevanja posebne skupine se dodajo k izbranemu razredu
    assert "jePosebni(a) && jeRazpon69" in telo
    # posebne skupine se dodajo tudi pri skupinskih izbirah (8./9. vsi)
    assert "jePosebni(a)" in telo
    # izbire 6.–9. ni več
    assert "__6_9__" not in telo


def test_client_filters_locally_so_ip_rows_are_available(client, make_user):
    """Mesečna ocenjevanja se naložijo BREZ filtra po razredu — drugače v odgovoru
    ne bi bilo zapisov IP/NIP/ID in jih ne bi mogli prikazati zraven."""
    telo = _load_js(_index_html(client, make_user))
    assert "&razred=" not in telo
    assert "/api/ocenjevanja?month=${month}" in telo


def test_api_returns_ip_and_class_rows_for_month(client, make_user):
    """Podlaga za prikaz: API za mesec vrne tudi zapise IP/NIP/ID."""
    u = make_user()
    db = SessionLocal()
    try:
        db.add(Assessment(school_id=default_school_id(), razred="IP/NIP/ID",
                          date=DAY, teacher_id=u.id))
        db.add(Assessment(school_id=default_school_id(), razred="6.a",
                          date=DAY, teacher_id=u.id))
        db.commit()
    finally:
        db.close()

    login(client, u.username)
    r = client.get(f"/api/ocenjevanja?month={MONTH}")
    assert r.status_code == 200
    razredi = {row["razred"] for row in r.json()}
    assert "IP/NIP/ID" in razredi
    assert "6.a" in razredi


# ── 4. Zelena značka + legenda ───────────────────────────────────────

def test_ip_assessment_badge_is_green(client, make_user):
    html = _index_html(client, make_user)

    assert ".assessment-ip" in html
    assert "background: #dcfce7" in html            # zelena podlaga značke
    assert "color: #14532d" in html                 # temnozelena pisava


def test_badge_uses_ip_style_and_shows_class(client, make_user):
    telo = _render_js(_index_html(client, make_user))

    assert "const jeIp = ipRazrediSet.has(a.razred);" in telo
    assert "jeIp ? 'assessment-ip'" in telo
    # oznaka razreda se pri IP/NIP/ID izpiše vedno (tudi ko gledamo en razred)
    assert "(jeIp || showAll)" in telo


def test_legend_has_ip_colour(client, make_user):
    html = _index_html(client, make_user)
    assert "background:#dcfce7;border-radius:2px;" in html
    # legenda je zdaj dinamična (flag iz nastavitev), ne več trdo IP/NIP/ID
    assert "Izbirni predmet" in html
    assert "ipRazredi.length ?" in html


# ── 5. Skupinski izbiri 8./9. pri dejavnostih + obrazec ──────────────

def test_activity_field_handles_group_selections(client, make_user):
    telo = _render_js(_index_html(client, make_user))
    assert "razred === '__8__' ? '8.' : '9.'" in telo
    assert "__6_9__" not in telo


def test_modal_prefill_ignores_group_values(client, make_user):
    html = _index_html(client, make_user)
    assert "indexOf('__') !== 0" in html
