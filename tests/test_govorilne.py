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
    """Šolski admin/glavni admin vidi urnike vseh učiteljev (npr. testni Matej Čušin)
    in ima urejanje učiteljev (dodaj/odstrani) + nastavitve popoldanskih ur."""
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.get("/govorilne/ure")
        assert r.status_code == 200
        assert "Čušin Matej" in r.text
        # Nove admin zmoglivosti.
        assert "Dodaj učitelja" in r.text
        assert "Odstrani" in r.text
        assert "Začetek ur" in r.text
        assert "Največ ur" in r.text


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
                opis="Pregled ocen pri slovenščini",
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
        assert "Kratek opis" in r.text
        assert "Pregled ocen pri slovenščini" in r.text


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

    # Razrednik (ima ločeno polje razred) → predmet + 'razrednik <razred>'.
    assert _opis_ucitelja({"razred": "1. a", "predmet": "razredni pouk"}) == "razredni pouk — razrednik 1. a"
    assert _opis_ucitelja({"razred": "8. č", "predmet": "razredni pouk"}) == "razredni pouk — razrednik 8. č"
    # Predmet iz podatkov (iz kabineta razrednika predmetne stopnje).
    assert _opis_ucitelja({"razred": "8. a", "predmet": "Slovenščina"}) == "Slovenščina — razrednik 8. a"
    assert _opis_ucitelja({"razred": "8. c", "predmet": "Slovenščina"}) == "Slovenščina — razrednik 8. c"
    # Predmetni učitelj (ni razrednik, razred=prazen) → zgolj predmet.
    assert _opis_ucitelja({"razred": None, "predmet": "Matematika"}) == "Matematika"
    assert _opis_ucitelja({"razred": None, "predmet": ""}) == ""

    with TestClient(app) as c:
        r = c.get("/govorilne")
        assert r.status_code == 200
        # Razrednik je označen s predmetom in razredom.
        assert "razredni pouk — razrednik 1. a" in r.text
        # Sort po priimkih + priimek naprej: Đuretić pred Pogačar (obe razrednici 1. a).
        assert r.text.index("Đuretić Arijana") < r.text.index("Pogačar Monika")
        # Prostor govorilnih ur je prikazan ob učitelju (kje so govorilne ure).
        assert "Đuretić Arijana — razredni pouk — razrednik 1. a" in r.text
        assert "— učilnica 1. a" in r.text

        # Enako v učiteljevem/adminskem pogledu /govorilne/ure.
        admin = make_user(role="admin")
        login(c, admin.username)
        r2 = c.get("/govorilne/ure")
        assert r2.status_code == 200
        assert "razredni pouk — razrednik 1. a" in r2.text
        assert r2.text.index("Đuretić Arijana") < r2.text.index("Pogačar Monika")


# ─────────────────────────────────────────────────────────────────────────
# UREJANJE na /govorilne/ure — popoldanske ure + lastni zapis učitelja
# ─────────────────────────────────────────────────────────────────────────

def test_ure_popoland_nezahtevan():
    with TestClient(app) as c:
        r = c.post("/govorilne/api/ure/popoldan", json={"popoldan_datumi": ["2026-12-10"]})
        assert r.status_code in (401, 403, 307)


def test_ure_popoldan_ucitelj_nima_pravic(make_user):
    """Navaden učitelj ne more urejati popoldanskih govorilnih ur (403)."""
    from app.govorilne_podatki import UCITELJI
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    ime, priimek = prvi["ime"].split(" ", 1)
    user = _ucitelj_uporabnik(ime, priimek)
    with TestClient(app) as c:
        login(c, user.username)
        r = c.post("/govorilne/api/ure/popoldan", json={"popoldan_datumi": ["2026-12-10"]})
        assert r.status_code == 403


def test_ure_admin_uredi_popoldanske_datum (make_user):
    """Šolski admin spremeni popoldanske datume (kdaj so); javna stran to upošteva."""
    from app.tenancy import _default_school_id
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.post("/govorilne/api/ure/popoldan", json={"popoldan_datumi": ["2026-12-17"]})
        assert r.status_code == 200, r.text
        assert r.json()["popoldan_datumi"] == ["2026-12-17"]

        # Konfiguracija je shranjena v school_settings (per šola).
        db = SessionLocal()
        try:
            from app.routers.govorilne import _load_cfg, GOVORILNE_SETTING_KEY
            cfg = _load_cfg(db, _default_school_id(db))
            assert cfg["popoldan_datumi"] == ["2026-12-17"]
        finally:
            db.close()


