# ─────────────────────────────────────────────────────────────────────────
# tests/test_govorilne.py — Testi prijav na govorilne ure (/govorilne)
#
# Podatki o učiteljih prihajajo iz app/govorilne_podatki.py (vir: spletna
# stran šole — https://ostcjesenice.splet.arnes.si/za-starse/govorilne-ure/).
# ─────────────────────────────────────────────────────────────────────────

import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres@localhost:5432/testdb")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import GovorilnaPrijava
from tests.conftest import login, make_user  # noqa: F401 (make_user je fixture)


def _termin(ucitelj: str):
    """Prvi prosti termin izbirega učitelja (dopoldan ali popoldan)."""
    db = SessionLocal()
    try:
        from app.routers.govorilne import _ucitelj_by_ime, _prosti_termini
        from app.tenancy import _default_school_id
        u = _ucitelj_by_ime(ucitelj)
        assert u is not None, f"učitelj {ucitelj!r} ni v podatkih"
        terms = _prosti_termini(db, _default_school_id(db), u)
        assert terms, f"učitelj {ucitelj!r} nima prostih terminov"
        return terms[0]
    finally:
        db.close()


def test_govorilne_stran_javna_in_vsebuje_ucitelje():
    with TestClient(app) as c:
        r = c.get("/govorilne")
        assert r.status_code == 200
        assert "Prijava na govorilne ure" in r.text
        # Javna stran (starš) — brez prijave mora biti dostopna.
        assert "izberite učitelja" in r.text
        # Izbrani učitelji iz podatkov so na voljo v izbirniku.
        assert "Matej Čušin" in r.text
        assert "Arijana Đuretić" in r.text


def test_govorilne_alias_sluga_javen():
    """Per-šola alias /govorilne_<slug> (npr. /govorilne_ostcj) je javen."""
    with TestClient(app) as c:
        # Javna stran prek aliasa — brez prijave.
        r = c.get("/govorilne_ostcj")
        assert r.status_code == 200
        assert "Prijava na govorilne ure" in r.text
        # API prek aliasa — prav tako javno.
        r = c.get("/govorilne_ostcj/api/termini", params={"ucitelj": "Matej Čušin"})
        assert r.status_code == 200
        assert r.json()["ucitelj"] == "Matej Čušin"
        # Pregled prijav prek aliasa NI javen (login jest).
        r = c.get("/govorilne_ostcj/prijave", follow_redirects=False)
        assert r.status_code in (302, 307)
        assert r.headers.get("location", "").startswith("/auth/login")


def test_termini_api_javen_in_vraca_15min_termine():
    with TestClient(app) as c:
        r = c.get("/govorilne/api/termini", params={"ucitelj": "Matej Čušin"})
        assert r.status_code == 200
        data = r.json()
        assert data["ucitelj"] == "Matej Čušin"
        assert data["termini"]
        t = data["termini"][0]
        assert t["datum"] and t["ura_od"] and t["ura_do"]
        # Vsak termin traja točno 15 minut.
        for tt in data["termini"]:
            h1, m1 = map(int, tt["ura_od"].split(":"))
            h2, m2 = map(int, tt["ura_do"].split(":"))
            assert (h2 * 60 + m2) - (h1 * 60 + m1) == 15
            # Vsak termin ima flag zaseden (javna stran kaže tudi zasedene).
            assert "zaseden" in tt


def test_termini_api_zasedeni_so_oznaceni():
    """Po prijavi se termin v javnem API-ju prikaže kot zaseden (flag true)."""
    t = _termin("Matej Čušin")
    with TestClient(app) as c:
        payload = {
            "ucitelj": "Matej Čušin",
            "datum": t["datum"],
            "ura_od": t["ura_od"],
            "ura_do": t["ura_do"],
            "ime_starsa": "Janez Novak",
            "email": "janez.novak@example.si",
            "otrok": "Miha Novak (3. b)",
        }
        r = c.post("/govorilne/api/prijava", json=payload)
        assert r.status_code == 200, r.text

        # Prav zaseden termin je v API-ju označen kot zaseden.
        r2 = c.get("/govorilne/api/termini", params={"ucitelj": "Matej Čušin"})
        assert r2.status_code == 200
        oznake = {(tt["datum"], tt["ura_od"]): tt["zaseden"]
                  for tt in r2.json()["termini"]}
        assert oznake[(t["datum"], t["ura_od"])] is True


