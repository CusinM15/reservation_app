# /docs/<dokument> ne sme vračati JSON — mora biti lepa HTML stran (302 → /docs/html/).
def test_docs_bare_redirects_to_html(client):
    r = client.get("/docs/pogoji-uporabe", follow_redirects=False)
    assert r.status_code == 302, (r.status_code, r.text[:120])
    assert r.headers.get("location", "") == "/docs/html/pogoji-uporabe"


def test_docs_html_je_lepa_stran(client):
    r = client.get("/docs/html/pogoji-uporabe")
    assert r.status_code == 200, r.status_code
    assert "text/html" in r.headers.get("content-type", "")
    assert "Pogoji uporabe" in r.text
    assert "<html" in r.text.lower()