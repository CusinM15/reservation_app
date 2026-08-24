# ─────────────────────────────────────────────────────────────────────────
# tests/test_ocenjevanja.py — Napovedovanje ocenjevanj
#
# Namen: Preveri, da je na dan dejavnosti (BlockedDate) za razred
# ocenjevanje ZAVRNJENO (400), medtem ko na prostem dnevu uspe (201).
# To je regresijski test za dogovor s šolo: "ne morejo napovedati
# ocenjevanja za razred, če ima ta dan dejavnosti".
# ─────────────────────────────────────────────────────────────────────────

from datetime import date, timedelta

from tests.conftest import login

# Dan dejavnosti preskoči vikende (blocked_dates.py: weekday() >= 5),
# zato vzamemo bodoči DELAVNIK — če pade na vikend, ga prestavimo naprej.
def _next_weekday(days_ahead: int = 7) -> date:
    d = date.today() + timedelta(days=days_ahead)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


FUTURE = _next_weekday(7).isoformat()
FUTURE2 = _next_weekday(8).isoformat()
H = {"Content-Type": "application/json"}
# teacher_id je obvezen v shemi, ampak server ga vedno override-a iz seje.
TID = 999


def _block(client, razredi, date_str, expected=201):
    """Vodstvo/admin blokira dan za razrede (dan dejavnosti)."""
    r = client.post(
        "/api/blocked-dates",
        json={"razredi": razredi, "date_from": date_str, "date_to": date_str},
    )
    assert r.status_code == expected, f"pričakovan {expected}, dobil {r.status_code}: {r.text}"
    return r


# ── Pozitivni kontroli ─────────────────────────────────────────────────

def test_ocenjevanje_na_prostem_datumu_ok(client, make_user):
    """Brez blokade učitelj normalno napove ocenjevanje (201)."""
    u = make_user()
    login(client, u.username)
    r = client.post("/api/ocenjevanja", json={"razred": "5.a", "date": FUTURE, "ponavljanje": False, "teacher_id": TID})
    assert r.status_code == 201, r.text
    assert r.json()["teacher_id"] == u.id


def test_ocenjevanje_ok_ce_je_dejavnost_drugi_razred(client, make_user):
    """Dan dejavnosti velja le za svoj razred — 5.a lahko napove, če je blokiran 6.a."""
    admin = make_user(role="admin")
    login(client, admin.username)
    _block(client, ["6.a"], FUTURE)
    client.post("/auth/logout")

    teacher = make_user()
    login(client, teacher.username)
    r = client.post("/api/ocenjevanja", json={"razred": "5.a", "date": FUTURE, "ponavljanje": False, "teacher_id": TID})
    assert r.status_code == 201, r.text


# ── Prepoved: dan dejavnosti ──────────────────────────────────────────

def test_ocenjevanje_zavrnjeno_na_dan_dejavnosti(client, make_user):
    """Če ima razred na ta dan dejavnost, API ocenjevanje zavrne s 400."""
    admin = make_user(role="admin")
    login(client, admin.username)
    _block(client, ["5.a"], FUTURE)
    client.post("/auth/logout")

    teacher = make_user()
    login(client, teacher.username)
    r = client.post("/api/ocenjevanja", json={"razred": "5.a", "date": FUTURE, "ponavljanje": False, "teacher_id": TID})
    assert r.status_code == 400, r.text
    assert "dan dejavnosti" in r.json()["detail"]

    # In v bazi ni nobenega ocenjevanja za ta dan.
    rl = client.get(f"/api/ocenjevanja?razred=5.a&month={FUTURE[:7]}")
    assert rl.status_code == 200
    assert all(a["date"] != FUTURE for a in rl.json())
