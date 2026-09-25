# ─────────────────────────────────────────────────────────────────────────
# tests/test_ocenjevanje_razredi.py — izbor razreda pri ocenjevanjih
#
# Zahteva uporabnika (2026-09-24): »ocenjevanja za razred IP/NIP/ID ni prisoten
# v dropdownu za izbor razreda, ampak je po defaultu prikazan za vse od 6 do 9
# razreda in naj bo druge barve (zelen)«.
#
# Preverjamo (na izrisanem HTML-ju strani, ker gre za odjemalčev JavaScript):
#   * »IP/NIP/ID« se NE ponudi kot razred v izboru (filtriranje po obliki <št>. <oddelek>),
#   * privzeta izbira je skupina 6.–9. razred (oznaka __6_9__), obarvana zeleno,
#   * nalaganje ocenjevanj zna to skupino razširiti na 6., 7., 8. in 9. razred.
# ─────────────────────────────────────────────────────────────────────────

from tests.conftest import login


def _index_html(client, make_user) -> str:
    user = make_user()
    login(client, user.username)
    r = client.get("/")
    assert r.status_code == 200
    return r.text


def _picker_js(html: str) -> str:
    """Izreži telo funkcije populateOcRazredi iz strani."""
    assert "function populateOcRazredi" in html
    return html.split("function populateOcRazredi", 1)[1].split("function populateHours", 1)[0]


def _load_js(html: str) -> str:
    """Izreži telo funkcije loadAssessments iz strani."""
    assert "async function loadAssessments" in html
    return html.split("async function loadAssessments", 1)[1].split("function renderMonthlyCalendar", 1)[0]


# ── 1. IP/NIP/ID ni v izboru razreda ─────────────────────────────────

def test_ip_nip_id_is_filtered_out_of_class_picker(client, make_user):
    html = _index_html(client, make_user)
    funkcija = _picker_js(html)

    # Vzorec za običajen oddelek (npr. 6.a, 9.5) — »IP/NIP/ID« te oblike nima.
    assert "jeObicajen" in funkcija
    assert r"/^\d+\.[A-Za-z0-9čšžČŠŽ]+$/" in funkcija
    # Možnosti se gradijo iz FILTRIRANEGA seznama, ne iz surovih podatkov.
    assert "const razredi = items.filter(jeObicajen)" in funkcija
    assert "items.forEach" not in funkcija
    assert '"IP/NIP/ID"' not in funkcija


# ── 2. Privzeto 6.–9. razred, zeleno ─────────────────────────────────

def test_default_selection_is_six_to_nine_and_green(client, make_user):
    funkcija = _picker_js(_index_html(client, make_user))

    assert 'value="__6_9__"' in funkcija
    assert "6.–9. razred (vsi)" in funkcija
    assert "background:#d1fae5" in funkcija          # zelena podlaga
    assert "color:#065f46" in funkcija                # temnozelena pisava
    # dejansko privzeto izbrano (ne le prva možnost v seznamu)
    assert "sel.value = '__6_9__'" in funkcija


def test_group_shortcuts_still_exist(client, make_user):
    funkcija = _picker_js(_index_html(client, make_user))
    assert 'value="__8__"' in funkcija
    assert 'value="__9__"' in funkcija


# ── 3. Nalaganje razume skupinsko izbiro ─────────────────────────────

def test_load_handles_six_to_nine_group(client, make_user):
    telo = _load_js(_index_html(client, make_user))

    assert "'__6_9__'" in telo
    assert "'6.', '7.', '8.', '9.'" in telo            # širi na vse štiri razrede
    assert "6.–9. razred (vsi)" in telo                # naslov koledarja
    assert "filterPrefix.some" in telo


def test_modal_prefill_ignores_group_values(client, make_user):
    """Skupinska izbira ('__6_9__') ni konkreten razred → obrazca ne prepišemo z njo."""
    html = _index_html(client, make_user)
    assert "indexOf('__') !== 0" in html
