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

import pytest

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


def _ucitelj_uporabnik(ime: str, priimek: str, ima_govorilne: bool = True):
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
            ima_govorilne=ima_govorilne,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _gos_osnovni_ucitelji():
    """Od 30.10.2026 je članstvo na govorilnih vezano na uporabnike (kljukica
    »ima govorilne ure«), ne več na trdi UCITELJI seznam. Ta fixture ob bootstrapu
    v privzeto šolo doda dva osnovna učitelja z odkljukano govorilno kljukico, da so
    testi, ki pričakujejo Mateja Čušina / Đuretićevo na /govorilne, deterministični."""
    # Bootstrap privzete šole (startup) — šele nato so uporabniki v pravi šoli.
    with TestClient(app) as c:
        pass
    _ucitelj_uporabnik("Matej", "Čušin")
    _ucitelj_uporabnik("Arijana", "Đuretić")
    _ucitelj_uporabnik("Monika", "Pogačar")
    _ucitelj_uporabnik("Neja", "Grohar")
    # ⚠️ Startup zapusti 'idle in transaction' povezavo v engine poolu → TRUNCATE
    # (clean_db) ob teardown-u bi deadlock-al. Pool dispose sprosti vse locke.
    from app.database import engine
    engine.dispose()


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


def test_govorilne_ure_mainadmin_zanikan_vedno(make_user):
    """Glavni admin (mainadmin) NE SME videti govorilnih ur v nobenem primeru.

    Preveri tako stran /govorilne/ure kot /govorilne/prijave — obe morata
    glavnega admina preusmeriti stran (redirect, ne vsebina).
    """
    mainadmin = make_user(role="main_admin")
    with TestClient(app) as c:
        login(c, mainadmin.username)
        for path in ("/govorilne/ure", "/govorilne/prijave"):
            r = c.get(path, follow_redirects=False)
            assert r.status_code in (302, 307), f"{path} -> {r.status_code}"
            assert r.headers.get("location", "") == "/"
        # mainadmin tudi na API-ju za urejanje nima pravic.
        r = c.post("/govorilne/api/ure/popoldan", json={"popoldan_datumi": []},
                   follow_redirects=False)
        assert r.status_code in (401, 403), f"API popoldan -> {r.status_code}"


def test_govorilne_ure_admin_vidi_vse_ucitelje(make_user):
    """Šolski admin vidi urnike vseh učiteljev (npr. testni Matej Čušin)
    in ima urejanje učiteljev (dodaj/odstrani) + nastavitve popoldanskih ur."""
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.get("/govorilne/ure")
        assert r.status_code == 200
        assert "Čušin Matej" in r.text
        # Članstvo od 30.10.2026: dodaj/odstrani se ne dela tu, ampak v Uporabniki.
        assert "Kako dodati / odstraniti učitelja?" in r.text
        assert "Dodaj učitelja" not in r.text
        # Nastavitve popoldanskih ur.
        assert "Začetek ur" in r.text
        assert "Največ ur" in r.text


def test_govorilne_ure_uciteljska_kartica_zlozljiva_več_manj(make_user):
    """Učiteljska kartica na /govorilne/ure je zložljiva (več/manj): header (ime pa to)
    ostane vedno viden kot summary, vse ostalo (termin, rezervacije, uredi-obrazec) je
    v details vsebini."""
    from app.govorilne_podatki import UCITELJI
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.get("/govorilne/ure")
        assert r.status_code == 200
        # Kartica = details.collapsible z data-ime; header = summary, vsebina zložljiva.
        assert "<details class=\"card collapsible\" data-ime=\"" in r.text
        assert "<summary class=\"card-header\">" in r.text
        # Ime učitelja je v headerju (summary), kjer je tudi toggle oznaka.
        assert "toggle-hint" in r.text
        assert "▸ več" in r.text
        # Vsebina (termin + rezervacije) je znotraj details, ne v summary.
        body_start = r.text.index("<details class=\"card collapsible\" data-ime=\"")
        summary_end = r.text.index("</summary>", body_start)
        assert "Objavljeni termin" not in r.text[body_start:summary_end]
        assert prvi["ime"] in r.text


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


