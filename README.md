# Šolski App – Reservation & Assessment Management

Spletna aplikacija za OŠ Toneta Čufarja Jesenice za rezervacije prostorov (tablice, računalnica, ladja) in napovedovanje ocenjevanj.

---

## 📦 Tehnologije

| Sloj | Tehnologija |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Podatkovna baza | SQLite (preko SQLAlchemy ORM) |
| Frontend | Jinja2 template, plain HTML/CSS/JS |
| Avtentikacija | cookie-based session z bcrypt hashom |
| Email | SMTP preko Arnesa (`mail.arnes.si`) |

---

## 🚀 Namestitev in zagon

### Prvi zagon

```bash
# 1. Pojdi v mapo projekta
cd /home/admin_os/reservation_app

# 2. Ustvari virtualno okolje (samo prvič)
python3 -m venv .res_app

# 3. Aktiviraj in namesti odvisnosti
source .res_app/bin/activate
pip install -r requirements.txt

# 4. Preveri .env datoteko (prilagodi po potrebi)
cat .env

# 5. Zaženi aplikacijo
.res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002
```

### Ponovni zagon

```bash
# Če je proces že zagnan, ga najprej ubij
fuser -k 8002/tcp 2>/dev/null
sleep 2

# Nato zaženi
cd /home/admin_os/reservation_app
nohup .res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 > /tmp/sola-app.log 2>&1 &
```

### Preverjanje, ali aplikacija teče

```bash
# Preveri process
ps aux | grep uvicorn | grep -v grep
# ali
ss -tlnp | grep 8002

# Preveri health endpoint
curl -s http://127.0.0.1:8002/health
# Pričakovan odgovor: {"status":"ok","version":"0.1.0"}
```

### Dnevnik (log)

```bash
# Zadnjih N vrstic
tail -50 /tmp/sola-app.log

# Spremljaj v realnem času
tail -f /tmp/sola-app.log
```

---

## 🛠️ Vzdrževanje

### Posodobitev kode (git pull)

```bash
cd /home/admin_os/reservation_app

# 1. Povleci spremembe
git pull

# 2. Počisti morebitne stare datoteke (če je kaj izbrisano v repu)
git clean -fd

# 3. Restartaj aplikacijo
fuser -k 8002/tcp 2>/dev/null
sleep 2
nohup .res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 > /tmp/sola-app.log 2>&1 &

# 4. Preveri, da je vse OK
sleep 3
curl -s http://127.0.0.1:8002/health
```

### Spreminjanje konfiguracije

Vse nastavitve so v `.env` datoteki. Po spremembi je potreben restart aplikacije.

| Ključ | Privzeto | Opis |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Naslov za bind |
| `APP_PORT` | `8001` | Vrata za HTTP |
| `SECRET_KEY` | – | Skrivnost za morebitne kriptografske operacije |
| `DB_PATH` | `./data/sola.db` | Pot do SQLite datoteke |
| `TABLICE_MAX` | `28` | Kapaciteta tablic |
| `SCHEDULE` | JSON objekt | Urnik – indeks ure → časovni interval |
| `RAZREDI` | CSV | Seznam vseh razredov |
| `PROSTORI` | CSV | Seznam prostorov (tablice,racunalnica,ladja) |
| `MAIL_*` | – | Nastavitve za Arnes SMTP |

---

## 👤 Uporabniki

### Privzeti admin

Ob prvem zagonu se samodejno ustvari admin uporabnik:

| Polje | Vrednost |
|---|---|
| Uporabniško ime | `admin` |
| Geslo | `admin123` |
| Vloga | `admin` |

**Takoj po namestitvi spremenite geslo!**

### Ustvarjanje novih uporabnikov

1. Prijavite se kot admin.
2. V navigaciji kliknite **Admin panel**.
3. Izpolnite obrazec "Dodaj uporabnika".

### Vloge

| Vloga | Opis |
|---|---|
| `teacher` | Osnovni učitelj – lahko rezervira prostore in napoveduje ocenjevanja |
| `vodstvo` | Kot učitelj + lahko briše tuje rezervacije/ocenjevanja + upravlja zasedene datume |
| `admin` | Polne pravice + admin panel za upravljanje uporabnikov |

---

## 🗄️ Podatkovna baza

### Lokacija

Privzeto: `./data/sola.db` (relativna pot glede na koren projekta).

### Struktura

Baza se ustvari **samodejno** ob prvem zagonu. Tabele:

- `users` – uporabniki
- `reservations` – rezervacije prostorov
- `assessments` – napovedana ocenjevanja
- `blocked_dates` – zasedeni datumi

