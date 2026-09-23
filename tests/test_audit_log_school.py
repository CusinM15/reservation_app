# ─────────────────────────────────────────────────────────────────────────
# tests/test_audit_log_school.py — dnevnik sprememb: stolpec »Šola« + filter
#
# Zahteva: glavni admin ima v dnevniku sprememb stolpec »Šola« za vsako vrstico
# in spustni seznam, da prikaže samo določeno šolo ali pa vse.
# Šolski admin vidi IZKLJUČNO svojo šolo (parameter school_id se ignorira).
# ─────────────────────────────────────────────────────────────────────────

from app.audit import log_audit
from app.config import settings
from app.database import SessionLocal
from app.tenancy import create_school
from tests.conftest import default_school_id, login


def _three_entries():
    """Dve šoli + po en dnevniški vnos na šolo + en globalni (brez šole)."""
    sid_a = default_school_id()
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Šola B", slug="solab")
        sid_b = school_b.id
        log_audit(db, None, "admin_a", "action_alpha", "vnos A", school_id=sid_a)
        log_audit(db, None, "admin_b", "action_beta", "vnos B", school_id=sid_b)
        log_audit(db, None, "sistem", "action_global", "globalni vnos", school_id=None)
        return sid_a, sid_b
    finally:
        db.close()


# ── 1. Glavni admin: stolpec »Šola« + seznam šol ──────────────────────

def test_main_admin_rows_have_school_column(client, make_user):
    sid_a, sid_b = _three_entries()
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)

    data = client.get("/api/audit-log").json()
    assert data["is_main_admin"] is True
    # seznam šol za spustni seznam
    ids = {s["id"] for s in data["schools"]}
    assert {sid_a, sid_b} <= ids
    # vsaka vrstica ima polji school_id in school (ime šole)
    assert all("school_id" in r and "school" in r for r in data["rows"])
    names = {r["school"] for r in data["rows"] if r["school"]}
    assert "Šola B" in names


def test_main_admin_can_filter_one_school(client, make_user):
    _sid_a, sid_b = _three_entries()
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)

    data = client.get(f"/api/audit-log?school_id={sid_b}").json()
    assert data["rows"], "filter mora vrniti vrstice šole B"
    assert {r["school_id"] for r in data["rows"]} == {sid_b}
    assert all(r["school"] == "Šola B" for r in data["rows"])
    assert data["filter_school_id"] == sid_b

    # brez filtra so v vrsticah tudi druge šole
    all_data = client.get("/api/audit-log").json()
    assert len({r["school_id"] for r in all_data["rows"]}) > 1


# ── 2. Šolski admin: samo svoja šola ──────────────────────────────────

def test_school_admin_sees_only_own_school(client, make_user):
    sid_a, sid_b = _three_entries()
    admin = make_user(role="admin")        # šolski admin šole A
    login(client, admin.username)

    data = client.get("/api/audit-log").json()
    assert data["is_main_admin"] is False
    assert data["schools"] == []           # spustni seznam je samo za glavnega admina
    assert all(r["school_id"] == sid_a for r in data["rows"])

    # poskus ogleda tuje šole ne spremeni obsega (varnostna meja)
    forced = client.get(f"/api/audit-log?school_id={sid_b}").json()
    assert all(r["school_id"] == sid_a for r in forced["rows"])


# ── 3. Stran /history ─────────────────────────────────────────────────

def test_history_page_has_school_dropdown_for_main_admin(client, make_user):
    _three_entries()
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    html = client.get("/history").text
    assert 'id="schoolFilter"' in html
    assert "— vse šole —" in html
    assert "Šola B" in html
    assert "setSchoolFilter(" in html


def test_history_page_has_no_dropdown_for_school_admin(client, make_user):
    _three_entries()
    admin = make_user(role="admin")
    login(client, admin.username)
    html = client.get("/history").text
    assert 'id="schoolFilter"' not in html
    # stolpec »Šola« v tabeli je vseeno prisoten (JS ga izriše vedno)
    assert "<th>Šola</th>" in html