def test_admin_kljukica_pojavi_uporabnika_na_govorilnih(make_user):
    """Kljukica »Govorilne ure« pri uporabniku = EDI pogoj članstva.

    Učitelj BREZ kljukice ni na /govorilne; ko jo admin odkluka (POST
    /auth/admin/users/{id}/govorilne), se samodejno pojavi na javni strani
    (in v izbiri za starše).
    """
    ucitelj = make_user(role="teacher", first_name="Tine", last_name="Novi")
    # Brez kljukice → ni na javni strani.
    with TestClient(app) as c:
        r = c.get("/govorilne")
        assert r.status_code == 200
        assert "Tine Novi" not in r.text
        # Admin odkluka kljukico.
        admin = make_user(role="admin")
        login(c, admin.username)
        r2 = c.post(f"/auth/admin/users/{ucitelj.id}/govorilne")
        assert r2.status_code == 200, r2.text  # redirect na /auth/admin/users (kljukica preklaplja)
        # Zdaj se pojavi na javni strani (priimek-ime: »Novi Tine«).
        r3 = c.get("/govorilne")
        assert r3.status_code == 200
        assert "Tine Novi" in r3.text


def test_admin_kljukica_odklopi_uporabnika_z_govorilnih(make_user):
    """Odkljukana kljukica → uporabnik izgine z /govorilne (za starše)."""
    ucitelj = make_user(role="teacher", first_name="Maja", last_name="Zgodbič",
                        ima_govorilne=True)
    with TestClient(app) as c:
        # S kljukico je prisoten.
        assert "Maja Zgodbič" in c.get("/govorilne").text
        admin = make_user(role="admin")
        login(c, admin.username)
        r = c.post(f"/auth/admin/users/{ucitelj.id}/govorilne")
        assert r.status_code == 200, r.text  # redirect na /auth/admin/users
        # Po odklikanju ga ni več.
        assert "Maja Zgodbič" not in c.get("/govorilne").text


def test_kljukica_toggle_samo_admin():
    """Uporabnikovo govorilno kljukico lahko preklaplja samo admin — učitelj 403."""
    ucitelj = _ucitelj_uporabnik("Oseba", "Načelnik")
    drugi = _ucitelj_uporabnik("Drugi", "Učenik")
    with TestClient(app) as c:
        login(c, drugi.username)
        r = c.post(f"/auth/admin/users/{ucitelj.id}/govorilne")
        assert r.status_code == 403


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


def test_prijava_brisanje_ucitelj_tuja_403():
    """Učitelj NE more izbrisati rezervacije drugega učitelja (ne svoje)."""
    with TestClient(app) as c:
        pid = _naredi_prijavo()  # prijava za "Matej Čušin"
        teacher = _ucitelj_uporabnik("Drugi", "Učenik")
        login(c, teacher.username)
        r = c.post("/govorilne/api/prijava/odstrani", json={"id": pid})
        assert r.status_code == 403
        # Prijava mora še vedno obstajati.
        db = SessionLocal()
        try:
            assert db.query(GovorilnaPrijava).filter(GovorilnaPrijava.id == pid).first() is not None
        finally:
            db.close()


def test_prijava_brisanje_ucitelj_svojo_200():
    """Učitelj IZBRIŠE lastno rezervacijo — 200 in prijava izgine."""
    with TestClient(app) as c:
        pid = _naredi_prijavo()  # prijava za "Matej Čušin"
        teacher = _ucitelj_uporabnik("Matej", "Čušin")
        login(c, teacher.username)
        r = c.post("/govorilne/api/prijava/odstrani", json={"id": pid})
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        db = SessionLocal()
        try:
            assert db.query(GovorilnaPrijava).filter(GovorilnaPrijava.id == pid).first() is None
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


# ─────────────────────────────────────────────────────────────────────────
# ŠOLSKI ZVONČNI URNIKI (17. 10. 2026; vir: /za-ucence-in-starse/solski-zvonec/)
# Vsak učitelj izbere svoj urnik (1.-2., 3.-5. ali 6.-9. razred); začetek
# njegove dopoldanske šolske ure (termina govorilnih) se vzame iz tega urnika.
# ─────────────────────────────────────────────────────────────────────────