### Varnostno kopiranje

Ker je baza SQLite, lahko preprosto kopirate datoteko:

```bash
# Varnostna kopija
cp ./data/sola.db ./data/sola.db.backup-$(date +%Y%m%d-%H%M)

# Obnovitev
cp ./data/sola.db.backup-YYYYMMDD-HHMM ./data/sola.db
```

**Pred obnovitvijo ustavite aplikacijo!**

```bash
fuser -k 8002/tcp 2>/dev/null
cp ./data/sola.db.backup-20250525-1200 ./data/sola.db
# nato ponovno zaženite aplikacijo
```

---

## 💥 Reševanje težav

### Aplikacija se ne zažene

**1. Preveri dnevnik:**
```bash
cat /tmp/sola-app.log
```

**2. Pogoste napake:**

| Napaka | Vzrok | Rešitev |
|---|---|---|
| `Address already in use` | Vrata so zasedena | `fuser -k 8002/tcp` |
| `No module named uvicorn` | Virtualno okolje ni aktivirano ali ni nameščeno | `.res_app/bin/pip install -r requirements.txt` |
| `No such file or directory: './data/sola.db'` | Manjka mapa `data` | `mkdir -p ./data` |
| `Permission denied` | Ni pravic za pisanje v bazo | `chown -R admin_os:admin_os ./data` |

**3. Preveri health:**
```bash
curl -s http://127.0.0.1:8002/health
```

### Email ne deluje

1. Preverite nastavitve v `.env`:
   - `MAIL_SERVER=mail.arnes.si`
   - `MAIL_PORT=587`
   - `MAIL_USERNAME=oscuf`
   - `MAIL_PASSWORD=...`

2. Testirajte povezavo:
```bash
python3 -c "
import smtplib, ssl
from app.config import settings
context = ssl.create_default_context()
s = smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=10)
s.starttls(context=context)
s.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
print('SMTP OK')
s.quit()
"
```

### Baza je zaklenjena (database is locked)

SQLite ne podpira sočasnega pisanja iz več procesov. Preverite, da ne tečeta dva instance aplikacije:

```bash
ps aux | grep uvicorn
fuser -k 8002/tcp 2>/dev/null
sleep 1
# nato poženite samo eno instanco
```

---

## 🔄 Zamenjava master strežnika (ko glavni crkne)

Aplikacija trenutno teče na enem strežniku. V primeru okvare:

### ✅ Če je podatkovna baza shranjena na Longhorn volumnu (Kubernetes)

Aplikacija naj bi v prihodnosti tekla v Kubernetes okolju z Longhorn za persistent storage.

```bash
# 1. Na novem strežniku kloniraj repozitorij
git clone https://github.com/os-tc-jesenice/reservation_app.git
cd reservation_app

# 2. Pripravi okolje
python3 -m venv .res_app
source .res_app/bin/activate
pip install -r requirements.txt

# 3. Poveži Longhorn volume
# Če Longhorn volume mountaš na /mnt/longhorn/sola:
ln -s /mnt/longhorn/sola/data ./data

# 4. Kopiraj .env
# scp user@old-server:/home/admin_os/reservation_app/.env ./.env

# 5. Zaženi
nohup .res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 > /tmp/sola-app.log 2>&1 &

# 6. Preveri
sleep 3
curl -s http://127.0.0.1:8002/health

# 7. Preusmeri DNS / proxy na nov IP
```

### ✅ Če je podatkovna baza samo na starem strežniku (ni skupnega diska)

```bash
# 1. Na starem stroju (če še deluje) ustvari varnostno kopijo baze
cd /home/admin_os/reservation_app
cp ./data/sola.db ./data/sola.db.backup

# 2. Kopiraj celoten projekt na nov strežnik
rsync -avz --progress /home/admin_os/reservation_app/ user@new-server:/home/admin_os/reservation_app/

# ali preko scp:
# scp -r /home/admin_os/reservation_app/ user@new-server:/home/admin_os/reservation_app/

# 3. Na novem strežniku aktiviraj okolje in zaženi
cd /home/admin_os/reservation_app
source .res_app/bin/activate
pip install -r requirements.txt  # če so se spremenile odvisnosti
fuser -k 8002/tcp 2>/dev/null
nohup .res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 > /tmp/sola-app.log 2>&1 &

# 4. Preveri
sleep 3
curl -s http://127.0.0.1:8002/health

# 5. Posodobi DNS ali proxy, da kaže na nov strežnik
```

