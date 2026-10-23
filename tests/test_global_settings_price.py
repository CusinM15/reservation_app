# ─────────────────────────────────────────────────────────────────────────
# tests/test_global_settings_price.py — Cena naročnine v Globalnih nastavitvah
#
# Zahteva uporabnika (2026-10-23): glavni admin ima v /global-settings
# spremenljivko »cena« (SUBSCRIPTION_PRICE_EUR, €/leto). Vsi izračuni
# (sorazmerna cena, e-račun) in vsi prikazi cene (nakup, naročnina,
# registracija, nastavitve) jemljejo ceno od tam — sprememba v globalnih
# nastavitvah velja povsod naenkrat.
# ─────────────────────────────────────────────────────────────────────────

from app.app_settings import get_app_setting, price_eur, selling_config
from app.config import settings as app_config
from app.database import SessionLocal

from tests.conftest import login

PRICE_KEY = "SUBSCRIPTION_PRICE_EUR"


def _main_admin_login(client):
    """Prijava glavnega admina (brez ostankov prejšnje seje)."""
    client.cookies.clear()
    return login(client, app_config.MAIN_ADMIN_USERNAME, app_config.MAIN_ADMIN_PASSWORD)


def _db_price() -> float:
    db = SessionLocal()
    try:
        return price_eur(db)
    finally:
        db.close()


def _db_raw_price() -> str:
    db = SessionLocal()
    try:
        return get_app_setting(db, PRICE_KEY, "")
    finally:
        db.close()


# ── 1. Stran /global-settings prikaže ceno ──────────────────────────────

def test_global_settings_page_shows_price(client):
    """Main admin vidi polje »Cena naročnine« z veljavno vrednostjo."""
    _main_admin_login(client)
    r = client.get("/global-settings")
    assert r.status_code == 200
    assert "Cena naročnine" in r.text
    assert 'id="price-eur"' in r.text
    # Privzeta cena (DEFAULT_PRICE_EUR = 220) se predizpolni v polju.
    assert str(_db_price()) in r.text


# ── 2. Shranjevanje cene prek /api/global-settings ─────────────────────

def test_api_global_settings_saves_price(client):
    """POST z 'price' shrani globalno ceno (velja za vse šole)."""
    _main_admin_login(client)
    r = client.post("/api/global-settings", json={"price": "45,50"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["price_eur"] == 45.5
    assert "45,50 €" in body["price_label"]
    assert _db_price() == 45.5
    assert _db_raw_price() == "45,50"


def test_api_global_settings_price_drives_calc_and_display(client):
    """Po novi ceni se osvežita sorazmerna cena in price_label."""
    _main_admin_login(client)
    r = client.post("/api/global-settings", json={"price": "120"})
    assert r.status_code == 200
    db = SessionLocal()
    try:
        cfg = selling_config(db)
        assert cfg["price_eur"] == 120
        assert "120,00 € / leto" in cfg["price_label"]
    finally:
        db.close()
    # Cenovno polje na strani se osveži.
    r = client.get("/global-settings")
    assert 'value="120.0"' in r.text


def test_api_global_settings_price_invalid_falls_back_to_default(client):
    """Neveljavna cena pade na privzeto (ne pokvari nastavitve)."""
    _main_admin_login(client)
    r = client.post("/api/global-settings", json={"price": "abc"})
    assert r.status_code == 200
    assert _db_price() == 220      # DEFAULT_PRICE_EUR
    r = client.post("/api/global-settings", json={"price": "-5"})
    assert r.status_code == 200
    assert _db_price() == 220


def test_api_global_settings_price_rejected_for_school_admin(client, make_user):
    """Samo glavni admin sme spreminjati ceno (šolski admin → 403)."""
    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.post("/api/global-settings", json={"price": "99"})
    assert r.status_code == 403
    assert _db_price() != 99


# ── 3. Cena ostane globalna tudi prek stare poti /narocnina/nastavitve ─

def test_narocnina_settings_and_global_settings_share_price(client):
    """Obe poti pišeta isto globalno spremenljivko SUBSCRIPTION_PRICE_EUR."""
    _main_admin_login(client)
    client.post("/api/global-settings", json={"price": "77"})
    assert _db_raw_price() == "77"

    r = client.post(
        "/narocnina/nastavitve",
        data={"selling": "1", "price_eur": "88", "paypal_url": "", "payment_note": ""},
        follow_redirects=False,
    )
    assert r.status_code in (303, 307)
    assert _db_raw_price() == "88"
    assert _db_price() == 88