def test_ure_ucitelj_uredi_svoj_zapis():
    """Učitelj uredi SVOJ dopoldanski termin, predmet in razred (razrednik eslint)."""
    from app.govorilne_podatki import UCITELJI
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    ime, priimek = prvi["ime"].split(" ", 1)

    user = _ucitelj_uporabnik(ime, priimek)
    with TestClient(app) as c:
        login(c, user.username)
        # Poskuša spremeniti zapis — a ime se vedno vzame iz prijave (ne more
        # urejati nekoga drugega, četudi pošlje tuje ime).
        r = c.post("/govorilne/api/ure/ucitelj", json={
            "ime": "Nekdo Drug",
            "predmet": "Razredni pouk",
            "razred": "1. a",
            "razred_prev": "",
            "dan": 0,
            "ura": 3,
            "prostor": "učilnica 1. a",
        })
        assert r.status_code == 200, r.text
        # Ime se vedno vzame iz prijave (tuje ime je ignorirano).
        data = r.json()["ucitelj"]
        assert data["ime"] == prvi["ime"]
        assert data["predmet_raw"] == "Razredni pouk"
        assert data["razred"] == "1. a"
        assert data["dan"] == 0
        assert data["ura"] == 3
        # Ostali učitelji se niso spremenili (tuje ime je ignorirano).
        r2 = c.post("/govorilne/api/ure/ucitelj", json={
            "ime": "Nekdo Drug",
            "predmet": "Pristranski",
            "razred": "5. č",
            "dan": 4,
            "ura": 1,
            "prostor": "x",
        })
        data2 = r2.json()["ucitelj"]
        assert data2["ime"] == prvi["ime"]


def test_ure_admin_uredi_vse_ucitelje(make_user):
    """Šolski admin lahko uredi poljubnega učitelja (podan `ime`)."""
    from app.govorilne_podatki import UCITELJI
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.post("/govorilne/api/ure/ucitelj", json={
            "ime": prvi["ime"],
            "predmet": "Slovenščina",
            "razred": "7. b",
            "dan": 2,
            "ura": 4,
            "prostor": "učilnica SLJ 1",
        })
        assert r.status_code == 200, r.text
        data = r.json()["ucitelj"]
        assert data["razred"] == "7. b"
        assert data["predmet_raw"] == "Slovenščina"


def test_ure_ucitelj_brez_prijave_401():
    with TestClient(app) as c:
        r = c.post("/govorilne/api/ure/ucitelj", json={"predmet": "x"})
        assert r.status_code in (401, 403, 307)


# ─────────────────────────────────────────────────────────────────────────
# NOVI FEATUREJI (24. 10. 2026):
#   1. Admin nastavi dolžino termina (termin_minut v school settings).
#   2. Dopoldanske govorilne SAMO teden, ko so tudi popoldanske.
#   3. Popoldan se dinamično podaljšuje: osnovna 1 ura → po en termin, max 5 ur.
#   4. Prijava vrne potrdilo (učitelj + termin + kratek opis).
# ─────────────────────────────────────────────────────────────────────────

def test_termin_minut_admin_nastavi_in_vpliva_na_termine(make_user):
    """Admin v /govorilne/ure nastavi dolžino termina; javni termini to upoštevajo."""
    from app.routers.govorilne import _load_cfg, _naslednji_popoldan
    from app.tenancy import _default_school_id
    naslednji = _naslednji_popoldan()
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.post("/govorilne/api/ure/popoldan",
                   json={"popoldan_datumi": [naslednji], "termin_minut": 30})
        assert r.status_code == 200, r.text
        assert r.json()["termin_minut"] == 30
        # Shranjeno po šoli v school_settings.
        db = SessionLocal()
        try:
            cfg = _load_cfg(db, _default_school_id(db))
            assert cfg["termin_minut"] == 30
        finally:
            db.close()
        # Neja Grohar = po dogovoru → samo popoldanski termini, zdaj 30-minutni.
        r2 = c.get("/govorilne/api/termini", params={"ucitelj": "Neja Grohar"})
        assert r2.status_code == 200
        terms = r2.json()["termini"]
        assert terms
        for t in terms:
            h1, m1 = map(int, t["ura_od"].split(":"))
            h2, m2 = map(int, t["ura_do"].split(":"))
            assert (h2 * 60 + m2) - (h1 * 60 + m1) == 30


