# ─────────────────────────────────────────────────────────────────────────
# tests/test_i18n.py — večjezični napisi (tabela ui_strings, SL/EN)
# ─────────────────────────────────────────────────────────────────────────
import pytest

from app.database import SessionLocal
from app.app_settings import save_selling_config
from app.i18n import (
    invalidate_cache,
    load_strings,
    normalize_lang,
    set_request_language,
    t,
)
from app.models import UIString
from app.tenancy import set_school_setting
from scripts.seed_ui_strings import STRINGS, seed
from tests.conftest import TEST_PASSWORD, default_school_id, login


def test_normalize_lang():
    assert normalize_lang("en") == "en"
    assert normalize_lang("SL") == "sl"
    assert normalize_lang("xx") == "sl"
    assert normalize_lang(None) == "sl"


def test_seed_creates_all_rows(client):
    """Ob zagonu aplikacije se tabela ui_strings napolni; seed je idempotenten."""
    db = SessionLocal()
    try:
        # TestClient ob zagonu požene on_startup → tabela je že napolnjena.
        assert db.query(UIString).count() == len(STRINGS)
        added, _ = seed(db)
        assert added == 0
    finally:
        db.close()


def test_t_reads_from_db_in_selected_language(client):
    """t() vrne napis v izbranem jeziku; če ključa ni, vrne privzeto."""
    db = SessionLocal()
    try:
        db.add(UIString(key="btn_test", sl="Shrani", en="Save"))
        db.commit()
        invalidate_cache()

        set_request_language(db, "en")
        assert t("btn_test") == "Save"

        set_request_language(db, "sl")
        assert t("btn_test") == "Shrani"

        assert t("kljuca_ni", "privzeto") == "privzeto"
    finally:
        db.close()
        set_request_language(None, "sl")


def test_t_falls_back_to_sl_when_en_missing(client):
    db = SessionLocal()
    try:
        db.add(UIString(key="samo_sl", sl="Samo slovensko", en=""))
        db.commit()
        invalidate_cache()
        set_request_language(db, "en")
        assert t("samo_sl") == "Samo slovensko"
    finally:
        db.close()
        set_request_language(None, "sl")