### ✅ Če stari strežnik ne deluje več in nimate backup-a baze

1. Klonirajte repo na nov strežnik.
2. Zaženite aplikacijo – baza se bo ustvarila prazna, vključno z admin uporabnikom.
3. Uvozite uporabnike preko admin panela (ali preko `scripts/import_users.py` če obstaja CSV).
4. **Podatki o rezervacijah in ocenjevanjih bodo izgubljeni** – zato redno delajte backup baze.

---

## ➕ Dodajanje worker strežnika (load balancing)

Aplikacija trenutno ni zasnovana za več workerjev zaradi SQLite baze (ne podpira sočasnega pisanja). Če želite dodati worker:

### Opcija 1: Read-only worker (za pregledovanje)

```bash
# Na worker strežniku
git clone https://github.com/os-tc-jesenice/reservation_app.git
cd reservation_app

# Ustvari okolje
python3 -m venv .res_app
source .res_app/bin/activate
pip install -r requirements.txt

# Kopiraj .env
scp user@master-server:/home/admin_os/reservation_app/.env ./.env

# Bazo mountaj iz Longhorn volume (če je na skupnem storage-u):
ln -s /mnt/longhorn/sola/data ./data
# Ali pa občasno sinkroniziraj:
# rsync -av user@master-server:/home/admin_os/reservation_app/data/sola.db ./data/sola.db

# Zaženi na drugih vratih (npr. 8003)
nohup .res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8003 > /tmp/sola-app.log 2>&1 &
```

**Omejitev:** Worker lahko služi samo za pregledovanje. Rezervacije in ocenjevanja bodo padla, ker SQLite ne podpira sočasnega pisanja.

### Opcija 2: Zamenjava SQLite s PostgreSQL (priporočeno za več workerjev)

Če želite pravi load balancing, **zamenjajte SQLite s PostgreSQL**:

1. Namestite PostgreSQL.
2. Spremenite `app/database.py`:
   ```python
   engine = create_engine("postgresql://user:password@localhost/sola")
   ```
3. Dodajte zahtevo v `requirements.txt`: `psycopg2-binary`.
4. Ponovno zaženite.

Nato lahko zaženete več worker procesov:

```bash
# Več workerjev na istem stroju
.res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 --workers 4

# Ali več instanc na različnih strojih pred proxyjem (nginx)
```

---

## 🔧 Service (systemd) – priporočen način zagona

Če želite, da aplikacija teče kot sistemska storitev in se samodejno zažene ob reboot-u:

```bash
# 1. Ustvari systemd service datoteko
sudo tee /etc/systemd/system/sola-app.service > /dev/null <<'EOF'
[Unit]
Description=Šolski App FastAPI
After=network.target

[Service]
Type=simple
User=admin_os
WorkingDirectory=/home/admin_os/reservation_app
ExecStart=/home/admin_os/reservation_app/.res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002
Restart=always
RestartSec=5
StandardOutput=append:/tmp/sola-app.log
StandardError=append:/tmp/sola-app.log

[Install]
WantedBy=multi-user.target
EOF

# 2. Omogoči in zaženi
sudo systemctl daemon-reload
sudo systemctl enable sola-app
sudo systemctl start sola-app

# 3. Preveri status
sudo systemctl status sola-app

# 4. Po pull-u restart
sudo systemctl restart sola-app
```

---

## 📁 Struktura projekta

```
reservation_app/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, middleware, startup
│   ├── config.py            # Nastavitve iz .env
│   ├── database.py          # SQLAlchemy engine, session
│   ├── models.py            # ORM modeli (User, Reservation, Assessment, BlockedDate)
│   ├── schemas.py           # Pydantic sheme
│   ├── race.py              # Race condition detection
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py          # Prijava, gesla, admin CRUD uporabnikov
│   │   ├── rezervacije.py   # Rezervacije prostorov
│   │   ├── ocenjevanja.py   # Napovedi ocenjevanj
│   │   └── blocked_dates.py # Zasedeni datumi
│   └── templates/
│       ├── index.html       # Glavna stran s koledarji
│       ├── login.html       # Prijavna stran
│       └── admin_users.html # Admin panel
├── data/
│   └── sola.db              # SQLite baza
├── .env                     # Konfiguracija
├── .res_app/                # Virtualno okolje
├── requirements.txt
├── navodila.md              # Navodila za uporabnike
└── README.md                # Tehnična dokumentacija
```

---

## 📧 Kontakt

Za tehnično podporo ali težave z aplikacijo kontaktirajte administratorja.