def test_termin_minut_neveljaven_400(make_user):
    """Dolžina termina izven dovoljenega obsega → 400 (admin)."""
    from app.routers.govorilne import _naslednji_popoldan
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.post("/govorilne/api/ure/popoldan",
                   json={"popoldan_datumi": [_naslednji_popoldan()], "termin_minut": 150})
        assert r.status_code == 400


def test_dopoldan_samo_teden_popoldanskih():
    """Dopoldanske govolne: termini so v ISTEM tednu kot naslednje popoldanske
    (učitelj dobi svoj dan znotraj tega tedna), ne v fiksnem testnem tednu."""
    import datetime as dt

    from app.routers.govorilne import (
        _dopoldan_monday,
        _naslednji_popoldan,
        _testni_datum,
    )
    naslednji = _naslednji_popoldan()
    assert naslednji is not None
    nd = dt.date.fromisoformat(naslednji)
    pon = nd - dt.timedelta(days=nd.weekday())  # ponedeljek tedna tega četrtka
    assert _dopoldan_monday() == pon
    # Vsak dan učitelja pade v teden, ki vsebuje popoldanske govorilne.
    for dan in range(5):
        d = _testni_datum(dan)
        assert d is not None
        assert d.isocalendar()[1] == nd.isocalendar()[1]
        assert d.weekday() == dan


def test_popoldan_dinamicno_podaljsanje_do_5ur():
    """Osnovna 1 ura; ko so vsi termini zasedeni, se doda po en
    nov termin — do največ 5 ur od začetka (17:30 → 22:30)."""
    from app.routers.govorilne import (
        _naslednji_popoldan,
        _popoldan_max_termov,
        _popoldan_odobrenih_termov,
        _popoldan_osnovnih_termov,
        _popoldan_term_od,
        _term_min,
    )
    base = _popoldan_osnovnih_termov()
    max_t = _popoldan_max_termov()
    assert base == 4            # 60 min / 15 min
    assert max_t == 20          # 5 ur / 15 min
    naslednji = _naslednji_popoldan()
    assert naslednji is not None
    tm = _term_min()
    # Prazen → samo osnovna 1 ura (4 termini).
    assert _popoldan_odobrenih_termov(naslednji, set()) == base
    # Vsi osnovni zasedeni → 1 nov termin (5).
    zasedi = {(naslednji, _popoldan_term_od(i, tm)) for i in range(base)}
    assert _popoldan_odobrenih_termov(naslednji, zasedi) == base + 1
    # Zasedeni do največ → ostane na max (20).
    zasedi_max = {(naslednji, _popoldan_term_od(i, tm)) for i in range(max_t)}
    assert _popoldan_odobrenih_termov(naslednji, zasedi_max) == max_t


def test_popoldan_ko_polna_ura_doda_nove_termine():
    """Po zasedbi vseh osnovnih popoldanskih terminov se v API-ju pojavi nov
    (podaljšan) termin pozneje popoldne."""
    from app.routers.govorilne import (
        _add_minutes,
        _naslednji_popoldan,
        _popoldan_osnovnih_termov,
    )
    ime = "Neja Grohar"  # po dogovoru → samo popoldanski termini
    naslednji = _naslednji_popoldan()
    base = _popoldan_osnovnih_termov()
    with TestClient(app) as c:
        # Zasedemo vse osnovne termine (17:30–18:30 → 4 × 15 min).
        for i in range(base):
            od = _add_minutes("17:30", i * 15)
            do = _add_minutes(od, 15)
            r = c.post("/govorilne/api/prijava", json={
                "ucitelj": ime, "datum": naslednji, "ura_od": od, "ura_do": do,
                "ime_starsa": "Starš", "email": "s@example.si", "otrok": "Otrok",
            })
            assert r.status_code == 200, r.text
        r = c.get("/govorilne/api/termini", params={"ucitelj": ime})
        assert r.status_code == 200
        data = r.json()["termini"]
        naslednji_ods = [t for t in data if t["datum"] == naslednji]
        # Pojavil se je vsaj en PROST podaljšani termin na koncu osnovne ure (18:30+).
        assert any(t["ura_od"] >= "18:30" and not t["zaseden"] for t in naslednji_ods), \
            "Po zasedbi osnovne ure se mora pojaviti podaljšan termin"


