# Namestitev na Oracle Cloud (Always Free)

Ena VM gosti CELO aplikacijo za VSE šole (app je večšolski): PostgreSQL + aplikacija +
(neobvezno) Caddy za samodejni HTTPS. Slika je ista kot na k3s — ARM verzija se zgradi kar na VM.

Poraba ene šole je majhna (~0,2 GB RAM, ~0,2 vCPU, <1 GB diska), zato Always Free
(2 OCPU / 12 GB) zdrži zelo veliko šol. Gostovanje = 0 €.

> Hitra pot brez domene: aplikacija je dosegljiva kar na `http://<JAVNI_IP>`.
> Točno tako narediš spodaj (koraki 1–5, uporabiš `docker-compose.ip.yml`).

---

## 1. Oracle račun in VM

1. Registriraj se na https://www.oracle.com/cloud/free/ (rabiš kartico za preverjanje).
   Ob prijavi izberi **Home Region v EU** (npr. Frankfurt / Amsterdam) — regije pozneje
   ni mogoče zamenjati.
2. **Compute → Instances → Create instance**. Izpolni:
   - **Name**: `sola-app`
   - **Image**: **Ubuntu 24.04** (Canonical Ubuntu)
   - **Shape**: klikni *Change shape* → zavihek **Ampere** → **VM.Standard.A1.Flex**
     → **OCPUs = 2**, **Memory = 12 GB** (to je Always Free kvota)
     *Če ARM ni na voljo (»out of capacity«): vzemi **VM.Standard.E2.1.Micro** (x86, 1/8 OCPU, 1 GB) —
     zastonj, a tesno; takrat bazo in app lažje tečeš na isti VM.*
   - **Networking**: pusti privzeto (nova VCN) — **Assign a public IPv4 address: Yes**
   - **Add SSH keys**: prilepi svoj javni ključ (`~/.ssh/id_ed25519.pub`) ali pusti
     *Generate a key pair* in prenesi zasebni ključ
   - **Boot volume**: privzeto (50 GB) je v Always Free
3. Klikni **Create**. Po ~1 minuti instanca teče; na seznamu si zapiši **Public IP address**.

## 2. Odpri vrata 80 in 443 (DVE mesti!)

**(a) Oracle Security List**
Networking → Virtual Cloud Networks → *(tvoja VCN)* → Security Lists → **Default Security List** →
**Add Ingress Rules** (dvakrat):
- Source CIDR `0.0.0.0/0`, IP Protocol **TCP**, Destination Port Range **80**
- Source CIDR `0.0.0.0/0`, IP Protocol **TCP**, Destination Port Range **443**

**(b) Notranji firewall VM-ja (pri Oraclu pogosta past!)**
Ubuntu slike pri Oraclu imajo vgrajene iptables rule, ki spustijo samo SSH — tudi ko je
Security List odprt, promet na 80/443 ne pride skozi. Zato na VM (prek SSH, glej korak 3):

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 3. SSH na VM in namestitev Docker + git

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@<JAVNI_IP>

sudo apt-get update
sudo apt-get install -y git ca-certificates curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker                      # ali: odjavi se in nazaj
```

## 4. Prenesi aplikacijo in nastavi .env

```bash
git clone https://github.com/CusinM15/reservation_app_sell.git
cd reservation_app_sell/deploy/oracle
cp .env.example .env
nano .env
```

V `.env` za dostop prek IP-ja nastavi:

```
BASE_HOST=<JAVNI_IP>
BASE_URL=http://<JAVNI_IP>
```

in izpolni še:
- naključna niza za `SECRET_KEY` in `POSTGRES_PASSWORD`
  (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`)
- močno geslo `MAIN_ADMIN_PASSWORD`
- pošto (`MAIL_*`) — brez nje ne delujeta obnova gesla in backup po e-pošti

## 5. Zaženi (dostop prek javnega IP)

```bash
docker compose -f docker-compose.yml -f docker-compose.ip.yml up -d --build
# prvi zagon traja nekaj minut (apt + pip)
docker compose ps
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8002/health     # 200
```

Z računalnika preveri še od zunaj:

```
http://<JAVNI_IP>/health          → {"status": ...}
http://<JAVNI_IP>/auth/login      → prijava
```

Prijavi se kot glavni admin (`MAIN_ADMIN_USERNAME` / `MAIN_ADMIN_PASSWORD` iz `.env`).

## 6. Ko dobiš domeno (preklop na HTTPS)

1. V Cloudflare naredi **A zapis** `app.tvoja-domena.si` → `<JAVNI_IP>`.
2. V `.env` popravi `BASE_HOST=app.tvoja-domena.si` in `BASE_URL=https://app.tvoja-domena.si`.
3. Ustavi IP-različico in zaženi privzeto (s Caddyjem, ki sam pridobi certifikat):

```bash
docker compose -f docker-compose.yml -f docker-compose.ip.yml down
docker compose up -d --build
```

## 7. Nočna varnostna kopija (cron)

```bash
crontab -e
# dodaj:
15 4 * * * /home/ubuntu/reservation_app_sell/deploy/oracle/backup.sh >> /home/ubuntu/sola-backup.log 2>&1
```

Kopije `.sql` (po šolah) ostanejo v Docker volumnu `backups`.

## Posodobitve aplikacije

```bash
cd ~/reservation_app_sell && git pull
cd deploy/oracle
docker compose -f docker-compose.yml -f docker-compose.ip.yml up -d --build   # ali brez .ip.yml, če imaš domeno
```

## Cene naročnin

Na sveži bazi sta privzeti ceni že pravi: **pol leta = 7 €**, **leto = 13 €**; šola ob nakupu
izbere obdobje. V **Naročnina → Nastavitve prodaje** le vklopi *Prodaja naročnin* in vnesi
PayPal povezavo + navodila ob plačilu.

## Kaj moraš vedeti

- **Always Free:** brez SLA/podpore; Oracle lahko pobere »idle« instanco in v skrajnem primeru
  zapre račun. Zato nočne `.sql` kopije pošiljaj tudi izven VM (e-pošta).
- **Ena VM = ena točka odpovedi** (zdaj ima k3s 2 vozlišči + 3-članski Postgres).
- **ARM:** slika `python:3.11-slim` je večarhitekturna → na ARM VM se zgradi brez težav.
- **GDPR:** podatki so osebni (učenci) → EU regija + pogodba o obdelavi.
- Fiksni strošek je le domena (~12 €/leto) — gostovanje je 0 €.
