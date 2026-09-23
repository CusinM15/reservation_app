# ─────────────────────────────────────────────────────────────────────────
# tests/test_stevila_and_razredi.py
#
# Pokriva dve zahtevi iz UI-ja /settings:
#   1. RAZREDI — vsak razred v SVOJI vrstici (kot prostori in urnik). Vrstice
#      se ob shranjevanju sestavijo v vejica-ločen seznam.
#   2. ŠTEVILA — imenovane številske spremenljivke (STEVILA) kot LOČEN objekt,
#      vsaka v svoji vrstici. Prostori se nanje vežejo (PROSTORI_STEVILO,
#      kljukica »število« + spustni seznam) — kapaciteta prostora na uro je
#      vrednost pripisane spremenljivke.
# ─────────────────────────────────────────────────────────────────────────

import json

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
    return client.post("/api/rezervacije", json=payload)


# ── 1. Razredi: vsak razred v svoji vrstici ───────────────────────────

def test_settings_renders_one_row_per_class(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, RAZREDI="1. a,1. b,2. a")

    html = client.get("/settings").text
    assert 'id="razredi-rows"' in html
    assert 'name="RAZREDI"' not in html, "razredi se še vedno izrisujejo kot eno polje"
    assert "function addRazredRow" in html and "function collectRazredi" in html
    assert "Razredi — vsak razred v svoji vrstici" in html
    for r in ("1. a", "1. b", "2. a"):
        assert f'"{r}"' in html


def test_razredi_round_trip(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, RAZREDI="3. a,3. b")
    data = client.get(f"/api/schools/{sid}/settings").json()
    assert data["values"]["RAZREDI"] == "3. a,3. b"


# ── 2. Števila: ločen objekt + vezava prostor → spremenljivka ─────────

def test_settings_renders_numbers_as_own_section(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    html = client.get("/settings").text

    assert 'id="stevila-rows"' in html
    assert 'name="STEVILA"' not in html, "števila se izrisujejo kot eno polje"
    assert "Števila — vsaka spremenljivka v svoji vrstici" in html
    assert "function addSteviloRow" in html and "function collectStevila" in html
    # privzeto (brez zapisa) se število napolni iz starega TABLICE_MAX
    assert '"name": "\\u0160tevilo tablic"' in html or '"name": "Število tablic"' in html


def test_numbers_and_room_binding_round_trip(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid,
         PROSTORI="tablice,racunalnica",
         STEVILA={"Število tablic": 15, "Število računalnikov": 22},
         PROSTORI_STEVILO={"tablice": "Število tablic",
                           "racunalnica": "Število računalnikov"})

    data = client.get(f"/api/schools/{sid}/settings").json()
    assert json.loads(data["values"]["STEVILA"]) == {
        "Število tablic": 15, "Število računalnikov": 22}
    assert json.loads(data["values"]["PROSTORI_STEVILO"]) == {
        "tablice": "Število tablic", "racunalnica": "Število računalnikov"}

    # /api/prostori-qty vrne omejitev po prostoru (ne le enega skupnega »max«)
    q = client.get("/api/prostori-qty").json()
    assert q["limits"] == {"tablice": 15, "racunalnica": 22}


def test_room_capacity_read_from_bound_variable(client, make_user):
    """Kapaciteta prostora je vrednost pripisane številske spremenljivke —
    ne več globalna TABLICE_MAX."""
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid,
         PROSTORI="tablice",
         STEVILA={"Število tablic": 3},
         PROSTORI_STEVILO={"tablice": "Število tablic"})

    assert _rez(client, "tablice", hour=0, qty=2).status_code in (200, 201)
    r = _rez(client, "tablice", hour=0, qty=2)          # 2 + 2 = 4 > 3
    assert r.status_code == 400
    assert "presega kapaciteto (3)" in r.json()["detail"]
    # še en kos se prilega (2 + 1 = 3)
    assert _rez(client, "tablice", hour=0, qty=1).status_code in (200, 201)


def test_two_rooms_with_different_variables_are_independent(client, make_user):
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid,
         PROSTORI="tablice,racunalnica",
         STEVILA={"Število tablic": 2, "Število računalnikov": 5},
         PROSTORI_STEVILO={"tablice": "Število tablic",
                           "racunalnica": "Število računalnikov"})

    assert _rez(client, "tablice", hour=1, qty=2).status_code in (200, 201)
    assert _rez(client, "tablice", hour=1, qty=1).status_code == 400     # 3 > 2
    # računalnica ima svojo kapaciteto (5) in ne omejuje tablic
    assert _rez(client, "racunalnica", hour=1, qty=5).status_code in (200, 201)


def test_room_without_binding_falls_back_to_tablice_max(client, make_user):
    """Prostor s kljukico, a BREZ vezave (npr. še iz starega PROSTORI_QTY),
    uporabi TABLICE_MAX — vedenje obstoječih šol je nespremenjeno."""
    sid = default_school_id()
    _admin(client, make_user)
    _set(client, sid, PROSTORI="tablice", PROSTORI_QTY=["tablice"], TABLICE_MAX=4)

    assert _rez(client, "tablice", hour=2, qty=4).status_code in (200, 201)
    assert _rez(client, "tablice", hour=2, qty=1).status_code == 400     # 5 > 4
