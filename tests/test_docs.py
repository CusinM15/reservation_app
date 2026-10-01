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
