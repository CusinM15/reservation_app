# Učitelj shrani svoj dopoldanski termin BREZ 'ime' (popravek: 400→200).
from tests.conftest import default_school_id


def _login(client, username):
    return client.post("/auth/login",
                       data={"username": username, "password": "Test12345"},
                       follow_redirects=False)


def test_teacher_shrani_dopoldan_brez_ime(client, make_user):
    from app.database import SessionLocal
    from app.routers.govorilne import _load_cfg
    from app.tenancy import set_school_setting

    sid = default_school_id()
    db = SessionLocal()
    try:
        set_school_setting(db, sid, "GOVORILNE_VLOGAROLE", "admin,teacher")
        db.commit()
    finally:
        db.close()

    u = make_user(role="teacher", ima_govorilne=True,
                  first_name="Marija", last_name="Novak")
    _login(client, u.username)

    r = client.post("/govorilne/api/ure/ucitelj", json={
        "predmet": "Matematika", "dan": "0", "ura": "2",
        "prostor": "Učilnica 8", "razred": "", "urnik": ""})
    assert r.status_code == 200, (r.status_code, r.text[:200])

    db = SessionLocal()
    try:
        cfg = _load_cfg(db, sid)
        me = next(x for x in cfg["ucitelji"] if "Marija Novak" in x.get("ime", ""))
        assert me["predmet"] == "Matematika"
        assert me["dan"] == 0 and me["ura"] == 2
    finally:
        db.close()


def test_editor_brez_ime_se_vedno_400(client, make_user):
    admin = make_user(role="admin")
    _login(client, admin.username)
    r = client.post("/govorilne/api/ure/ucitelj", json={"predmet": "x"})
    assert r.status_code == 400, (r.status_code, r.text[:120])
