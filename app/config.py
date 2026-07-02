# ─────────────────────────────────────────────────────────────────────────
# app/config.py — Centralna konfiguracija aplikacije
#
# Namen: Nalaga okoljske spremenljivke (.env) in jih izpostavi kot
# atribute razreda Settings. Vsebuje tudi pomožne funkcije, kot je
# validacija moči gesla.
#
# Zakaj lastni Settings razred namesto pydantic-settings?
# Zgodovinski razlog — ta aplikacija je začela kot preprost FastAPI
# projekt, kjer je bil Settings razred dovolj. Prav tako pydantic-settings
# takrat ni bil na voljo.
# ─────────────────────────────────────────────────────────────────────────

import os
import json
import re
from dotenv import load_dotenv

# Naloži .env datoteko, če obstaja. To je pomembno za lokalni razvoj,
# medtem ko v Kubernetes okolju uporabljamo Secrets.
load_dotenv()


class Settings:
    # ── Osnovna konfiguracija strežnika ──────────────────────────────
    # APP_HOST in APP_PORT določata, kje strežnik posluša.
    # Privzeto 0.0.0.0:8001 — v Dockerju se vedno uporabi 0.0.0.0.
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", 8001))

    # ── Podatkovna baza ─────────────────────────────────────────────
    # Privzeta vrednost je SQLite (za lokalni razvoj). V produkciji
    # (k8s) nastavimo DATABASE_URL na PostgreSQL.
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.getenv('DB_PATH', './data/sola.db')}")

    # ── Kapaciteta tablic ───────────────────────────────────────────
    # Največje število tablic, ki jih je mogoče rezervirati v eni uri.
    TABLICE_MAX = int(os.getenv("TABLICE_MAX", 28))

    # ── Urnik (SCHEDULE) ────────────────────────────────────────────
    # JSON objekt, ki preslika številko ure (0-7) v opis, npr.:
    # {"0": "7.00 - 7.45", "1": "7.50 - 8.35", ...}
    # Uporablja se za prikaz v UI in za izvoze CSV.
    SCHEDULE = json.loads(os.getenv("SCHEDULE", "{}"))

    # ── Seznami razredov in prostorov ───────────────────────────────
    # Shranjeni kot vejica-ločen niz v okoljski spremenljivki.
    # Npr.: RAZREDI="1.a,1.b,2.a,2.b,3.a,..."
    # V kodi jih razdelimo in filtriramo prazne vnose.
    RAZREDI = os.getenv("RAZREDI", "").split(",")
    RAZREDI = [r for r in RAZREDI if r]  # filtriramo prazne
    PROSTORI = os.getenv("PROSTORI", "").split(",")
    PROSTORI = [p for p in PROSTORI if p]  # filtriramo prazne

    # ── URL in timeout ──────────────────────────────────────────────
    # BASE_URL se uporablja za generiranje povezav v emailih.
    # Upoštevaj: ngrok in druge proxy storitve spremenijo URL, zato
    # v emailih uporabljamo dinamično pridobljen request.base_url.
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")

    # ── Timeout za neaktivnost ──────────────────────────────────────
    # Različen timeout za admin/vodstvo (krajši, ker imajo dostop do
    # občutljivih funkcij) in za navadne učitelje.
    INACTIVITY_TIMEOUT_MINUTES = int(os.getenv("INACTIVITY_TIMEOUT_MINUTES", 30))
    INACTIVITY_TIMEOUT_ADMIN_MINUTES = int(os.getenv("INACTIVITY_TIMEOUT_ADMIN_MINUTES", 20))

    # ── Ponastavitev gesla ──────────────────────────────────────────
    # Koliko časa je povezava za ponastavitev gesla veljavna.
    RESET_TOKEN_EXPIRATION_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRATION_MINUTES", 120))

    # ── Email konfiguracija ─────────────────────────────────────────
    # Uporablja Arnes SMTP strežnik (mail.arnes.si) za pošiljanje
    # obvestil o preklicanih rezervacijah, ocenjevanjih in ponastavitvi
    # gesel. MAIL_PASSWORD je obvezen za delovanje SMTP.
    # BACKUP_EMAIL je kamor leti dnevno poročilo o zdravju k3s.
    # STANJE_MAIL je za namensko poročanje o stanju sistema.
    MAIL_FROM = os.getenv("MAIL_FROM", "")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "mail.arnes.si")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    BACKUP_EMAIL = os.getenv("BACKUP_EMAIL", "")
    STANJE_MAIL = os.getenv("STANJE_MAIL", "")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@ostc.si")

    # ── Audit log — admin token ────────────────────────────────────
    # Dodaten token za dostop do /history?token=..., če želimo dati
    # dostop do audit loga nekomu, ki ni admin.
    AUDIT_TOKEN = os.getenv("AUDIT_TOKEN", "")


settings = Settings()


def validate_password_strength(password: str) -> str | None:
    """Preveri moč gesla po pravilih šole.
    
    Zakaj ta pravila? Šola zahteva minimalno varnost gesel, vendar
    ne prestrogo (ni zahtev po posebnih znakih), ker si učitelji
    pogosto težko zapomnijo kompleksna gesla.
    
    Args:
        password: Geslo za preverjanje.
    
    Returns:
        None, če je geslo dovolj močno, sicer sporočilo o napaki v slovenščini.
    """
    if len(password) < 5:
        return "Geslo mora biti dolgo vsaj 5 znakov."
    if not re.search(r'[a-z]', password):
        return "Geslo mora vsebovati vsaj eno malo črko."
    if not re.search(r'[A-Z]', password):
        return "Geslo mora vsebovati vsaj eno veliko črko."
    if not re.search(r'[0-9]', password):
        return "Geslo mora vsebovati vsaj eno številko."
    return None
