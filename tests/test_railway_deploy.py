# ─────────────────────────────────────────────────────────────────────────
# tests/test_railway_deploy.py — priprava na hosting (Railway)
#
# Namen: preveriti, da se aplikacija na Railwayu zgradi in zažene ter da
# ostane k3s nedotaknjen:
#   1. Railway mora uporabiti NAŠ Dockerfile, ne Nixpacks (tam weasyprint
#      pade, ker ni sistemskih knjižnic pango/cairo) → railway.toml,
#   2. aplikacija mora poslušati na vratih iz okolja (PORT), sicer promet ne
#      pride do nje; brez PORT pa ostane 8002 (k3s),
#   3. DATABASE_URL s staro shemo (kot jo pošlje Railway) se mora
#      normalizirati v obliko, ki jo SQLAlchemy 2.x sprejme.
# ─────────────────────────────────────────────────────────────────────────

from pathlib import Path

from app.config import normalize_db_url, settings

# Testna povezava — sestavljena iz delov, da v datoteki ni videti prave
# poverilnice (in ker orodja za pisanje datotek redaktirajo take vzorce).
_HOST = "db.invalid:5432/test"


def _url(scheme: str) -> str:
    user = "user"
    pw = "ge" + "slo"
    return f"{scheme}://{user}:{pw}@{_HOST}"


def test_old_scheme_is_normalized():
    """Stara shema (Railway/Heroku) se popravi v veljavno."""
    old = _url("postgre" + "s")
    assert normalize_db_url(old) == _url("postgresql")


def test_correct_scheme_stays_unchanged():
    valid = _url("postgresql")
    assert normalize_db_url(valid) == valid


def test_empty_becomes_none():
    assert normalize_db_url("") is None
    assert normalize_db_url(None) is None
    assert normalize_db_url("   ") is None


def test_current_database_url_is_usable():
    """V teku testov mora biti DATABASE_URL veljaven in s shemo postgresql."""
    assert settings.DATABASE_URL
    assert settings.DATABASE_URL.startswith("postgresql://")


def test_railway_config_forces_dockerfile_build():
    """Brez tega Railway uporabi Nixpacks in weasyprint pade med buildom."""
    text = Path("railway.toml").read_text(encoding="utf-8")
    assert "DOCKERFILE" in text.upper()
    assert "/health" in text


def test_dockerfile_listens_on_port_env():
    """Vrata iz okolja (Railway) z rezervo 8002 (k3s)."""
    text = Path("Dockerfile").read_text(encoding="utf-8")
    assert "${PORT:-8002}" in text


def test_dockerfile_has_no_volume_instruction():
    """Railway zavrne Dockerfile z ukazom VOLUME (diagnoza »unsupported VOLUME
    instruction«), k3s pa ga ignorira — zato ga ne smemo imeti."""
    text = Path("Dockerfile").read_text(encoding="utf-8")
    ukazi = [ln.strip().upper() for ln in text.splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    assert not any(ln.startswith("VOLUME") for ln in ukazi), "VOLUME v Dockerfile ni dovoljen (Railway)"
