#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# deploy/oracle/install-hermes.sh — namesti Hermes agenta na VM in preseli
# spomin + skille iz repa CusinM15/documentation (mapa agent-memory/).
#
# Zagon na VM (znotraj kloniranega repa):
#   cd ~/reservation_app_sell/deploy/oracle
#   ./install-hermes.sh
#
# Kaj naredi:
#   1) namesti Hermes agenta (uradni install.sh), če ga še ni
#   2) klonira/posodobi CusinM15/documentation
#   3) v ~/.hermes/ preseli: memories/ (MEMORY.md, USER.md), skills/, SOUL.md, cron/
#   4) preveri namestitev in izpiše, kaj še moraš nastaviti (ključ, gateway)
#
# Skrivnosti (API ključi, bot tokeni) se NIKOLI ne prenašajo — ostanejo samo
# na VM v ~/.hermes/.env.
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

MEM_REPO_URL="https://github.com/CusinM15/documentation.git"
MEM_REPO="${HOME}/agent-memory-repo"
HH="${HERMES_HOME:-$HOME/.hermes}"

echo "=== 1/4  Hermes agent"
if command -v hermes >/dev/null 2>&1; then
    echo "že nameščen: $(hermes --version 2>/dev/null || echo '?')"
else
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
fi
export PATH="${HOME}/.local/bin:${PATH}"
grep -q '.local/bin' "${HOME}/.bashrc" 2>/dev/null || \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${HOME}/.bashrc"

echo "=== 2/4  Izvoz spomina in skillov (CusinM15/documentation)"
if [ -d "${MEM_REPO}/.git" ]; then
    git -C "${MEM_REPO}" pull --rebase --quiet || true
else
    git clone --quiet "${MEM_REPO_URL}" "${MEM_REPO}"
fi
SRC="${MEM_REPO}/agent-memory"
[ -d "${SRC}" ] || { echo "NAPAKA: v repu ni mape agent-memory/"; exit 1; }

echo "=== 3/4  Preselitev v ${HH}"
mkdir -p "${HH}/memories" "${HH}/skills" "${HH}/cron"

# Obstoječe nastavitve ohranimo (config.yaml in .env se NIKOLI ne prepišeta).
[ -f "${HH}/memories/MEMORY.md" ] && cp "${HH}/memories/MEMORY.md" \
    "${HH}/memories/MEMORY.md.bak.$(date +%Y%m%d%H%M)" || true

cp -r "${SRC}/memories/." "${HH}/memories/"
cp -r "${SRC}/skills/."   "${HH}/skills/"
[ -f "${SRC}/SOUL.md" ] && cp "${SRC}/SOUL.md" "${HH}/SOUL.md" || true
[ -f "${SRC}/cron/jobs.json" ] && cp "${SRC}/cron/jobs.json" "${HH}/cron/jobs.json" || true

chmod 700 "${HH}" 2>/dev/null || true
[ -f "${HH}/.env" ] && chmod 600 "${HH}/.env" || true

echo "=== 4/4  Preverjanje"
echo -n "  spomin: "; ls "${HH}/memories" | tr '\n' ' '; echo
echo -n "  skillov: "; find "${HH}/skills" -name SKILL.md | wc -l
hermes --version 2>/dev/null || true
echo
echo "── Kaj še moraš nastaviti ──────────────────────────────────────────"
echo "1) Ključ za model (npr. OpenRouter) — vpiši ga SAM, naj ne gre skozi chat:"
echo "     nano ${HH}/.env          # vpiši svoj ključ za model (npr. OPENROUTER_API_KEY)"
echo "     hermes doctor"
echo
echo "2) Da Hermes govori SAMO s tabo (Discord):"
echo "     hermes gateway setup     # izberi Discord, vpiši bot token"
echo "     hermes gateway install"
echo "     sudo loginctl enable-linger \$USER"
echo "     hermes pairing list      # tu odobriš SAMO sebe:  hermes pairing approve <id>"
echo
echo "3) Preveri, da vidiš svoj spomin in skille:"
echo "     hermes chat -q 'Kaj veš o meni in o aplikaciji reservation_app?'"
echo "     hermes skills list | head"
echo
echo "Opomba: SSH vrata 22 omeji na svoj IP (Oracle Security List) — glej HERMES.md."
