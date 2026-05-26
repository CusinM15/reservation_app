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
    PROSTORI = os.getenv("PROSTORI", "").split(",")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")

    # Email
    MAIL_FROM = os.getenv("MAIL_FROM", "matej.cusin2+ocenjevanje@guest.arnes.si")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "matcus1")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "mail.arnes.si")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    BACKUP_EMAIL = os.getenv("BACKUP_EMAIL", "admin@ostonecufar.local")


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
