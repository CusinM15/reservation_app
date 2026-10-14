# ─────────────────────────────────────────────────────────────────────────
# tests/test_popoldan.py — popoldanski urnik za prostore
#
# Preverja:
#   - /api/popoldan vrne popoldanski urnik (privzeto 6 terminov 15:00–21:00)
#     in seznam prostorov, ki ga uporabljajo,
#   - ko je prostor označen kot popoldanski (PROSTORI_POPOLDAN), rezervacija
#     uporablja popoldanske ure (0..5), ura 6 pa je zanj neveljavna,
#   - običajni prostori še vedno uporabljajo šolski urnik (0..7+).
# ─────────────────────────────────────────────────────────────────────────

from datetime import date, timedelta

from tests.conftest import login, default_school_id

FUTURE = (date.today() + timedelta(days=7)).isoformat()
POP = ('{"0":"15:00-16:00","1":"16:00-17:00","2":"17:00-18:00",'
       '"3":"18:00-19:00","4":"19:00-20:00","5":"20:00-21:00"}')


def _put_settings(client, school_id, values):
    r = client.put(f"/api/schools/{school_id}/settings", json={"values": values})
    assert r.status_code == 200, r.text
    return r


def test_api_popoldan_default(client, make_user):
    u = make_user(role="teacher")
    login(client, u.username)
    r = client.get("/api/popoldan")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("schedule"), dict)
    assert len(data["schedule"]) == 6          # privzeto 15:00–21:00
    assert data["prostori"] == []              # privzeto ni popoldanskih prostorov


def test_popoldan_room_accepts_afternoon_hours(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = default_school_id()
    _put_settings(client, sid, {"PROSTORI_POPOLDAN": "ladja", "POPOLDAN_SCHEDULE": POP})

    r = client.get("/api/popoldan")
    assert r.json()["prostori"] == ["ladja"]

    # Popoldanska ura 5 (= 20:00–21:00) v popoldanskem prostoru je dovoljena.
    r = client.post("/api/rezervacije", json={
        "date": FUTURE, "hour": 5, "prostor": "ladja", "razred": "5.a", "teacher_id": 999})
    assert r.status_code == 201, r.text

    # Ura 6 je izven obsega popoldanskega urnika (0..5) → 400.
    r = client.post("/api/rezervacije", json={
        "date": FUTURE, "hour": 6, "prostor": "ladja", "razred": "5.a", "teacher_id": 999})
    assert r.status_code == 400, r.text

    # Isti ura 6 v običajnem prostoru je še vedno dovoljena (šolski urnik 0..7).
    r = client.post("/api/rezervacije", json={
        "date": FUTURE, "hour": 6, "prostor": "racunalnica", "razred": "5.a", "teacher_id": 999})
    assert r.status_code == 201, r.text


def test_popoldan_schedule_saved_via_settings(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = default_school_id()
    _put_settings(client, sid, {"PROSTORI_POPOLDAN": "ladja", "POPOLDAN_SCHEDULE": POP})

    r = client.get(f"/api/schools/{sid}/settings")
    assert r.status_code == 200
    vals = r.json()["values"]
    assert "ladja" in vals.get("PROSTORI_POPOLDAN", "")
    assert "15:00-16:00" in vals.get("POPOLDAN_SCHEDULE", "")
