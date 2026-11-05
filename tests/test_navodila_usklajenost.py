# Usklajenost /navodila s preveri_strani.md — isti razdelki, iste strani.
# Javno razdelek mora vsebovati vseh 9 javnih strani (isti red kot checklista).
from tests.conftest import login

JAVNO_PATHS = [
    "/auth/login",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/registracija",
    "/nadomescanja_&lt;kratica&gt;",
    "/govorilne",
    "/nastavitev?demo=1",
    "/health",
]


def test_navodila_javno_razdelek_je_usklajen_s_preveri_strani(client, make_user):
    a = make_user(role="main_admin")
    login(client, a.username)
    r = client.get("/navodila")
    assert r.status_code == 200, r.status_code
    text = r.text
    # Vseh 9 javnih strani je v razdelku Javno (znotraj istega <details> bloka).
    blok = text[text.index("🔓 Javno"):text.index("Učitelji (prijavljeni)")]
    for p in JAVNO_PATHS:
        assert p in blok, f"manjka v Javno: {p}"
    # Kojek: korenska pot "/" kot plink
    assert 'plink">/' in blok or "/</span>" in blok, "manjka korenska pot /"
    assert "/rezervacije</span>" in text  # Učitelji razdelek še vedno obstaja
    assert "/docs/html/navodila-ucitelji" in text  # 📚 dokumenti prisotni