# Namestitev na Oracle Cloud (Always Free)

Ena VM gosti CELO aplikacijo za VSE šole (app je večšolski): PostgreSQL + aplikacija +
Caddy (samodejni HTTPS). Slika je ista kot na k3s (ARM verzija se zgradi kar na VM).

Poraba ene šole je majhna (~0,2 GB RAM, ~0,2 vCPU, <1 GB diska), zato Always Free
(2 OCPU / 12 GB) zdrži zelo veliko šol. Gostovanje = 0 €.

---

## 1. Oracle račun in VM

1. Registriraj se na https://www.oracle.com/cloud/free/ (rabiš kartico za preverjanje).
   Ob prijavi izberi regijo v EU (npr. Frankfurt ali Amsterdam).
2. **Compute → Instances → Create Instance**:
   - Image: **Ubuntu 24.04** (ali Canonical Ubuntu 22.04)
   - Shape: **VM.Standard.A1.Flex** (ARM Ampere) → **2 OCPU, 12 GB RAM**
     (to je v Always Free kvoti)
   - SSH ključ: naloži svoj javni ključ (ali pusti Oracle, da ga ustvari)
3. Po ustvarjanju si zapiši **javni IP** (Public IP address).

> Alternativa brez ARM: 2× VM.Standard.E2.1.Micro (x86, 1/8 OCPU, 1 GB) — app na eni,
> baza na drugi. Bolj tesno, a tudi zastonj.

## 2. Odpri vrata 80 in 443

V **Networking → Virtual Cloud Networks → (tvoja VCN) → Security Lists → Default Security List**:
dodaj Ingress Rules:
- Source `0.0.0.0/0`, IP Protocol TCP, Destination Port `80`
- Source `0.0.0.0/0`, IP Protocol TCP, Destination Port `443`
(22 za SSH je običajno že odprt.)

## 3. Namesti Docker in git (na VM)

```bash
sudo apt-get update && sudo apt-get install -y git ca-certificates curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
```

## 4. Prenesi in zaženi aplikacijo

```bash
git clone https://github.com/CusinM15/reservation_app_sell.git
cd reservation_app_sell/deploy/oracle

cp .env.example .env
nano .env
```

V `.env` obvezno izpolni:
- `BASE_HOST` in `BASE_URL` (npr. `app.tvoja-domena.si` / `https://app.tvoja-domena.si`)
- naključna skrivnostna niza za `SECRET_KEY` in `POSTGRES_PASSWORD`
  (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`)
- močno geslo za `MAIN_ADMIN_PASSWORD`
- pošto (`MAIL_*`), če želiš obvestila/obnovitev gesla/backup po e-pošti

Nato:

```bash
docker compose up -d --build      # prvi zagon traja nekaj minut (apt + pip)
docker compose ps                 # vsi trije: db, app, caddy → »running«
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8002/health   # 200
```

## 5. Domena in HTTPS

V Cloudflare (ali pri svojem registrarju) naredi **A zapis**: `app.tvoja-domena.si` → javni IP VM.
Caddy ob prvem obisku sam pridobi veljavno potrdilo (Let's Encrypt) — vrata 80/443 morata biti odprta.

Preveri: `https://app.tvoja-domena.si/health` → `{"status":"ok"}` ali podobno.

## 6. Prva prijava in cene

1. Prijavi se kot glavni admin (`MAIN_ADMIN_USERNAME` / `MAIN_ADMIN_PASSWORD` iz `.env`).
2. **Naročnina (stranska vrstica / narocnina) → Nastavitve prodaje**:
   - Prodaja naročnin: **vklopljena**
   - Cena — pol leta (€): **7**
   - Cena — leto (€): **13**
   - PayPal povezava + navodila ob plačilu
   - Shrani.
3. Nova šola se registrira na `/registracija`; sama izbere **pol leta (7 €)** ali **leto (13 €)**.

## 7. Nočna varnostna kopija (cron)

```bash
crontab -e
# dodaj:
15 4 * * * /home/ubuntu/reservation_app_sell/deploy/oracle/backup.sh >> /home/ubuntu/sola-backup.log 2>&1
```

Kopije (.sql po šolah) ostanejo v Docker volumnu `backups`:
`docker compose run --rm backup` (ročno) oz. `docker compose --profile backup run --rm backup`.
Če želiš kopije še po e-pošti, odstrani `--no-email` v `docker-compose.yml` (storitev `backup`)
in izpolni `BACKUP_EMAIL` / `MAIL_*`.

## Posodobitve

```bash
cd reservation_app_sell && git pull
cd deploy/oracle && docker compose up -d --build
```

## Kaj moraš vedeti

- **Always Free:** brez SLA/podpore; Oracle lahko pobere »idle« instanco in v skrajnem primeru
  zapre račun. Zato naj nočne `.sql` kopije letijo tudi izven VM (e-pošta). Za produkcijsko
  prodajo razmisli o Pay-As-You-Go (mikro poraba, ~9 €/mes) ali majhnem VPS.
- **Ena VM = ena točka odpovedi.** Če pade, padejo vse šole hkrati.
- **ARM:** slika `python:3.11-slim` je večarhitekturna, zato se na ARM VM zgradi brez težav.
- **GDPR:** podatki so osebni (učenci) → izberi EU regijo, uredi pogodbo o obdelavi.
- Fiksni stroški so samo domena (~12 €/leto) — gostovanje je 0 €.
