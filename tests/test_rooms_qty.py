# ─────────────────────────────────────────────────────────────────────────
# tests/test_rooms_qty.py — prostori: vsak v svoji vrstici + kljukica »število«
#
# Zahteva: na /settings naj bo vsak prostor v svoji vrstici, s kljukico
# »število«. Ob kljukici se odpre spustni seznam z imenovanimi številskimi
# spremenljivkami (STEVILA) — prostor se veže na izbrano, kapaciteta na uro
# pa je njena vrednost. Brez kljukice ostane prostor ekskluziven.
#
# Pomembno: privzeto je PROSTORI_QTY = "tablice" in TABLICE_MAX = 28, zato je
# vedenje obstoječih šol (ostcj) NESPREMENJENO.
# ─────────────────────────────────────────────────────────────────────────

from app.database import SessionLocal
from tests.conftest import login, default_school_id


def _admin(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    return admin


def _set(client, sid, **values):
    r = client.put(f"/api/schools/{sid}/settings", json={"values": values})
    assert r.status_code == 200, r.text
    return r


def _rez(client, prostor, hour, qty=None, day=15):
    payload = {"date": f"2026-12-{day:02d}", "hour": hour, "prostor": prostor,
               "teacher_id": 1}
    if qty is not None:
        payload["qty"] = qty
        payload["name"] = None
    return client.post("/api/rezervacije", json=payload)


# ── 1. Stran /settings: vrstice prostorov + kljukice ──────────────────

def test_settings_renders_one_row_per_room_with_checkbox(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    html = client.get("/settings").text

    assert 'id="prostori-rows"' in html
    assert 'name="PROSTORI"' not in html, "prostori se še vedno izrisujejo kot eno polje"
    assert "function addProstorRow" in html and "function collectProstori" in html
    # Kljukica se zdaj imenuje samo »število« (prej »kot Tablice«).
    assert "število" in html
    assert "kot Tablice" not in html
    assert "<label>Prostori</label>" in html
    # vrstice se izrišejo na odjemalcu iz tega seznama
    assert '"name": "tablice"' in html
    assert '"name": "racunalnica"' in html
    # spustni seznam številskih spremenljivk
    assert "function refreshSteviloOptions" in html and "prostor-stevilo-name" in html


def test_settings_checkbox_follows_saved_setting(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, PROSTORI="tablice,racunalnica,ladja", PROSTORI_QTY=["tablice", "ladja"])
    html = client.get("/settings").text
    assert '"name": "tablice"' in html
    assert '"name": "racunalnica"' in html
    assert '"name": "ladja"' in html
    # prostori s kljukico imajo vezavo na spremenljivko, prostor brez pa ne
    # (Jinja |tojson ključe izpiše po abecedi: name, popoldan, stevilo)
    assert '"stevilo": "\\u0160tevilo tablic"' in html, "prostor s kljukico nima vezave"
    assert '"name": "racunalnica", "popoldan": false, "stevilo": ""' in html, "prostor brez kljukice ne sme imeti vezave"


def test_rooms_and_qty_round_trip(client, make_user):
    """PROSTORI_QTY se shranjuje kot seznam — tako je mogoče izraziti tudi
    PRAZEN seznam (admin odkljuka vse), česar prazen niz ne bi omogočil."""
    import json
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, PROSTORI="tablice,ladja,tablice2", PROSTORI_QTY=["tablice", "tablice2"])
    data = client.get(f"/api/schools/{sid}/settings").json()
    values = data.get("values", data)
    assert values["PROSTORI"] == "tablice,ladja,tablice2"
    assert json.loads(values["PROSTORI_QTY"]) == ["tablice", "tablice2"]


# ── 2. Endpoint za stran ──────────────────────────────────────────────

def test_prostori_qty_endpoint(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, PROSTORI="tablice,ladja", PROSTORI_QTY=["ladja"], TABLICE_MAX=7)
    d = client.get("/api/prostori-qty").json()
    assert d["rooms"] == ["ladja"]
    assert d["max"] == 7
    # kapaciteta je na voljo tudi po prostoru
    assert d["limits"]["ladja"] == 7


# ── 3. Vedenje: prostor »kot Tablice« ─────────────────────────────────

def test_custom_qty_room_requires_quantity(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, PROSTORI="tablice,tablice2", PROSTORI_QTY=["tablice2"])

    r = _rez(client, "tablice2", hour=0)          # brez qty
    assert r.status_code == 400
    assert "morate navesti število" in r.json()["detail"]


def test_custom_qty_room_is_shared_and_capped(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, PROSTORI="tablice,tablice2", PROSTORI_QTY=["tablice2"], TABLICE_MAX=5)

    assert _rez(client, "tablice2", hour=1, qty=2).status_code in (200, 201)
    # ni ekskluziven — druga rezervacija v isti uri je dovoljena
    assert _rez(client, "tablice2", hour=1, qty=2).status_code in (200, 201)
    # skupna vsota 4+2 = 6 > 5 → zavrnjeno
    r = _rez(client, "tablice2", hour=1, qty=2)
    assert r.status_code == 400
    assert "presega kapaciteto" in r.json()["detail"]


def test_room_without_checkbox_stays_exclusive(client, make_user):
    """Prostor BREZ kljukice se obnaša kot prej: ena rezervacija na uro."""
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, PROSTORI="tablice,racunalnica", PROSTORI_QTY=["tablice"])

    assert _rez(client, "racunalnica", hour=2).status_code in (200, 201)
    r = _rez(client, "racunalnica", hour=2)
    assert r.status_code == 400


