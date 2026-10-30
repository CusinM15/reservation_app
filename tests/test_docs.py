# tests/test_docs.py — dokumenti/navodila (docs router)
#
# Preverja, da so vsi dokumenti navodil dosegljivi v HTML (SL + EN) in da se
# admin navodila prevedejo tudi v PDF. Brez tega bi napačen ključ v ALLOWED
# pomenil 404 (npr. manjkajoč -en variant pokvari preklop jezika).

import pytest

DOCS = ["navodila-ucitelji", "navodila-vodstvo", "navodila-admin"]


@pytest.mark.parametrize("name", DOCS)
def test_doc_html_si(client, name):
    r = client.get(f"/docs/html/{name}")
    assert r.status_code == 200
    assert len(r.text) > 200


@pytest.mark.parametrize("name", DOCS)
def test_doc_html_en(client, name):
    r = client.get(f"/docs/html/{name}-en")
    assert r.status_code == 200
    assert len(r.text) > 200


def test_admin_doc_html_has_content(client):
    """Admin navodila vsebujejo ključne razdelke (nastavitve, uporabniki, kopije)."""
    r = client.get("/docs/html/navodila-admin")
    assert r.status_code == 200
    text = r.text
    assert "Nastavitve šole" in text
    assert "Uporabniki" in text
    assert "Varnostna kopija" in text


def test_admin_doc_pdf(client):
    r = client.get("/docs/download/navodila-admin")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_ucitelji_navodila_so_splosna(client):
    """Navodila za učitelje so SPLOŠNA — brez imena posamezne šole in brez njenih
    specifičnih prostorov, da so uporabna za vsako šolo."""
    r = client.get("/docs/html/navodila-ucitelji")
    assert r.status_code == 200
    for bad in ("Toneta", "Čufar", "Cufar", "tonecufar", "ostc-app", "Ladja"):
        assert bad not in r.text, f"v navodilih ostaja specifično: {bad}"


def test_ucitelji_en_navodila_so_splosna(client):
    r = client.get("/docs/html/navodila-ucitelji-en")
    assert r.status_code == 200
    for bad in ("Toneta", "Cufar", "tonecufar", "ostc-app", "Ship"):
        assert bad not in r.text, f"v navodilih ostaja specifično: {bad}"


def test_vodstvo_navodila_brez_admin_navodil(client):
    """Navodila za vodstvo ne smejo vsebovati (admin) skrbniške plošče —
    ta je prestavljena v ločena Navodila za administratorja."""
    for key in ("navodila-vodstvo", "navodila-vodstvo-en"):
        r = client.get(f"/docs/html/{key}")
        assert r.status_code == 200
        for bad in ("Skrbniška plošča", "Admin Panel", "create_rezervacija",
                    "Administrator Guide", "Upravljanje uporabnikov"):
            assert bad not in r.text, f"{key}: ostaja admin vsebina: {bad}"


def test_vodstvo_navodila_poudarjajo_dejavnosti(client):
    """Vodstvo naj dela predvsem prek strani /dejavnosti."""
    for key, needle in (("navodila-vodstvo", "/dejavnosti"),
                        ("navodila-vodstvo-en", "/dejavnosti")):
        r = client.get(f"/docs/html/{key}")
        assert r.status_code == 200
        assert needle in r.text
    assert "Vnos dejavnosti" in client.get("/docs/html/navodila-vodstvo").text

def test_obvestili_vsebujeta_link(client):
    """Vsako obvestilo vključuje link: učitelji → login stran, starši → /govorilne_<šola>."""
    r = client.get("/docs/html/obvestilo-ucitelji")
    assert r.status_code == 200
    assert "https://reservationapp.site/auth/login" in r.text
    assert "Prijava v aplikacijo" in r.text

    r = client.get("/docs/html/obvestilo-starsi")
    assert r.status_code == 200
    assert "/govorilne_ostcj" in r.text
    assert "Najava na govorilne" in r.text


def test_obvestila_imajo_cta_izgled(client):
    """Obvestila uporabljajo banner CSS (gradient h1 + CTA gumb za link)."""
    r = client.get("/docs/html/obvestilo-ucitelji")
    assert "linear-gradient(135deg, #0b3b5c" in r.text
    assert "blockquote a, blockquote a:visited" in r.text
    r = client.get("/docs/html/obvestilo-starsi")
    assert "linear-gradient(135deg, #0b3b5c" in r.text

def test_obvestilo_starsi_link_per_sola(client):
    """Obvestilo za starše uporabi kratico (slug) šole iz ?skola — ne trdo ostcj.

    Ustvarimo šolo z kratico 'zgled' in preverimo, da /docs/html/obvestilo-starsi
    z ?skola=zgled substituira URL na /govorilne_zgled, privzeto (brez parama)
    pa /govorilne_ostcj.
    """
    from app.database import SessionLocal
    from app.models import School
    db = SessionLocal()
    try:
        s = School(slug="zgled", name="OŠ Zgled", is_active=True)
        db.add(s); db.commit()
    finally:
        db.close()

    # privzeto (brez ?skola) → ostcj
    r = client.get("/docs/html/obvestilo-starsi")
    assert r.status_code == 200
    assert "govorilne_ostcj" in r.text
    assert "govorilne_zgled" not in r.text

    # ?skola=zgled → zgled
    r2 = client.get("/docs/html/obvestilo-starsi?skola=zgled")
    assert r2.status_code == 200
    assert "govorilne_zgled" in r2.text
    assert "govorilne_ostcj" not in r2.text
    # PDF prav tako upošteva šolo
    r3 = client.get("/docs/download/obvestilo-starsi?skola=zgled")
    assert r3.status_code == 200
    assert r3.headers["content-type"].startswith("application/pdf")