def test_termini_api_neznan_ucitelj_404():
    with TestClient(app) as c:
        r = c.get("/govorilne/api/termini", params={"ucitelj": "Ne obstaja"})
        assert r.status_code == 404


def test_prijava_uspe_termin_postane_zaseden():
    t = _termin("Matej Čušin")
    with TestClient(app) as c:
        payload = {
            "ucitelj": "Matej Čušin",
            "datum": t["datum"],
            "ura_od": t["ura_od"],
            "ura_do": t["ura_do"],
            "ime_starsa": "Janez Novak",
            "email": "janez.novak@example.si",
            "otrok": "Miha Novak (3. b)",
        }
        r = c.post("/govorilne/api/prijava", json=payload)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # Isti termin druga stranka → 409 (zaseden).
        r2 = c.post("/govorilne/api/prijava", json=payload)
        assert r2.status_code == 409, r2.text


def test_prijava_neveljaven_termin_400():
    with TestClient(app) as c:
        r = c.post("/govorilne/api/prijava", json={
            "ucitelj": "Matej Čušin",
            "datum": "2026-11-19",
            "ura_od": "09:00",          # ni veljaven termin (zunaj okna)
            "ura_do": "09:15",
            "ime_starsa": "Janez Novak",
            "email": "janez.novak@example.si",
            "otrok": "Miha Novak",
        })
        assert r.status_code == 400


def test_prijava_manjkajoci_podatki_400():
    with TestClient(app) as c:
        r = c.post("/govorilne/api/prijava", json={
            "ucitelj": "Matej Čušin",
            "datum": "2026-11-19",
            "ura_od": "17:30",
            "ura_do": "17:45",
            "ime_starsa": "",
            "email": "janez.novak@example.si",
            "otrok": "",
        })
        assert r.status_code == 400


def test_prijave_pregled_auth_in_vloge(make_user):
    from app.routers.govorilne import _ucitelj_by_ime, _prosti_termini
    from app.tenancy import _default_school_id

    with TestClient(app) as c:
        # Po startupu obstaja privzeta šola → default_school_id deluje.
        db = SessionLocal()
        try:
            t = _termin("Matej Čušin")
            p = GovorilnaPrijava(
                school_id=_default_school_id(db), ucitelj="Matej Čušin",
                datum=t["datum"][:10], ura_od=t["ura_od"], ura_do=t["ura_do"],
                ime_starsa="Janez Novak", email="janez.novak@example.si",
                otrok="Miha Novak",
            )
            db.add(p)
            db.commit()
        finally:
            db.close()

        # Neprijavljen → preusmeritev na login (ni javno).
        r = c.get("/govorilne/prijave", follow_redirects=False)
        assert r.status_code in (302, 307)

        # Učitelj (Test Teacher) vidi samo svoje prijave → ta jih nima.
        teacher = make_user(role="teacher")
        login(c, teacher.username)
        r = c.get("/govorilne/prijave")
        assert r.status_code == 200
        assert "Janez Novak" not in r.text  # ni njegova prijava

    with TestClient(app) as c:
        # Šolski admin vidi vse prijave šole.
        db = SessionLocal()
        try:
            t = _termin("Matej Čušin")
            p = GovorilnaPrijava(
                school_id=_default_school_id(db), ucitelj="Matej Čušin",
                datum=t["datum"][:10], ura_od=t["ura_od"], ura_do=t["ura_do"],
                ime_starsa="Janez Novak", email="janez.novak@example.si",
                otrok="Miha Novak",
            )
            db.add(p)
            db.commit()
        finally:
            db.close()
        admin = make_user(role="admin")
        login(c, admin.username)
        r = c.get("/govorilne/prijave")
        assert r.status_code == 200
        assert "Janez Novak" in r.text
        assert "Matej Čušin" in r.text


