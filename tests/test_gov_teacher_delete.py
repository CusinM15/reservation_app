# Učitelj briše najave SAMO za svoje govorilne ure; vodstvo/admin vse.
from app.database import SessionLocal
from app.models import GovorilnaPrijava
from app.tenancy import set_school_setting
from tests.conftest import default_school_id

TEST_PW = "Test12345"


def _set_vloge(sid, vloge="admin,teacher"):
    db = SessionLocal()
    try:
        set_school_setting(db, sid, "GOVORILNE_VLOGAROLE", vloge)
        db.commit()
    finally:
        db.close()


def _login(client, username):
    return client.post("/auth/login",
                       data={"username": username, "password": TEST_PW},
                       follow_redirects=False)


def _load_cfg(sid):
    from app.routers.govorilne import _load_cfg
    db = SessionLocal()
    try:
        return _load_cfg(db, sid)
    finally:
        db.close()


def _termin_za(cfg, ime):
    from app.routers.govorilne import _prosti_termini
    db = SessionLocal()
    try:
        u = next(x for x in cfg["ucitelji"] if x.get("ime") == ime)
        return _prosti_termini(db, default_school_id(), u)[0]
    finally:
        db.close()


def _rezerviraj(client, ime, t, star="A Star", email="a@example.si"):
    return client.post("/govorilne/api/prijava", json={
        "ucitelj": ime, "datum": t["datum"], "ura_od": t["ura_od"],
        "ura_do": t["ura_do"], "ime_starsa": star, "email": email,
        "otrok": "Otrok A"})


def _last_prijava_id(sid, ime):
    db = SessionLocal()
    try:
        return db.query(GovorilnaPrijava).filter_by(
            school_id=sid, ucitelj=ime).order_by(GovorilnaPrijava.id.desc()).first().id
    finally:
        db.close()


def test_ucitelj_bris_svojo_najavo(client, make_user):
    sid = default_school_id()
    _set_vloge(sid)
    u = make_user(role="teacher", ima_govorilne=True,
                  first_name="Marija", last_name="Novak")
    _login(client, u.username)
    cfg = _load_cfg(sid)
    t = _termin_za(cfg, "Marija Novak")
    assert _rezerviraj(client, "Marija Novak", t).status_code == 200
    pid = _last_prijava_id(sid, "Marija Novak")
    r = client.post("/govorilne/api/prijava/odstrani", json={"id": pid})
    assert r.status_code == 200, (r.status_code, r.text[:150])


def test_ucitelj_ne_more_brisati_drugega(client, make_user):
    sid = default_school_id()
    _set_vloge(sid)
    uA = make_user(role="teacher", ima_govorilne=True,
                   first_name="Marija", last_name="Novak")
    make_user(role="teacher", ima_govorilne=True,
              first_name="Ivan", last_name="Zupan")
    _login(client, uA.username)
    cfg = _load_cfg(sid)
    tB = _termin_za(cfg, "Ivan Zupan")
    assert _rezerviraj(client, "Ivan Zupan", tB, star="B Star").status_code == 200
    pidB = _last_prijava_id(sid, "Ivan Zupan")
    r = client.post("/govorilne/api/prijava/odstrani", json={"id": pidB})
    assert r.status_code == 403, (r.status_code, r.text[:150])


def test_admin_bris_katerokoli(client, make_user):
    sid = default_school_id()
    _set_vloge(sid, "admin,teacher")
    make_user(role="teacher", ima_govorilne=True,
              first_name="Marija", last_name="Novak")
    admin = make_user(role="admin")
    _login(client, admin.username)
    cfg = _load_cfg(sid)
    t = _termin_za(cfg, "Marija Novak")
    assert _rezerviraj(client, "Marija Novak", t).status_code == 200
    pid = _last_prijava_id(sid, "Marija Novak")
    r = client.post("/govorilne/api/prijava/odstrani", json={"id": pid})
    assert r.status_code == 200, (r.status_code, r.text[:150])