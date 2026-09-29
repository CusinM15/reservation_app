# ─────────────────────────────────────────────────────────────────────────
# tests/test_subscriptions.py — mesečne naročnine šol (30 €/mesec)
#
# Zahteva uporabnika (2026-09-25): vsaka šola ima v bazi datum veljavnosti;
# dokler je datum v prihodnosti, šola dela normalno; ko poteče, aplikacija za
# to šolo ni več dostopna, prijavita pa se lahko le ŠOLSKI ADMIN (ki ima v
# nastavitvah možnost nakupa za en mesec) in glavni admin.
#
# Pravilo v ozadju: ko je prodaja v namestitvi IZKLOPLJENA (privzeto, npr. v
# šoli na k3s), aplikacija deluje brez kakršnihkoli omejitev.
# ─────────────────────────────────────────────────────────────────────────

import re
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.app_settings import (
    get_app_setting,
    is_free,
    plan_by_id,
    plans,
    price_eur,
    save_selling_config,
)
from app.config import settings as app_config
from app.database import SessionLocal
from app.models import AuditLog, Payment, RoleEnum, School, User
from app.tenancy import (
    TEST_EMAIL_PLACEHOLDER,
    default_school_admin_username,
    get_school_config,
    school_admin_username_from_initials,
    set_school_setting,
)
from app.subscriptions import (
    auto_renew_enabled,
    days_left,
    extend_subscription,
    get_valid_until,
    is_active,
    next_charge_day,
    set_valid_until,
)
from tests.conftest import TEST_PASSWORD, default_school_id, login

PAYPAL = "https://www.paypal.com/ncp/payment/PRIMER123"


def _set_selling(enabled: bool, price: int = 30, price_half: int = 30, paypal: str = PAYPAL,
                 note: str = "Navodila"):
    db = SessionLocal()
    try:
        save_selling_config(db, enabled=enabled, price=price, price_half=price_half,
                            paypal=paypal, note=note)
        db.commit()
    finally:
        db.close()


def _set_until(day: date | None, school_id: int | None = None):
    db = SessionLocal()
    try:
        set_valid_until(db, school_id or default_school_id(), day)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_state(client):
    """Vsak test začnemo in končamo z izklopljeno prodajo in brez naročnine.

    Prek parametra `client` poskrbimo, da se aplikacija (in s tem tabele v
    bazi) najprej zažene — sicer bi fixture tekla pred ustvarjanjem tabel.
    """
    _set_selling(False)
    _set_until(None)
    yield
    _set_selling(False)
    _set_until(None)


def _login(client, username: str, password: str = TEST_PASSWORD):
    """Prijava BEZ sledenja preusmeritvi (da vidimo, ali je prijava uspela)."""
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def _db_until(school_id: int | None = None) -> date | None:
    """Preberi datum veljavnosti z lastno sejo (pomembno: sejo ZAPREMO).

    Če seje ne zapremo, ostane odprta transakcija in conftest.clean_db
    (TRUNCATE) čaka nanjo — testi se obesijo. Zato v testih nikoli ne kličimo
    SessionLocal() kar v izrazu.
    """
    db = SessionLocal()
    try:
        return get_valid_until(db, school_id or default_school_id())
    finally:
        db.close()


def _is_active(school_id: int | None = None) -> bool:
    db = SessionLocal()
    try:
        return is_active(db, school_id or default_school_id())
    finally:
        db.close()


def _days_left(school_id: int | None = None) -> int | None:
    db = SessionLocal()
    try:
        return days_left(db, school_id or default_school_id())
    finally:
        db.close()


def _payment_rows(school_id: int | None = None) -> list[Payment]:
    db = SessionLocal()
    try:
        query = db.query(Payment)
        if school_id:
            query = query.filter(Payment.school_id == school_id)
        return query.order_by(Payment.id).all()
    finally:
        db.close()


# ── 1. Ko prodaja ni vklopljena, ni nobenih omejitev ─────────────────

def test_selling_off_does_not_restrict(client, make_user):
    teacher = make_user()
    r = _login(client, teacher.username)
    assert r.status_code == 303
    assert client.get("/rezervacije").status_code == 200
    assert _is_active() is True


# ── 2. Potekla naročnina: učitelj se ne more prijaviti ───────────────

