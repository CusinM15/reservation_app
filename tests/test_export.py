"""Testi za CSV izvoz rezervacij in ocenjevanj."""
import pytest
from conftest import create_user, login, make_client, get_user_id

DATE = "2026-09-07"


def make_teacher(app_ready):
    c = make_client()
    uname = create_user(c)
    c.get("/auth/logout")
    login(c, uname)
    return c, get_user_id(uname)


@pytest.fixture()
def data_pripravljena(app_ready):
    """Učitelj naredi rezervacijo in ocenjevanje, da je kaj za izvoz."""
    c, uid = make_teacher(app_ready)
    assert c.post("/api/rezervacije", json={
        "date": DATE, "hour": 0, "prostor": "tablice", "teacher_id": uid, "qty": 10}).status_code == 201
    assert c.post("/api/rezervacije", json={
        "date": DATE, "hour": 2, "prostor": "racunalnica", "teacher_id": uid, "razred": "5.a"}).status_code == 201
    assert c.post("/api/ocenjevanja", json={
        "razred": "5.a", "date": DATE, "ponavljanje": False, "teacher_id": uid}).status_code == 201
    return c, uid


# ═══ IZVOZ REZERVACIJ ═══
def test_export_rezervacije_csv_admin(admin_client, data_pripravljena):
    r = admin_client.get("/api/rezervacije/export/csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    body = r.text
    assert "Datum" in body and "Prostor" in body
    assert "tablice" in body and "racunalnica" in body
    assert "5.a" in body


def test_export_rezervacije_csv_teacher_forbidden(app_ready, data_pripravljena):
    c, uid = data_pripravljena
    r = c.get("/api/rezervacije/export/csv")
    assert r.status_code == 403


def test_export_rezervacije_csv_filter_prostor(admin_client, data_pripravljena):
    r = admin_client.get("/api/rezervacije/export/csv?prostor=tablice")
    assert r.status_code == 200
    assert "tablice" in r.text
    assert "racunalnica" not in r.text


def test_export_rezervacije_csv_filter_dates(admin_client, data_pripravljena):
    r = admin_client.get("/api/rezervacije/export/csv?date_from=2026-09-01&date_to=2026-09-30")
    assert r.status_code == 200
    assert "tablice" in r.text
    r = admin_client.get("/api/rezervacije/export/csv?date_from=2026-10-01&date_to=2026-10-31")
    assert "tablice" not in r.text


# ═══ IZVOZ OCENJEVANJ ═══
def test_export_ocenjevanja_csv_admin(admin_client, data_pripravljena):
    r = admin_client.get("/api/ocenjevanja/export/csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "5.a" in r.text


def test_export_ocenjevanja_csv_teacher_forbidden(app_ready, data_pripravljena):
    c, uid = data_pripravljena
    r = c.get("/api/ocenjevanja/export/csv")
    assert r.status_code == 403


def test_export_ocenjevanja_csv_filter_razred(admin_client, data_pripravljena):
    r = admin_client.get("/api/ocenjevanja/export/csv?razred=5.a")
    assert r.status_code == 200
    assert "5.a" in r.text
    r = admin_client.get("/api/ocenjevanja/export/csv?razred=6.b")
    assert "5.a" not in r.text
