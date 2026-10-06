# ─────────────────────────────────────────────────────────────────────────
# tests/test_i18n.py — večjezični napisi (tabela ui_strings, SL/EN)
# ─────────────────────────────────────────────────────────────────────────
import pytest

from app.database import SessionLocal
from app.i18n import (
    invalidate_cache,
    load_strings,
    normalize_lang,
    set_request_language,
    t,
)
from app.models import UIString
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
