#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# scripts/clean_test_data.sh — Počisti TESTNE podatke (TRUNCATE, ne DROP)
#
# Uporaba (na k3s-1 ali k3s-2):
#   git pull
#   bash scripts/clean_test_data.sh        # interaktivno (potrditev da/NE)
#   bash scripts/clean_test_data.sh -y     # brez potrditve (avtomatizacija)
#
# POZOR: TRUNCATE izprazni:
#   - reservations      (vključno s serijskimi rezervacijami — series_id)
#   - assessments       (ocenjevanja)
#   - blocked_dates     (dnevi dejavnosti / zasedeni datumi)
# Tabele ostanejo (prazne), ID-ji se resetirajo (RESTART IDENTITY).
# Uporabniki in audit log ostanejo nedotaknjeni.
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

echo "🔍 Iščem pod sola-app..."
POD=$(kubectl get pods -n sola-app -l app=sola-app -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$POD" ]; then
    echo "❌ Ne najdem poda sola-app v namespace sola-app"
    exit 1
fi
echo "✅ Pod: $POD"

echo ""
echo "📊 Stanje pred brisanjem:"
kubectl exec -i "$POD" -n sola-app -- python -c "
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    for t in ['reservations', 'assessments', 'blocked_dates']:
        n = c.execute(text(f'SELECT count(*) FROM {t}')).scalar()
        print(f'  {t}: {n} vrstic')
    s = c.execute(text('SELECT count(*) FROM reservations WHERE series_id IS NOT NULL')).scalar()
    print(f'  od tega serijske rezervacije: {s}')
"

echo ""
if [ "${1:-}" = "-y" ]; then
    echo "⚠️  -y: TRUNCATE brez potrditve"
else
    read -p "⚠️  TRUNCATE rezervacij (tudi serijskih), ocenjevanj in dnevov dejavnosti? (da/NE): " CONFIRM || CONFIRM=""
    if [ "$CONFIRM" != "da" ]; then
        echo "Preklicano — nič ni izbrisano."
        exit 0
    fi
fi

echo ""
echo "🗑️  TRUNCATE..."
kubectl exec -i "$POD" -n sola-app -- python -c "
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ['DATABASE_URL'])
with e.begin() as c:
    for t in ['reservations', 'assessments', 'blocked_dates']:
        n = c.execute(text(f'SELECT count(*) FROM {t}')).scalar()
        c.execute(text(f'TRUNCATE {t} RESTART IDENTITY'))
        print(f'  ✅ {t}: izpraznjeno ({n} vrstic, ID resetiran)')
"

echo ""
echo "📊 Stanje po brisanju:"
kubectl exec -i "$POD" -n sola-app -- python -c "
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    for t in ['reservations', 'assessments', 'blocked_dates']:
        n = c.execute(text(f'SELECT count(*) FROM {t}')).scalar()
        print(f'  {t}: {n} vrstic')
"

echo ""
echo "🎉 Končano! Tabele so prazne (ne pobrisane)."
