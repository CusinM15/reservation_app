#!/bin/bash
# =============================================================
# replace-ips.sh — zamenjaj {{VAR}} placeholderje v dokumentaciji
# =============================================================
# Uporaba:
#   1. Kopiraj .env.ip.example → .env.ip
#   2. Uredi .env.ip s svojimi IP-ji
#   3. Poženi: ./replace-ips.sh
#
# Skripta prebere .env.ip in v vseh .md datotekah pod documentation/
# zamenja {{VAR}} place holderje z dejanskimi vrednostmi.
# =============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env.ip"
DOC_DIR="$SCRIPT_DIR"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Napaka: $ENV_FILE ne obstaja!"
    echo "Kopiraj .env.ip.example → .env.ip in ga uredi."
    exit 1
fi

source "$ENV_FILE"

# Define replacements: "PLACEHOLDER" "VALUE"
REPLACEMENTS=(
    "{{K3S_1_IP}}:$K3S_1_IP"
    "{{K3S_2_IP}}:$K3S_2_IP"
    "{{SSH_USER}}:$SSH_USER"
    "{{LB_IP}}:$LB_IP"
    "{{LB_PORT}}:$LB_PORT"
    "{{METALLB_RANGE_START}}:$METALLB_RANGE_START"
    "{{METALLB_RANGE_END}}:$METALLB_RANGE_END"
    "{{NGINX_PORT}}:$NGINX_PORT"
    "{{DOMAIN}}:$DOMAIN"
    "{{K8S_NAMESPACE_APP}}:$K8S_NAMESPACE_APP"
    "{{K8S_NAMESPACE_DB}}:$K8S_NAMESPACE_DB"
    "{{K8S_CLUSTER_DB}}:$K8S_CLUSTER_DB"
    "{{K8S_SERVICE_DB}}:$K8S_SERVICE_DB"
    "{{K8S_DB_PORT}}:$K8S_DB_PORT"
    "{{GATEWAY_IP}}:$GATEWAY_IP"
    "{{DNS_IP}}:$DNS_IP"
)

COUNT=0

for file in $(find "$DOC_DIR" -name '*.md' -not -path '*.env.ip*' | sort); do
    changed=false
    for entry in "${REPLACEMENTS[@]}"; do
        placeholder="${entry%%:*}"
        value="${entry#*:}"
        if grep -q "$placeholder" "$file" 2>/dev/null; then
            sed -i "s|$placeholder|$value|g" "$file"
            changed=true
        fi
    done
    if $changed; then
        echo "  ✅ ${file#$DOC_DIR/}"
        COUNT=$((COUNT + 1))
    fi
done

echo ""
echo "=== Končano! $COUNT datotek posodobljenih ==="
echo ""
echo "💡 Uredi .env.ip, poženi skripto in dokumentacija bo prilagojena tvojim IP-jem."
