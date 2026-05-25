import os
import json
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", 8001))
    SECRET_KEY = os.getenv("SECRET_KEY")
    DB_PATH = os.getenv("DB_PATH", "./data/sola.db")
    TABLICE_MAX = int(os.getenv("TABLICE_MAX", 28))
    SCHEDULE = json.loads(os.getenv("SCHEDULE", "{}"))
    RAZREDI = os.getenv("RAZREDI", "").split(",")
    PROSTORI = os.getenv("PROSTORI", "").split(",")

    # Email
    MAIL_FROM = os.getenv("MAIL_FROM", "matej.cusin2+ocenjevanje@guest.arnes.si")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "matcus1")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "mail.arnes.si")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))


settings = Settings()
