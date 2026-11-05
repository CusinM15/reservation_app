# Pred plačilom (prodaja vklopljena, naročnina neaktivna) imata dostop
# šolski admin in vodstvo (brezplačen preizkus); učitelji šele po plačilu.
from tests.conftest import login


def _omogoci_prodajo():
    from app.app_settings import KEY_SELLING, invalidate_cache, set_app_setting
    from app.database import SessionLocal
    invalidate_cache()
    db = SessionLocal()
    try:
        set_app_setting(db, KEY_SELLING, "1")
        db.commit()
    finally:
        db.close()
    invalidate_cache()


def test_admin_in_vodstvo_lahko_pred_placilom(client, make_user):
    """Oba se lahko prijavita (login route) in uporabljata app (middleware)."""
    _omogoci_prodajo()
    admin = make_user(role="admin")
    vodstvo = make_user(role="vodstvo")
    login(client, admin.username)
    assert client.get("/auth/me").json().get("id") == admin.id
    login(client, vodstvo.username)
    assert client.get("/auth/me").json().get("id") == vodstvo.id


def test_ucitelj_je_pred_placilom_blokiran(client, make_user):
    """Učitelj se pred plačilom NE more prijaviti; če je že prijavljen, ga
    middleware preusmeri na /narocnina (stran pa zavrne API z 403)."""
    teacher = make_user(role="teacher")
    login(client, teacher.username)          # prodaja še izklopljena → vstopi
    assert client.get("/auth/me").json().get("id") == teacher.id

    _omogoci_prodajo()                      # vklop prodaje brez naročnine

    r = client.get("/rezervacije", follow_redirects=False)
    assert r.status_code == 303, (r.status_code, r.headers.get("location"))
    assert "/narocnina" in r.headers.get("location", "")
    r2 = client.get("/api/schools/current", follow_redirects=False)
    assert r2.status_code == 403, (r2.status_code, r2.text[:120])