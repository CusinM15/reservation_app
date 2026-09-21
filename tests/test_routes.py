"""Testi za organizacijo URL-jev strani.

Preverjajo novo shemo poti:
  /                        → preusmeri na /rezervacije
  /rezervacije             → glavna stran, aktiven zavihek Rezervacije
  /ocenjevanje             → glavna stran, aktiven zavihek Ocenjevanje
  /ocenjevanje/dejavnosti  → stran Vnos dejavnosti (vodstvo/admin)
  /dejavnosti              → preusmeri na /ocenjevanje/dejavnosti (stara pot)
"""

from tests.conftest import login

REDIRECT_CODES = (301, 302, 303, 307, 308)


def test_root_redirects_to_rezervacije(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in REDIRECT_CODES
    assert r.headers["location"] == "/rezervacije"


def test_rezervacije_page_sets_active_tab(client, make_user):
    u = make_user(role="teacher")
    login(client, u.username)
    r = client.get("/rezervacije")
    assert r.status_code == 200
    assert 'ACTIVE_TAB = "rezervacije"' in r.text


def test_ocenjevanje_page_sets_active_tab(client, make_user):
    u = make_user(role="teacher")
    login(client, u.username)
    r = client.get("/ocenjevanje")
    assert r.status_code == 200
    assert 'ACTIVE_TAB = "ocenjevanja"' in r.text


def test_nav_links_point_to_new_urls(client, make_user):
    u = make_user(role="teacher")
    login(client, u.username)
    html = client.get("/rezervacije").text
    assert 'href="/rezervacije"' in html
    assert 'href="/ocenjevanje"' in html
    assert "location.href='/ocenjevanje/dejavnosti'" in html


def test_dejavnosti_teacher_can_view(client, make_user):
    """Učitelj VIDE stran /ocenjevanje/dejavnosti (ne dobi več 403)."""
    u = make_user(role="teacher")
    login(client, u.username)
    r = client.get("/ocenjevanje/dejavnosti")
    assert r.status_code == 200
    assert 'USER_ROLE' in r.text and 'teacher' in r.text
    # Gumbi za urejanje so v kodi, a JS jih ne prikaže — api post/put/delete jih blokira server


def test_dejavnosti_teacher_cannot_edit(client, make_user, monkeypatch):
    """Učitelj NE SME ustvariti/posodobiti/izbrisati dejavnosti (403).

    ALLOWED_USER_IDS = {1,2,3,4} je whitelist, ki obide role check.
    Za test ga izpraznimo, da velja SAMO check vloge.  """
    monkeypatch.setattr("app.routers.dejavnosti.ALLOWED_USER_IDS", set())
    u = make_user(role="teacher")
    login(client, u.username)
    # POST
    assert client.post("/api/dejavnosti", json={"grade": "1", "section": "KULTURNI", "title": "x", "date_from": "2027-01-01"}).status_code == 403
    # PUT
    assert client.put("/api/dejavnosti/1", json={"grade": "1", "section": "KULTURNI", "title": "x"}).status_code == 403
    # DELETE
    assert client.delete("/api/dejavnosti/1").status_code == 403


def test_dejavnosti_new_path_ok_for_vodstvo(client, make_user):
    u = make_user(role="vodstvo")
    login(client, u.username)
    r = client.get("/ocenjevanje/dejavnosti")
    assert r.status_code == 200





def test_dejavnosti_old_path_redirects(client, make_user):
    # Prijavljen uporabnik: stara pot preusmeri na novo (ne na login).
    u = make_user(role="teacher")
    login(client, u.username)
    r = client.get("/dejavnosti", follow_redirects=False)
    assert r.status_code in REDIRECT_CODES
    assert r.headers["location"] == "/ocenjevanje/dejavnosti"


def test_dejavnosti_page_has_full_day_column(client, make_user):
    """Stran /ocenjevanje/dejavnosti ima stolpec »Cel. dan« (Celoten dan)."""
    u = make_user(role="vodstvo")
    login(client, u.username)
    html = client.get("/ocenjevanje/dejavnosti").text
    assert ">Cel. dan</th>" in html
    # celica prikaže ✔ / — glede na r.full_day
    assert "r.full_day ? '✔' : '—'" in html
    # prazno stanje ima pravilen colspan (10 stolpcev + 1 nov = 11)
    assert 'colspan="11"' in html


def test_rezervacije_requires_login(client):
    r = client.get("/rezervacije", follow_redirects=False)
    assert r.status_code in REDIRECT_CODES
    assert r.headers["location"] == "/auth/login"


def test_ocenjevanje_requires_login(client):
    r = client.get("/ocenjevanje", follow_redirects=False)
    assert r.status_code in REDIRECT_CODES
    assert r.headers["location"] == "/auth/login"
