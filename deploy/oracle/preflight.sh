#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# deploy/oracle/preflight.sh — hitro preverjanje VM-ja pred namestitvijo.
# Zaženi na VM in prilepi izpis (pove, ali je instanca primerna in kaj manjka).
#   bash preflight.sh
# ─────────────────────────────────────────────────────────────────────────
set -uo pipefail

echo "== OS:";        (lsb_release -ds 2>/dev/null || grep -m1 PRETTY_NAME /etc/os-release)
echo "== Arhitektura:"; uname -m
echo "== CPU jedra:"; nproc
echo "== Pomnilnik (MB):"; free -m | head -3
echo "== Swap:";     (swapon --show || echo "brez swap")
echo "== Disk /:";   df -h / | tail -1
echo "== Docker:";   (docker --version 2>/dev/null || echo "docker NI nameščen")
echo "== compose:";  (docker compose version 2>/dev/null || echo "compose NI")
echo "== Javni IP:"; (curl -fsS --max-time 5 https://api.ipify.org || echo "?")
echo
echo "== iptables INPUT (ali sta 80/443 odprta?):"
sudo iptables -L INPUT -n --line-numbers 2>/dev/null | head -12 || echo "(ni sudo/iptables)"
echo
echo "== Priporočilo:"
RAM="$(awk '/MemTotal/{printf "%d", $2/1024}' /proc/meminfo)"
if [ "${RAM:-0}" -lt 2000 ]; then
    echo "   <2 GB RAM → gradnje NE; uporabi objavljeno sliko:"
    echo "   docker compose -f docker-compose.yml -f docker-compose.ip.yml pull && \\"
    echo "   docker compose -f docker-compose.yml -f docker-compose.ip.yml up -d --no-build"
    echo "   (bootstrap.sh doda 2 GB swap sam)"
else
    echo "   dovolj RAM → navaden build je v redu:"
    echo "   docker compose -f docker-compose.yml -f docker-compose.ip.yml up -d --build"
fi
