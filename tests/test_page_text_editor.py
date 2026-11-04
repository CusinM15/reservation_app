# tests/test_page_text_editor.py — urejanje strani brez kode (BLOKI besedila)
# VSE vidno besedilo je urejevalno (tudi t('...') → pri shranitvi postane navadno).
# Le '{% ... %}'-dinamično (nastavitve, npr. cena iz global-settings) ni za urejati.
from tests.conftest import login

TPL = """<!DOCTYPE html>
<html>
<head><title>Nova šola — Šolski app</title></head>
<body>
<h1>Naslov poglavja</h1>
<p class="uvod"><span class="brand">Šolski app</span> — zelo dolg odstavek, ki ga
grem lahko urejati v celoti na /navodila, brez kode, takoj v produkciji.</p>
<ul>
<li><strong>Prvi</strong> element seznama</li>
<li>{{ t('reg_gumb', 'Ustvari šolo') }}</li>
</ul>
<p>{{ t('reg_intro', 'Večjezični uvod') }} in <b>posebno</b> besedilo.</p>
<p>Cena: <strong>{% if cena %}1,00 € / leto{% endif %}</strong></p>
</body>
</html>
"""


def test_vse_besedilo_je_urejevalno_edin_dinamicno(client, make_user):
    from app.routers.docs import _extract_passages
    a = make_user(role="main_admin")
    login(client, a.username)
    passages, _ = _extract_passages(TPL)

    editable = [p for p in passages if not p["dynamic"]]
    dynamics = [p for p in passages if p["dynamic"]]

    # dolg odstavek je ENA čista enota (brez <span>, cel tekst)
    p_uvod = next(p for p in editable if "zelo dolg odstavek" in p["text"])
    assert "urejati v celoti" in p_uvod["text"]
    assert "Šolski app" in p_uvod["text"]
    assert "<span" not in p_uvod["text"]
    assert "<strong" not in p_uvod["text"]

    # t('...') postavka je prav tako UREJEVALNA (razrešena iz defaulta)
    gumb = next(p for p in editable if "Ustvari šolo" in p["text"])
    assert not gumb["dynamic"]
    assert gumb["text"] == "Ustvari šolo"

    # mešan t() + literal → urejevalno
    assert any("Večjezični uvod" in p["text"] and "posebno" in p["text"] for p in editable)

    # dinamično ({% %}, cena) → ločeno, ni za urejati
    assert any(p["dynamic"] for p in dynamics)
    assert any("1,00 € / leto" in p["text"] or "cena" in p["text"] for p in dynamics)

    assert editable and dynamics


def test_rebuild_pusti_nespremenjene_in_flat_spremenjene_t(client, make_user):
    from app.routers.docs import _extract_passages, _rebuild_passages
    make_user(role="main_admin")
    passages, _ = _extract_passages(TPL)
    p_uvod = next(p for p in passages if "zelo dolg odstavek" in p["text"])
    idx = passages.index(p_uvod)

    # nespremenjen blok → predloga identična (Jinja/t() ohranjeni)
    r1 = _rebuild_passages(TPL, passages, {str(idx): p_uvod["text"]})
    assert r1 == TPL

    # spremenjen → sanitizirano novo besedilo; dinamično ostane
    new = "<script>x</script>Novo <b>krepko</b> besedilo odstavka"
    r2 = _rebuild_passages(TPL, passages, {str(idx): new})
    assert "<script>x</script>" not in r2
    assert "Novo <b>krepko</b> besedilo odstavka" in r2
    assert "{% if cena %}" in r2  # dinamično (cena) nedotaknjeno
    assert "{{ t('reg_gumb', 'Ustvari šolo') }}" in r2  # neurejen t() ostane t()

    # urejanje t()-postavke → flat v navadno besedilo
    p_gumb = next(p for p in passages if "Ustvari šolo" in p["text"])
    ig = passages.index(p_gumb)
    r3 = _rebuild_passages(TPL, passages, {str(ig): "Registriraj šolo"})
    assert "{{ t('reg_gumb', 'Ustvari šolo') }}" not in r3
    assert "Registriraj šolo" in r3


def test_post_api_shrani_override(client, make_user):
    a = make_user(role="main_admin")
    login(client, a.username)
    items = client.get("/api/pages/registracija.html/text").json().get("items", [])
    ed = next(i for i in items if not i["dynamic"])
    newv = ed["text"] + " ·SPREMENJENO·"
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
    assert ov and "·SPREMENJENO·" in ov, "override naj vsebuje novo besedilo"


def test_403_za_neadmin(client, make_user):
    u = make_user(role="admin")
    login(client, u.username)
    assert client.get("/api/pages/registracija.html/text").status_code == 403