def test_prijava_vrne_potrdilo_z_opisom():
    """Prijava vrne potrdilo (učitelj + termin + kratek opis), da ga starš
    prepiše/slika, ker ga drugje ne bo več videl."""
    from app.routers.govorilne import _naslednji_popoldan
    naslednji = _naslednji_popoldan()
    with TestClient(app) as c:
        r = c.post("/govorilne/api/prijava", json={
            "ucitelj": "Neja Grohar", "datum": naslednji,
            "ura_od": "17:30", "ura_do": "17:45",
            "ime_starsa": "Ana Starš", "email": "ana@example.si",
            "otrok": "Miha Novak", "opis": "Pregled ocen pri matematiki",
        })
        assert r.status_code == 200, r.text
        pot = r.json()["potrdilo"]
        assert pot["ucitelj"] == "Neja Grohar"
        assert pot["datum"] == naslednji
        assert pot["ura_od"] == "17:30"
        assert pot["opis"] == "Pregled ocen pri matematiki"


def test_govorilne_stran_vsebuje_opis_in_prepis_potrdilo():
    """Javna stran ima polje 'Kratek opis' in potrdilo s pozivom, naj starš
    podatek prepiše/slika (ni vidno drugje)."""
    with TestClient(app) as c:
        r = c.get("/govorilne")
        assert r.status_code == 200
        assert "Kratek opis" in r.text
        assert "Prepisite ali slikajte" in r.text


def test_admin_doda_novega_ucitelja(make_user):
    """Admin/vodstvo lahko doda novega učitelja — pojavi se v javni strani."""
    from app.routers.govorilne import _ucitelj_by_ime
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.post("/govorilne/api/ure/ucitelj/dodaj", json={
            "ime": "Testni Učitelj", "predmet": "Angleščina", "prostor": "učilnica ANG 2",
            "dan": 1, "ura": 3,
        })
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        # Javna stran ga zdaj izpiše.
        r2 = c.get("/govorilne")
        assert r2.status_code == 200
        assert "Testni Učitelj" in r2.text


