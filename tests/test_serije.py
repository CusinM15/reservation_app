"""Testi za serijske rezervacije: tedenske, celodnevne, konflikti, kapaciteta."""
import pytest
from conftest import create_user, login, make_client, get_user_id

MON = "2026-09-07"  # ponedeljek
WED = "2026-09-09"  # sreda


def make_teacher(app_ready):
    """Ustvari učitelja in vrne (client prijavljen kot učitelj, user_id)."""
    c = make_client()
    uname = create_user(c)   # notranja admin prijava + ustvarjanje
    c.get("/auth/logout")    # odjava admina
    login(c, uname)          # prijava kot učitelj
    return c, get_user_id(uname)


# ═══ TEDENSKE SERIJE ═══
def test_weekly_series_created(admin_client):
    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "tablice", "hour": 0, "weekday": 0,
        "date_from": MON, "date_to": "2026-09-21", "qty": 28})
    assert r.status_code == 201
    data = r.json()
    assert data["created"] == 3  # 7.9, 14.9, 21.9
    assert data["removed"] == 0


def test_weekly_series_tablice_conflict_deletes_old(app_ready, admin_client):
    """KLJUČNI TEST: serija mora izbrisati konfliktno tablice rezervacijo (db.delete fix)."""
    c, uid = make_teacher(app_ready)
    # Učitelj rezervira 10 tablic za ponedeljek 1. uro
    assert c.post("/api/rezervacije", json={
        "date": MON, "hour": 0, "prostor": "tablice", "teacher_id": uid, "qty": 10}).status_code == 201

    # Admin ustvari tedensko serijo qty=28 za iste ponedeljke
    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "tablice", "hour": 0, "weekday": 0,
        "date_from": MON, "date_to": "2026-09-21", "qty": 28})
    assert r.status_code == 201
    assert r.json()["removed"] == 1  # učiteljeva rezervacija izbrisana

    # Kapaciteta na slotu = točno 28 (stara NE sme ostati!)
    rez = admin_client.get(f"/api/rezervacije?date={MON}&prostor=tablice").json()
    assert len(rez) == 1
    assert rez[0]["qty"] == 28
    assert sum(x["qty"] or 0 for x in rez) <= 28


def test_weekly_series_exclusive_conflict_deletes(app_ready, admin_client):
    c, uid = make_teacher(app_ready)
    assert c.post("/api/rezervacije", json={
        "date": MON, "hour": 1, "prostor": "racunalnica", "teacher_id": uid}).status_code == 201

    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "racunalnica", "hour": 1, "weekday": 0,
        "date_from": MON, "date_to": "2026-09-21"})
    assert r.status_code == 201
    assert r.json()["removed"] == 1
    rez = admin_client.get(f"/api/rezervacije?date={MON}&prostor=racunalnica").json()
    assert len(rez) == 1  # samo serijska ostane


def test_weekly_series_tablice_within_capacity_keeps_old(app_ready, admin_client):
    """Če kapaciteta dopušča (5+20=25<=28), se obstoječa rezervacija OHRANI."""
    c, uid = make_teacher(app_ready)
    assert c.post("/api/rezervacije", json={
        "date": WED, "hour": 6, "prostor": "tablice", "teacher_id": uid, "qty": 5}).status_code == 201

    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "tablice", "hour": 6, "weekday": 2,
        "date_from": WED, "date_to": "2026-09-23", "qty": 20})
    assert r.status_code == 201
    assert r.json()["removed"] == 0
    rez = admin_client.get(f"/api/rezervacije?date={WED}&prostor=tablice").json()
    assert sum(x["qty"] or 0 for x in rez) == 25


def test_weekly_series_qty_over_max_rejected(admin_client):
    """Serija ne sme rezervirati več tablic, kot jih je (fix kapacitete)."""
    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "tablice", "hour": 0, "weekday": 0,
        "date_from": MON, "date_to": "2026-09-21", "qty": 100})
    assert r.status_code == 400


