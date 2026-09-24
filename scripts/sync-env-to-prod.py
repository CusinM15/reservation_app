#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────
# scripts/sync-env-to-prod.py — Prenese vrednosti iz .env v produkcijo (k8s)
#
# Uporaba (na k3s-1, po `scp` .env-ja iz k3s-2):
#   python3 scripts/sync-env-to-prod.py
#
# Kaj naredi:
#   - ConfigMap sola-config  <- ne-secret kljuci (RAZREDI, SCHEDULE, ...)
#   - Secret   sola-secrets  <- secret kljuci (DATABASE_URL, MAIL_*, ...)
#   - Ne izpisuje vrednosti (samo imena kljucev + status)
#   - Ne spreminja SECRET_KEY (ni v .env) in ne brise obstojecih kljucev
# ─────────────────────────────────────────────────────────────────────────
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / ".env"
NS = "sola-app"
CM = "sola-config"
SECRET = "sola-secrets"

# Kam gre kateri kljuc (samo tisti, ki jih .env vsebuje)
CM_KEYS = [
    "RAZREDI", "SCHEDULE", "PROSTORI", "TABLICE_MAX",
    "APP_HOST", "APP_PORT", "BASE_URL",
    "INACTIVITY_TIMEOUT_MINUTES", "INACTIVITY_TIMEOUT_ADMIN_MINUTES",
]
SECRET_KEYS = [
    "DATABASE_URL", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_SERVER",
    "MAIL_PORT", "MAIL_FROM", "BACKUP_EMAIL", "STANJE_MAIL", "AUDIT_TOKEN",
]


def parse_env(path: Path) -> dict:
    """Robustno prebere .env (KEY=VALUE, vrednost lahko vsebuje '=' in navednice)."""
    result = {}
    if not path.exists():
        print(f"❌ {path} ne obstaja. Najprej skopiraj .env iz k3s-2!")
        sys.exit(1)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        result[key] = value
    return result


def kubectl(*args: str) -> str:
    return subprocess.run(
        ["kubectl", *args], capture_output=True, text=True, check=True
    ).stdout


def mask_db_url(url: str) -> str:
    """Prikaze samo host:port/db iz DATABASE_URL (kredenciali maskirani)."""
    m = re.match(r"postgresql://([^@]*)@([^/]+)/(\w+)", url or "")
    if not m:
        return "(neveljaven format)"
    return f"postgresql://***@{m.group(2)}/{m.group(3)}"


def main():
    env = parse_env(ENV_FILE)
    if not env:
        print("❌ .env je prazen.")
        sys.exit(1)

    print(f"📄 .env: {ENV_FILE} ({len(env)} kljucev)")

    # ── Predogled: DATABASE_URL host (kritično!) ──
    cur_db = ""
    try:
        cur_db = kubectl("get", "secret", "-n", NS, SECRET,
                         "-o", "jsonpath={.data.DATABASE_URL}")
        cur_db = base64.b64decode(cur_db).decode()
    except Exception:
        pass
    new_db = env.get("DATABASE_URL", "")
    print("\n🔎 DATABASE_URL (kritično!):")
    print(f"   .env   -> {mask_db_url(new_db)}")
    print(f"   prod   -> {mask_db_url(cur_db)}")
    if mask_db_url(new_db) != mask_db_url(cur_db):
        print("   ⚠️  HOST se razlikuje! Preveri, da .env res kaže na produkcijsko bazo!")
    else:
        print("   ✅ host:port/db enak produkciji (razlika je lahko samo v kredencialih)")

    # ── Kaj se bo posodobilo ──
    cm_updates = {k: v for k, v in env.items() if k in CM_KEYS}
    sec_updates = {k: v for k, v in env.items() if k in SECRET_KEYS}
    ignored = [k for k in env if k not in CM_KEYS and k not in SECRET_KEYS]
    print(f"\n📋 ConfigMap {CM}: {', '.join(sorted(cm_updates)) or '(nič)'}")
    print(f"📋 Secret {SECRET}: {', '.join(sorted(sec_updates)) or '(nič)'}")
    if ignored:
        print(f"ℹ️  Preskočeni (neznani/notranji): {', '.join(sorted(ignored))}")

    ok = input("\n⚠️  Posodobim produkcijo? (da/NE): ").strip().lower()
    if ok != "da":
        print("Preklicano — nič ni spremenjeno.")
        sys.exit(0)

    # ── ConfigMap ──
    if cm_updates:
        payload = json.dumps({"data": cm_updates})
        kubectl("patch", "configmap", "-n", NS, CM, "--type", "merge", "-p", payload)
        print(f"✅ ConfigMap {CM}: {', '.join(sorted(cm_updates))}")

    # ── Secret (base64) ──
    if sec_updates:
        data = {k: base64.b64encode(v.encode()).decode() for k, v in sec_updates.items()}
        payload = json.dumps({"data": data})
        kubectl("patch", "secret", "-n", NS, SECRET, "--type", "merge", "-p", payload)
        print(f"✅ Secret {SECRET}: {', '.join(sorted(sec_updates))}")

    print("\n🎉 Končano! Restartaj deployment:")
    print("   kubectl rollout restart deployment -n sola-app sola-app")
    print("   kubectl rollout status deployment -n sola-app sola-app --timeout=120s")


if __name__ == "__main__":
    main()
