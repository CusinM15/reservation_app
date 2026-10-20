#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# scripts/daily-report-cron.sh — dnevno poročilo o zdravju clustra (node-1)
# Zažene scripts/daily_report.py s pravimi nastavitvami (iz sola-secrets)
# in pošlje na BACKUP_EMAIL (privzeto reservation.app@proton.me).
# Kliče ga crontab uporabnika deploy (node-1).
# ─────────────────────────────────────────────────────────────────────────
set -u
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# nastavitve iz clusterja (brez tiskanja)
for K in SECRET_KEY MAIL_FROM MAIL_USERNAME MAIL_PASSWORD MAIL_SERVER MAIL_PORT; do
  v=$(kubectl get secret sola-secrets -n sola-app -o "jsonpath={.data.$K}" 2>/dev/null | base64 -d 2>/dev/null)
  [ -n "$v" ] && export "$K=$v"
done

# DATABASE_URL: preusmeri na ClusterIP (node-1 ne pozna k8s DNS-ja)
NIP=$(kubectl get svc sola-db-rw -n sola-app -o jsonpath='{.spec.clusterIP}' 2>/dev/null)
DBURL=$(kubectl get secret sola-secrets -n sola-app -o jsonpath='{.data.DATABASE_URL}' 2>/dev/null | base64 -d 2>/dev/null)
if [ -n "$DBURL" ]; then
  DBURL=$(printf '%s' "$DBURL" | sed -E "s#@[^:/]+:[0-9]+#@${NIP}:5432#")
  export DATABASE_URL="$DBURL"
fi

# kam gre poročilo (lahko iz okolja crontaba, privzeto proton)
export BACKUP_EMAIL="${BACKUP_EMAIL:-reservation.app@proton.me}"

cd /home/deploy/reservation_app_sell || exit 1
exec /home/deploy/venv-daily/bin/python -m scripts.daily_report >> /tmp/daily-report.log 2>&1