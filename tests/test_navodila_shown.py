from tests.conftest import login

SHOWN = ["navodila-ucitelji", "navodila-vodstvo", "navodila-admin",
         "obvestilo-ucitelji", "obvestilo-starsi"]
# razni notranji/dev/EN — na /navodila NE smejo biti (niti v editorju)
HIDDEN = ["navodila-ucitelji-en", "navodila-vodstvo-en", "navodila-admin-en",
          "pogoji-uporabe", "reklama-sola", "main", "main-en",
          "aplikacija-rezervacije", "aplikacija-rezervacije-en", "govorilne-ure",
          "admin-devops-navodila", "admin-devops-navodila-en",
          "postavi-lokalni-app", "postavi-lokalni-app-en"]


def test_navodila_stran_kaze_samo_production_docs(client, make_user):
    a = make_user(role="main_admin")
    login(client, a.username)
    r = client.get("/navodila")
    assert r.status_code == 200, r.text[:200]
    # editor dropdown (docSelect) + seznam dosegljivih uporabita all_preview
    for name in SHOWN:
        assert f"/docs/{name}" in r.text, f"manjka na /navodila: {name}"
    for name in HIDDEN:
        assert f"/docs/{name}" not in r.text, f"se še kaže na /navodila: {name}"


def test_api_navodila_docs_omejen_na_prikazane(client, make_user):
    """API /api/navodila/docs za glavnega admina vrne SAMO prikazane (SL, ne main/dev/EN)."""
    a = make_user(role="main_admin")
    login(client, a.username)
    r = client.get("/api/navodila/docs")
    assert r.status_code == 200
    names = {d["name"] for d in r.json().get("docs", [])}
    assert names == set(SHOWN), names
    # notranji/dev dokumenti niso urejevalni prek /navodila editorja
    for name in HIDDEN:
        assert name not in names, f"se še editura na /navodila: {name}"
    # POST na notranji dokument → zavrnjeno
    bad = client.post("/api/navodila/docs/main", json={"content": "# x"})
    assert bad.status_code in (400, 403, 404)
    # prikazani dokument je še vedno služiran (read-only v /docs)
    assert client.get("/docs/html/navodila-ucitelji").status_code == 200