def _ucitelj_uporabnik(ime: str, priimek: str):
    """Učitelj (role=teacher) s polnim imenom iz podatkov, za test vidnosti prijav.

    Uporabi SVOJO sejo in jo zapre — klicateljeva je lahko že zaprta
    (prejšnji finally jo je zaprl) in ponovna uporaba bi pustila odprto
    transakcijo (db.refresh po commitu), ki blokira clean_db TRUNCATE
    naslednjega testa.
    """
    from uuid import uuid4
    from app.models import User, RoleEnum
    from app.tenancy import _default_school_id
    from tests.conftest import pwd_context, TEST_PASSWORD
    from app.database import SessionLocal
    username = f"ucitelj_{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        user = User(
            school_id=_default_school_id(db),
            username=username,
            email=f"{username}@test.si",
            first_name=ime,
            last_name=priimek,
            password_hash=pwd_context.hash(TEST_PASSWORD),
            role=RoleEnum.teacher,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def test_prijave_so_vidne_ucitelju_po_imenu():
    """Učitelj s polnim imenom, ki ga najdemo v podatkih, vidi svoje prijave.

    Uporabimo ime iz prvega vrstice podatkov (npr. Arijana Đuretić), ustvarimo
    uporabnika s tem imenom in prijavo zanj ter preverimo vidnost.
    """
    from app.govorilne_podatki import UCITELJI
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    ime, priimek = prvi["ime"].split(" ", 1)

    from app.tenancy import _default_school_id

    with TestClient(app) as c:
        db = SessionLocal()
        try:
            t = _termin(prvi["ime"])
            p = GovorilnaPrijava(
                school_id=_default_school_id(db), ucitelj=prvi["ime"],
                datum=t["datum"][:10], ura_od=t["ura_od"], ura_do=t["ura_do"],
                ime_starsa="Ana Starš", email="ana@example.si", otrok="Otrok",
            )
            db.add(p)
            db.commit()
        finally:
            db.close()

        user = _ucitelj_uporabnik(ime, priimek)
        login(c, user.username)
        r = c.get("/govorilne/prijave")
        assert r.status_code == 200
        assert "Ana Starš" in r.text


# ─────────────────────────────────────────────────────────────────────────
# »Moje govorilne ure« — /govorilne/ure (objavljeni urnik za učitelja)
# ─────────────────────────────────────────────────────────────────────────

def test_govorilne_ure_nezahtevana_zahteva_login():
    """Neprijavljen → preusmeritev na login (ni javna stran)."""
    with TestClient(app) as c:
        r = c.get("/govorilne/ure", follow_redirects=False)
        assert r.status_code in (302, 307)


def test_govorilne_ure_ucitelj_vidi_samo_svoj_urnik():
    """Učitelj vidi svoj objavljeni termin; drug učitelj se ne prikaže."""
    from app.govorilne_podatki import UCITELJI
    from app.routers.govorilne import _ime_priimek
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    ime, priimek = prvi["ime"].split(" ", 1)
    drugi = next(u for u in UCITELJI if u["ime"] != prvi["ime"])

    user = _ucitelj_uporabnik(ime, priimek)
    with TestClient(app) as c:
        login(c, user.username)
        r = c.get("/govorilne/ure")
        assert r.status_code == 200
        assert _ime_priimek(prvi["ime"]) in r.text
        assert drugi["ime"] not in r.text


def test_govorilne_ure_admin_vidi_vse_ucitelje(make_user):
    """Šolski admin/glavni admin vidi urnike vseh učiteljev (npr. testni Matej Čušin)."""
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.get("/govorilne/ure")
        assert r.status_code == 200
        assert "Čušin Matej" in r.text


