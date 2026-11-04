# tests/test_gov_termin_minut.py — polje »trajanje termina« v nastavitvah šole
# Šolski admin v Nastavitvah → Govorilne ure nastavi TERMIN_MINUT; shrani se v
# GOVORILNE_KONFIG.termin_minut in se pozna povsod (term_min / termini).
# Testi ne renderirajo HTML-ja (PAP: venv starlette render bug) — le PUT + logika.
from tests.conftest import default_school_id


def _login_admin(client, username):
    return client.post("/auth/login",
                       data={"username": username, "password": "Test12345"},
                       follow_redirects=False)


def test_termin_minut_se_shrani_v_govorilne_cfg(client, make_user):
    from app.database import SessionLocal
    from app.routers.govorilne import _load_cfg, _term_min

    admin = make_user(role="admin")
    _login_admin(client, admin.username)
    sid = default_school_id()

    r = client.put(f"/api/schools/{sid}/settings", json={"values": {"TERMIN_MINUT": "30"}})
    assert r.status_code == 200, r.text[:200]

    db = SessionLocal()
    try:
        c = _load_cfg(db, sid)
        assert c["termin_minut"] == 30, c["termin_minut"]
        assert _term_min(c) == 30
    finally:
        db.close()


def test_termin_minut_validacija(client, make_user):
    from app.database import SessionLocal
    from app.routers.govorilne import _load_cfg, _term_min

    admin = make_user(role="admin")
    _login_admin(client, admin.username)
    sid = default_school_id()

    for bad in ("4", "121", "abc"):
        r = client.put(f"/api/schools/{sid}/settings", json={"values": {"TERMIN_MINUT": bad}})
        assert r.status_code == 400, (bad, r.text[:120])

    db = SessionLocal()
    try:
        assert _term_min(_load_cfg(db, sid)) == 15
    finally:
        db.close()


def test_termin_minut_sprememba_spremeni_dopoldan_termini(client, make_user):
    """Sprememba trajanja termina se pozna v razporeditvi dopoldanskih terminov."""
    from app.database import SessionLocal
    from app.routers.govorilne import _dopoldan_termini, _load_cfg

    admin = make_user(role="admin")
    _login_admin(client, admin.username)
    sid = default_school_id()

    db = SessionLocal()
    try:
        cfg = _load_cfg(db, sid)
        u = next((x for x in cfg.get("ucitelji") or []
                  if x.get("dan") is not None and x.get("ura") is not None), None)
        if u is None:
            u = {"ime": "Test Ucitelj", "dan": 0, "ura": 1,
                 "po_dogovoru": False, "urnik": None}
        cfg["termin_minut"] = 45
        t45 = _dopoldan_termini(u, cfg)
        cfg["termin_minut"] = 15
        t15 = _dopoldan_termini(u, cfg)
        if t15 and t45:
            # 45-min šolska ura: 15 → 3 termini, 45 → 1 termin
            assert len(t15) == 3, len(t15)
            assert len(t45) == 1, len(t45)
    finally:
        db.close()