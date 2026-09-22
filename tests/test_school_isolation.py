# ─────────────────────────────────────────────────────────────────────────
# tests/test_school_isolation.py — stroga ločitev podatkov med šolami
#
# Ozadje (prijava iz produkcije): glavni admin je odprl pot šole B
# (/rezervacije_st), vendar je stran prikazala rezervacije šole A. Vzrok:
# stran se naloži z eno zahtevo, PODATKE pa prinese JavaScript z ločenimi
# klici na /api/... — ti klici ne vsebujejo imena poti šole, zato so se
# uporabili podatki brez konteksta (= vse šole) oz. prejšnja izbrana šola.
#
# Popravek: obisk poti šole nastavi piškotek school_ctx, ki izbrano šolo
# ohrani tudi za nadaljnje API klice. Za ŠOLSKE uporabnike obseg ostaja
# vezan na user.school_id (piškotek ne more razkriti tuje šole — 403).
# ─────────────────────────────────────────────────────────────────────────

from datetime import date

from app.database import SessionLocal
from app.models import Reservation
from app.tenancy import create_school
from tests.conftest import login, default_school_id


def _reserva(school_id: int, prostor: str, hour: int, day: int = 15):
    return Reservation(school_id=school_id, prostor=prostor, date=date(2026, 11, day),
                       hour=hour, teacher_id=1, qty=1)


def _two_schools_with_reservations():
    """Šola A (privzeta) z dvema rezervacijama, šola B z eno (ladja)."""
    sid_a = default_school_id()
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Šola B", slug="solab")
        sid_b = school_b.id
        db.add_all([
            _reserva(sid_a, "tablice", 1),
            _reserva(sid_a, "racunalnica", 2),
            _reserva(sid_b, "ladja", 3),
        ])
        db.commit()
        return sid_a, sid_b
    finally:
        db.close()


def _api_reservations(client):
    r = client.get("/api/rezervacije?start=2026-11-01&end=2026-11-30")
    assert r.status_code == 200, r.text
    return r.json()


# ── 1. Pot šole mora nastaviti kontekst šole ──────────────────────────

def test_alias_sets_school_context_cookie(client, make_user):
    """Obisk poti šole nastavi piškotek school_ctx (brez njega JS klici na
    /api/... niso vezani na izbrano šolo)."""
    from app.config import settings
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)

    r = client.get("/rezervacije_ostcj", follow_redirects=False)
    assert r.status_code == 200
    cookies = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else []
    assert any("school_ctx=" in c for c in cookies), f"ni piškotka school_ctx: {cookies}"


def test_main_admin_alias_page_shows_only_that_schools_data(client, make_user):
    """REGRESIJA: glavni admin odpre /rezervacije_solab, nato JS naloži
    /api/rezervacije — vrniti se smejo SAMO podatki šole B."""
    from app.config import settings
    sid_a, sid_b = _two_schools_with_reservations()

    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)

    # obisk poti šole B (piškotek school_ctx se nastavi samodejno)
    page = client.get("/rezervacije_solab", follow_redirects=False)
    assert page.status_code == 200
    assert client.cookies.get("school_ctx") == str(sid_b)

    rows = _api_reservations(client)
    assert len(rows) == 1, f"pričakovana 1 vrstica šole B, dobljeno {len(rows)}"
    assert rows[0]["prostor"] == "ladja", rows[0]


def test_alias_page_marks_which_school_is_shown(client, make_user):
    """Na vrhu strani mora biti oznaka šole, da ni dvoma, čigavi so podatki."""
    from app.config import settings
    _two_schools_with_reservations()
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)

    html = client.get("/rezervacije_solab", follow_redirects=False).text
    assert "Šola B" in html
    assert "/rezervacije_solab" in html


def test_canonical_page_has_no_school_badge(client, make_user):
    """Kanonična pot (brez poti šole) ne dodaja oznake šole."""
    from app.config import settings
    _two_schools_with_reservations()
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    html = client.get("/rezervacije", follow_redirects=False).text
    assert 'id="school-badge" style="display:none;' in html


# ── 2. Glavni admin: brez konteksta vidi vse (dokumentirano vedenje) ──

