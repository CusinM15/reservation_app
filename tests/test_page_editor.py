# tests/test_page_editor.py — univerzalni editor predlog (strani appa)
#
# Preveri, da override HTML predloge (AppSetting TEMPLATE_OVERRIDE:<ime>)
# dejansko pride skozi jinja loader na prikaz strani, in da brez override-a
# stran ostane vgrajena. Dvakrat zapored izriše stran, da ujame regresijo
# 'bool object is not callable' (tretji element get_source mora biti CALLABLE).

def test_login_brez_override_ostane_vgrajena(client):
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert "Prijavna stran" in r.text


def test_override_login_spreminja_prikaz(client):
    from app.database import SessionLocal
    from app.models import AppSetting
    from app import template_override as tov
    db = SessionLocal()
    try:
        db.add(AppSetting(key="TEMPLATE_OVERRIDE:login.html",
                          value="<html><body>PAGE_OVERRIDE_MARKER_ABC</body></html>"))
        db.commit()
    finally:
        db.close()
    tov.invalidate("login.html")   # preseže 30 s predpomnilnik v procesu
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert "PAGE_OVERRIDE_MARKER_ABC" in r.text
    # DRUGI render — ob ponovnem prikazu mora override še vedno delovati
    # (regresija: tretji element loaderja je moral biti callable, ne bool).
    r2 = client.get("/auth/login")
    assert r2.status_code == 200, f"drugi render padel: {r2.status_code}"
    assert "PAGE_OVERRIDE_MARKER_ABC" in r2.text


def test_reset_override_vrne_vgrajeno(client):
    from app.database import SessionLocal
    from app.models import AppSetting
    from app import template_override as tov
    db = SessionLocal()
    try:
        db.query(AppSetting).filter(AppSetting.key == "TEMPLATE_OVERRIDE:login.html").delete()
        db.commit()
    finally:
        db.close()
    tov.invalidate("login.html")
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert "Prijavna stran" in r.text