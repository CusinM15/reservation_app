# tests/test_urniki.py — koledarji (urniki) govorilnih ur v šolskih nastavitvah.
#
# Preverja, da lahko šolski admin nastavi lastne poimenovane urnike (URNIKI)
# in da jih govorilni modul dejansko uporabi (cfg["urniki"]), namesto vgrajenih.

from tests.conftest import login


def _admin(client, make_user):
    a = make_user(role="admin")
    login(client, a.username)
    return a


def test_urniki_privzeto_vgrajeni(client, make_user):
    from app.tenancy import _default_school_id
    from app.database import SessionLocal
    from app.routers.govorilne import _load_cfg
    db = SessionLocal()
    try:
        sid = _default_school_id(db)
        cfg = _load_cfg(db, sid)
        assert "6-9" in cfg["urniki"]
        assert cfg["urniki"]["6-9"].get("label")
    finally:
        db.close()


def test_urniki_per_sola_prek_nastavitev(client, make_user):
    from app.tenancy import _default_school_id
    from app.database import SessionLocal
    from app.models import SchoolSetting
    from app.routers.govorilne import _load_cfg
    db = SessionLocal()
    sid = None
    try:
        sid = _default_school_id(db)
        _admin(client, make_user)
        payload = {"URNIKI": {"novi": {
            "label": "Testni koledar",
            "zacetki": {"1": "08:00"},
        }}}
        r = client.put(f"/api/schools/{sid}/settings", json={"values": payload})
        assert r.status_code == 200, r.text[:300]
        cfg = _load_cfg(db, sid)
        assert cfg["urniki"]["novi"]["label"] == "Testni koledar"
        assert cfg["urniki"]["novi"]["zacetki"]["1"] == "08:00"
    finally:
        if sid is not None:
            db.query(SchoolSetting).filter(
                SchoolSetting.school_id == sid, SchoolSetting.key == "URNIKI").delete()
        db.commit()
        db.close()