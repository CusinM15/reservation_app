# tests/test_navodila_editor.py — diagnostika /navodila editorja (glavni admin)
from tests.conftest import login


def test_navodila_vsi_dokumenti_se_nalozijo(client, make_user):
    a = make_user(role="main_admin")
    r0 = login(client, a.username)
    assert r0.status_code == 200, r0.text[:200]

    r = client.get("/navodila")
    assert r.status_code == 200, f"GET /navodila -> {r.status_code}: {r.text[:400]}"

    docs = client.get("/api/navodila/docs").json().get("docs", [])
    assert docs, "seznam dokumentov je prazen"
    bad = []
    for d in docs:
        g = client.get(f"/api/navodila/docs/{d['name']}")
        if g.status_code != 200:
            bad.append((d["name"], g.status_code, g.text[:120]))
    assert not bad, f"dokumenti se ne naložijo: {bad}"

    pages = client.get("/api/pages/list").json().get("templates", [])
    assert pages, "seznam predlog je prazen"
    for p in pages[:3]:
        g = client.get(f"/api/pages/{p['name']}")
        assert g.status_code == 200, f"/api/pages/{p['name']} -> {g.status_code}: {g.text[:150]}"