# ─────────────────────────────────────────────────────────────────────────
# tests/test_user_csv_import.py — uvoz uporabnikov iz CSV (tolerantno)
#
# Poročilo uporabnika: »import csv uporabnikov mi nikakor ne dela« — poskusil je
# vnesti CSV BREZ glave, z SLOVENSKO vlogo in BREZ gesel:
#
#   mt.cusin@gmail.com,mt.cusin@gmail.com,ime1,priimek1,učitelj
#   ...
#
# Prej je importer zahteval glavo username/email/first_name/last_name/role/password,
# poznal samo angleške vloge in brez gesla uporabil privzeto. Zdaj:
#   * glava ni obvezna (privzeti vrstni red), imena stolpcev SI ali EN;
#   * vloga je lahko učitelj/vodstvo/admin;
#   * geslo si izmisli aplikacija (vrne ga v povzetku), če ga v vrstici ni;
#   * podvojeni uporabniki v datoteki se zavrnejo z jasno napako.
# ─────────────────────────────────────────────────────────────────────────

from app.config import validate_password_strength
from app.database import SessionLocal
from app.models import User
from app.routers.auth import (
    _generate_import_password,
    _parse_user_csv,
    verify_password,
)
from tests.conftest import default_school_id, login


def _admin(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    return admin


def _import(client, csv_text: str):
    return client.post(
        "/auth/admin/users/import",
        files={"file": ("u.csv", csv_text, "text/csv")},
    )


def _school_users():
    db = SessionLocal()
    try:
        return {u.username: u for u in
                db.query(User).filter(User.school_id == default_school_id()).all()}
    finally:
        db.close()


# ── 1. Točno uporabnikov primer (brez glave, SI vloga, brez gesel) ────

def test_user_exact_csv_without_header(client, make_user):
    """Podvojeni uporabnik v datoteki: prvi se uvozi, ostali dobijo jasno
    napako (trije enaki računi ne morejo obstajati — prijava bi bila dvoumna)."""
    _admin(client, make_user)
    csv_text = (
        "mt.cusin@gmail.com,mt.cusin@gmail.com,ime1,priimek1,učitelj\n"
        "mt.cusin@gmail.com,mt.cusin@gmail.com,ime2,priimek2,učitelj\n"
        "mt.cusin@gmail.com,mt.cusin@gmail.com,ime3,priimek3,učitelj\n"
    )
    r = _import(client, csv_text)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 1
    assert len(data["errors"]) == 2
    assert all("naveden večkrat" in e for e in data["errors"])
    # geslo si je aplikacija izmislila in ga vrnila
    assert len(data["users"]) == 1
    assert data["users"][0]["password"]

    u = _school_users()["mt.cusin@gmail.com"]
    assert u.role.value == "teacher"
    assert u.first_name == "ime1"


def test_distinct_usernames_all_created_and_login_works(client, make_user):
    """Ločena uporabniška imena, brez gesel → vsi se uvozijo, vsak dobi svoje
    izmišljeno geslo, s katerim se lahko PRIJAVI (geslo je veljavno)."""
    _admin(client, make_user)
    csv_text = (
        "ana.novak@test.si,ana.novak@test.si,Ana,Novak,učitelj\n"
        "bor.kralj@test.si,bor.kralj@test.si,Bor,Kralj,profesor\n"
        "cvetka.zupan@test.si,cvetka.zupan@test.si,Cvetka,Župan,vodstvo\n"
    )
    r = _import(client, csv_text)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 3 and data["errors"] == []
    passwords = {u["username"]: u["password"] for u in data["users"]}
    assert len(passwords) == 3
    assert all(validate_password_strength(pw) is None for pw in passwords.values())

    users = _school_users()
    assert users["ana.novak@test.si"].role.value == "teacher"
    assert users["bor.kralj@test.si"].role.value == "teacher"      # profesor → učitelj
    assert users["cvetka.zupan@test.si"].role.value == "vodstvo"
    # geslo res deluje (hash ustreza izmišljenemu geslu)
    assert verify_password(passwords["ana.novak@test.si"],
                           users["ana.novak@test.si"].password_hash)

    # ... in prijava z njim uspe
    r2 = login(client, "ana.novak@test.si", passwords["ana.novak@test.si"])
    assert r2.status_code in (200, 303), r2.text


# ── 2. Slovenske glave in vloge ───────────────────────────────────────

def test_slovenian_header_aliases(client, make_user):
    _admin(client, make_user)
    csv_text = (
        "uporabnisko_ime,e-posta,ime,priimek,vloga,geslo\n"
        "dana.d@test.si,dana.d@test.si,Dana,Dolenc,učitelj,Geslo123\n"
    )
    data = _import(client, csv_text).json()
    assert data["created"] == 1 and data["errors"] == []
    # gesla iz datoteke NE vračamo nazaj (ni razkrito v povzetku)
    assert data["users"][0]["password"] is None
    u = _school_users()["dana.d@test.si"]
    assert u.role.value == "teacher" and u.last_name == "Dolenc"


def test_english_header_still_works(client, make_user):
    _admin(client, make_user)
    csv_text = ("username,email,first_name,last_name,role,password\n"
                "eve.e@test.si,eve.e@test.si,Eve,Erjavec,teacher,Geslo123\n")
    data = _import(client, csv_text).json()
    assert data["created"] == 1 and data["errors"] == []
    assert _school_users()["eve.e@test.si"].role.value == "teacher"


# ── 3. Napake ─────────────────────────────────────────────────────────

def test_invalid_role_and_missing_username_reported(client, make_user):
    _admin(client, make_user)
    csv_text = ("username,email,role\n"
                ",brez.imena@test.si,teacher\n"
                "slaba.vloga@test.si,slaba.vloga@test.si,neobstoji\n")
    data = _import(client, csv_text).json()
    assert data["created"] == 0
    assert len(data["errors"]) == 2
    assert any("manjka uporabniško ime" in e for e in data["errors"])
    assert any("neveljavna vloga" in e for e in data["errors"])


def test_weak_password_in_file_is_rejected(client, make_user):
    _admin(client, make_user)
    csv_text = ("username,email,ime,priimek,vloga,geslo\n"
                "slab@test.si,slab@test.si,Slab,Geslo,učitelj,abc\n")
    data = _import(client, csv_text).json()
    assert data["created"] == 0
    assert any("prešibko" in e for e in data["errors"])


def test_existing_username_is_skipped(client, make_user):
    _admin(client, make_user)
    csv_text = ("username,email,ime,priimek,vloga\n"
                "ze.obstaja@test.si,ze.obstaja@test.si,Ze,Obstaja,učitelj\n")
    assert _import(client, csv_text).json()["created"] == 1
    data = _import(client, csv_text).json()
    assert data["created"] == 0 and data["skipped"] == 1 and data["errors"] == []


def test_empty_file_reports_error(client, make_user):
    _admin(client, make_user)
    assert _import(client, "\n\n").status_code == 400


# ── 4. Enote (parser in generator) ────────────────────────────────────

def test_parse_without_header_uses_positional_order():
    rows = _parse_user_csv("a@x.si,a@x.si,Ime,Priimek,učitelj\n")
    assert rows == [{"username": "a@x.si", "email": "a@x.si", "first_name": "Ime",
                     "last_name": "Priimek", "role": "učitelj", "password": ""}]


def test_parse_with_header_ignores_extra_columns_and_blank_lines():
    rows = _parse_user_csv("ime,priimek,email\nAna,Novak,ana@x.si\n\n")
    assert rows == [{"username": "", "email": "ana@x.si", "first_name": "Ana",
                     "last_name": "Novak", "role": "", "password": ""}]


def test_generated_passwords_are_random_and_strong():
    pws = {_generate_import_password() for _ in range(25)}
    assert len(pws) == 25                                   # ni ponovitev
    assert all(validate_password_strength(pw) is None for pw in pws)
    assert all(len(pw) >= 10 for pw in pws)
