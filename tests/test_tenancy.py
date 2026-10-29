# ─────────────────────────────────────────────────────────────────────────
# tests/test_tenancy.py — Večšolska (multi-tenant) osnova
#
# Preverja:
#   1. Glavni admin (main_admin) — prijava, stran /schools, ustvarjanje šole.
#   2. Šolski admin — NE vidi strani/API-ja glavnega admina (403).
#   3. URL-aliasi šole — /rezervacije_ostc, /ocenjevanje_ostcj/... delujejo
#      in se prevedejo na kanonične poti.
#   4. Izolacija podatkov — šola A ne vidi rezervacij/uporabnikov šole B.
#   5. Nastavitve šole — branje/pisanje prek API-ja, vpliv na pravila
#      ocenjevanja (ASSESSMENT_MAX_PER_WEEK).
#
# Zakaj ti testi? Večšolska logika je varnostna meja: če se kje pozabi
# filter school_id, ena šola vidi podatke druge. Zato mora biti pokrita.
# ─────────────────────────────────────────────────────────────────────────

from datetime import date, timedelta

from app.database import SessionLocal
from app.config import settings
from app.tenancy import create_school
from tests.conftest import login, default_school_id

MAIN_ADMIN_USER = settings.MAIN_ADMIN_USERNAME
MAIN_ADMIN_PASS = settings.MAIN_ADMIN_PASSWORD

REDIRECT_CODES = (301, 302, 303, 307, 308)

# Vzamemo PON in SRE naslednjega tedna — isti teden, oba v prihodnosti,
# nista 3 zaporedni dni.
_TODAY = date.today()
_MONDAY = _TODAY + timedelta(days=(7 - _TODAY.weekday()) or 7)
_WEDNESDAY = _MONDAY + timedelta(days=2)
MONDAY = _MONDAY.isoformat()
WEDNESDAY = _WEDNESDAY.isoformat()
RAZRED = "5.a"


def _count(model, **filters) -> int:
    db = SessionLocal()
    try:
        return db.query(model).filter_by(**filters).count()
    finally:
        db.close()


# ── 1. Glavni admin ───────────────────────────────────────────────────

def test_main_admin_login_redirects_to_schools(client):
    r = client.post("/auth/login",
                    data={"username": MAIN_ADMIN_USER, "password": MAIN_ADMIN_PASS},
                    follow_redirects=False)
    assert r.status_code in REDIRECT_CODES
    assert r.headers["location"] == "/schools"


def test_main_admin_sees_schools_page(client):
    login(client, MAIN_ADMIN_USER, MAIN_ADMIN_PASS)
    r = client.get("/schools")
    assert r.status_code == 200
    assert settings.SCHOOL_NAME in r.text
    assert settings.DEFAULT_SCHOOL_SLUG in r.text


