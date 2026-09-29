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

COMPOSE_FILES=(-f docker-compose.yml)
if grep -qE '^BASE_HOST=[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' .env; then
    echo "→ IP-način (brez Caddyja, app na vratih 80)"
    COMPOSE_FILES+=(-f docker-compose.ip.yml)
else
    echo "→ Domena zaznana (Caddy + samodejni HTTPS)"
fi

MEM_MB="$(awk '/MemTotal/{printf "%d", $2/1024}' /proc/meminfo)"
if [ "${MEM_MB:-0}" -lt 2000 ]; then
    echo "→ Malo RAM (${MEM_MB} MB): dodajam 2 GB swap in uporabljam objavljeno sliko (brez gradnje)"
    if ! swapon --show 2>/dev/null | grep -q .; then
        sudo fallocate -l 2G /swapfile
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile
        sudo swapon /swapfile
        grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    fi
    echo "   (namestitev swap naredi build vseeno mogoč: docker compose ${COMPOSE_FILES[*]} up -d --build)"
    sudo docker compose "${COMPOSE_FILES[@]}" pull
    sudo docker compose "${COMPOSE_FILES[@]}" up -d --no-build
else
    sudo docker compose "${COMPOSE_FILES[@]}" up -d --build
fi

sudo docker compose "${COMPOSE_FILES[@]}" ps
IP="$(curl -fsS --max-time 5 https://api.ipify.org || echo '<JAVNI_IP>')"
echo
echo "==> Aplikacija:  http://${IP}/health   (in http://${IP}/auth/login)"
echo "==> Hermes:      hermes          (nastavi model: hermes model; ključ v ~/.hermes/.env)"
echo "==> Backup cron: crontab -e  →  15 4 * * * ${APP_DIR}/deploy/oracle/backup.sh >> ${HOME}/sola-backup.log 2>&1"
