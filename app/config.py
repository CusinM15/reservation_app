import os
import json
import re
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", 8001))
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.getenv('DB_PATH', './data/sola.db')}")
    TABLICE_MAX = int(os.getenv("TABLICE_MAX", 28))
    SCHEDULE = json.loads(os.getenv("SCHEDULE", "{}"))
    RAZREDI = os.getenv("RAZREDI", "").split(",")
    RAZREDI = [r for r in RAZREDI if r]  # filtriramo prazne
    PROSTORI = os.getenv("PROSTORI", "").split(",")
    PROSTORI = [p for p in PROSTORI if p]  # filtriramo prazne
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")
    INACTIVITY_TIMEOUT_MINUTES = int(os.getenv("INACTIVITY_TIMEOUT_MINUTES", 30))
    INACTIVITY_TIMEOUT_ADMIN_MINUTES = int(os.getenv("INACTIVITY_TIMEOUT_ADMIN_MINUTES", 20))
    RESET_TOKEN_EXPIRATION_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRATION_MINUTES", 120))

    # Email
    MAIL_FROM = os.getenv("MAIL_FROM", "")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "mail.arnes.si")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    BACKUP_EMAIL = os.getenv("BACKUP_EMAIL", "")
    STANJE_MAIL = os.getenv("STANJE_MAIL", "")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@ostc.si")

    # Audit log — admin token za dostop do /history?token=...
    AUDIT_TOKEN = os.getenv("AUDIT_TOKEN", "")


settings = Settings()


def validate_password_strength(password: str) -> str | None:
    """Validate password strength. Returns error message or None if valid."""
    if len(password) < 5:
        return "Geslo mora biti dolgo vsaj 5 znakov."
    if not re.search(r'[a-z]', password):
        return "Geslo mora vsebovati vsaj eno malo črko."
    if not re.search(r'[A-Z]', password):
        return "Geslo mora vsebovati vsaj eno veliko črko."
    if not re.search(r'[0-9]', password):
        return "Geslo mora vsebovati vsaj eno številko."
    return None