def test_expired_subscription_blocks_teacher_login(client, make_user):
    _set_selling(True)
    _set_until(date.today() - timedelta(days=1))
    teacher = make_user()

    r = _login(client, teacher.username)
    assert r.status_code == 200                     # ostane na prijavni strani
    assert "Naročnina vaše šole je potekla" in r.text


def test_active_subscription_allows_teacher_login(client, make_user):
    _set_selling(True)
    _set_until(date.today() + timedelta(days=10))
    teacher = make_user()

    r = _login(client, teacher.username)
    assert r.status_code == 303
    assert client.get("/rezervacije").status_code == 200


def test_school_admin_can_always_log_in(client, make_user):
    _set_selling(True)
    _set_until(date.today() - timedelta(days=3))
    admin = make_user(role="admin")

    r = _login(client, admin.username)
    assert r.status_code == 303                     # admin se prijavi
    assert client.get("/narocnina").status_code == 200
    assert "Nakup naročnine" in client.get("/narocnina").text


def test_main_admin_can_always_log_in(client):
    _set_selling(True)
    _set_until(date.today() - timedelta(days=3))

    r = _login(client, app_config.MAIN_ADMIN_USERNAME, app_config.MAIN_ADMIN_PASSWORD)
    assert r.status_code == 303


# ── 3. Že odprta seja se prav tako zapre ─────────────────────────────

def test_existing_session_is_blocked_after_expiry(client, make_user):
    teacher = make_user()
    login(client, teacher.username)
    assert client.get("/rezervacije").status_code == 200

    # šola zdaj ostane brez veljavne naročnine
    _set_selling(True)
    _set_until(date.today() - timedelta(days=1))

    r = client.get("/rezervacije", follow_redirects=False)
    assert r.status_code == 303
    assert "/narocnina" in r.headers.get("location", "")

    api = client.get("/api/rezervacije")
    assert api.status_code == 403
    assert "Naročnina" in api.json()["detail"]


def test_teacher_sees_notice_not_error(client, make_user):
    """Učitelj z VELJAVNO naročnino se prijavi, nato naročnina poteče in
    middleware ga preusmeri na /narocnina — tam naj vidi obvestilo, ne napake."""
    _set_selling(True)
    _set_until(date.today() + timedelta(days=5))
    teacher = make_user()
    assert _login(client, teacher.username).status_code == 303

    _set_until(date.today() - timedelta(days=1))     # naročnina poteče
    r = client.get("/narocnina")
    assert r.status_code == 200
    assert "Kaj zdaj?" in r.text
    assert "Nakup naročnine" not in r.text       # nakup je le za admina


# ── 4. Logika podaljševanja ──────────────────────────────────────────

def test_days_left_and_state():
    _set_until(date.today() + timedelta(days=5))
    assert _days_left() == 5
    assert _is_active() is True


def test_extend_from_existing_validity_keeps_paid_days():
    """Če naročnina še velja, se mesec DODA (šola ne izgubi plačanih dni)."""
    base = date.today() + timedelta(days=10)
    _set_until(base)
    db = SessionLocal()
    try:
        new_until = extend_subscription(db, default_school_id(), 1)
        db.commit()
    finally:
        db.close()
    assert new_until > base
    assert new_until.day in (base.day, 28, 29, 30, 31)   # isti dan v naslednjem mesecu


def test_extend_from_expired_starts_today():
    _set_until(date.today() - timedelta(days=40))
    db = SessionLocal()
    try:
        new_until = extend_subscription(db, default_school_id(), 1)
        db.commit()
    finally:
        db.close()
    assert new_until >= date.today() + timedelta(days=27)
    assert _db_until() == new_until


def test_school_without_subscription_is_not_active():
    _set_selling(True)
    _set_until(None)
    db = SessionLocal()
    try:
        assert is_active(db, default_school_id()) is False
    finally:
        db.close()


# ── 5. Nakup: sporočilo o plačilu in potrditev ───────────────────────

def test_report_payment_creates_pending_entry(client, make_user):
    _set_selling(True)
    _set_until(date.today() - timedelta(days=1))
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.post(
        "/narocnina/sporoci-placilo",
        data={"reference": "PP-123", "note": "plačano 25. 9."},
        follow_redirects=False,
    )
    assert r.status_code == 303

    rows = _payment_rows(default_school_id())
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].amount_eur == 30
    assert rows[0].reference == "PP-123"


