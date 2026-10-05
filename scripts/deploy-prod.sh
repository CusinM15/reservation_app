#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# scripts/deploy-prod.sh — povleci spremembe z GitHuba in objavi v produkcijo
#
# Namen: en ukaz, ki naredi CELOTEN tok objave:
#   1. git fetch + fast-forward pull (tvoje commite z GitHuba)
#   2. docker build + docker push slike
#   3. kubectl rollout restart + status (zero-downtime)
#   4. hiter health-check (pričakuje HTTP 200)
#
# Uporaba:
#   scripts/deploy-prod.sh                 # pull + build + push + rollout + preverjanje
#   FORCE=1 scripts/deploy-prod.sh         # tudi če ni novih commitov
#   NO_BUILD=1 scripts/deploy-prod.sh      # ne gradi slike (samo pull + rollout)
#   APP_URL= scripts/deploy-prod.sh        # preskoči health-check
#
# Nastavljivo z okoljskimi spremenljivkami (privzete vrednosti v oklepajih):
#   IMAGE      (mato12345/sola-app:latest)   slika, ki jo zgradimo/objavimo
#   NAMESPACE  (sola-app)                    Kubernetes namespace
#   DEPLOYMENT (sola-app)                    ime deployment-a
#   BRANCH     (main)   REMOTE (origin)      veja/remote
#   APP_URL    (https://ostc-app.org)        URL za health-check
#   KUBECONFIG (/etc/rancher/k3s/k3s.yaml)   kubeconfig za kubectl
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Delovna mapa = koren repozitorija (mapa nad scripts/).
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

IMAGE="${IMAGE:-mato12345/sola-app:latest}"
NAMESPACE="${NAMESPACE:-sola-app}"
DEPLOYMENT="${DEPLOYMENT:-sola-app}"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
APP_URL="${APP_URL:-https://ostc-app.org}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*" >&2; }
die() { printf '\n\033[1;31mNAPAKA: %s\033[0m\n' "$*" >&2; exit 1; }

# ── 0. Preveri orodja ─────────────────────────────────────────────────
for cmd in git docker kubectl; do
  command -v "$cmd" >/dev/null 2>&1 || die "manjka ukaz '$cmd' (namesti ga ali popravi PATH)."
done

# ── 1. Preveri, da ni lokalnih (sledenih) sprememb ────────────────────
# (Urejaš prek GitHuba, zato naj bo delovna kopija čista; untracked datoteke
#  pull-a ne motijo.)
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  warn "Imaš lokalne spremembe sledenih datotek:"
  git status --short --untracked-files=no >&2
  die "najprej jih commitaj ali shrani (git stash), sicer pull/objava ni varna."
fi

# ── 2. Pull (fast-forward) ────────────────────────────────────────────
log "Povlečem z $REMOTE/$BRANCH"
BEFORE="$(git rev-parse HEAD)"
git fetch "$REMOTE" "$BRANCH"
if ! git merge --ff-only "$REMOTE/$BRANCH"; then
  die "zgodovina se je razdvojila (diverged) — naredi 'git pull --rebase $REMOTE $BRANCH' ročno, nato poženi skripto znova."
fi
AFTER="$(git rev-parse HEAD)"

if [ "$BEFORE" = "$AFTER" ] && [ "${FORCE:-0}" != "1" ] && [ "${NO_BUILD:-0}" != "1" ]; then
  log "Ni novih sprememb (HEAD = $(git rev-parse --short "$AFTER")). Nič za objaviti."
  echo "   (za vsiljeno objavo: FORCE=1 $0)"
  exit 0
fi

log "Spremembe, ki jih objavljam:"
git --no-pager log --oneline "$BEFORE..$AFTER" 2>/dev/null | sed 's/^/    /' || true
[ "$BEFORE" = "$AFTER" ] && echo "    (brez novih commitov — FORCE)"

# ── 3. Build + push slike ─────────────────────────────────────────────
if [ "${NO_BUILD:-0}" != "1" ]; then
  log "Gradim sliko: $IMAGE"
  docker build -t "$IMAGE" .
  log "Pošiljam sliko v register: $IMAGE"
  docker push "$IMAGE"
else
  log "NO_BUILD=1 — preskočim gradnjo in pošiljanje slike."
fi

# ── 4. Rollout ────────────────────────────────────────────────────────
log "Ponovni zagon $NAMESPACE/$DEPLOYMENT"
kubectl -n "$NAMESPACE" rollout restart "deployment/$DEPLOYMENT"
kubectl -n "$NAMESPACE" rollout status "deployment/$DEPLOYMENT" --timeout=180s

# ── 5. Health-check ───────────────────────────────────────────────────
if [ -n "$APP_URL" ] && command -v curl >/dev/null 2>&1; then
  log "Preverjam $APP_URL"
  ok=0
  for i in $(seq 1 12); do
    code="$(curl -s -o /dev/null -w '%{http_code}' -L "$APP_URL" || true)"
    printf '    poskus %2d: HTTP %s\n' "$i" "${code:-?}"
    if [ "$code" = "200" ]; then ok=1; break; fi
    sleep 6
  done
  [ "$ok" = "1" ] || die "aplikacija na $APP_URL ne odgovarja 200 — preveri: kubectl -n $NAMESPACE get pods"
fi

log "KONČANO ✅  objavljeno: $(git rev-parse --short "$AFTER") — $(git log -1 --format=%s "$AFTER")"
