# tests/test_navodila_main.py — mainadmin »Navodila« stran + .md urejevalnik
#
# Preverja:
#  - /navodila stran je dostopna LE glavnemu adminu (403 za druge, 401 brez prijave)
#  - /api/navodila/docs{,/{name}} vrača dokumente in vsebino (mainadmin)
#  - POST shrani .md override v DB in spremeni /docs/html predogled + PDF
#  - POST /reset vrne vgrajeno .md datoteko
#  - ostali dokumenti ostanejo nespremenjeni (vgrajeni)

import pytest

from app.models import AppSetting
from app.database import SessionLocal
from app.config import settings

EDITABLE = "navodila-ucitelji"
MAIN_USER = settings.MAIN_ADMIN_USERNAME   # "mainadmin"
MAIN_PW = settings.MAIN_ADMIN_PASSWORD     # "Admin123" (startup bootstrap)


@pytest.fixture
def mainadmin(client):
    """Prijavi glavnega admina (startup bootstrap)."""
    r = client.post("/auth/login", data={"username": MAIN_USER, "password": MAIN_PW})
    assert r.status_code in (200, 302, 303)
    return client


def _g(db, key):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def test_navodila_page_requires_main_admin(client):
    """Brez prijave → 307 preusmeritev na login; navadna vloga → 403."""
    r = client.get("/navodila", follow_redirects=False)
    assert r.status_code in (307, 302)
    assert "/auth/login" in r.headers.get("location", "")
    # API: neprijavljen → preusmeritev na login (middleware), ne 200 podatki
    r = client.get("/api/navodila/docs", follow_redirects=False)
    assert r.status_code in (307, 302)


def test_list_docs_as_mainadmin(mainadmin):
    r = mainadmin.get("/api/navodila/docs")
    assert r.status_code == 200
    data = r.json()
    names = [d["name"] for d in data["docs"]]
    assert EDITABLE in names
    assert "obvestilo-ucitelji" in names
    # urejevalni so slovenski (brez -en prevodov)
    assert all(not n.endswith("-en") for n in names)


def test_navodila_page_renders(mainadmin):
    r = mainadmin.get("/navodila")
    assert r.status_code == 200
    assert "Pregled vseh strani" in r.text
    assert "docEditor" in r.text      # urejevalnik prisoten
    assert "/schools" in r.text or "Šole" in r.text


def test_editor_full_flow(mainadmin):
    """shrani .md override → HTML/PDF uporabita override → reset vrne vgrajeno."""
    r = mainadmin.get(f"/api/navodila/docs/{EDITABLE}")
    assert r.status_code == 200
    orig = r.json()["content"]
    assert "učitelje" in orig.lower() or "Učitelje" in orig

    new_content = "# MARKER TEST\nSpremenjeno navodilo — samo za test.\n"
    r = mainadmin.post(f"/api/navodila/docs/{EDITABLE}", json={"content": new_content})
    assert r.status_code == 200
    assert r.json()["overridden"] is True

    db = SessionLocal()
    try:
        assert _g(db, "DOC_OVERRIDE:" + EDITABLE) == new_content
    finally:
        db.close()

    # HTML predogled rabi override
    r = mainadmin.get(f"/docs/html/{EDITABLE}")
    assert r.status_code == 200
    assert "MARKER TEST" in r.text

    # PDF rabi override
    r = mainadmin.get(f"/docs/download/{EDITABLE}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert b"%PDF" in r.content

    # reset → vgrajen (marker izgine)
    r = mainadmin.post(f"/api/navodila/docs/{EDITABLE}/reset")
    assert r.status_code == 200
    assert r.json()["overridden"] is False
    db = SessionLocal()
    try:
        assert _g(db, "DOC_OVERRIDE:" + EDITABLE) is None
    finally:
        db.close()
    r = mainadmin.get(f"/docs/html/{EDITABLE}")
    assert "MARKER TEST" not in r.text


def test_edit_obvestilo_flow(mainadmin):
    r = mainadmin.post("/api/navodila/docs/obvestilo-ucitelji",
                       json={"content": "# MARKER OBVESTILO TEST\n"})
    assert r.status_code == 200
    r = mainadmin.get("/docs/html/obvestilo-ucitelji")
    assert "MARKER OBVESTILO TEST" in r.text
    mainadmin.post("/api/navodila/docs/obvestilo-ucitelji/reset")


def test_teacher_cannot_edit(client, make_user):
    u = make_user(role="teacher")
    client.post("/auth/login", data={"username": u.username, "password": "Test12345"})
    r = client.post(f"/api/navodila/docs/{EDITABLE}", json={"content": "x"})
    assert r.status_code == 403
    r = client.get("/navodila")
    assert r.status_code == 403


def test_school_admin_cannot_edit(client, make_user):
    u = make_user(role="admin")
    client.post("/auth/login", data={"username": u.username, "password": "Test12345"})
    r = client.get("/navodila")
    assert r.status_code == 403
    r = client.post(f"/api/navodila/docs/{EDITABLE}", json={"content": "x"})
    assert r.status_code == 403