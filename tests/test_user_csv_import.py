# ─────────────────────────────────────────────────────────────────────────
# tests/test_user_csv_import.py — uvoz uporabnikov iz CSV (tolerantno)
#
# CSV je POENOSTAVLJEN: e-pošta JE uporabniško ime, zato jo zapišete samo
# enkrat. Vrstni red brez glave: e-pošta, ime, priimek, vloga.
#
#   ana.novak@guest.arnes.si,ime1,priimek1,učitelj
#   ...
#
#   * glava ni obvezna (privzeti vrstni red), imena stolpcev SI ali EN;
#   * e-pošta = uporabniško ime (prijava in »Pozabljeno geslo« potekata po njej);
#   * vloga je lahko učitelj/vodstvo/admin (privzeto učitelj);
#   * geslo NI stolpec CSV — aplikacija ga vedno izmisli in ga nikoli ne izpiše;
#   * uvoženi uporabniki PRIVZETO NIMAJO govorilnih ur (ima_govorilne=False);
#   * podvojeni uporabniki v datoteki se zavrnejo z jasno napako;
#   * stare oblike datotek (ločeno uporabniško ime + e-pošta, stolpec geslo)
#     še vedno delujejo.
# ─────────────────────────────────────────────────────────────────────────

from app.config import validate_password_strength
from app.database import SessionLocal
from app.models import User
from app.routers.auth import (
    _generate_import_password,
    _parse_user_csv,
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


# ── 1. Točno uporabnikov primer (brez glave, e-pošta enkrat, SI vloga) ──

def test_user_exact_csv_without_header(client, make_user):
    """Uporabnikov primer: e-pošta samo enkrat, brez gesla, SI vloga.

    Podvojeni uporabnik v datoteki: prvi se uvozi, ostali dobijo jasno
    napako (trije enaki računi ne morejo obstajati — prijava bi bila dvoumna).
    """
    _admin(client, make_user)
    csv_text = (
        "ana.novak@guest.arnes.si,ime1,priimek1,učitelj\n"
        "ana.novak@guest.arnes.si,ime2,priimek2,učitelj\n"
        "ana.novak@guest.arnes.si,ime3,priimek3,učitelj\n"
    )
    r = _import(client, csv_text)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 1
    assert len(data["errors"]) == 2
    assert all("naveden večkrat" in e for e in data["errors"])
    # geslo se NE vrača — gesel ne izpisujemo nikoli (zahteva 2026-09-29)
    assert len(data["users"]) == 1
    assert "password" not in data["users"][0]

    u = _school_users()["ana.novak@guest.arnes.si"]
    assert u.role.value == "teacher"
    assert u.first_name == "ime1"
    # e-pošta je tudi uporabniško ime
    assert u.email == "ana.novak@guest.arnes.si"
    # privzeto NIMA govorilnih ur
    assert u.ima_govorilne is False


def test_distinct_emails_all_created_without_passwords_in_response(client, make_user):
    """Ločene e-pošte, brez gesel → vsi se uvozijo.

    Gesla se NIKOLI ne vrnejo (zahteva uporabnika 2026-09-29: gesla uporabnikov se
    nikjer ne prikažejo). Uporabnik si geslo nastavi sam prek »Pozabljeno geslo« —
    zato je e-pošta hkrati uporabniško ime.
    """
    _admin(client, make_user)
    csv_text = (
        "ana.novak@test.si,Ana,Novak,učitelj\n"
        "bor.kralj@test.si,Bor,Kralj,profesor\n"
        "cvetka.zupan@test.si,Cvetka,Župan,vodstvo\n"
    )
    r = _import(client, csv_text)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 3 and data["errors"] == []
    # v odgovoru NI nobenega gesla
    assert all("password" not in u for u in data["users"])
    assert {u["username"] for u in data["users"]} == {
        "ana.novak@test.si", "bor.kralj@test.si", "cvetka.zupan@test.si",
    }

    users = _school_users()
    imported = [users[k] for k in (
        "ana.novak@test.si", "bor.kralj@test.si", "cvetka.zupan@test.si",
    )]
    assert imported[0].role.value == "teacher"
    assert imported[1].role.value == "teacher"      # profesor → učitelj
    assert imported[2].role.value == "vodstvo"
    # e-pošta = uporabniško ime (shranjeno na obe mesti)
    assert all(u.email == u.username for u in imported)
    # privzeto NIMAJO govorilnih ur
    assert all(u.ima_govorilne is False for u in imported)
    # vsak dobi veljaven hash (račun deluje), a gesla ne pozna nihče
    assert all(u.password_hash for u in imported)


# ── 2. Slovenske glave in vloge ───────────────────────────────────────

def test_slovenian_header_aliases(client, make_user):
    _admin(client, make_user)
    csv_text = (
        "e-posta,ime,priimek,vloga\n"
        "dana.d@test.si,Dana,Dolenc,učitelj\n"
    )
    data = _import(client, csv_text).json()
    assert data["created"] == 1 and data["errors"] == []
    assert "password" not in data["users"][0]
    u = _school_users()["dana.d@test.si"]
    assert u.role.value == "teacher" and u.last_name == "Dolenc"
    assert u.ima_govorilne is False


def test_english_header_still_works(client, make_user):
    _admin(client, make_user)
    csv_text = ("email,first_name,last_name,role\n"
                "eve.e@test.si,Eve,Erjavec,teacher\n"
                "evi.f@test.si,Evi,Fink,\n")
    data = _import(client, csv_text).json()
    assert data["created"] == 2 and data["errors"] == []
    users = _school_users()
    assert users["eve.e@test.si"].role.value == "teacher"
    # prazna vloga → privzeto učitelj
    assert users["evi.f@test.si"].role.value == "teacher"


def test_legacy_headers_username_and_password_still_work(client, make_user):
    """Stare datoteke (ločena uporabniško ime in e-pošta, stolpec geslo) se
    še vedno uvozijo; geslo iz datoteke se zdaj ignorira (generira se novo)."""
    _admin(client, make_user)
    csv_text = ("username,email,first_name,last_name,role,password\n"
                "fani.f@test.si,fani.f@test.si,Fani,Fink,teacher,abc\n")
    data = _import(client, csv_text).json()
    assert data["created"] == 1 and data["errors"] == []
    u = _school_users()["fani.f@test.si"]
    assert u.username == "fani.f@test.si" and u.email == "fani.f@test.si"
    assert u.ima_govorilne is False


# ── 3. Napake ─────────────────────────────────────────────────────────

def test_invalid_role_and_missing_email_reported(client, make_user):
    _admin(client, make_user)
    csv_text = ("email,ime,priimek,vloga\n"
                ",Brez,Imena,teacher\n"
                "slaba.vloga@test.si,Slaba,Vloga,neobstoji\n")
    data = _import(client, csv_text).json()
    assert data["created"] == 0
    assert len(data["errors"]) == 2
    assert any("manjka e-pošta" in e for e in data["errors"])
    assert any("neveljavna vloga" in e for e in data["errors"])


def test_existing_email_is_skipped(client, make_user):
    _admin(client, make_user)
    csv_text = ("email,ime,priimek,vloga\n"
                "ze.obstaja@test.si,Ze,Obstaja,učitelj\n")
    assert _import(client, csv_text).json()["created"] == 1
    data = _import(client, csv_text).json()
    assert data["created"] == 0 and data["skipped"] == 1 and data["errors"] == []


def test_empty_file_reports_error(client, make_user):
    _admin(client, make_user)
    assert _import(client, "\n\n").status_code == 400


# ── 4. Enote (parser in generator) ────────────────────────────────────

def test_parse_without_header_uses_positional_order():
    rows = _parse_user_csv("a@x.si,Ime,Priimek,učitelj\n")
    assert rows == [{"email": "a@x.si", "first_name": "Ime",
                     "last_name": "Priimek", "role": "učitelj"}]


def test_parse_without_header_legacy_six_columns():
    """Stara 6-stolpčna datoteka brez glave: uporabniško ime (= e-pošta),
    ime, priimek, vloga; geslo (zadnji stolpec) se ignorira."""
    rows = _parse_user_csv("a@x.si,a@x.si,Ime,Priimek,učitelj,geslo123\n")
    assert rows == [{"email": "a@x.si", "first_name": "Ime",
                     "last_name": "Priimek", "role": "učitelj"}]


def test_parse_with_header_ignores_extra_columns_and_blank_lines():
    rows = _parse_user_csv("ime,priimek,email\nAna,Novak,ana@x.si\n\n")
    assert rows == [{"email": "ana@x.si", "first_name": "Ana",
                     "last_name": "Novak", "role": ""}]


def test_generated_passwords_are_random_and_strong():
    pws = {_generate_import_password() for _ in range(25)}
    assert len(pws) == 25                                   # ni ponovitev
    assert all(validate_password_strength(pw) is None for pw in pws)
    assert all(len(pw) >= 10 for pw in pws)