def test_weekly_series_tablice_without_qty_rejected(admin_client):
    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "tablice", "hour": 0, "weekday": 0,
        "date_from": MON, "date_to": "2026-09-21"})
    assert r.status_code == 400


def test_weekly_series_invalid_dates(admin_client):
    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "ladja", "hour": 0, "weekday": 0,
        "date_from": "2026-09-30", "date_to": "2026-09-01"})
    assert r.status_code == 400


def test_weekly_series_invalid_weekday(admin_client):
    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "ladja", "hour": 0, "weekday": 7,
        "date_from": MON, "date_to": "2026-09-21"})
    assert r.status_code == 422


def test_weekly_series_no_matching_day(admin_client):
    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "ladja", "hour": 0, "weekday": 6,  # nedelja
        "date_from": MON, "date_to": "2026-09-11"})   # pon–pet, brez nedelje
    assert r.status_code == 400


# ═══ CELODNEVNE SERIJE ═══
def test_full_day_series_created(admin_client):
    r = admin_client.post("/api/rezervacije/series/full-day", json={
        "prostor": "gospodinjska-ucilnica", "date_from": MON, "date_to": MON})
    assert r.status_code == 201
    assert r.json()["created"] == 8  # vse ure 0–7


def test_full_day_limited_hours(admin_client):
    r = admin_client.post("/api/rezervacije/series/full-day", json={
        "prostor": "gospodinjska-ucilnica", "date_from": MON, "date_to": MON,
        "hours": [0, 1, 2]})
    assert r.status_code == 201
    assert r.json()["created"] == 3


def test_full_day_weekend_rejected(admin_client):
    r = admin_client.post("/api/rezervacije/series/full-day", json={
        "prostor": "ladja", "date_from": "2026-09-12", "date_to": "2026-09-13"})  # sob+ned
    assert r.status_code == 400


def test_full_day_invalid_hour(admin_client):
    r = admin_client.post("/api/rezervacije/series/full-day", json={
        "prostor": "ladja", "date_from": MON, "date_to": MON, "hours": [9]})
    assert r.status_code == 400


# ═══ PRAVICE ═══
def test_teacher_cannot_create_series(app_ready):
    c, uid = make_teacher(app_ready)
    r = c.post("/api/rezervacije/series/weekly", json={
        "prostor": "tablice", "hour": 0, "weekday": 0,
        "date_from": MON, "date_to": "2026-09-21", "qty": 10})
    assert r.status_code == 403


def test_unauthenticated_series_redirected(app_ready):
    c = make_client()
    r = c.post("/api/rezervacije/series/weekly", json={
        "prostor": "ladja", "hour": 0, "weekday": 0,
        "date_from": MON, "date_to": "2026-09-21"}, follow_redirects=False)
    assert r.status_code == 307


# ═══ SEZNAM IN BRISANJE SERIJ ═══
def test_series_list_and_delete(admin_client):
    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "tablice", "hour": 0, "weekday": 0,
        "date_from": MON, "date_to": "2026-09-21", "qty": 28})
    series_id = r.json()["series_id"]

    lst = admin_client.get("/api/rezervacije/series")
    assert lst.status_code == 200
    assert any(s["series_id"] == series_id for s in lst.json())

    d = admin_client.delete(f"/api/rezervacije/series/{series_id}")
    assert d.status_code == 200
    assert d.json()["deleted"] == 3


def test_series_delete_forbidden_for_teacher(app_ready, admin_client):
    r = admin_client.post("/api/rezervacije/series/weekly", json={
        "prostor": "tablice", "hour": 0, "weekday": 0,
        "date_from": MON, "date_to": "2026-09-21", "qty": 28})
    series_id = r.json()["series_id"]

    c, uid = make_teacher(app_ready)
    resp = c.delete(f"/api/rezervacije/series/{series_id}")
    assert resp.status_code == 403