def test_room_removed_from_qty_becomes_exclusive(client, make_user):
    """Če šola tablici ODVZAME kljukico, tablice niso več deljene."""
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, PROSTORI="tablice,racunalnica", PROSTORI_QTY=[])

    assert _rez(client, "tablice", hour=3).status_code in (200, 201)   # brez qty
    r = _rez(client, "tablice", hour=3)
    assert r.status_code == 400


# ── 4. Privzeto vedenje (ostcj) je nespremenjeno ──────────────────────

def test_default_qty_room_is_tablice(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    d = client.get("/api/prostori-qty").json()
    assert "tablice" in d["rooms"]

    # tablice zahtevajo qty in so omejene s TABLICE_MAX
    assert _rez(client, "tablice", hour=4).status_code == 400
    assert _rez(client, "tablice", hour=4, qty=5).status_code in (200, 201)
    assert _rez(client, "tablice", hour=4, qty=5).status_code in (200, 201)
    # dve rezervaciji sta dovoljeni (prostor ni ekskluziven)
    first_two = client.get("/api/rezervacije?start=2026-12-15&end=2026-12-15").json()
    assert len([r for r in first_two if r["prostor"] == "tablice" and r["hour"] == 4]) == 2


def test_adding_room_like_tablice_later(client, make_user):
    """Scenarij uporabnika: tablice so bile izbrisane, pozneje jih želi nazaj
    »kot na ostcj« — doda prostor in obkljuka »kot Tablice«."""
    sid = default_school_id()
    _admin(client, make_user)

    # 1) prostor ni več v seznamu
    _set(client, sid, PROSTORI="racunalnica,ladja", PROSTORI_QTY=[])
    r = _rez(client, "tablice", hour=5, qty=1)
    assert r.status_code == 400, "neveljaven prostor mora biti zavrnjen"

    # 2) prostor vrne in obkljuka »kot Tablice«
    _set(client, sid, PROSTORI="racunalnica,ladja,tablice", PROSTORI_QTY=["tablice"])
    assert _rez(client, "tablice", hour=5).status_code == 400        # zahteva qty
    assert _rez(client, "tablice", hour=5, qty=3).status_code in (200, 201)
    assert _rez(client, "tablice", hour=5, qty=3).status_code in (200, 201)   # deljen prostor

    html = client.get("/settings").text
    assert '"name": "tablice"' in html