def test_main_admin_without_context_sees_all_schools(client, make_user):
    from app.config import settings
    _two_schools_with_reservations()
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    rows = _api_reservations(client)
    assert len(rows) == 3        # vse šole (2 + 1)


# ── 3. Šolski uporabnik ostaja strogo omejen na svojo šolo ────────────

def test_school_user_sees_only_own_school(client, make_user):
    sid_a, _ = _two_schools_with_reservations()
    user = make_user(role="teacher")          # uporabnik privzete šole (A)
    login(client, user.username)
    rows = _api_reservations(client)
    assert len(rows) == 2
    assert {r["prostor"] for r in rows} == {"tablice", "racunalnica"}


def test_school_user_cannot_spoof_other_school_by_cookie(client, make_user):
    """Piškotek school_ctx šolskemu uporabniku NE sme odpreti tuje šole."""
    sid_a, sid_b = _two_schools_with_reservations()
    user = make_user(role="teacher")
    login(client, user.username)
    client.cookies.set("school_ctx", str(sid_b))

    r = client.get("/api/rezervacije?start=2026-11-01&end=2026-11-30")
    assert r.status_code == 403
    assert "Nimate dostopa" in r.json()["detail"]


def test_school_user_gets_403_on_other_schools_alias(client, make_user):
    sid_a, _ = _two_schools_with_reservations()
    user = make_user(role="teacher")
    login(client, user.username)
    r = client.get("/rezervacije_solab", follow_redirects=False)
    assert r.status_code == 403


def test_school_user_own_alias_works(client, make_user):
    sid_a, _ = _two_schools_with_reservations()
    user = make_user(role="teacher")
    login(client, user.username)
    r = client.get("/rezervacije_ostcj", follow_redirects=False)
    assert r.status_code == 200
    assert client.cookies.get("school_ctx") == str(sid_a)

# ── 4. Pot šole se ohrani med prehajanjem med zavihki ─────────────────
# Prijava: uporabnik je bil na /rezervacije_st in kliknil »Ocenjevanje« —
# odprlo se je /ocenjevanje (brez poti šole). Zdaj mora ostati /ocenjevanje_st.

def test_nav_keeps_alias_when_switching_tabs(client, make_user):
    from app.config import settings
    _two_schools_with_reservations()
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)

    html = client.get("/rezervacije_solab", follow_redirects=False).text
    assert 'href="/ocenjevanje_solab"' in html, "zavihek Ocenjevanje ni ostal na poti šole"
    assert 'href="/rezervacije_solab"' in html
    assert "location.href='/ocenjevanje_solab/dejavnosti'" in html

    # in nazaj: z ocenjevalne poti na rezervacije
    html2 = client.get("/ocenjevanje_solab", follow_redirects=False).text
    assert 'href="/rezervacije_solab"' in html2


def test_dejavnosti_page_keeps_alias(client, make_user):
    from app.config import settings
    _two_schools_with_reservations()
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    html = client.get("/ocenjevanje_solab/dejavnosti", follow_redirects=False).text
    assert 'href="/rezervacije_solab"' in html


def test_canonical_nav_stays_canonical(client, make_user):
    """Kdor vstopi po kanonični poti, dobi kanonične povezave (nespremenjeno)."""
    user = make_user()
    login(client, user.username)
    html = client.get("/rezervacije", follow_redirects=False).text
    assert 'href="/ocenjevanje"' in html
    assert 'href="/rezervacije"' in html
    assert "location.href='/ocenjevanje/dejavnosti'" in html
    assert "_solab" not in html


# ── 5. Vloga v predlogi dejavnosti ────────────────────────────────────

def test_teacher_gets_teacher_role_in_template(client, make_user):
    """Učitelj je bralec — v predlogo gre 'teacher', zato so gumbi za urejanje
    skriti. Prej je str(RoleEnum.teacher) dal 'RoleEnum.teacher', zato so se
    učitelju gumbi POKAZALI (klik pa je vrgel 403)."""
    teacher = make_user()
    login(client, teacher.username)
    html = client.get("/ocenjevanje/dejavnosti").text
    assert 'const USER_ROLE = "teacher";' in html


def test_admin_gets_admin_role_in_template(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    html = client.get("/ocenjevanje/dejavnosti").text
    assert 'const USER_ROLE = "admin";' in html
