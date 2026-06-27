[🇸🇮 Slovenščina](../lokalni_zagon.md) | [🇬🇧 English](lokalni_zagon.md)

---

# 💻 **Local Setup — ostc-app**

Instructions for running the app locally (without Kubernetes) on a single computer using uvicorn.

## Requirements

- Python 3.11+
- Git
- SQLite (default) or PostgreSQL access

## Installation

```bash
# Clone the repository
git clone git@github.com:os-tc-jesenice/ostc-app_deli.git
cd ostc-app_deli

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
nano .env   # Configure your settings
```

## Running

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Open http://localhost:8001 in your browser.

## Environment Variables (.env)

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (or SQLite by default) |
| `MAIL_SERVER` | SMTP server (e.g. `mail.arnes.si`) |
| `MAIL_PORT` | SMTP port (587) |
| `MAIL_USERNAME` | SMTP username |
| `MAIL_PASSWORD` | SMTP password |
| `MAIL_FROM` | Sender email address |
| `PROSTORI` | Comma-separated room list |
| `SCHEDULE` | JSON schedule of time slots |
| `RAZREDI` | Comma-separated class list |
| `TABLICE_MAX` | Maximum number of tablets (28) |
| `BASE_URL` | Public URL of the app |