def test_urnik_razberi_iz_razreda():
    """Privzet zvončni urnik se razbere iz razreda razrednika."""
    from app.govorilne_podatki import _razberi_urnik, _urnik_ucitelja_za
    assert _razberi_urnik("1. a") == "1-2"
    assert _razberi_urnik("2. č") == "1-2"
    assert _razberi_urnik("3. b") == "3-5"
    assert _razberi_urnik("5. č") == "3-5"
    assert _razberi_urnik("6. a") == "6-9"
    assert _razberi_urnik("9. c") == "6-9"
    assert _razberi_urnik(None) == "6-9"
    assert _razberi_urnik("") == "6-9"
    # Eksplicitna izbira učitelja prevlada nad razredom.
    u = {"ime": "X", "razred": "1. a", "urnik": "6-9"}
    assert _urnik_ucitelja_za(u) == "6-9"
    assert _urnik_ucitelja_za({"ime": "Y", "razred": "1. a"}) == "1-2"


def test_zacetki_za_ucitelja_po_njegovem_urniku():
    """Tabela začetkov se izbere po učiteljevem urniku (ne globalni)."""
    from app.govorilne_podatki import URNIKI, _urnik_ucitelja_za
    from app.routers.govorilne import _zacetki_za_ucitelja
    # Učitelj 1. razreda → urnik 1-2 (npr. 2. ura = 09:25).
    u12 = {"ime": "A", "razred": "1. a", "ura": 2}
    assert _urnik_ucitelja_za(u12) == "1-2"
    assert _zacetki_za_ucitelja(u12)[2] == URNIKI["1-2"]["zacetki"][2]
    # Učitelj 6.-9. razreda → 2. ura = 09:15 (drugače kot 1-2).
    u69 = {"ime": "B", "razred": "8. b", "ura": 2}
    assert _zacetki_za_ucitelja(u69)[2] == URNIKI["6-9"]["zacetki"][2]
    assert URNIKI["6-9"]["zacetki"][2] != URNIKI["1-2"]["zacetki"][2]
    # Neznan id → fallback na private globalne URA_ZACETKI.
    assert _zacetki_za_ucitelja({"ime": "C", "razred": "1. a", "urnik": "nonsense"})


def test_dopoldan_termin_zacetek_sledi_urniku():
    """Dopoldanski termin učitelja se začne ob uri iz NEGOVEGA urnika (ne 07:50)."""
    from app.govorilne_podatki import URNIKI, _urnik_ucitelja_za
    from app.routers.govorilne import _dopoldan_termini
    # Učitelj razrednega pouka 1. a, 2. ura → 1-2 urnik → 09:25.
    u1 = {"ime": "Arijana Đuretić", "razred": "1. a", "dan": 0, "ura": 2, "po_dogovoru": False}
    terms1 = _dopoldan_termini(u1, {})
    assert terms1  # mora obstajati (teden popoldanskih = 2026-11-19 → naprej)
    assert terms1[0]["ura_od"] == URNIKI["1-2"]["zacetki"][2]
    # Eksplicitno predmetni učitelj (6-9), 3. ura → 10:20.
    u2 = {"ime": "Goran Ilić", "razred": None, "dan": 0, "ura": 3, "po_dogovoru": False}
    terms2 = _dopoldan_termini(u2, {})
    assert terms2 and terms2[0]["ura_od"] == URNIKI["6-9"]["zacetki"][3]


def test_urnik_neveljaven_400(make_user):
    """Neznan id urnika pri urejanju → 400."""
    from app.govorilne_podatki import UCITELJI
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        r = c.post("/govorilne/api/ure/ucitelj", json={
            "ime": prvi["ime"], "urnik": "ne-veljaven", "dan": 0, "ura": 1,
        })
        assert r.status_code == 400