def test_admin_odstrani_ucitelja(make_user):
    """Admin/vodstvo lahko odstrani učitelja — izgine iz javne strani."""
    from app.routers.govorilne import _ucitelj_by_ime
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        # dodaj
        r = c.post("/govorilne/api/ure/ucitelj/dodaj", json={
            "ime": "Za Odstrani", "predmet": "Zgodovina", "prostor": "učilnica ZGO 1",
        })
        assert r.status_code == 200, r.text
        assert "Za Odstrani" in c.get("/govorilne").text
        # odstrani
        r2 = c.post("/govorilne/api/ure/ucitelj/odstrani", json={"ime": "Za Odstrani"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["ok"] is True
        assert "Za Odstrani" not in c.get("/govorilne").text


def test_dodaj_ucitelja_duplikat_409(make_user):
    """Dodajanje učitelja, ki že obstaja, vrne 409."""
    from app.routers.govorilne import _ucitelj_by_ime
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.post("/govorilne/api/ure/ucitelj/dodaj", json={"ime": "Neja Grohar"})
        assert r.status_code == 409


def test_ucitelj_nima_pravic_dodajati(make_user):
    """Navaden učitelj ne more dodajati/odstranjevati učiteljev."""
    from app.govorilne_podatki import UCITELJI
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    ime, priimek = prvi["ime"].split(" ", 1)
    user = _ucitelj_uporabnik(ime, priimek)
    with TestClient(app) as c:
        login(c, user.username)
        r = c.post("/govorilne/api/ure/ucitelj/dodaj", json={"ime": "Nov Učitelj"})
        assert r.status_code == 403
        r2 = c.post("/govorilne/api/ure/ucitelj/odstrani", json={"ime": prvi["ime"]})
        assert r2.status_code == 403


def test_popoldan_zacetek_spremeni_ure(make_user):
    """Admin spremeni začetek popoldanskih ur (npr. 16:00) — termini se od njega začnejo."""
    from app.routers.govorilne import _naslednji_popoldan, _popoldan_osnovnih_termov
    admin = make_user(role="admin")
    naslednji = _naslednji_popoldan()
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.post("/govorilne/api/ure/popoldan", json={
            "popoldan_datumi": [naslednji], "popoldan_zacetek": "16:00",
            "popoldan_osnovni_min": 45, "popoldan_max_ur": 2,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["popoldan_zacetek"] == "16:00"
        assert data["popoldan_osnovni_min"] == 45
        assert data["popoldan_max_ur"] == 2
        # Javna (ali ure) stran: termin za "Neja Grohar" (po dogovoru) se začne 16:00.
        r2 = c.get("/govorilne/api/termini", params={"ucitelj": "Neja Grohar"})
        assert r2.status_code == 200
        ods = [t["ura_od"] for t in r2.json()["termini"] if t["datum"] == naslednji]
        assert ods and ods[0] == "16:00"


def test_popoldan_zacetek_neveljaven_400(make_user):
    """Neveljaven začetek popoldanskih ur vrne 400."""
    admin = make_user(role="admin")
    from app.routers.govorilne import _naslednji_popoldan
    naslednji = _naslednji_popoldan()
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.post("/govorilne/api/ure/popoldan", json={
            "popoldan_datumi": [naslednji], "popoldan_zacetek": "99:99",
        })
        assert r.status_code == 400


# ── Brisanje rezervacij — SAMO šolski admin (nihče drug) ─────────────────

def _naredi_prijavo():
    """Ustvari rezervacijo starša v prvi prosti termin — vrne njen id."""
    from app.routers.govorilne import _ucitelj_by_ime, _prosti_termini
    from app.tenancy import _default_school_id
    db = SessionLocal()
    try:
        u = _ucitelj_by_ime("Matej Čušin")
        assert u is not None
        terms = _prosti_termini(db, _default_school_id(db), u)
        assert terms, "učitelj nima prostih terminov"
        t = terms[0]
        p = GovorilnaPrijava(
            school_id=_default_school_id(db), ucitelj="Matej Čušin",
            datum=t["datum"][:10], ura_od=t["ura_od"], ura_do=t["ura_do"],
            ime_starsa="Janez Novak", email="janez.novak@example.si",
            otrok="Miha Novak", opis="Vprašanje o snovi",
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p.id
    finally:
        db.close()


def test_prijava_brisanje_neprijavljen_401():
    """Neprijavljen ne more brisati rezervacij."""
    with TestClient(app) as c:
        r = c.post("/govorilne/api/prijava/odstrani", json={"id": 1})
        assert r.status_code == 401


def test_prijava_brisanje_ucitelj_403(make_user):
    """Učitelj NE more brisati rezervacij (niti svojega učitelja)."""
    with TestClient(app) as c:
        pid = _naredi_prijavo()
        teacher = make_user(role="teacher")
        login(c, teacher.username)
        r = c.post("/govorilne/api/prijava/odstrani", json={"id": pid})
        assert r.status_code == 403
        # Prijava mora še vedno obstajati.
        db = SessionLocal()
        try:
            assert db.query(GovorilnaPrijava).filter(GovorilnaPrijava.id == pid).first() is not None
        finally:
            db.close()


def test_prijava_brisanje_vodstvo_403(make_user):
    """Vodstvo NE more brisati rezervacij — samo šolski admin."""
    with TestClient(app) as c:
        pid = _naredi_prijavo()
        vodstvo = make_user(role="vodstvo")
        login(c, vodstvo.username)
        r = c.post("/govorilne/api/prijava/odstrani", json={"id": pid})
        assert r.status_code == 403


def test_prijava_brisanje_main_admin_403(make_user):
    """Glavni admin tudi NE more brisati — 'nihče drug' razen šolskega admina."""
    with TestClient(app) as c:
        pid = _naredi_prijavo()
        main = make_user(role="main_admin")
        login(c, main.username)
        r = c.post("/govorilne/api/prijava/odstrani", json={"id": pid})
        assert r.status_code == 403


def test_prijava_brisanje_solski_admin_200(make_user):
    """Šolski admin IZBRIŠE rezervacijo — 200 in prijava izgine."""
    with TestClient(app) as c:
        pid = _naredi_prijavo()
        admin = make_user(role="admin")
        login(c, admin.username)
        r = c.post("/govorilne/api/prijava/odstrani", json={"id": pid})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        db = SessionLocal()
        try:
            assert db.query(GovorilnaPrijava).filter(GovorilnaPrijava.id == pid).first() is None
        finally:
            db.close()


def test_prijava_brisanje_neobstojece_404(make_user):
    """Neobstoječa prijava vrne 404 tudi šolskemu adminu."""
    with TestClient(app) as c:
        admin = make_user(role="admin")
        login(c, admin.username)
        r = c.post("/govorilne/api/prijava/odstrani", json={"id": 999999})
        assert r.status_code == 404


def test_prijava_brisanje_manjka_id_400(make_user):
    """Telo brez 'id' vrne 400."""
    with TestClient(app) as c:
        admin = make_user(role="admin")
        login(c, admin.username)
        r = c.post("/govorilne/api/prijava/odstrani", json={})
        assert r.status_code == 400
