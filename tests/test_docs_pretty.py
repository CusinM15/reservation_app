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


def test_pogoji_uporabe_seznami_so_seznami():
    """Seznami v pogoji-uporabe se renderirajo kot <ul>, ne kot '- ' v odstavku."""
    import re
    import markdown
    from app.routers.docs import _read_docs
    content, _ = _read_docs("pogoji-uporabe", None)
    html = markdown.markdown(content)
    for m in re.finditer(r"<p>(.*?)</p>", html, re.S):
        body = m.group(1)
        assert not any(l.strip().startswith("-") for l in body.split("\n")), \
            f"seznam ostal v odstavku: {body[:120]}"
    assert html.count("<ul>") >= 10
