# tests/test_page_text_editor.py — urejanje strani brez kode (BLOKI besedila)
from tests.conftest import login

TPL = """<!DOCTYPE html>
<html>
<head><title>Nova šola</title></head>
<body>
<h1>Naslov poglavja</h1>
<p class="uvod"><span class="brand">Šolski app</span> — zelo dolg odstavek, ki ga
grem lahko urejati v celoti, brez kode, takoj v produkciji.</p>
<ul>
<li><strong>Prvi</strong> element seznama</li>
<li>{{ t('reg_gumb', 'Ustvari šolo') }}</li>
</ul>
<p>{{ t('reg_intro', 'Večjezični uvod') }} in <b>posebno</b> besedilo.</p>
</body>
</html>
"""


def _api_items(client):
    r = client.get("/api/pages/registracija.html/text")
    assert r.status_code == 200, r.text[:200]
    return r.json().get("items", [])


def test_bloki_zdruzijo_ves_odstavek_in_jinja_je_locen(client, make_user):
    from app.routers.docs import _extract_passages
    a = make_user(role="main_admin")
    login(client, a.username)
    passages, codes = _extract_passages(TPL)
    # odstavki/naslovi/postavke so CELOTE (ne drobni čipi)
    editable = [p for p in passages if not p["jinja"]]
    jinja = [p for p in passages if p["jinja"]]
    # dolg odstavek je ENA enota
    p_uvod = next(p for p in editable if "zelo dolg odstavek" in p["text"])
    assert "urejati v celoti" in p_uvod["text"]  # ves odstavek notri
    assert "<span class=\"brand\">" in p_uvod["text"]  # inline oznaka ohranjena
    # Jinja postavka je ločena (večjezična) in neurejevalna
    j = next(p for p in jinja if "Ustvari šolo" in p["text"])
    assert j["jinja"] is True
    # mešan p (jinja + b) je prav tako 'jinja'
    assert any(("reg_intro" in p["text"]) for p in jinja)
    assert editable and jinja


def test_rebuild_pusti_nespremenjene_in_sanitizira_spremenjene(client, make_user):
    from app.routers.docs import _extract_passages, _rebuild_passages
    make_user(role="main_admin")
    passages, codes = _extract_passages(TPL)
    p_uvod = next(p for p in passages if not p["jinja"] and "Šolski app" in p["text"])
    idx = passages.index(p_uvod)

    # 1) nespremenjen blok -> POVSEM enak (span class se ohrani)
    r1 = _rebuild_passages(TPL, passages, {str(idx): p_uvod["text"]})
    assert r1 == TPL

    # 2) spremenjen tekst -> sanitiziran, span dovoljen? (span je brez attrs) -> class izpade, besedilo spremenjeno
    new = "<script>x</script>Novo <b>krepko</b> besedilo odstavka"
    r2 = _rebuild_passages(TPL, passages, {str(idx): new})
    assert "<script>x</script>" not in r2
    assert "<b>krepko</b>" in r2
    assert "Novo <b>krepko</b> besedilo odstavka" in r2
    # Jinja postavke so osvojene
    assert "{{ t('reg_gumb', 'Ustvari šolo') }}" in r2


def test_post_api_shrani_override(client, make_user):
    # override registracija.html v TEST bazi — zamenja jo naša predloga
    from app.routers.docs import _extract_passages
    a = make_user(role="main_admin")
    login(client, a.username)
    items = _api_items(client)
    # poišči prvi urejevalni (ne-jinja) blok
    ed = next(i for i in items if not i["jinja"])
    newv = ed["text"] + " (TESTDOD)"
    r = client.post("/api/pages/registracija.html/text", json={"fragments": {str(ed["id"]): newv}})
    assert r.status_code == 200, r.text
    from app.database import SessionLocal
    from app.models import AppSetting
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == "TEMPLATE_OVERRIDE:registracija.html").first()
        ov = row.value if row else None
    finally:
        db.close()
    assert ov and "TESTDOD" in ov, "override naj vsebuje novo besedilo"


def test_fragmenti_403_za_neadmin(client, make_user):
    u = make_user(role="admin")
    login(client, u.username)
    assert client.get("/api/pages/registracija.html/text").status_code == 403