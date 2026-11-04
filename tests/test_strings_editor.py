# tests/test_strings_editor.py — urejevalnik besedil (ui_strings) v /navodila
from tests.conftest import login


def test_navodila_stran_ima_urejevalnik_besedil(client, make_user):
    a = make_user(role="main_admin")
    login(client, a.username)
    r = client.get("/navodila")
    assert r.status_code == 200
    assert "Urejevalnik besedil" in r.text
    assert "/api/strings" in r.text
    assert "pagePreviewFrame" in r.text  # predogled v HTML editorju


def test_strings_list_in_save(client, make_user):
    a = make_user(role="main_admin")
    login(client, a.username)
    r = client.get("/api/strings")
    assert r.status_code == 200
    data = r.json()
    assert data["strings"]
    assert "pages" in data

    target = data["strings"][0]
    new_sl = (target["sl"] + "_X") if target["sl"] else "TestX"
    rr = client.post(f"/api/strings/{target['key']}", json={"sl": new_sl})
    assert rr.status_code == 200, rr.text
    assert rr.json()["sl"] == new_sl

    # neznan ključ -> 404
    assert client.post("/api/strings/ne_obstaja_xyz", json={"sl": "x"}).status_code == 404


def test_strings_page_filter(client, make_user):
    a = make_user(role="main_admin")
    login(client, a.username)
    d = client.get("/api/strings?page=login.html").json()
    names = [s["key"] for s in d["strings"]]
    assert names, "bi morali najti napise za login.html"
    for s in d["strings"]:
        assert "login.html" in s["pages"], f"{s['key']} naj bi bil na login.html"


def test_strings_ne_mainadmin_403(client, make_user):
    u = make_user(role="admin")
    login(client, u.username)
    assert client.get("/api/strings").status_code == 403