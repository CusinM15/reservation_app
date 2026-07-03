# POSTAVI LOKALEN APP — Šolski App

Navodila za zagon aplikacije **na enem računalniku** (brez Kubernetes, brez PostgreSQL).
Primerno za druge šole, testiranje ali demonstracijo.

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
RAZREDI=1.a,1.b,1.c,2.a,2.b,2.c,3.a,3.b,3.c,4.a,4.b,4.c,5.a,5.b,5.c,6.a,6.b,6.c,7.a,7.b,7.c,8.a,8.b,8.c,8.1,8.2,8.3,8.4,8.5,9.a,9.b,9.c,9.1,9.2,9.3,9.4,9.5
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

Private dostop: `admin` / `admin123` (geslo takoj spremeni).

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

`--reload` pomeni, da se ob spremembi kode samodejno restart-a (uporabno za razvoj).

Aplikacija: **http://localhost:8001**
Admin: `admin` / `admin123`

### 3c) Ustavi

`Ctrl+C` v terminalu.

---

## 4) Prvi zagon — kaj se zgodi?

Ob prvem zagonu aplikacija:
1. ustvari SQLite bazo (`data/sola.db`)
2. doda začetnega admin uporabnika (`admin` / `admin123`)
3. vse je pripravljeno za uporabo

**Baza je prazna** — ni rezervacij, ni ocenjevanj, ni učiteljev.

---

## 5) Uvoz učiteljev s šolske spletne strani

Če imaš javno objavljen seznam zaposlenih (podobno kot OŠ Toneta Čufarja),
lahko učitelje uvoziš samodejno.

### 5a) Namesti orodja

```bash
pip install requests beautifulsoup4 lxml
```

### 5b) Zaženi uvoz

```bash
# Če app teče na localhost:8001:
python3 scripts/import_teachers.py --base-url http://localhost:8001

# Če app teče na drugem strežniku:
python3 scripts/import_teachers.py --base-url https://moja-sola.si

# Samo poglej, kdo bi se uvozil (brez spreminjanja):
python3 scripts/import_teachers.py --base-url http://localhost:8001 --dry-run
```

### 5c) Prilagodi za svojo šolo

Če imaš drugačno spletno stran, uredi `scripts/import_teachers.py`:

1. Spremeni `SCRAPE_URL` na URL svojega seznama zaposlenih
2. Po potrebi popravi `ROLE_MAP` in `NON_TEACHING_TABS`
3. Po želji prilagodi `scrape_employees()` za strukturo tvoje strani

### 5d) Kako učitelji dostopajo?

- Gredo na **http://localhost:8001** (ali tvoj URL)
- Kliknejo **"Pozabljeno geslo"**
- Vnesejo svoj email
- Dobijo email z linkom za nastavitev gesla
- Nastavijo geslo in se prijavijo

Če nimaš email strežnika, lahko gesla nastaviš ročno prek admin panela:
`http://localhost:8001/auth/admin/users`

### 5e) Urejanje najetih prostorov

V `.env` nastavi:
```env
PROSTORI=tablice,racunalnica,ladja,zbornica,telovadnica
RAZREDI=1.a,1.b,2.a,2.b,3.a,3.b,4.a,4.b,5.a,5.b,6.a,6.b,7.a,7.b,8.a,8.b,9.a,9.b
```

---

## 6) Pomembne opombe

| Značilnost | Lokalno (SQLite) | Produkcija (PostgreSQL) |
|---|---|---|
| Baza | `data/sola.db` | PostgreSQL v k3s |
| Email | Ne deluje brez SMTP | Arnes mail |
| Vzdržljivost | Samo 1 uporabnik naenkrat | Več uporabnikov |
| Varnost | Samo za lokalni dostop | HTTPS prek reverse proxyja |

Če želiš PostgreSQL namesto SQLite, spremeni `DATABASE_URL` v `.env`:
```env
DATABASE_URL=postgresql://uporabnik:geslo@localhost:5432/sola
```
in namesti PostgreSQL (`sudo apt install postgresql`).

---

## 7) Pogoste težave

| Težava | Rešitev |
|---|---|
| `Port already in use` | Spremeni `APP_PORT=8002` v `.env` |
| SQLite `database is locked` | Ustavi app, zbriši `data/sola.db`, zaženi znova |
| Učitelji niso uvoženi | Preveri `--dry-run` najprej; poglej če so emaili pravilni |
| Ne vidim prostorov | Preveri `PROSTORI` v `.env` — `"".split(",")` vrne `[""]` |
