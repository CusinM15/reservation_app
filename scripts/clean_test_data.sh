#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# scripts/clean_test_data.sh — Počisti TESTNE podatke iz rezervacij in ocenjevanj
#
# Uporaba (na k3s-1 ali k3s-2):
#   git pull
#   bash scripts/clean_test_data.sh
#
# POZOR: Izbriše VSE rezervacije in ocenjevanja (testni podatki).
# Uporabniki, audit log in blokirani datumi ostanejo.
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
kubectl exec -it "$POD" -n sola-app -- python -c "
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    for t in ['reservations', 'assessments']:
        n = c.execute(text(f'SELECT count(*) FROM {t}')).scalar()
        print(f'  {t}: {n} vrstic')
"

echo ""
read -p "⚠️  Izbrisati vse rezervacije in ocenjevanja? (da/NE): " CONFIRM
if [ "$CONFIRM" != "da" ]; then
    echo "Preklicano — nič ni izbrisano."
    exit 0
fi

echo ""
echo "🗑️  Brisanje..."
kubectl exec -it "$POD" -n sola-app -- python -c "
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ['DATABASE_URL'])
with e.begin() as c:
    for t in ['reservations', 'assessments']:
        n = c.execute(text(f'SELECT count(*) FROM {t}')).scalar()
        c.execute(text(f'DELETE FROM {t}'))
        print(f'  ✅ {t}: izbrisanih {n} vrstic')
"

echo ""
echo "🎉 Končano! Rezervacije in ocenjevanja so prazni."