def test_main_admin_confirms_payment_and_extends(client, make_user):
    _set_selling(True)
    _set_until(date.today() - timedelta(days=1))
    admin = make_user(role="admin")
    login(client, admin.username)
    client.post("/narocnina/sporoci-placilo", data={"reference": "PP-9"}, follow_redirects=False)
    payment_id = _payment_rows(default_school_id())[0].id

    client.get("/auth/logout")
    _login(client, app_config.MAIN_ADMIN_USERNAME, app_config.MAIN_ADMIN_PASSWORD)
    # 307 (preusmeritev na pot šole) ohrani metodo in telo — brskalnik jo izvede,
    # zato v testu sledimo preusmeritvi in preverimo DEJSTVO v bazi.
    r = client.post(f"/narocnina/potrdi/{payment_id}", follow_redirects=False)
    assert r.status_code in (303, 307)

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        assert payment.status == "confirmed"
        assert payment.confirmed_by == app_config.MAIN_ADMIN_USERNAME
        assert payment.valid_until == get_valid_until(db, default_school_id())
        assert get_valid_until(db, default_school_id()) >= date.today() + timedelta(days=27)
        # dogodek je v dnevniku sprememb
        actions = [a.action for a in db.query(AuditLog).all()]
        assert "report_payment" in actions and "confirm_payment" in actions
    finally:
        db.close()


def test_main_admin_can_grant_months_without_payment(client):
    _set_selling(True)
    _set_until(None)
    _login(client, app_config.MAIN_ADMIN_USERNAME, app_config.MAIN_ADMIN_PASSWORD)

    r = client.post("/narocnina/podaljsaj", data={"months": 2}, follow_redirects=False)
    assert r.status_code in (303, 307)
    db = SessionLocal()
    try:
        assert get_valid_until(db, default_school_id()) >= date.today() + timedelta(days=55)
    finally:
        db.close()


def test_selling_settings_are_main_admin_only(client, make_user):
    _set_selling(True)
    admin = make_user(role="admin")
    login(client, admin.username)

    forbidden = client.post(
        "/narocnina/nastavitve",
        data={"selling": "1", "price_eur": "99", "paypal_url": "x", "payment_note": "y"},
        follow_redirects=False,
    )
    assert forbidden.status_code == 403

    client.get("/auth/logout")
    _login(client, app_config.MAIN_ADMIN_USERNAME, app_config.MAIN_ADMIN_PASSWORD)
    ok = client.post(
        "/narocnina/nastavitve",
        data={"selling": "1", "price_eur": "45", "paypal_url": PAYPAL, "payment_note": "Novo"},
        follow_redirects=False,
    )
    assert ok.status_code in (303, 307)

    db = SessionLocal()
    try:
        assert get_app_setting(db, "SUBSCRIPTION_PRICE_EUR") == "45"
        assert get_app_setting(db, "SUBSCRIPTION_PAYPAL_URL") == PAYPAL
    finally:
        db.close()


# ── 7. Javna stran za nakup (popravek napake »klik ne naredi nič«) ───

def test_nakup_page_is_public(client):
    """Gumb za nakup je na PRIJAVNI strani, kjer uporabnik še ni prijavljen —
    zato mora biti stran za nakup dosegljiva BREZ prijave. Če bi kazala na
    zaščiteno /narocnina, bi middleware obiskovalca vrnil na prijavo in klik
    bi izgledal, kot da ne naredi nič."""
    _set_selling(True, price=30)
    r = client.get("/nakup")
    assert r.status_code == 200
    assert "30 €" in r.text
    assert PAYPAL in r.text
    assert "Kako kupite" in r.text


def test_nakup_page_when_selling_off(client):
    r = client.get("/nakup")
    assert r.status_code == 200
    assert "niso v prodaji" in r.text


def test_login_buy_button_points_to_registration(client):
    """Na prijavni strani je le pot za novo šolo, oznaka je »Nova šola«
    (brez cene, kot je zahteval uporabnik)."""
    _set_selling(True)
    html = client.get("/auth/login").text
    assert 'href="/registracija"' in html
    assert re.search(r'href="/registracija"[^>]*>\s*Nova šola', html)
    assert "30 €" not in html
    assert 'href="/narocnina"' not in html


