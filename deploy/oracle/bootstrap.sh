#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# deploy/oracle/bootstrap.sh — en ukaz na sveži Oracle Ubuntu VM:
#   1) Docker + git + orodja, odpre vrata 80/443 (iptables — Oracle past)
#   2) namesti Hermes agenta (uradni install.sh)
#   3) klonira aplikacijo in pripravi .env
#   4) požene app (db + app; Caddy samo, če je nastavljena domena)
#
# Zagon na VM:
#   curl -fsSL https://raw.githubusercontent.com/CusinM15/reservation_app_sell/main/deploy/oracle/bootstrap.sh | bash
# ali (priporočeno, da vidiš skript):
#   git clone https://github.com/CusinM15/reservation_app_sell.git
#   cd reservation_app_sell/deploy/oracle && ./bootstrap.sh
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/CusinM15/reservation_app_sell.git"
APP_DIR="${HOME}/reservation_app_sell"

echo "=== 1/4  Sistemski paketi in Docker"
sudo apt-get update -y
sudo apt-get install -y git ca-certificates curl python3-venv
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER" || true

echo "=== 2/4  Odpiram vrata 80 in 443 (Oracle Ubuntu jih privzeto blokira)"
sudo iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save >/dev/null 2>&1 || true
echo "   (ne pozabi odpreti 80/443 tudi v Oracle Security List!)"

echo "=== 3/4  Hermes agent"
if ! command -v hermes >/dev/null 2>&1; then
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    export PATH="${HOME}/.local/bin:${PATH}"
fi
hermes --version || true

echo "=== 4/4  Aplikacija"
if [ ! -d "$APP_DIR" ]; then
    git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR/deploy/oracle"

if [ ! -f .env ]; then
    cp .env.example .env
    echo
    echo "!! Ustvarjen .env — izpolni ga in nato znova poženi ta skript (ali docker compose)."
    echo "   Vsaj: BASE_HOST, BASE_URL, SECRET_KEY, POSTGRES_PASSWORD, MAIN_ADMIN_PASSWORD"
    echo "   Naključen niz:  python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
    exit 0
fi

# Če je v .env prava domena → privzeti način (Caddy + HTTPS), sicer IP-način.
if grep -qE '^BASE_HOST=[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' .env; then
    echo "→ IP-način (brez Caddyja, app na vratih 80)"
    sudo docker compose -f docker-compose.yml -f docker-compose.ip.yml up -d --build
else
    echo "→ Domena zaznana (Caddy + samodejni HTTPS)"
    sudo docker compose up -d --build
fi

sudo docker compose ps
IP="$(curl -fsS --max-time 5 https://api.ipify.org || echo '<JAVNI_IP>')"
echo
echo "==> Aplikacija:  http://${IP}/health   (in http://${IP}/auth/login)"
echo "==> Hermes:      hermes          (nastavi model: hermes model; ključ v ~/.hermes/.env)"
echo "==> Backup cron: crontab -e  →  15 4 * * * ${APP_DIR}/deploy/oracle/backup.sh >> ${HOME}/sola-backup.log 2>&1"
