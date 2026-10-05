# Hermes agent na Oracle VM (namestitev + preselitev + omejitev dostopa)

Namen: na VM teče aplikacija (Docker) IN Hermes agent, ki je dosegljiv samo tebi.

---

## A. Prvi koraki na VM (ko se prvič povežeš)

```bash
ssh ubuntu@<JAVNI_IP>

# 1) Geslo za sudo — VPIŠI GA SAM (naj ne gre skozi chat/dnevnik):
sudo passwd ubuntu

# 2) Osnovna orodja
sudo apt-get update && sudo apt-get install -y git curl ca-certificates

# 3) (priporočeno) SSH omeji na svoj IP:
#    Oracle → Networking → VCN → Subnets → (public subnet) → Security Lists →
#    Default Security List → Ingress za port 22 → spremeni Source iz 0.0.0.0/0 v <TVOJ-IP>/32
curl -s ifconfig.me; echo      # to je tvoj javni IP (doma/služba)
```

## B. Namestitev Hermesa

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"       # dodaj v ~/.bashrc, da velja tudi naslednjič
hermes --version
hermes doctor
```

## C. Model in ključ

Ključ živi v `~/.hermes/.env` (nikoli v gitu). Npr. OpenRouter:

```bash
nano ~/.hermes/.env        # OPENROUTER_API_KEY=<tvoj-ključ>
hermes model               # izbira ponudnika/modela (interaktivno)
hermes config set model.default <provider>/<model>
```

## D. Preselitev spomina in skillov (iz CusinM15/documentation)

Spomin + skilli so izvoženi v repu `CusinM15/documentation`, mapa `agent-memory/`
(brez skrivnosti — glej `scripts/ocisti-skrivnosti.py`).

```bash
git clone https://github.com/CusinM15/documentation.git ~/agent-memory-repo
mkdir -p ~/.hermes/memories ~/.hermes/skills ~/.hermes/cron

cp -r ~/agent-memory-repo/agent-memory/memories/. ~/.hermes/memories/
cp -r ~/agent-memory-repo/agent-memory/skills/.   ~/.hermes/skills/
cp    ~/agent-memory-repo/agent-memory/SOUL.md    ~/.hermes/SOUL.md 2>/dev/null || true
cp -r ~/agent-memory-repo/agent-memory/cron/.     ~/.hermes/cron/   2>/dev/null || true

hermes skills list          # preveri, da so skilli tu
hermes memory status
```

Osvežitev spomina pozneje: v repu je `agent-memory/scripts/izvoz-spomina.py`.

## E. Da Hermes govori SAMO s tabo

**Možnost 1 — Discord (priporočeno, dela tudi ko nisi prijavljen):**
```bash
hermes gateway setup        # izberi Discord, vpiši bot token
hermes gateway install      # teče v ozadju
sudo loginctl enable-linger $USER   # preživi odjavo SSH
hermes gateway status
```
Prvič, ko botu pišeš v DM, bo zahteval odobritev:
```bash
hermes pairing list         # vidiš zahteve
hermes pairing approve <id> # odobriš SAMO sebe
```
Neodobreni uporabniki ne dobijo odgovora. Občasno preveri `hermes pairing list`.

**Možnost 2 — samo CLI prek SSH:** agent teče le, ko si prijavljen; dostop omejiš tako, da v
Security List dovoliš port 22 samo s svojega IP-ja (korak A3).

**Možnost 3 — API/Webhook:** če kdaj izpostaviš, omeji vir na svoj IP in uporabi žeton.

Varnost:
- Gateway NE posluša javno (nobene odprte porte razen 80/443 za aplikacijo).
- Ne dodajaj portov 8001/8002/API v Oracle Security List.
- Skrivnosti (bot token, API ključi) samo v `~/.hermes/.env`.

## F. Preverjanje, da vse dela

```bash
hermes chat -q "preveri: docker compose -f ~/reservation_app_sell/deploy/oracle/docker-compose.yml \
  -f ~/reservation_app_sell/deploy/oracle/docker-compose.ip.yml ps"
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8002/health   # 200
```

## G. Aplikacija na isti VM

```bash
git clone https://github.com/CusinM15/reservation_app_sell.git
cd reservation_app_sell/deploy/oracle
cp .env.example .env && nano .env     # BASE_HOST=<IP>, BASE_URL=http://<IP>, SECRET_KEY, POSTGRES_PASSWORD, MAIN_ADMIN_PASSWORD
./bootstrap.sh                        # sam doda swap, odpre 80/443, pull slike, požene stack
```
