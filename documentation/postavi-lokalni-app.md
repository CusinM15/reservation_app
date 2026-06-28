🌐 **Jezik / Language:** [🇸🇮 Slovenščina](postavi-lokalni-app.md) | [🇬🇧 English](en/postavi-lokalni-app.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# POSTAVI LOKALEN APP — Navodila za druge šole

Tole je **poenostavljena** namestitev — vse teče na **enem računalniku**, brez Kubernetes, brez PostgreSQL.
Narejeno za druge šole, za testiranje, za demonstracijo. Ko boš tole pognal, bo app deloval takoj.

> **Avtor:** Matej Čušin
> **Šola:** OŠ Toneta Čufarja, Jesenice

---

## Kaj so predpogoji? (checklista)

Preden začneš, preveri, da imaš vse na seznamu. Če kaj manjka, boš obtičal sredi navodil.

- [ ] **Računalnik z internetom** — očitno, ampak vseeno.
- [ ] **Docker** nameščen (če greš po Docker poti) — `docker --version` naj vrne številko. Če ga nimaš: [docs.docker.com/get-docker](https://docs.docker.com/get-docker)
- [ ] Ali pa **Python 3.11+** nameščen (če greš brez Dockerja) — `python3 --version` naj vrne `3.11.x` ali več.
- [ ] **Git** (opcijsko) — `git --version`. Lahko tudi ročno skopiraš mapo, če si jo že dobil zipano.
- [ ] **Brskalnik** — Chrome, Firefox, Edge, karkoli.
- [ ] **Terminal / ukazna vrstica** — na Mac/Linux je to Terminal, na Windows PowerShell ali CMD.
- [ ] **Pravice za pisanje v mapo** — app bo ustvaril `data/` mapo z bazo. Ne smeš biti v read-only direktoriju.

---

## Kako se lotiti? Dve poti: Docker ali uvicorn

Imaš dve možnosti. Tukaj je razlika v preprostem jeziku:

**Docker** je kot **embalaža za živilo**. Aplikacija in vse, kar rabi (Python, knjižnice, nastavitve), je zapakirano v eno škatlo. Ti samo poženeš škatlo in vse deluje — ne rabiš nameščat Pythona, pipa, ničesar. Docker poskrbi za vse.

**Uvicorn** pa je kot **goli zagon** — vzameš aplikacijo in jo poženeš direktno na svojem računalniku. Ampak prej moraš ročno namestiti Python, ustvariti virtualno okolje, pognati `pip install`. Bolj pregledno (vidiš točno kaj se dogaja), ampak več dela.

| Pot | Ko je dobra? | Zakaj? |
|---|---|---|
| **Docker** ✅ priporočeno | Večina ljudi | Ne rabiš nič nameščat razen Dockerja. Vse pride zapakirano. |
| **Uvicorn** | Razvijalci, učitelji informatike | Vidiš točno kaj se dogaja. Lažje debugiraš. |

**Ok, izberi eno in sledi.**

---

## 1) Namestitev prek Docker (priporočeno)

Ne rabiš Pythona. Ne rabiš pipa. Samo docker.

### 1a) Priprava

```bash
# 1. Kloniraj repo ali skopiraj mapo
git clone https://github.com/sola-app.git
cd sola-app

# 2. Naredi .env za lokalno uporabo
cp .env.example .env
```

### 1b) Kaj mora biti v `.env` datoteki?

Vsako vrstico razložimo spodaj. Tukaj je delujoč zgled za lokalni zagon:

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

**Razlaga `.env` vrstica za vrstico:**

| Vrstica | Pomen | Kot v resničnem svetu… |
|---|---|---|
| `APP_HOST=0.0.0.0` | IP naslov, na katerem app posluša. `0.0.0.0` pomeni **vse omrežne vmesnike** — ne samo tvoj računalnik (localhost), ampak tudi drugi računalniki v istem omrežju (WiFi, LAN) lahko dostopajo. | Kot če bi bil na radiu: `0.0.0.0` = oddajaš na vseh frekvencah, `127.0.0.1` = oddajaš samo znotraj svoje sobe. |
| `APP_PORT=8001` | Vrata (port), na katerih app čaka na obiskovalce. | Kot vrata na hiši: če daš 8001, prideš noter skozi vrata 8001. |
| `BASE_URL=http://localhost:8001` | Povezava do appa, ki jo app uporablja za ustvarjanje linkov (npr. za pozabljeno geslo). Lokalno je to `localhost`. | Kot tvoj domači naslov — app ve, kje "stanuje", da lahko drugim pošlje pravilen link. |
| `DATABASE_URL=sqlite:///./data/sola.db` | Kje je baza. `sqlite` pomeni lokalno datoteko. App bo sam ustvaril `data/sola.db`. | Kot beležka v mapi `data/` — samo app jo lahko odpre. |
| `TABLICE_MAX=28` | Koliko tablic (npr. iPadov) imate na šoli. | Številka, ki pove appu, koliko naprav je na voljo. |
| `SCHEDULE=...` | Urnik — kdaj se začne in konča vsaka ura. Ure so oštevilčene od 0 do 7. | Razpored zvonjenja na šoli. |
| `RAZREDI=...` | Seznam vseh razredov, ločenih z vejico. | Seznam na vratih razrednika. |
| `PROSTORI=...` | Seznam posebnih prostorov (ne učilnic), ki so na voljo za rezervacije. | Kot seznam: "tablice so v omari, računalnica je soba 12, ladja je v avli". |

### 1c) Zgradi in zaženi

```bash
docker build -t sola-app .
docker run -d --name sola-app -p 8001:8001 \
  -v $(pwd)/data:/app/data \
  sola-app
```

**Kaj se zdaj zgodi?**
1. Docker zgradi "škatlo" (image) s celotno aplikacijo
2. Zažene škatlo (container) in jo poveže s tvojim računalnikom na vratih 8001
3. Ustvari mapo `data/` na tvojem računalniku, kjer bo shranjena baza

Aplikacija je na voljo na: **http://localhost:8001**

Privzet dostop: `admin` / `your_password` (geslo takoj spremeni, ko prvič vstopiš).

### 1d) Ustavi Docker

```bash
docker stop sola-app && docker rm sola-app
```

`stop` = ugasni. `rm` = zbriši container (podatki v `data/` ostanejo — baza je na tvojem disku, ne v containerju).

### 1e) Ponovni zagon (ko že imaš bazo)

```bash
docker start sola-app
```

Samo če container obstaja (nisi ga zbrisal z `docker rm`). Podatki so tam, kjer so bili.

---

## 2) Namestitev brez Dockerja (uvicorn)

Če nimaš Dockerja, ga nočeš nameščati, ali pa želiš videti kaj točno se dogaja — uporabi uvicorn.
Zahteva Python 3.11+ ročno nameščen.

### 2a) Priprava okolja

```bash
# 1. Kloniraj repo
git clone https://github.com/sola-app.git
cd sola-app

# 2. Ustvari virtualno okolje
# Virtualno okolje = svoja sobica za tvoj projekt. Knjižnice v njej ne vplivajo na ostale projekte.
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Namesti odvisnosti (knjižnice, ki jih app potrebuje)
pip install -r requirements.txt

# 4. Uredi .env za lokalno uporabo — enako kot zgoraj pri Dockerju
cp .env.example .env
# Odpri .env v urejevalniku in nastavi po zgledu v točki 1b
```

### 2b) Zaženi

```bash
# Ustvari mapo za podatke (SQLite baza bo šla sem)
mkdir -p data

# Poženi aplikacijo
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**Razlaga parametrov:**

| Parameter | Pomen |
|---|---|
| `app.main:app` | Povej Pythonu: "vzemi datoteko `app/main.py` in iz nje objekt `app`" |
| `--host 0.0.0.0` | Poslušaj na vseh omrežnih vmesnikih (ne samo localhost). **Brez tega** bi app deloval samo na tvojem računalniku — drugi v omrežju ne bi mogli dostopati. |
| `--port 8001` | Vrata. Če jih daš 8001, odpreš http://localhost:8001. |
| `--reload` | **Samodejni restart ob spremembi kode.** Vsakič ko shraniš spremembo v kodi (.py datoteko), se app samodejno ugasne in zažene znova. Super za razvoj, **ne uporabljaj v produkciji** — zakaj bi restartal app vsakič ko nekdo samo pogleda v kodo? |

Aplikacija je na voljo na: **http://localhost:8001**

Admin: `admin` / `your_password`

### 2c) Ustavi

Pritisni `Ctrl+C` v terminalu. To je vse.

---

## 3) Prvi zagon — kaj se zgodi? (isti za Docker in uvicorn)

Ko app prvič poženeš:

1. **Ustvari SQLite bazo** v datoteki `data/sola.db`. Če datoteke ni, jo naredi. Če že obstaja, jo uporabi.
2. **Doda začetnega admin uporabnika** — `admin` / `your_password`.
3. **Pripravljeno.** Vse drugo je prazno: ni rezervacij, ni učiteljev, ni ocenjevanj.

**Ampak pozor — SQLite ni PostgreSQL.** Kako si predstavljati razliko?

| Baza | Kot… | Slabost |
|---|---|---|
| **SQLite** (lokalno) | Beležka v enem zvezku. Samo en človek lahko piše naenkrat. Če dva hkrati odpirata zvezek, se zalaufata. | Ne prenese več ljudi hkrati. |
| **PostgreSQL** (produkcija) | Spletna tabela v oblaku. Več ljudi lahko piše hkrati, zaklepanje je pametno. | Treba je nastaviti strežnik. |

Za lokalno testiranje in demonstracijo je SQLite čisto dovolj. Samo ne pričakuj, da bo 50 učiteljev istočasno rezerviralo tablice — potem bo "database is locked".

---

## 4) Uvoz učiteljev (opcijsko)

Če imaš javno objavljen seznam zaposlenih (npr. na šolski spletni strani), lahko učitelje uvoziš samodejno namesto da jih vnašaš ročno.

### 4a) Namesti orodja za uvoz

```bash
pip install requests beautifulsoup4 lxml
```

### 4b) Zaženi uvoz

```bash
# Če app teče na localhost:8001:
python3 scripts/import_teachers.py --base-url http://localhost:8001

# Samo poglej, kdo bi se uvozil (brez spreminjanja):
python3 scripts/import_teachers.py --base-url http://localhost:8001 --dry-run
```

**`--dry-run`** je tvoj prijatelj — najprej preveri kaj se bo zgodilo, šele potem dejansko poženi.

### 4c) Prilagodi za svojo šolo

Uredi `scripts/import_teachers.py`:

1. `SCRAPE_URL` — spremeni na URL svojega seznama zaposlenih (tvoja šolska stran)
2. `ROLE_MAP` — kako se tvoji nazivi (npr. "učitelj", "profesor") preslikajo v vloge v appu
3. `NON_TEACHING_TABS` — kateri zavihki na tvoji strani niso učitelji (npr. "kuhar", "hišnik")

### 4d) Kako učitelji dostopajo?

1. Gredo na **http://localhost:8001** (ali tvoj URL, če si app objavil v omrežju)
2. Kliknejo **"Pozabljeno geslo"**
3. Vnesejo svoj email
4. Dobijo email z linkom za nastavitev gesla

**Če nimaš email strežnika:** gesla lahko nastaviš ročno prek admin panela. Ali pa preprosto poveš učiteljem naj kliknejo "Pozabljeno geslo" — če nimajo dostopa do emaila na tem računalniku, pač ne bo šlo. Lokalno je to pričakovana omejitev.

---

## 5) Primerjava: lokalno vs. produkcija

| Značilnost | Lokalno (SQLite) | Produkcija (PostgreSQL / k3s) |
|---|---|---|
| **Baza** | `data/sola.db` — ena datoteka | PostgreSQL v k3s — strežnik |
| **Email** | Ne deluje brez SMTP strežnika | Arnes mail |
| **Vzdržljivost** | Manj uporabnikov (5–10 hkrati) | Več uporabnikov, visoka razpoložljivost |
| **Varnost** | Samo za lokalni/omrežni dostop | HTTPS prek Cloudflare proxyja |
| **Namestitev** | En ukaz | Kubernetes, ingress, certifikati… |

**V glavnem:** lokalno = testiraš in pokažeš. Produkcija = uporablja cela šola.

---

## 6) Pogoste težave

| Težava | Zakaj? | Rešitev |
|---|---|---|
| `Port already in use` | Nekaj drugega že teče na vratih 8001. | Spremeni `APP_PORT=8002` v `.env`, potem ponovno zaženi. |
| SQLite `database is locked` | Več ljudi hkrati piše v bazo (ali pa si app grdo ugasnil). | Ustavi app, zbriši `data/sola.db` (POZOR: izgubiš vse podatke!), zaženi znova. |
| Učitelji niso uvoženi | Napačen URL ali struktura strani. | Najprej poženi z `--dry-run` — vidiš kaj se dogaja. |
| Ne vidim prostorov | `PROSTORI` v `.env` je prazen ali napačen. | Preveri `.env` — prostori morajo biti ločeni z vejicami. |
| `docker: command not found` | Docker ni nameščen. | [docs.docker.com/get-docker](https://docs.docker.com/get-docker) — ali pa uporabi uvicorn pot. |
| `python3: command not found` | Python ni nameščen. | Namesti Python 3.11+ s python.org ali prek ustreznega package managerja. |

---

**Kratek povzetek:** skopiraj `.env.example` v `.env`, nastavi vrednosti (glej tabelo zgoraj), zaženi z Dockerjem ali uvicornom, in app deluje na `http://localhost:8001`. Prvi uporabnik je `admin` / `your_password`. Vse ostalo je prazno — dodaš po svojih potrebah.

Če si kdaj v dvomih: **Docker je lažji** — ne rabiš nameščat Pythona in knjižnic ročno. **Uvicorn je bolj pregleden** — vidiš točno kaj se dogaja, kar je super za učenje in debugiranje.
