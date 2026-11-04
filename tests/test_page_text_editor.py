# tests/test_page_text_editor.py — urejanje strani brez kode (besedilni fragmenti)
from tests.conftest import login


def _main(client, make_user):
    a = make_user(role="main_admin")
    login(client, a.username)
    return client


def test_fragmenti_vsebujejo_besedilo_in_ne_kode(client, make_user):
    _main(client, make_user)
    r = client.get("/api/pages/registracija.html/text")
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    items = j["items"]
    assert items, "stran naj ima besedilne fragmente"
    texts = [i for i in items if i["type"] == "text"]
    codes = [i for i in items if i["type"] == "code"]
    assert texts, "naj bodo fragmenti"
    assert codes, "naj bodo tudi kodni (Jinja) čipi"
    # vsaj ena beseda je prepoznavna
    all_text = " ".join(x["text"] for x in texts).lower()
    assert "šolski" in all_text or "aplikacija" in all_text or "prijava" in all_text


def test_post_uredi_besedilo_in_ohrani_kodo(client, make_user):
    from app.database import SessionLocal
    from app.models import AppSetting
    from app.routers.docs import _extract_text_fragments, _rebuild_fragments

    _main(client, make_user)
    # vzamemo VGRAJENO registracijo kot osnovo (ne dotikamo se override-a v produ)
    from app import template_override as tov
    content = tov.read_builtin("registracija.html")
    assert content
    frags, codes = _extract_text_fragments(content)
    assert frags and codes

    # uredi prvi fragment
    fid = 0
    new_text = "ŠOLSKI APP — povsem novo besedilo X1"
    rebuilt = _rebuild_fragments(content, frags, {str(fid): new_text})

    # koda (Jinja/oznake) je ohranjena
    assert rebuilt.count("{{") == content.count("{{")
    assert rebuilt.count("{%") == content.count("{%")
    assert rebuilt.count("<form") == content.count("<form")
    # novo besedilo je notri; originale se je odstranilo le na svojem mestu
    assert new_text in rebuilt
    assert rebuilt.count(frags[0]["text"]) == content.count(frags[0]["text"]) - 1

    # sanitizacija: odvržemo skripte in nedovoljene oznake
    dirty = _rebuild_fragments(content, frags, {str(fid): '<script>alert(1)</script>Beseda <b>krepko</b> <a href="https://x.si" onclick="pwn()">link</a>'})
    assert "<script>" not in dirty
    assert "onclick" not in dirty
    assert "<b>krepko</b>" in dirty
    assert 'href="https://x.si"' in dirty


def test_post_api_shrani_override(client, make_user):
    from app.database import SessionLocal
    from app.models import AppSetting
    from app.routers.docs import _extract_text_fragments

    _main(client, make_user)
    r0 = client.get("/api/pages/registracija.html/text")
    items = r0.json()["items"]
    texts = [i for i in items if i["type"] == "text"]
    assert texts
    t0 = texts[0]

    newv = t0["text"] + " (TEST)"
    r = client.post("/api/pages/registracija.html/text", json={"fragments": {str(t0["id"]): newv}})
    assert r.status_code == 200, r.text
    assert r.json()["overridden"] is True

    # override objektivno vsebuje novo besedilo
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == "TEMPLATE_OVERRIDE:registracija.html").first()
        ov = row.value if row else None
    finally:
        db.close()
    assert ov and newv in ov, "override naj vsebuje novo besedilo"


def test_fragmenti_403_za_neadmin(client, make_user):
    u = make_user(role="admin")
    login(client, u.username)
    assert client.get("/api/pages/registracija.html/text").status_code == 403