def test_govorilne_ure_ucitelj_vidi_svoje_rezervacije():
    """Učitelj v svojem urniku vidi rezervacije staršev za svoje termine."""
    from app.govorilne_podatki import UCITELJI
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    ime, priimek = prvi["ime"].split(" ", 1)

    from app.tenancy import _default_school_id
    with TestClient(app) as c:
        db = SessionLocal()
        try:
            t = _termin(prvi["ime"])
            p = GovorilnaPrijava(
                school_id=_default_school_id(db), ucitelj=prvi["ime"],
                datum=t["datum"][:10], ura_od=t["ura_od"], ura_do=t["ura_do"],
                ime_starsa="Bojan Starš", email="bojan@example.si", otrok="Otrok",
            )
            db.add(p)
            db.commit()
        finally:
            db.close()

        user = _ucitelj_uporabnik(ime, priimek)
        login(c, user.username)
        r = c.get("/govorilne/ure")
        assert r.status_code == 200
        assert "Bojan Starš" in r.text


def test_termini_okno_24ur_do_naslednjih_popoldanskih():
    """Javna stran kaže samo termine od 24 ur nazaj do naslednjih popoldanskih
    govorilnih — starejši in bolj oddaljeni (po naslednjem četrtku) izginejo."""
    from datetime import date, timedelta

    from app.govorilne_podatki import POPOLDAN_DATUMI
    from app.routers.govorilne import _naslednji_popoldan, _v_oknu

    naslednji = _naslednji_popoldan()
    assert naslednji is not None  # v času testa obstaja prihodnji četrtek

    # Starejši od 24 ur → ven.
    stari = {"datum": (date.today() - timedelta(days=2)).isoformat(), "ura_od": "17:30"}
    assert _v_oknu(stari) is False

    # Naslednji popoldanski datum → v oknu (termini 17:30–18:30).
    for ura in ("17:30", "18:15"):
        assert _v_oknu({"datum": naslednji, "ura_od": ura}) is True

    # Datum po naslednjih popoldanskih govorilnih → ven.
    if POPOLDAN_DATUMI[-1] > naslednji:
        assert _v_oknu({"datum": POPOLDAN_DATUMI[-1], "ura_od": "17:30"}) is False

    # API (javna stran staršev) vrača samo termine znotraj okna.
    with TestClient(app) as c:
        r = c.get("/govorilne/api/termini", params={"ucitelj": "Matej Čušin"})
        assert r.status_code == 200
        datumi = {tt["datum"] for tt in r.json()["termini"]}
        assert all(d <= naslednji for d in datumi)
        assert naslednji in datumi
        if POPOLDAN_DATUMI[-1] > naslednji:
            assert POPOLDAN_DATUMI[-1] not in datumi


def test_prijava_termina_po_naslednjih_govorilnih_400():
    """Prijava na termin po naslednjih popoldanskih govorilnih ni dovoljena."""
    from app.govorilne_podatki import POPOLDAN_DATUMI
    zadnji = POPOLDAN_DATUMI[-1]
    with TestClient(app) as c:
        r = c.post("/govorilne/api/prijava", json={
            "ucitelj": "Matej Čušin",
            "datum": zadnji,
            "ura_od": "17:30",
            "ura_do": "17:45",
            "ime_starsa": "Janez Novak",
            "email": "janez.novak@example.si",
            "otrok": "Miha Novak",
        })
        assert r.status_code == 400