def test_main_admin_can_create_school_with_generated_aliases(client):
    """Nova šola dobi poti iz oznake: /rezervacije_<oznaka>, /ocenjevanje_<oznaka>."""
    login(client, MAIN_ADMIN_USER, MAIN_ADMIN_PASS)
    r = client.post("/api/schools", data={"name": "Testna šola", "slug": "xtest"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slug"] == "xtest"
    assert "rezervacije_xtest" in body["aliases"]
    assert "ocenjevanje_xtest" in body["aliases"]
    # nova šola je takoj vidna v seznamu
    names = [s["slug"] for s in client.get("/api/schools").json()]
    assert "xtest" in names


def test_create_school_requires_unique_short_name(client):
    """Kratko ime (oznaka) je obvezno in mora biti unikatno."""
    login(client, MAIN_ADMIN_USER, MAIN_ADMIN_PASS)
    # 1) prazen slug -> 400
    r0 = client.post("/api/schools", data={"name": "Šola brez oznake", "slug": ""})
    assert r0.status_code == 400, r0.text
    assert "obvezno" in r0.json()["detail"].lower()
    # 2) podvojen slug (obstoječa šola) -> 400
    r1 = client.post("/api/schools", data={"name": "Duplikat", "slug": "ostcj"})
    assert r1.status_code == 400, r1.text
    assert "že obstaja" in r1.json()["detail"]


def test_main_admin_sees_data_of_all_schools(client, make_user):
    """Glavni admin brez izbrane šole vidi rezervacije vseh šol."""
    from app.models import Reservation
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Druga šola", slug="drugi")
    finally:
        db.close()

    teacher_a = make_user()
    login(client, teacher_a.username)
    client.post("/api/rezervacije", json={
        "date": MONDAY, "hour": 0, "prostor": "tablice", "qty": 5, "teacher_id": 999,
    })
    client.post("/auth/logout")

    teacher_b = make_user(school_id=school_b.id)
    login(client, teacher_b.username)
    client.post("/api/rezervacije", json={
        "date": MONDAY, "hour": 1, "prostor": "Tablice", "qty": 5, "teacher_id": 999,
    })
    client.post("/auth/logout")

    login(client, MAIN_ADMIN_USER, MAIN_ADMIN_PASS)
    rows = client.get("/api/rezervacije").json()
    assert len(rows) == 2  # obe šoli


# ── 2. Šolski admin nima pravic glavnega admina ───────────────────────

def test_school_admin_cannot_list_schools(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    assert client.get("/api/schools").status_code == 403
    assert client.get("/schools").status_code == 403


def test_bootstrap_admin_is_school_admin_of_default_school(client):
    """Bootstrap ustvari ŠOLSKEGA admina privzete šole z imenom admin_<oznaka>
    (golo "admin" ni več uporabljeno, ker je admin vezan na šolo)."""
    from app.models import User
    from app.tenancy import default_school_admin_username
    expected = default_school_admin_username(settings.DEFAULT_SCHOOL_SLUG)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == expected).first()
        assert admin is not None, f"pričakovan uporabnik {expected}"
        assert admin.school_id == default_school_id()
        assert admin.role.value == "admin"
    finally:
        db.close()


# ── 3. URL-aliasi šole ────────────────────────────────────────────────

def test_school_alias_paths_resolve(client, make_user):
    u = make_user()
    login(client, u.username)
    for path in ["/rezervacije_ostc", "/ocenjevanje_ostcj", "/ocenjevanje_ostcj/dejavnosti"]:
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
    # kanonične poti ostajajo enake
    for path in ["/rezervacije", "/ocenjevanje", "/ocenjevanje/dejavnosti"]:
        assert client.get(path, follow_redirects=False).status_code == 200


def test_unknown_alias_is_not_rewritten(client, make_user):
    """Neobstoječ alias ne sme pasti na podatke privzete šole."""
    u = make_user()
    login(client, u.username)
    r = client.get("/rezervacije_neobstojeca", follow_redirects=False)
    assert r.status_code == 404


# ── 4. Izolacija podatkov med šolama ─────────────────────────────────

def test_school_a_does_not_see_school_b_reservations(client, make_user):
    from app.models import Reservation
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Druga šola", slug="drugi")
    finally:
        db.close()

    teacher_b = make_user(school_id=school_b.id)
    login(client, teacher_b.username)
    r = client.post("/api/rezervacije", json={
        "date": MONDAY, "hour": 2, "prostor": "Tablice", "qty": 4, "teacher_id": 999,
    })
    assert r.status_code == 201, r.text
    b_reservation_id = r.json()["id"]
    client.post("/auth/logout")

    teacher_a = make_user()  # privzeta šola
    login(client, teacher_a.username)
    ids = [x["id"] for x in client.get("/api/rezervacije").json()]
    assert b_reservation_id not in ids
    # in rezervacija je res v drugi šoli
    assert _count(Reservation, id=b_reservation_id, school_id=school_b.id) == 1


def test_school_admin_does_not_see_users_of_other_school(client, make_user):
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Druga šola", slug="drugi")
    finally:
        db.close()
    foreign = make_user(username="tuj.ucitelj@test.si", school_id=school_b.id)

    admin_a = make_user(role="admin")
    login(client, admin_a.username)
    r = client.get("/auth/admin/users")
    assert r.status_code == 200
    assert foreign.username not in r.text


def test_school_admin_cannot_delete_user_of_other_school(client, make_user):
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Druga šola", slug="drugi")
    finally:
        db.close()
    foreign = make_user(username="tuj.ucitelj@test.si", school_id=school_b.id)

    admin_a = make_user(role="admin")
    login(client, admin_a.username)
    r = client.post(f"/auth/admin/users/{foreign.id}/deactivate", follow_redirects=False)
    assert r.status_code in REDIRECT_CODES  # ne pade, ampak tudi ne spremeni
    assert _count(type(foreign), id=foreign.id, is_active=True) == 1


# ── Tolerantna prijava (velikost črk / presledki) ─────────────────────
# Zakaj: e-pošta je po standardu neobčutljiva na velikost črk, uporabniki pa
# pogosto vtipkajo drugačno velikost ali prilepijo presledek. V tem primeru
# prijava ne sme pasti z »napačno uporabniško ime ali geslo«.

def test_login_is_tolerant_of_case_and_spaces(client, make_user):
    u = make_user(username="mixed.case@test.si", email="Mixed.Case@Test.SI")
    for ident in ["mixed.case@test.si", "MIXED.CASE@TEST.SI",
                  "  Mixed.Case@Test.SI  ", "mixed.case@TEST.si"]:
        client.post("/auth/logout")
        login(client, ident)
        me = client.get("/auth/me")
        assert me.status_code == 200, f"prijava z {ident!r} ni uspela"
        assert me.json()["id"] == u.id


def test_tolerant_login_still_requires_correct_password(client, make_user):
    """Tolerantnost velja samo za iskanje uporabnika — geslo mora biti pravilno."""
    make_user(username="case2@test.si")
    r = login(client, "CASE2@TEST.SI", password="NapacoGeslo1")
    assert "Napačno" in r.text
    assert client.get("/auth/me", follow_redirects=False).status_code == 307


def test_forgot_password_is_tolerant_of_email_case(client, make_user):
    u = make_user(email="Forgot.Case@Test.SI")
    r = client.post("/auth/forgot-password", data={"email": "forgot.case@TEST.si"})
    assert r.status_code == 200
    assert "poslali povezavo" in r.text
    db = SessionLocal()
    try:
        from app.models import User as _User
        assert db.query(_User).filter(_User.id == u.id).first().reset_token
    finally:
        db.close()


def test_forgot_password_real_typo_still_reported(client, make_user):
    """Resnično neobstoječ e-naslov (npr. vguest namesto guest) se še vedno javi."""
    make_user(email="someone@guest.arnes.si")
    r = client.post("/auth/forgot-password", data={"email": "someone@vguest.arnes.si"})
    assert r.status_code == 200
    assert "ne obstaja" in r.text


# ── 5. Nastavitve šole ────────────────────────────────────────────────

def test_school_admin_can_read_and_write_own_settings(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = default_school_id()

    r = client.get(f"/api/schools/{sid}/settings")
    assert r.status_code == 200, r.text
    assert "values" in r.json() and "RAZREDI" in r.json()["values"]

    r = client.put(f"/api/schools/{sid}/settings", json={"values": {"TABLICE_MAX": "17"}})
    assert r.status_code == 200, r.text
    assert r.json()["values"]["TABLICE_MAX"] == "17"
    # nastavitev res vpliva na aplikacijo (kapaciteta tablic)
    assert client.get("/api/razredi").status_code == 200
    r = client.post("/api/rezervacije", json={
        "date": MONDAY, "hour": 0, "prostor": "tablice", "qty": 18, "teacher_id": 999,
    })
    assert r.status_code == 400
    assert "17" in r.json()["detail"]


def test_school_admin_cannot_write_settings_of_other_school(client, make_user):
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Druga šola", slug="drugi")
    finally:
        db.close()

    admin_a = make_user(role="admin")
    login(client, admin_a.username)
    r = client.put(f"/api/schools/{school_b.id}/settings", json={"values": {"TABLICE_MAX": "99"}})
    assert r.status_code == 403


def test_settings_page_renders_for_school_admin(client, make_user):
    """Stran /settings se izriše (predloga school_settings.html) — brez tega
    bi šolski admin po prijavi dobil 500."""
    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.get("/settings")
    assert r.status_code == 200, r.text
    assert settings.SCHOOL_NAME in r.text
    # obrazec vsebuje razdelke nastavitev — razredi, števila in urnik so zdaj
    # izrisani kot vrstice (vsak v svoji vrstici), ne kot eno polje.
    assert 'id="settings-form"' in r.text
    assert 'id="razredi-rows"' in r.text
    assert 'id="stevila-rows"' in r.text
    assert 'id="schedule-rows"' in r.text
    assert "<label>Razredi</label>" in r.text
    assert "<label>Števila</label>" in r.text


def test_settings_page_renders_for_main_admin(client):
    login(client, MAIN_ADMIN_USER, MAIN_ADMIN_PASS)
    r = client.get("/settings")
    assert r.status_code == 200, r.text
    assert 'id="settings-form"' in r.text


def test_assessment_rules_are_per_school(client, make_user):
    """ASSESSMENT_MAX_PER_WEEK=1 → drugo običajno ocenjevanje v istem tednu pade."""
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = default_school_id()
    r = client.put(f"/api/schools/{sid}/settings", json={"values": {"ASSESSMENT_MAX_PER_WEEK": "1"}})
    assert r.status_code == 200, r.text
    client.post("/auth/logout")

    teacher = make_user()
    login(client, teacher.username)
    first = client.post("/api/ocenjevanja", json={
        "razred": RAZRED, "date": MONDAY, "ponavljanje": False, "teacher_id": 999,
    })
    assert first.status_code == 201, first.text

    second = client.post("/api/ocenjevanja", json={
        "razred": RAZRED, "date": WEDNESDAY, "ponavljanje": False, "teacher_id": 999,
    })
    assert second.status_code == 400, second.text


def test_default_assessment_rules_match_current_school_behaviour(client, make_user):
    """Privzete vrednosti morajo dati dosedanje vedenje: 2 običajni/teden sta OK,
    tretje običajno pade (max 2), ponavljanje pa je dovoljeno (do 3 skupaj)."""
    teacher = make_user()
    login(client, teacher.username)

    # 2 običajni v istem tednu (pon, sre) — obe uspeta
    assert client.post("/api/ocenjevanja", json={
        "razred": RAZRED, "date": MONDAY, "ponavljanje": False, "teacher_id": 999,
    }).status_code == 201
    assert client.post("/api/ocenjevanja", json={
        "razred": RAZRED, "date": WEDNESDAY, "ponavljanje": False, "teacher_id": 999,
    }).status_code == 201

    # tretje običajno (petek) → 400 (max 2 običajni)
    friday = (_MONDAY + timedelta(days=4)).isoformat()
    r = client.post("/api/ocenjevanja", json={
        "razred": RAZRED, "date": friday, "ponavljanje": False, "teacher_id": 999,
    })
    assert r.status_code == 400

    # ponavljanje na petek → dovoljeno (skupaj 3 na teden)
    r = client.post("/api/ocenjevanja", json={
        "razred": RAZRED, "date": friday, "ponavljanje": True, "teacher_id": 999,
    })
    assert r.status_code == 201, r.text


# ── 6. Privzete nastavitve NOVE šole (jezikovno občutljive) ────────────

def test_new_school_default_rooms_follow_language(client):
    """Nova šola dobi majhen nabor prostorov v JEZIKU ustvarjanja:
    Računalnica + Tablice (SL) oz. Computer room + Tablets (EN), tablice = 25."""
    from uuid import uuid4
    from app.tenancy import create_school, get_school_config

    sfx = uuid4().hex[:6]
    db = SessionLocal()
    try:
        s_en = create_school(db, name="Nova EN", slug=f"novaen{sfx}", ui_language="en")
        s_sl = create_school(db, name="Nova SL", slug=f"novasl{sfx}", ui_language="sl")
        en_id, sl_id = s_en.id, s_sl.id
    finally:
        db.close()

    db = SessionLocal()
    try:
        cfg_en = get_school_config(db, en_id)
        cfg_sl = get_school_config(db, sl_id)
        assert cfg_en.get_str("UI_LANGUAGE", "sl") == "en"
        assert cfg_sl.get_str("UI_LANGUAGE", "sl") == "sl"
        assert cfg_en.PROSTORI == ["Computer room", "Tablets"], cfg_en.PROSTORI
        assert cfg_sl.PROSTORI == ["Računalnica", "Tablice"], cfg_sl.PROSTORI
        assert cfg_en.STEVILA.get("Number of tablets") == 25
        assert cfg_sl.STEVILA.get("Število tablic") == 25
        assert cfg_en.PROSTORI_STEVILO.get("Tablets") == "Number of tablets"
        assert cfg_sl.PROSTORI_STEVILO.get("Tablice") == "Število tablic"
    finally:
        db.close()


def test_existing_default_school_rooms_unchanged(client):
    """Privzeta (obstoječa) šola obdrži svoje prostore iz .env — novi privzetki
    veljajo le za NOVE šole (trenutnih šol se ne preimenuje)."""
    from app.tenancy import get_school_config
    db = SessionLocal()
    try:
        cfg = get_school_config(db, default_school_id())
        assert "tablice" in cfg.PROSTORI
    finally:
        db.close()