def test_admin_uredi_urnik_in_zacetek_se_spremeni(make_user):
    """Admin nastavi učitelju 3-5 urnik; dopoldanski termin dobi pripadajoči začetek."""
    from app.govorilne_podatki import URNIKI, UCITELJI
    from app.routers.govorilne import _testni_datum
    prvi = next(u for u in UCITELJI if not u["po_dogovoru"])
    admin = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin.username)
        # Nastavi 3-5 urnik, 3. ura.
        r = c.post("/govorilne/api/ure/ucitelj", json={
            "ime": prvi["ime"], "urnik": "3-5", "dan": 0, "ura": 3, "prostor": "x",
        })
        assert r.status_code == 200, r.text
        data = r.json()["ucitelj"]
        assert data["urnik"] == "3-5"
        assert data["urnik_label"] == URNIKI["3-5"]["label"]
        # Javni termini zdaj oddajajo 3-5 začetek za 3. uro (dopoldanski datum).
        od = _testni_datum(0).isoformat()
        r2 = c.get("/govorilne/api/termini", params={"ucitelj": prvi["ime"]})
        assert r2.status_code == 200
        spodnji = [t["ura_od"] for t in r2.json()["termini"]
                   if t["datum"] == od and t["ura_od"].startswith(URNIKI["3-5"]["zacetki"][3])]
        assert spodnji, f"dopoldanski termin ({od}) naj bo pri 3-5 začetku 3. ure"


def test_obrazec_za_ucitelje_ima_urnik_dropdown_in_link(make_user):
    """Obrazec /govorilne/ure vsebuje izbiro šolskega zvončnega urnika + link."""
    with TestClient(app) as c:
        admin = make_user(role="admin")
        login(c, admin.username)
        r = c.get("/govorilne/ure")
        assert r.status_code == 200
        # Dropdown za urnik z 3 opcijami + link na zvončni urnik šole.
        assert 'name="urnik"' in r.text
        assert 'value="1-2"' in r.text and 'value="3-5"' in r.text and 'value="6-9"' in r.text
        assert "šolski-zvonec" in r.text or "zvonec" in r.text
        assert "urnik zvonjenja" in r.text


def test_druga_sola_ne_podeduje_uciteljev_ostc(make_user):
    """CROSS-ŠOLA VARNOST: druga (ne-ostcj) šola na /govorilne/ure in javni
    (/govorilne_<slug>) NIKDAR ne sme videti učiteljev OŠ Toneta Čufarja.

    Pred popravkom je _load_cfg šolo brez GOVORILNE_KONFIG seed-al iz modula
    (govorilne_podatki.py) — torej s HARDKODIRANIM OSTC seznamom učiteljev →
    vsaka nova šola je kazala tuje (ostcj) učitelje. Zdaj se ne-ostcj šola
    seed-a s PRAZNIM seznamom učiteljev.
    """
    from app.tenancy import create_school
    from app.models import School, SchoolSetting
    slug = "druga-sole"
    db = SessionLocal()
    try:
        # Prečisti, če test teče večkrat v isti DB.
        old = db.query(School).filter(School.slug == slug).first()
        if old:
            db.query(SchoolSetting).filter(
                SchoolSetting.school_id == old.id,
            ).delete(synchronize_session=False)
            db.query(School).filter(School.id == old.id).delete(synchronize_session=False)
        db.commit()
        create_school(db, "Druga šola", slug=slug)
        db.commit()
        school2 = db.query(School).filter(School.slug == slug).first()
        assert school2 is not None
        sid = school2.id
    finally:
        db.close()

    # Admin pripada DRUGI šoli (ne ostcj).
    admin2 = make_user(role="admin", school_id=sid)
    with TestClient(app) as c:
        login(c, admin2.username)
        r = c.get("/govorilne/ure")
        assert r.status_code == 200
        # Noben OSTC učitelj sme biti viden.
        assert "Đuretić" not in r.text
        assert "Arijana" not in r.text
        assert "Čušin" not in r.text
        # Javna stran druge šole prav tako brez OSTC učiteljev.
        r2 = c.get("/govorilne_drugasole")
        assert r2.status_code == 200
        assert "Đuretić" not in r2.text
        assert "Čušin" not in r2.text

    # OSTC (privzeta šola) MORA še vedno kazati svoje učitelje.
    admin_ostc = make_user(role="admin")
    with TestClient(app) as c:
        login(c, admin_ostc.username)
        r3 = c.get("/govorilne/ure")
        assert r3.status_code == 200
        assert "Đuretić" in r3.text
