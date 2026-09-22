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
    assert "Največ tablic na uro" in html
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