def test_settings_accepts_language_and_rejects_invalid(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = default_school_id()

    ok = client.put(f"/api/schools/{sid}/settings",
                    json={"values": {"UI_LANGUAGE": "en"}})
    assert ok.status_code in (200, 204)

    bad = client.put(f"/api/schools/{sid}/settings",
                     json={"values": {"UI_LANGUAGE": "xx"}})
    assert bad.status_code == 400


def test_navodila_have_no_language_switch(client):
    """V navodilih (glavna stran) ni preklopa jezika — le jezik šole."""
    r = client.get("/")
    assert r.status_code == 200
    assert "navodilaLangToggle" not in r.text
    assert "navodila-lang-toggle" not in r.text


def test_school_language_switches_whole_ui(client, make_user):
    """Ko šola izbere angleščino, se napisi vmesnika prikažejo v angleščini."""
    db = SessionLocal()
    try:
        set_school_setting(db, default_school_id(), "UI_LANGUAGE", "en")
        db.commit()
    finally:
        db.close()

    u = make_user(role="teacher")
    login(client, u.username)
    r = client.get("/")
    assert r.status_code == 200
    # Gumbi, prevedeni prek tabele ui_strings, so zdaj angleški.
    assert "Cancel" in r.text        # Prekliči → Cancel
    assert "Close" in r.text         # Zapri → Close
    # Isti (prej slovenski) napis gumba ni več prisoten kot gumb.
    assert ">Prekliči<" not in r.text


def test_settings_page_translated(client, make_user):
    """Ko je jezik šole angleščina, so tudi Nastavitve šole v angleščini."""
    db = SessionLocal()
    try:
        set_school_setting(db, default_school_id(), "UI_LANGUAGE", "en")
        db.commit()
    finally:
        db.close()

    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.get("/settings")
    assert r.status_code == 200
    for napis in ("School settings", "Basic", "Interface language", "Classes", "Rooms", "Schedule",
                  "Save settings", "School backup",
                  # oznake polj (prej trdo SL v SCHOOL_SETTING_FIELDS)
                  "Inactivity timeout — teachers (min)", "SMTP server", "SMTP password",
                  "School admin email", "Assessments: max per week", "Assessments: max consecutive days",
                  "Schedule – afternoon", "School paths (click opens the app for that school):"):
        assert napis in r.text, f"manjka angleški napis: {napis}"


def test_public_lang_param_translates_registration(client):
    """?lang=en prevede javno stran (registracija) tudi brez šole/seje."""
    db = SessionLocal()
    try:
        save_selling_config(db, enabled=True, price=50, paypal="https://x", note="y")
        db.commit()
    finally:
        db.close()
    r = client.get("/registracija?lang=en")
    assert r.status_code == 200
    assert "Full school name" in r.text
    r2 = client.get("/registracija")
    assert "Polno ime šole" in r2.text


def test_login_links_to_english_setup_and_registration(client):
    """Prijavna stran ponuja angleška navodila za nastavitev in preklop na EN pri Novi šoli."""
    db = SessionLocal()
    try:
        save_selling_config(db, enabled=True, price=50, paypal="https://x", note="y")
        db.commit()
    finally:
        db.close()
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert "navodila-admin-en" in r.text          # English setup instructions (admin guide)
    assert "registracija?lang=en" in r.text       # New school in English


def test_new_school_language_follows_registration_link(client):
    """»New school« (lang=en) → nova šola v angleščini; »Nova šola« → slovensko."""
    from app.models import School
    from app.tenancy import get_school_config

    db = SessionLocal()
    try:
        save_selling_config(db, enabled=True, price=50, paypal="https://x", note="y")
        db.commit()
    finally:
        db.close()

    def jezik_sole(ime_predpona: str) -> str:
        db = SessionLocal()
        try:
            s = db.query(School).filter(School.name.like(ime_predpona + "%")).first()
            assert s is not None, f"šola {ime_predpona!r} ni bila ustvarjena"
            return get_school_config(db, s.id).get_str("UI_LANGUAGE", "sl")
        finally:
            db.close()

    assert client.post("/registracija", data={"name": "En šola test", "lang": "en"}).status_code == 200
    assert jezik_sole("En šola test") == "en"

    # Drugi vpis z novim odjemalcem (brez piškotkov prve šole) — »Nova šola«.
    client.cookies.clear()
    assert client.post("/registracija", data={"name": "Sl sola test"}).status_code == 200
    assert jezik_sole("Sl sola test") == "sl"


def test_main_nav_translated_to_english(client, make_user):
    """Glavni gumbi so v angleščini, ko je jezik šole 'en'.

    Preverja: Rezervacije, Ocenjevanje in dnevi dejavnosti, Rezervacije
    prostorov (naslov) in Nastavitve šole — ti so bili prej trdo zapisani (SL).
    """
    db = SessionLocal()
    try:
        set_school_setting(db, default_school_id(), "UI_LANGUAGE", "en")
        db.commit()
    finally:
        db.close()

    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.get("/rezervacije")
    assert r.status_code == 200
    for napis in ("Reservations", "Assessment and activity days",
                  "Room reservations", "School settings", "Start of week"):
        assert napis in r.text, f"manjka angleški napis: {napis}"
    assert ">Rezervacije<" not in r.text
    assert ">Ocenjevanje in dnevi dejavnosti<" not in r.text
    assert "<h2>Rezervacije prostorov</h2>" not in r.text


def test_filter_options_translated(client, make_user):
    """Izbirniki filtrov: »Vsi razredi«, »8. razred (vsi)«, »9. razred (vsi)«,
    »Vsi prostori« so v angleščini, ko je jezik šole 'en'."""
    db = SessionLocal()
    try:
        set_school_setting(db, default_school_id(), "UI_LANGUAGE", "en")
        db.commit()
    finally:
        db.close()

    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.get("/rezervacije")
    assert r.status_code == 200
    for napis in ("All classes", "All rooms", "8th grade (all)", "9th grade (all)"):
        assert napis in r.text, f"manjka angleški napis: {napis}"
    # Prej trdo zapisani slovenski napisi (zunaj t()) ne smejo več nastopati kot izbire.
    assert '>Vsi razredi</option>' not in r.text
    assert '8. razred (vsi)</option>' not in r.text
    assert '9. razred (vsi)</option>' not in r.text


def test_reservation_ui_translated_to_english(client, make_user):
    """Rezervacije: »Število:« → »Number of:«, »Prosto« → »Free«, »preostalih« →
    »remaining«, dnevi v tednu angleško."""
    db = SessionLocal()
    try:
        set_school_setting(db, default_school_id(), "UI_LANGUAGE", "en")
        db.commit()
    finally:
        db.close()

    admin = make_user(role="admin")
    login(client, admin.username)
    html = client.get("/rezervacije").text
    for napis in ("Number of:", "Free", "remaining", "Monday", "Tuesday", "Wednesday",
                  "Thursday", "Friday", "Free:"):
        assert napis in html, f"manjka angleški napis: {napis}"


def test_dejavnosti_page_translated_to_english(client, make_user):
    """Stran Dejavnosti: tipi sekcij in glavni napisi so v angleščini."""
    db = SessionLocal()
    try:
        set_school_setting(db, default_school_id(), "UI_LANGUAGE", "en")
        db.commit()
    finally:
        db.close()

    admin = make_user(role="admin")
    login(client, admin.username)
    html = client.get("/ocenjevanje/dejavnosti").text
    for napis in ("CULTURAL", "SCIENCE", "TECHNICAL", "SPORTS", "OTHER", "DAYS",
                  "OVERVIEW OF ACTIVITIES", "Grade 1", "Actions"):
        assert napis in html, f"manjka angleški napis: {napis}"
    # stari slovenski napisi naj ne nastopajo več kot sekcije/naslovi
    assert "PREGLED DEJAVNOSTI" not in html
    assert ">Akcije<" not in html


def test_settings_hides_variable_keys_for_school_admin(client, make_user):
    """Kode spremenljivk (UI_LANGUAGE, RAZREDI, …) so skrite šolskemu adminu."""
    admin = make_user(role="admin")
    login(client, admin.username)
    html = client.get("/settings").text
    assert '<span class="key">UI_LANGUAGE</span>' not in html
    assert '<span class="key">RAZREDI</span>' not in html
    assert '<span class="key">INACTIVITY_TIMEOUT_MINUTES</span>' not in html
    assert '<span class="key">PROSTORI + PROSTORI_STEVILO</span>' not in html


def test_settings_shows_variable_keys_for_main_admin(client, make_user):
    """Glavni admin še vedno vidi kode spremenljivk."""
    from app.config import settings
    make_user()  # poskrbi, da je šola/uporabnik (bootstrap) na voljo
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    html = client.get("/settings").text
    assert '<span class="key">UI_LANGUAGE</span>' in html
    assert '<span class="key">RAZREDI</span>' in html
