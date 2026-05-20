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


settings = Settings()
