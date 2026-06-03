#!/usr/bin/env bash
# Sync ključnih nastavitev iz .env v k8s ConfigMap sola-config
# Uporaba: ./scripts/sync_env_to_configmap.sh
#
# To je potrebno le za nastavitve, ki jih app ne more dinamično določiti
# (BASE_URL je zdaj dinamičen — glej auth.py forgot_password)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
NAMESPACE="sola-app"
CONFIGMAP="sola-config"

# Preberi vrednosti iz .env
load_env() {
    local key="$1"
    grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' || echo ""
}

# Zgradi JSON patch
PATCH='{"data":{'

# DATABASE_URL
DB_URL=$(load_env "DATABASE_URL")
if [ -n "$DB_URL" ]; then
    # Če vsebuje ***, poskusi dobiti pravo geslo iz k8s secret
    if echo "$DB_URL" | grep -q '\*\*\*'; then
        REAL_PASS=$(kubectl get secret sola-postgresql -n sola -o jsonpath='{.data.password}' 2>/dev/null | base64 -d || echo "")
        if [ -n "$REAL_PASS" ]; then
            DB_URL=$(echo "$DB_URL" | sed "s|sola:\*\*\*@|sola:${REAL_PASS}@|")
        fi
    fi
    PATCH+='"DATABASE_URL":"'"$DB_URL"'",'
fi

# PROSTORI, RAZREDI, SCHEDULE, TABLICE_MAX
for key in PROSTORI RAZREDI SCHEDULE TABLICE_MAX; do
    val=$(load_env "$key")
    if [ -n "$val" ]; then
        # Escape for JSON
        val_escaped=$(echo "$val" | sed 's/"/\\"/g')
        PATCH+='"'"$key"'":"'"$val_escaped"'",'
    fi
done

# Odstrani zadnjo vejico in zapri JSON
PATCH="${PATCH%,}}"

# Uporabi
echo "Syncing configmap $CONFIGMAP in namespace $NAMESPACE..."
echo "$PATCH" | kubectl patch configmap "$CONFIGMAP" -n "$NAMESPACE" --type merge -p "$(cat)"

echo "Done. Restart deployment: kubectl rollout restart deployment -n $NAMESPACE sola-app"
