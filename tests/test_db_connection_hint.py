# ─────────────────────────────────────────────────────────────────────────
# tests/test_db_connection_hint.py — razumljivo sporočilo ob neuspešni povezavi
#
# Povod (2026-09-25): na Railwayu je v DATABASE_URL ostal VZOREC iz navodil
# (gostitelj dobesedno »host«), aplikacija pa je javila le psycopg2 sled
# »could not translate host name "host" to address«. Zdaj ob tem dobi uporabnik
# jasno razlago, kaj naj popravi.
# ─────────────────────────────────────────────────────────────────────────

from app.database import db_connection_hint

# Povezava je sestavljena brez poverilnic — za preverjanje razlage zadostuje
# naslov gostitelja (funkcija bere le tega).
def _url(host: str) -> str:
    return "postgresql://" + host + ":5432/railway"


def test_placeholder_host_is_detected():
    sporocilo = db_connection_hint(_url("host"))
    assert "VZOREC" in sporocilo
    assert "host" in sporocilo
    assert "Add Reference" in sporocilo          # konkretno navodilo za Railway


def test_localhost_points_to_same_machine():
    sporocilo = db_connection_hint(_url("localhost"))
    assert "isti strežnik" in sporocilo


def test_missing_host_is_explained():
    assert "ni naslova baze" in db_connection_hint(None)
    assert "ni naslova baze" in db_connection_hint("")
    # brez gostitelja: "postgresql:///ime-baze" (samo pot, brez strežnika)
    assert "ni naslova baze" in db_connection_hint("postgresql:///sola")


def test_real_host_gives_generic_message():
    host = "containers-us-west-1.railway.app"
    sporocilo = db_connection_hint(_url(host))
    assert "ni uspela" in sporocilo
    assert host in sporocilo
    # tudi v splošnem primeru dobi uporabnik namig za Railway
    assert "Add Reference" in sporocilo
