# ─────────────────────────────────────────────────────────────────────────
# tests/test_ui_aliases_and_settings.py
#
# Pokriva popravke, ki so jih javili uporabniki v produkciji:
#   1. Poti šole (alias) z zaključno poševnico morajo delovati BREZ preusmeritve
#      (prej je 307 hop izgubil kontekst šole → kazali so se podatki druge šole).
#   2. Odvečno pot šole je mogoče odstraniti (✕ v pregledu šol).
#   3. Uvoz uporabnikov iz CSV (gumb je manjkal).
#   4. Stran /settings: odstranjena polji »Veljavnost povezave za novo geslo« in
#      »E-pošta za poročilo o stanju«, preimenovana povezava »Domov (urnik)« →
#      »Aplikacija«, dodani gumbi za obnovo iz varnostne kopije.
# ─────────────────────────────────────────────────────────────────────────

from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.tenancy import default_school_admin_username
from tests.conftest import login, default_school_id


def _school_admin_login(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    return admin


# ── 1. Poti šole ──────────────────────────────────────────────────────

def test_alias_with_trailing_slash_works_without_redirect(client, make_user):
    """'/rezervacije_ostcj/' mora postreči stran takoj (brez 307), sicer se pri
    preusmeritvi izgubi izbrana šola."""
    u = make_user()
    login(client, u.username)
    for path in ("/rezervacije_ostcj", "/rezervacije_ostcj/",
                 "/ocenjevanje_ostcj", "/ocenjevanje_ostcj/"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 200, f"{path} → {r.status_code}"


def test_alias_keeps_its_own_school_context(client, make_user):
    """Pot šole B postreže nastavitve šole B, tudi če ima uporabnik izbrano
    drugo šolo (piškotek school_ctx). Prej je preusmeritev pri zaključni
    poševnici to izgubila in prikazali so se podatki napačne šole."""
    from app.tenancy import create_school, set_school_setting

    sid = default_school_id()
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Šola B", slug="solab")
        # INACTIVITY_TIMEOUT_ADMIN_MINUTES je per-šola in se izpiše v HTML strani
        # (za admina), zato je dobra sled: katera šola je bila res uporabljena.
        set_school_setting(db, sid, "INACTIVITY_TIMEOUT_ADMIN_MINUTES", "11")
        set_school_setting(db, school_b.id, "INACTIVITY_TIMEOUT_ADMIN_MINUTES", "22")
        db.commit()
    finally:
        db.close()

    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    client.cookies.set("school_ctx", str(sid))     # izbrana je šola A

    html_b = client.get("/rezervacije_solab/", follow_redirects=False)
    assert html_b.status_code == 200
    assert "1320000" in html_b.text                # 22 min → šola B
    assert "660000" not in html_b.text

    html_a = client.get("/rezervacije", follow_redirects=False)
    assert "660000" in html_a.text                 # 11 min → šola A


# ── 2. Odstranitev poti ───────────────────────────────────────────────

def test_alias_can_be_added_and_removed(client, make_user):
    _school_admin_login(client, make_user)
    sid = default_school_id()
    alias = "rezervacije_odvecna"

    r = client.post(f"/api/schools/{sid}/aliases", data={"alias": alias})
    assert r.status_code == 201, r.text
    assert client.get(f"/{alias}", follow_redirects=False).status_code == 200

    r = client.delete(f"/api/schools/{sid}/aliases/{alias}")
    assert r.status_code == 200, r.text
    assert alias not in r.json()["aliases"]
    assert client.get(f"/{alias}", follow_redirects=False).status_code == 404


def test_alias_remove_unknown_returns_404(client, make_user):
    _school_admin_login(client, make_user)
    sid = default_school_id()
    r = client.delete(f"/api/schools/{sid}/aliases/ne-obstaja")
    assert r.status_code == 404


# ── 3. Uvoz uporabnikov iz CSV ────────────────────────────────────────

def test_csv_import_adds_users_to_own_school(client, make_user):
    _school_admin_login(client, make_user)
    csv_text = (
        "username,email,first_name,last_name,role,password\n"
        "novi.ucitelj@test.si,novi.ucitelj@test.si,Novi,Učitelj,teacher,Geslo123\n"
        "se.ucitelj@test.si,se.ucitelj@test.si,Se,Enkrat,teacher,Geslo123\n"
    )
    r = client.post("/auth/admin/users/import",
                    files={"file": ("u.csv", csv_text, "text/csv")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 2
    assert data["errors"] == []

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "novi.ucitelj@test.si").first()
        assert u is not None
        assert u.school_id == default_school_id()
        assert u.first_name == "Novi"
    finally:
        db.close()


def test_csv_import_reports_bad_rows(client, make_user):
    _school_admin_login(client, make_user)
    csv_text = (
        "username,email,role\n"
        ",brez.imena@test.si,teacher\n"
        "slaba.vloga@test.si,slaba.vloga@test.si,neobstoji\n"
    )
    r = client.post("/auth/admin/users/import",
                    files={"file": ("u.csv", csv_text, "text/csv")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 0
    assert len(data["errors"]) == 2


def test_csv_import_teacher_forbidden(client, make_user):
    teacher = make_user()
    login(client, teacher.username)
    r = client.post("/auth/admin/users/import",
                    files={"file": ("u.csv", "username,role\nx@test.si,teacher\n", "text/csv")})
    assert r.status_code == 403


# ── 4. Stran /settings ────────────────────────────────────────────────

def test_settings_page_omits_removed_fields_and_renames_home_link(client, make_user):
    _school_admin_login(client, make_user)
    html = client.get("/settings").text

    # odstranjeni polji — v obrazcu jih ne sme biti
    assert "Veljavnost povezave za novo geslo" not in html
    assert "E-pošta za poročilo o stanju" not in html
    # preimenovana povezava
    assert "Aplikacija" in html
    assert "Domov (urnik)" not in html
    # polja, ki morajo ostati
    assert "Število tablic" in html
    assert "Timeout neaktivnosti" in html


def test_settings_page_has_restore_buttons(client, make_user):
    _school_admin_login(client, make_user)
    html = client.get("/settings").text
    assert "Obnova iz varnostne kopije" in html
    for domain in ("dejavnosti", "rezervacije", "ocenjevanje", "vse"):
        assert f"startRestore('{domain}')" in html
    assert 'id="restore-file"' in html


def test_settings_page_has_password_change(client, make_user):
    """Glavni admin in šolski admin morata imeti možnost zamenjati svoje geslo."""
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    html = client.get("/schools").text
    assert "Spremeni geslo" in html
    assert "submitChangePassword" in html
    assert 'id="pw-old"' in html

# ── 5. Urnik: vsaka ura v svoji vrstici ───────────────────────────────
# Zahteva: na /settings naj bo urnik iz vrstic (ena ura = ena vrstica),
# ne eno samo polje s surovim JSON-om.

def test_settings_renders_schedule_as_one_row_per_hour(client, make_user):
    sid = default_school_id()
    _school_admin_login(client, make_user)

    r = client.put(f"/api/schools/{sid}/settings", json={
        "values": {"SCHEDULE": {"0": "07:30-08:15", "1": "08:20-09:05", "2": "09:15-10:00"}}
    })
    assert r.status_code == 200, r.text

    html = client.get("/settings").text
    assert 'id="schedule-rows"' in html
    assert 'name="SCHEDULE"' not in html, "urnik se še vedno izrisuje kot eno polje"
    # ure pridejo v stran kot vrstice (JS jih izriše)
    assert '"index": "0", "value": "07:30-08:15"' in html
    assert '"index": "1", "value": "08:20-09:05"' in html
    assert '"index": "2", "value": "09:15-10:00"' in html
    assert "function addScheduleRow" in html and "function collectSchedule" in html
    assert "<label>Urnik</label>" in html


def test_schedule_saved_from_ui_round_trips_as_json(client, make_user):
    """Kar uporabnik vpiše v vrstice, se shrani kot JSON in prebere nazaj
    v iste vrstice (oblika v bazi ostane nespremenjena)."""
    sid = default_school_id()
    _school_admin_login(client, make_user)

    # tako kot bi poslal JS: SCHEDULE kot JSON niz iz vrstic
    r = client.put(f"/api/schools/{sid}/settings", json={
        "values": {"SCHEDULE": '{"0": "08:00-08:45", "1": "08:50-09:35"}'}
    })
    assert r.status_code == 200, r.text

    html = client.get("/settings").text
    assert '"index": "0", "value": "08:00-08:45"' in html
    assert '"index": "1", "value": "08:50-09:35"' in html
    # vrstni red je numeričen (0 pred 1), ne leksikografski
    assert html.index('"index": "0"') < html.index('"index": "1"')


def test_schedule_rows_sorted_numerically(client, make_user):
    """Pri 10+ urah mora vrstni red ostati 2, 9, 10 (ne 10, 2, 9)."""
    sid = default_school_id()
    _school_admin_login(client, make_user)
    client.put(f"/api/schools/{sid}/settings", json={
        "values": {"SCHEDULE": {"10": "18:00-18:45", "2": "09:15-10:00", "9": "17:00-17:45"}}
    })
    html = client.get("/settings").text
    i2 = html.index('"index": "2"')
    i9 = html.index('"index": "9"')
    i10 = html.index('"index": "10"')
    assert i2 < i9 < i10


def test_invalid_schedule_json_is_rejected(client, make_user):
    sid = default_school_id()
    _school_admin_login(client, make_user)
    r = client.put(f"/api/schools/{sid}/settings", json={"values": {"SCHEDULE": "{ni-json"}})
    assert r.status_code == 400
    assert "veljaven JSON" in r.json()["detail"]


# ── 6. Dostop do /settings iz rezervacij/ocenjevanja ─────────────────
# Poročilo uporabnika: občasne težave pri odpiranju /settings iz strani
# »Rezervacije in ocenjevanje«. Preverimo oba zavihka, obe poti (kanonično in
# pot šole) ter poseben primer glavnega admina brez izbrane šole.

def test_settings_link_carries_school_context(client, make_user):
    """Povezava »⚙️ Nastavitve šole« v aplikaciji mora prenesti izbrano šolo,
    da pri glavnem adminu (in na poteh šol) ne pade v napako 400."""
    sid = default_school_id()
    _school_admin_login(client, make_user)
    for tab in ("/rezervacije", "/ocenjevanje"):
        html = client.get(tab).text
        assert f'href="/settings?school_id={sid}"' in html, f"{tab}: manjka kontekst šole"
        assert 'id="settings-link"' in html


def test_settings_reachable_from_both_tabs_and_school_paths(client, make_user):
    """Šolski admin mora /settings odpreti z obeh zavihkov in z obeh poti šole."""
    _school_admin_login(client, make_user)
    for path in ("/rezervacije", "/ocenjevanje",
                 "/rezervacije_ostcj", "/ocenjevanje_ostcj"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 200, f"{path} → {r.status_code}"
        s = client.get("/settings", follow_redirects=False)
        assert s.status_code == 200, f"/settings po {path} → {s.status_code}"


def test_alias_path_sets_context_so_settings_open_same_school(client, make_user):
    """Glavni admin, ki vstopi prek poti šole, dobi piškotek school_ctx — zato
    /settings (kanonična pot) odpre ISTO šolo (prej bi se izgubil kontekst)."""
    sid = default_school_id()
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    r = client.get("/rezervacije_ostcj", follow_redirects=False)
    assert r.status_code == 200
    assert client.cookies.get("school_ctx") == str(sid)
    html = client.get("/settings")
    assert html.status_code == 200
    assert "Nastavitve šole" in html.text


def test_settings_main_admin_without_school_gets_chooser(client, make_user):
    """Glavni admin z VEČ šolami in brez izbrane šole naj ne dobi gole napake
    400, ampak izbiro šol (stran se odpre)."""
    from app.tenancy import create_school

    db = SessionLocal()
    try:
        create_school(db, name="Šola B", slug="solab")
    finally:
        db.close()

    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    r = client.get("/settings")                     # brez school_id in brez piškotka
    assert r.status_code == 200
    assert "Izberite šolo" in r.text
    assert "Šola B" in r.text
    assert "school_id=" in r.text


def test_nastavitev_demo_je_javen_s_psevdo_podatki(client):
    """Povezava z prijavne strani (?demo=1) deluje BREZ prijave in prikaže
    predogled navodil s psevdo (demo) podatki."""
    r = client.get("/nastavitev?demo=1")
    assert r.status_code == 200
    assert "OŠ Primer" in r.text
    assert "Predogled navodil" in r.text
    assert "test@example.invalid" in r.text


def test_nastavitev_brez_prijave_brez_demo_preusmeri_na_prijavo(client):
    """Brez ?demo=1 neprijavljen uporabnik ne sme videti navodil."""
    r = client.get("/nastavitev", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert "/auth/login" in r.headers.get("location", "")
