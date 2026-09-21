#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# scripts/run-local-dev.sh — Zaženi aplikacijo LOKALNO (razvoj/testiranje)
#
# Namen: omogoči lokalno preizkušanje večšolske prenove, BREZ dotika
# produkcije. Baza je lokalna (privzeto "sola_dev").
#
# Zakaj ta skript?
#   app/config.py (fail-fast) zahteva SECRET_KEY in DATABASE_URL. V .env ju
#   ni — na produkciji prideta iz k8s Secret. Skript ju nastavi za lokalni
#   zagon, ne da bi se dotaknil .env datoteke.
#
# Nastavitve (RAZREDI, PROSTORI, SCHEDULE, TABLICE_MAX, MAIL_*) se pri
# prvem zagonu preberejo iz .env in zapišejo v tabelo school_settings za
# privzeto šolo (ostcj) — tako vidiš, kaj je bilo prej v .env.
#
# Varnost: MAIL_PASSWORD je lokalno prazen, zato aplikacija NE pošilja
# pravih emailov (obvestila o preklicih, ponastavitev gesla).
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

DB_NAME="${LOCAL_DB_NAME:-sola_dev}"
DB_URL="${LOCAL_DATABASE_URL:-postgresql://postgres@127.0.0.1:5432/${DB_NAME}}"
PORT="${LOCAL_PORT:-8001}"

# Lokalna baza (če je še ni, jo ustvarimo — prazna, brez produkcijskih podatkov)
if ! psql -U postgres -h 127.0.0.1 -Atc "select 1 from pg_database where datname='${DB_NAME}'" | grep -q 1; then
    echo "→ lokalna baza '${DB_NAME}' še ne obstaja — ustvarjam ..."
    psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE ${DB_NAME}"
fi

# SECRET_KEY: vsakič nova (za razvoj dovolj; stare seje potečejo ob restartu)
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DATABASE_URL="${DB_URL}"
export APP_PORT="${PORT}"
export MAIL_PASSWORD=""   # lokalno ne pošiljamo pravih emailov

echo
echo "  Aplikacija:   http://127.0.0.1:${PORT}/auth/login"
echo "  Baza:         ${DB_URL}"
echo
echo "  Šolski admin (ostcj):  admin_ostcj / admin123"
echo "  Glavni admin:          mainadmin / Admin123"
echo
echo "  Nastavitve šole:       http://127.0.0.1:${PORT}/settings"
echo "  Pregled šol:           http://127.0.0.1:${PORT}/schools"
echo

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
