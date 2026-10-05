#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# deploy/oracle/backup.sh — nočna varnostna kopija (zažene jo cron)
# Kopije (.sql po šolah) ostanejo v Docker volumnu »backups«.
# Izvoz na host:  docker compose exec backup ls /backups   (oz. volume)
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"
docker compose run --rm backup
