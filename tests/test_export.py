# ─────────────────────────────────────────────────────────────────────────
# tests/test_export.py — CSV izvoz rezervacij in ocenjevanj (admin/vodstvo)
# ─────────────────────────────────────────────────────────────────────────

from datetime import date, timedelta

from tests.conftest import login

FUTURE = (date.today() + timedelta(days=7)).isoformat()
H = {"Content-Type": "application/json"}


def _setup_data(client, make_user):
    """Učitelj naredi rezervacijo + ocenjevanje, da imamo kaj izvoziti."""
    teacher = make_user()
    login(client, teacher.username)
    client.post("/api/rezervacije", json={"date": FUTURE, "hour": 0, "prostor": "tablice", "razred": "5.a", "qty": 12, "teacher_id": 999})
    client.post("/api/rezervacije", json={"date": FUTURE, "hour": 1, "prostor": "racunalnica", "razred": "5.a", "teacher_id": 999})
    client.post("/api/ocenjevanja", json={"date": FUTURE, "razred": "5.a", "ponavljanje": False, "teacher_id": 999})
    client.post("/auth/logout")
    return teacher


def test_export_rezervacije_csv(client, make_user):
    _setup_data(client, make_user)
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.get(f"/api/export/rezervacije?date_from={FUTURE}&date_to={FUTURE}")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "Content-Disposition" in r.headers
    body = r.text
    assert "Datum" in body and "Ura" in body and "Prostor" in body
    assert "tablice" in body and "12" in body  # rezervacija je v izvozu
    assert "racunalnica" in body


def test_export_rezervacije_prostor_filter(client, make_user):
    _setup_data(client, make_user)
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.get(f"/api/export/rezervacije?date_from={FUTURE}&date_to={FUTURE}&prostor=racunalnica")
    assert r.status_code == 200
    assert "tablice" not in r.text
    assert "racunalnica" in r.text


def test_export_ocenjevanja_csv(client, make_user):
    _setup_data(client, make_user)
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.get(f"/api/export/ocenjevanja?date_from={FUTURE}&date_to={FUTURE}")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "5.a" in r.text and "Tip" in r.text


def test_export_teacher_forbidden(client, make_user):
    teacher = make_user()
    login(client, teacher.username)
    r = client.get(f"/api/export/rezervacije?date_from={FUTURE}&date_to={FUTURE}")
    assert r.status_code == 403


def test_export_vodstvo_allowed(client, make_user):
    _setup_data(client, make_user)
    vodstvo = make_user(role="vodstvo")
    login(client, vodstvo.username)
    r = client.get(f"/api/export/rezervacije?date_from={FUTURE}&date_to={FUTURE}")
    assert r.status_code == 200


def test_export_invalid_date(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.get("/api/export/rezervacije?date_from=abc&date_to=2026-08-19")
    assert r.status_code == 400


def test_export_date_range_invalid(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.get(f"/api/export/rezervacije?date_from={FUTURE}&date_to=2020-01-01")
    assert r.status_code == 400