def test_school_admin_settings_link_goes_to_protected_page(client, make_user):
    """Šolski admin je prijavljen, zato njegova povezava vodi na /narocnina
    (tam je stanje in sporočanje plačila)."""
    _set_selling(True)
    admin = make_user(role="admin")
    login(client, admin.username)
    html = client.get("/settings").text
    assert "/narocnina?school_id=" in html


# ── 8. Prijavna stran in nastavitve šole ─────────────────────────────

def test_login_page_shows_registration_link_when_selling(client):
    r = client.get("/auth/login")
    assert 'href="/registracija"' not in r.text

    _set_selling(True, price=30)
    r2 = client.get("/auth/login")
    assert 'href="/registracija"' in r2.text
    assert "Nova šola" in r2.text


def test_school_settings_shows_subscription_box(client, make_user):
    _set_selling(True)
    _set_until(date.today() + timedelta(days=8))
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.get("/settings")
    assert r.status_code == 200
    assert "Naročnina šole" in r.text
    assert "Podaljšaj naročnino" in r.text


def test_settings_hide_subscription_box_when_selling_off(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    assert "Naročnina šole" not in client.get("/settings").text


# ── 9. Cena 0 = brez plačila (a naročnina je vseeno obvezna) ─────────

def test_price_zero_is_allowed(client):
    """Obrazec sprejme ceno 0 (npr. za lastno šolo ali poskusno obdobje).

    Cena 0 pomeni »nič za plačati« — a NE »brez omejitev«: naročnino je treba
    vseeno mesečno obnoviti (zahteva uporabnika 2026-09-29).
    """
    _set_selling(True, price=0, price_half=0)
    db = SessionLocal()
    try:
        assert price_eur(db) == 0
        assert is_free(db) is True
    finally:
        db.close()


def test_price_zero_shows_zero_eur(client):
    _set_selling(True, price=0, price_half=0)
    r = client.get("/nakup")
    assert r.status_code == 200
    assert "0 €" in r.text
    assert "Brezplačno" not in r.text


def test_settings_save_zero_price(client):
    login(client, app_config.MAIN_ADMIN_USERNAME, app_config.MAIN_ADMIN_PASSWORD)
    r = client.post(
        "/narocnina/nastavitve",
        data={"selling": "1", "price_eur": "0", "paypal_url": PAYPAL,
              "paypal_sub_url": "", "payment_note": "x"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 307)
    db = SessionLocal()
    try:
        assert price_eur(db) == 0
    finally:
        db.close()


def test_price_zero_still_requires_subscription(client, make_user):
    """Tudi pri ceni 0 mora biti naročnina veljavna, sicer šola ne dela.

    Zahteva uporabnika 2026-09-29: »cena je 0 €, toda potrebno je mesečno
    plačati/obnoviti, da app dela«. Cena 0 torej ne odvezuje veljavnosti.
    """
    _set_selling(True, price=0, price_half=0)
    _set_until(date.today() - timedelta(days=30))

    db = SessionLocal()
    try:
        assert is_active(db, default_school_id()) is False
    finally:
        db.close()

    teacher = make_user()
    r = _login(client, teacher.username)
    assert r.status_code == 200                     # ostane na prijavni strani
    assert "Naročnina vaše šole je potekla" in r.text


# ── 10. Registracija nove šole ───────────────────────────────────────

def test_registracija_is_public_when_selling_on(client):
    _set_selling(True)
    r = client.get("/registracija")
    assert r.status_code == 200
    assert "Nova šola" in r.text
    assert "Kaj aplikacija dela" in r.text
    assert "Zakaj jo potrebujemo" in r.text


def test_registracija_requires_selling(client):
    r = client.get("/registracija", follow_redirects=False)
    assert r.status_code == 303
    assert "/auth/login" in r.headers.get("location", "")


def test_registracija_creates_school_and_auto_admin(client):
    """Uporabnik vpiše ZGOLJ ime šole — administrator se določi samodejno.

    Zahteva uporabnika 2026-09-29: gesla se NIKJER ne izpišejo. Administrator je po
    registraciji že prijavljen, svoje geslo pa nastavi prek povezave, ki jo prejme na
    e-pošto šole (ko je SMTP nastavljen).
    """
    _set_selling(True)
    ime = f"Testna šola {uuid4().hex[:6]}"

    r = client.post("/registracija", data={"name": ime}, follow_redirects=False)
    assert r.status_code == 200                      # stran s podatki (ne preusmeritev)
    assert "Šola je ustvarjena" in r.text
    assert 'class="pw"' not in r.text                # gesla NE izpisujemo
    assert "povezavo za" in r.text                   # pojasnilo, kako do gesla (e-pošta)

    assert "user_id" in client.cookies
    assert client.cookies.get("school_ctx")          # nastavljen na novo šolo

    db = SessionLocal()
    try:
        school = db.query(School).filter(School.name == ime).first()
        assert school is not None
        admin = db.query(User).filter(User.school_id == school.id,
                                      User.role == RoleEnum.admin).first()
        assert admin is not None
        # uporabniško ime je samodejno: admin_<inicialke imena šole>
        assert admin.username == (
            school_admin_username_from_initials(ime)
            or default_school_admin_username(school.slug)
        )
        assert admin.first_name == "Administrator"
        # nova šola še nima naročnine → učitelji se ne morejo prijaviti
        assert is_active(db, school.id) is False
    finally:
        db.close()

    # seja po registraciji deluje (admin je že prijavljen)
    assert client.get("/settings").status_code == 200


def test_registracija_rejects_bad_input(client):
    _set_selling(True)
    r = client.post("/registracija", data={"name": "ab"}, follow_redirects=False)
    assert r.status_code == 400
    assert "ime šole" in r.text


def test_registracija_slug_collision_gets_suffix(client):
    """Dve šoli z enakim imenom: kratici se razlikujeta (-2), registracija uspe."""
    _set_selling(True)
    ime = f"Podvojena šola {uuid4().hex[:4]}"
    r1 = client.post("/registracija", data={"name": ime}, follow_redirects=False)
    assert r1.status_code == 200
    r2 = client.post("/registracija", data={"name": ime}, follow_redirects=False)
    assert r2.status_code == 200

    db = SessionLocal()
    try:
        sole = db.query(School).filter(School.name == ime).order_by(School.id).all()
        assert len(sole) == 2
        assert sole[1].slug == f"{sole[0].slug}-2"
    finally:
        db.close()


# ── 11. Samodejno mesečno plačilo ────────────────────────────────────

def test_auto_renew_toggle(client, make_user):
    _set_selling(True)
    _set_until(date.today() + timedelta(days=5))
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.post("/narocnina/avto", data={"auto": "1"}, follow_redirects=False)
    assert r.status_code in (303, 307)
    db = SessionLocal()
    try:
        assert auto_renew_enabled(db, default_school_id()) is True
        assert next_charge_day(db, default_school_id()) == (date.today() + timedelta(days=5)).day
    finally:
        db.close()

    page = client.get("/narocnina")
    assert "Samodejno plačilo" in page.text
    assert "Vklopljeno" in page.text

    client.post("/narocnina/avto", data={"auto": "0"}, follow_redirects=False)
    db = SessionLocal()
    try:
        assert auto_renew_enabled(db, default_school_id()) is False
    finally:
        db.close()


def test_monthly_paypal_link_is_saved(client):
    login(client, app_config.MAIN_ADMIN_USERNAME, app_config.MAIN_ADMIN_PASSWORD)
    sub_url = "https://www.paypal.com/webapps/billing/plans/PRIMER"
    r = client.post(
        "/narocnina/nastavitve",
        data={"selling": "1", "price_eur": "30", "paypal_url": PAYPAL,
              "paypal_sub_url": sub_url, "payment_note": "x"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 307)
    db = SessionLocal()
    try:
        assert get_app_setting(db, "SUBSCRIPTION_PAYPAL_SUB_URL") == sub_url
    finally:
        db.close()


def test_settings_button_label_depends_on_state(client, make_user):
    _set_selling(True)
    admin = make_user(role="admin")
    login(client, admin.username)

    _set_until(date.today() - timedelta(days=1))
    assert "Kupi naročnino" in client.get("/settings").text

    _set_until(date.today() + timedelta(days=10))
    assert "Podaljšaj naročnino" in client.get("/settings").text


# ── 13. Inicialke, testna e-pošta in navodila za nastavitev ──────────

def test_admin_username_from_initials():
    """Uporabniško ime admina = admin_<največ 3 inicialke imena šole>."""
    assert school_admin_username_from_initials(
        "Osnovna šola Toneta Čufarja Jesenice") == "admin_ost"
    assert school_admin_username_from_initials("OŠ Toneta Čufarja Jesenice") == "admin_otc"
    assert school_admin_username_from_initials("Gimnazija Kranj") == "admin_gk"
    # neveljavno/prekratko ime → prazen niz (klicatelj uporabi oznako šole)
    assert school_admin_username_from_initials("") == ""
    assert school_admin_username_from_initials("Šola") == ""


def test_registration_uses_initials_for_username(client):
    _set_selling(True)
    ime = "OŠ Testna Preizkusna Jesenice"
    r = client.post("/registracija", data={"name": ime}, follow_redirects=False)
    assert r.status_code == 200

    db = SessionLocal()
    try:
        school = db.query(School).filter(School.name == ime).first()
        assert school is not None
        admin = db.query(User).filter(User.school_id == school.id).first()
        assert admin is not None
        # inicialke (največ 3): OŠ Testna Preizkusna Jesenice → otp
        assert admin.username.startswith("admin_otp")
    finally:
        db.close()


def test_registration_sets_test_email_addresses(client):
    """Nova šola dobi TESTNE naslove (ne naših iz .env) — admin jih zamenja."""
    _set_selling(True)
    ime = f"Testna šola {uuid4().hex[:6]}"
    r = client.post("/registracija", data={"name": ime}, follow_redirects=False)
    assert r.status_code == 200

    db = SessionLocal()
    try:
        school = db.query(School).filter(School.name == ime).first()
        cfg = get_school_config(db, school.id)
        assert cfg.MAIL_FROM == TEST_EMAIL_PLACEHOLDER
        assert cfg.ADMIN_EMAIL == TEST_EMAIL_PLACEHOLDER
        assert cfg.BACKUP_EMAIL == TEST_EMAIL_PLACEHOLDER
    finally:
        db.close()


def test_setup_guide_page(client, make_user):
    """Stran /nastavitev pokaže kontrolni seznam in opozori na testne naslove."""
    _set_selling(True)
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.get("/nastavitev")
    assert r.status_code == 200
    assert "Navodila za nastavitev šole" in r.text
    assert "naslov pošiljatelja" in r.text.lower()
    assert "✗ uredi" in r.text                     # testni naslovi še niso urejeni
    assert "Naročnina" in r.text

    # ko admin vpiše svoje vrednosti, se kazalniki obrnejo
    _set_until(date.today() + timedelta(days=10))
    db = SessionLocal()
    try:
        set_school_setting(db, default_school_id(), "ADMIN_EMAIL", "tajnistvo@os-primer.si")
        set_school_setting(db, default_school_id(), "MAIL_FROM", "tajnistvo@os-primer.si")
        set_school_setting(db, default_school_id(), "BACKUP_EMAIL", "kopije@os-primer.si")
        set_school_setting(db, default_school_id(), "RAZREDI", "1. a, 2. a")
        set_school_setting(db, default_school_id(), "PROSTORI", "tablice, računalnica")
        db.commit()
    finally:
        db.close()

    r2 = client.get("/nastavitev")
    assert "✓ urejeno" in r2.text


# ── 12. Zaklenitev po registraciji (piškotek school_ctx) ─────────────
#
# Napaka, ki jo je uporabnik doživel 28. 9. 2026: po ustvarjanju nove šole je
# vsaka stran vrnila 403 »Nimate dostopa do podatkov te šole.«, ker je v
# brskalniku ostal piškotek school_ctx prejšnje šole, novi admin pa pripada
# drugi šoli. Piškotek za šolske vloge ne sme imeti veljave.

def _nova_sola_iz_tenancy(name: str = "Druga šola") -> int:
    from app.tenancy import create_school

    db = SessionLocal()
    try:
        suffix = uuid4().hex[:6]
        school = create_school(db, name=f"{name} {suffix}", slug=f"druga-{suffix}")
        db.commit()
        return int(school.id)
    finally:
        db.close()


def test_registration_sets_school_ctx(client):
    _set_selling(True)
    r = client.post("/registracija", data={"name": f"Nova šola {uuid4().hex[:6]}"},
                    follow_redirects=False)
    assert r.status_code == 200
    assert client.cookies.get("school_ctx")            # nastavljen na novo šolo

    # ključno: takoj po registraciji mora aplikacija DELOVATI
    assert client.get("/narocnina").status_code == 200
    assert client.get("/settings").status_code == 200


def test_stale_school_ctx_does_not_lock_school_user(client, make_user):
    """Zastarel piškotek school_ctx (druga šola) ne sme vrniti 403."""
    other_school_id = _nova_sola_iz_tenancy()
    admin = make_user(role="admin", school_id=other_school_id)

    # napačna (stara) šola — pošljemo kot glavo, da ne onesnažimo piškotkov
    client.cookies.clear()
    r = client.post("/auth/login",
                    data={"username": admin.username, "password": TEST_PASSWORD},
                    headers={"Cookie": "school_ctx=1"}, follow_redirects=False)
    assert r.status_code == 303

    assert client.get("/rezervacije").status_code == 200
    assert client.get("/settings").status_code == 200
    assert client.get("/narocnina").status_code == 200


def test_login_sets_own_school_ctx(client, make_user):
    other_school_id = _nova_sola_iz_tenancy()
    admin = make_user(role="admin", school_id=other_school_id)

    client.cookies.clear()
    client.post("/auth/login",
                data={"username": admin.username, "password": TEST_PASSWORD},
                headers={"Cookie": "school_ctx=1"}, follow_redirects=False)
    assert client.cookies.get("school_ctx") == str(other_school_id)


def test_logout_clears_school_ctx(client, make_user):
    other_school_id = _nova_sola_iz_tenancy()
    admin = make_user(role="admin", school_id=other_school_id)
    _login(client, admin.username)

    client.get("/auth/logout", follow_redirects=False)
    assert not client.cookies.get("school_ctx")


# ── 14. Planа naročnine: pol leta (6 mes.) in leto (12 mes.) ─────────

def test_half_year_plan_reports_six_months(client, make_user):
    """Plan »pol leta«: znesek 7 €, podaljšanje za 6 mesecev."""
    _set_selling(True, price=13, price_half=7)
    _set_until(date.today() - timedelta(days=1))
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.post("/narocnina/sporoci-placilo",
                    data={"reference": "PP-H", "plan": "polletje"}, follow_redirects=False)
    assert r.status_code == 303
    row = _payment_rows(default_school_id())[0]
    assert row.amount_eur == 7
    assert row.months == 6

    client.get("/auth/logout")
    _login(client, app_config.MAIN_ADMIN_USERNAME, app_config.MAIN_ADMIN_PASSWORD)
    client.post(f"/narocnina/potrdi/{row.id}", follow_redirects=False)
    db = SessionLocal()
    try:
        until = get_valid_until(db, default_school_id())
        assert until >= date.today() + timedelta(days=175)
    finally:
        db.close()


def test_yearly_plan_reports_twelve_months(client, make_user):
    """Plan »leto«: znesek 13 €, podaljšanje za 12 mesecev."""
    _set_selling(True, price=13, price_half=7)
    _set_until(date.today() - timedelta(days=1))
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.post("/narocnina/sporoci-placilo",
                    data={"reference": "PP-Y", "plan": "leto"}, follow_redirects=False)
    assert r.status_code == 303
    row = _payment_rows(default_school_id())[0]
    assert row.amount_eur == 13
    assert row.months == 12


def test_nakup_shows_both_plans(client):
    _set_selling(True, price=13, price_half=7)
    r = client.get("/nakup")
    assert "7 €" in r.text and "13 €" in r.text
    assert "pol leta" in r.text and "leto" in r.text


def test_default_plans_are_seven_and_thirteen():
    """Brez zapisa v bazi sta privzeti ceni 7 € (pol leta) in 13 € (leto)."""
    db = SessionLocal()
    try:
        seznam = plans(db)
        assert [p["id"] for p in seznam] == ["polletje", "leto"]
        assert plan_by_id(db, "polletje")["months"] == 6
        assert plan_by_id(db, "leto")["months"] == 12
        assert plan_by_id(db, "neznano")["id"] == "leto"      # neznano → letni plan
    finally:
        db.close()
