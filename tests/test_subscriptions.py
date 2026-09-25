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

from datetime import date, timedelta

import pytest

from app.app_settings import get_app_setting, save_selling_config
from app.config import settings as app_config
from app.database import SessionLocal
from app.models import AuditLog, Payment, User
from app.subscriptions import (
    days_left,
    extend_subscription,
    get_valid_until,
    is_active,
    set_valid_until,
)
from tests.conftest import TEST_PASSWORD, default_school_id, login

PAYPAL = "https://www.paypal.com/ncp/payment/PRIMER123"


def _set_selling(enabled: bool, price: int = 30, paypal: str = PAYPAL, note: str = "Navodila"):
    db = SessionLocal()
    try:
        save_selling_config(db, enabled=enabled, price=price, paypal=paypal, note=note)
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
    assert "Nakup enega meseca" in client.get("/narocnina").text


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
    assert "Nakup enega meseca" not in r.text       # nakup je le za admina


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


# ── 6. Prijavna stran in nastavitve šole ─────────────────────────────

def test_login_page_shows_buy_option_when_selling(client):
    r = client.get("/auth/login")
    assert "Nakup / podaljšanje naročnine" not in r.text

    _set_selling(True, price=30)
    r2 = client.get("/auth/login")
    assert "Nakup / podaljšanje naročnine" in r2.text
    assert "30 €" in r2.text


def test_school_settings_shows_subscription_box(client, make_user):
    _set_selling(True)
    _set_until(date.today() + timedelta(days=8))
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.get("/settings")
    assert r.status_code == 200
    assert "Naročnina šole" in r.text
    assert "Nakup / podaljšanje naročnine" in r.text


def test_settings_hide_subscription_box_when_selling_off(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    assert "Naročnina šole" not in client.get("/settings").text
