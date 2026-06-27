# 🖥️ Postavi lokalni app

Navodila za zagon aplikacije **na enem računalniku** (brez Kubernetes, brez PostgreSQL).
Primerno za druge šole, testiranje ali demonstracijo.

> **Avtor:** Matej Čušin  
> **Šola:** OŠ Toneta Čufarja, Jesenice

---

## 1) Kaj rabiš

- **Python 3.11+** ali **Docker**
- Git (če želiš klonirati repo)
- Brskalnik (Chrome, Firefox, Edge)

---

## 2) Namestitev prek Docker (priporočeno)

### 2a) Priprava

```bash
# 1. Kloniraj repo
git clone https://github.com/mato12345/sola-app.git
cd sola-app

# 2. Uredi .env za lokalno uporabo (SQLite, brez emaila)
cp .env.example .env
```

`.env` naj vsebuje:

```env
APP_HOST=0.0.0.0
APP_PORT=8001
BASE_URL=http://localhost:8001
DATABASE_URL=sqlite:///./data/sola.db
TABLICE_MAX=28
SCHEDULE={"0":"07:30-08:15","1":"08:20-09:05","2":"09:15-10:00","3":"10:20-11:05","4":"11:10-11:55","5":"12:00-12:45","6":"12:50-13:35","7":"14:00-14:45"}
RAZREDI=1.a,1.b,2.a,2.b,3.a,3.b,4.a,4.b,5.a,5.b,6.a,6.b,7.a,7.b,8.a,8.b,9.a
PROSTORI=tablice,racunalnica,ladja
```

### 2b) Zgradi in zaženi

```bash
docker build -t sola-app .
docker run -d --name sola-app -p 8001:8001 \
  -v $(pwd)/data:/app/data \
  sola-app
```

Aplikacija je na **http://localhost:8001**.

Privzet dostop: `admin` / `admin123` (geslo takoj spremeni).

Ustavi:
```bash
docker stop sola-app && docker rm sola-app
```

---

## 3) Namestitev brez Dockerja (uvicorn)

### 3a) Priprava okolja

```bash
# 1. Kloniraj repo
git clone https://github.com/mato12345/sola-app.git
cd sola-app

# 2. Ustvari virtualno okolje
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Namesti odvisnosti
pip install -r requirements.txt

# 4. Uredi .env za lokalno uporabo
cp .env.example .env
# Uredi .env — poglej zgled zgoraj v točki 2a
```

### 3b) Zaženi

```bash
# Ustvari mapo za podatke
mkdir -p data

# Poženi
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

`--reload` pomeni samodejni restart ob spremembi kode (uporabno za razvoj).

Aplikacija: **http://localhost:8001**
Admin: `admin` / `admin123`

### 3c) Ustavi

`Ctrl+C` v terminalu.

---

## 4) Prvi zagon — kaj se zgodi?

Ob prvem zagonu aplikacija:
1. Ustvari SQLite bazo (`data/sola.db`)
2. Doda začetnega admin uporabnika (`admin` / `admin123`)
3. Vse je pripravljeno za uporabo

**Baza je prazna** — ni rezervacij, ni ocenjevanj, ni učiteljev.

---

## 5) Uvoz učiteljev

Če imaš javno objavljen seznam zaposlenih, lahko učitelje uvoziš samodejno.

### 5a) Namesti orodja

```bash
pip install requests beautifulsoup4 lxml
```

### 5b) Zaženi uvoz

```bash
# Če app teče na localhost:8001:
python3 scripts/import_teachers.py --base-url http://localhost:8001

# Samo poglej, kdo bi se uvozil (brez spreminjanja):
python3 scripts/import_teachers.py --base-url http://localhost:8001 --dry-run
```

### 5c) Prilagodi za svojo šolo

Uredi `scripts/import_teachers.py`:
1. Spremeni `SCRAPE_URL` na URL svojega seznama zaposlenih
2. Po potrebi popravi `ROLE_MAP` in `NON_TEACHING_TABS`

### 5d) Kako učitelji dostopajo?

1. Gredo na **http://localhost:8001** (ali tvoj URL)
2. Kliknejo **"Pozabljeno geslo"**
3. Vnesejo svoj email
4. Dobijo email z linkom za nastavitev gesla

Če nimaš email strežnika, lahko gesla nastaviš ročno prek admin panela.

---

## 6) Pomembne opombe

| Značilnost | Lokalno (SQLite) | Produkcija (PostgreSQL/k3s) |
|---|---|---|
| Baza | `data/sola.db` | PostgreSQL v k3s |
| Email | Ne deluje brez SMTP | Arnes mail |
| Vzdržljivost | Manj uporabnikov | Več uporabnikov, HA |
| Varnost | Samo za lokalni dostop | HTTPS prek Cloudflare proxyja |

---

## 7) Pogoste težave

| Težava | Rešitev |
|---|---|
| `Port already in use` | Spremeni `APP_PORT=8002` v `.env` |
| SQLite `database is locked` | Ustavi app, zbriši `data/sola.db`, zaženi znova |
| Učitelji niso uvoženi | Preveri `--dry-run` najprej |
| Ne vidim prostorov | Preveri `PROSTORI` v `.env` |