def test_prijave_se_izbrisejo_24ur_po_terminu(make_user):
    """Prijava, od katere je minilo več kot 24 ur po koncu termina, se avtomatsko
    izbriše in ni več vidna; sveža (v prihodnosti) ostane."""
    from datetime import date, timedelta

    from app.routers.govorilne import _prijava_pretekla
    from app.tenancy import _default_school_id

    with TestClient(app) as c:
        # Bootstrap privzete šole se zgodi ob odprtju TestClient-a (conftest);
        # šele nato ročno ustvarimo prijave (rabijo veljaven school_id).
        db = SessionLocal()
        try:
            # Pretekla prijava: termin pred 2 dnevoma (konec + 24 h je že mimo).
            p = GovorilnaPrijava(
                school_id=_default_school_id(db), ucitelj="Matej Čušin",
                datum=date.today() - timedelta(days=2),
                ura_od="17:30", ura_do="17:45",
                ime_starsa="Stari Starš", email="stari@example.si", otrok="Otrok",
            )
            db.add(p)
            db.commit()
            assert _prijava_pretekla(p) is True

            # Sveža prijava: termin v prihodnosti → ni pretekla.
            p2 = GovorilnaPrijava(
                school_id=_default_school_id(db), ucitelj="Matej Čušin",
                datum=date.today() + timedelta(days=1),
                ura_od="17:30", ura_do="17:45",
                ime_starsa="Sveži Starš", email="svezi@example.si", otrok="Otrok",
            )
            db.add(p2)
            db.commit()
            assert _prijava_pretekla(p2) is False
        finally:
            db.close()

        admin = make_user(role="admin")
        login(c, admin.username)
        r = c.get("/govorilne/prijave")
        assert r.status_code == 200
        assert "Stari Starš" not in r.text   # pretekla ni več vidna (izbrisana)
        assert "Sveži Starš" in r.text       # sveža še vidna

    # _pocisti_stare ob ogledu fizično izbriše preteklo prijavo.
    db = SessionLocal()
    try:
        ostala = db.query(GovorilnaPrijava).filter(
            GovorilnaPrijava.email == "stari@example.si").first()
        assert ostala is None
    finally:
        db.close()


def test_ucitelji_sortirani_po_priimkih_in_razredniki_oznaceni(make_user):
    """Javna stran: učitelji po abecedi priimkov; razredniki z oznako
    'predmet — razrednik <razred>'; priimek naprej v prikazu."""
    from app.routers.govorilne import _opis_ucitelja, _ime_priimek

    # Priimek-ime: zadnja beseda naprej.
    assert _ime_priimek("Arijana Đuretić") == "Đuretić Arijana"
    assert _ime_priimek("Barbara Potočan Iskra") == "Iskra Barbara Potočan"
    assert _ime_priimek("Matej Čušin") == "Čušin Matej"

    # Razrednik (v polju predmet = razred) → predmet + 'razrednik <razred>'.
    # Brez imena → privzeti 'razredni pouk'.
    assert _opis_ucitelja({"predmet": "1. a"}) == "razredni pouk — razrednik 1. a"
    assert _opis_ucitelja({"predmet": "8. č"}) == "razredni pouk — razrednik 8. č"
    # Z imenom iz slovarja RAZREDNIK_PREDMET → njegov dejanski predmet.
    assert _opis_ucitelja({"ime": "Mojca Čušin", "predmet": "8. a"}) == "Slovenščina — razrednik 8. a"
    assert _opis_ucitelja({"ime": "Špela Skumavec", "predmet": "8. c"}) == "Slovenščina — razrednik 8. c"
    # Predmetni učitelj → predmet kot je objavljen.
    assert _opis_ucitelja({"predmet": "Matematika"}) == "Matematika"
    assert _opis_ucitelja({"predmet": ""}) == ""

    with TestClient(app) as c:
        r = c.get("/govorilne")
        assert r.status_code == 200
        # Razrednik je označen s predmetom in razredom.
        assert "razredni pouk — razrednik 1. a" in r.text
        # Sort po priimkih + priimek naprej: Đuretić pred Pogačar (obe razrednici 1. a).
        assert r.text.index("Đuretić Arijana") < r.text.index("Pogačar Monika")

        # Enako v učiteljevem/adminskem pogledu /govorilne/ure.
        admin = make_user(role="admin")
        login(c, admin.username)
        r2 = c.get("/govorilne/ure")
        assert r2.status_code == 200
        assert "razredni pouk — razrednik 1. a" in r2.text
        assert r2.text.index("Đuretić Arijana") < r2.text.index("Pogačar Monika")
