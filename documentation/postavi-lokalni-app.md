🌐 **Jezik / Language:** [🇸🇮 Slovenščina](postavi-lokalni-app.md) | [🇬🇧 English](en/postavi-lokalni-app.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# POSTAVI LOKALNI APP — Šolski sistem OSTC App


Ta dokument je napisan za **čisto lokalno namestitev** — aplikacijo poženemo na **enem samem računalniku**. Brez Kubernetes gruče, brez PostgreSQL strežnika, brez omrežnega čudeža. Samo ti in tvoj računalnik.

> 🎯 **Kdaj to uporabim?** Ko želiš aplikacijo pokazati kolegom, jo preizkusiti na svojem prenosniku, ali jo namestiti v šoli, ki nima svojega Kubernetes okolja.

---

## Kazalo vsebine

1. [Kaj sploh pomeni "lokalna namestitev"?](#1-kaj-sploh-pomeni-lokalna-namestitev)
2. [Kaj rabiš — kontrola, preden začneš](#2-kaj-rabiš--kontrola-preden-začneš)
3. [Kaj je Docker? (za tiste, ki prvič slišite)](#3-kaj-je-docker-za-tiste-ki-prvič-slišite)
4. [Namestitev prek Dockerja](#4-namestitev-prek-dockerja)
5. [Namestitev brez Dockerja — na roke (uvicorn) ](#5-namestitev-brez-dockerja--na-roke-uvicorn-️-priporočeno)
6. [Prvi zagon — kaj se zgodi v ozadju?](#6-prvi-zagon--kaj-se-zgodi-v-ozadju)
7. [Uvoz učiteljev iz spleta](#7-uvoz-učiteljev-iz-spleta)
8. [Pomembne razlike: Lokalno vs. Produkcija](#8-pomembne-razlike-lokalno-vs-produkcija)
8.5. [Dostop iz drugih naprav — nastavitev mDNS](#85-dostop-iz-drugih-naprav--nastavitev-mdns)
9. [Pogoste težave in kako jih rešiti](#9-pogoste-težave-in-kako-jih-rešiti)

---

## 1) Kaj sploh pomeni "lokalna namestitev"?

Predstavljaj si, da imaš na polici škatlo sestavljanke (aplikacije). **Lokalna namestitev** pomeni, da to škatlo odpreš in sestaviš **kar na svoji mizi** — ne pošiljaš je v tovarno, ne uporabljaš industrijskih strojev. Vse, kar rabiš, je na dosegu roke.

V našem primeru:
- **Aplikacija** (spletna stran z koledarjem in rezervacijami) teče na **tvojem računalniku**.
- **Baza podatkov** (kjer so shranjeni učitelji, rezervacije) je **datoteka na tvojem disku**.
- **Drugi uporabniki** lahko dostopajo samo, če so v istem omrežju in poznajo tvoj IP naslov.

> 📌 **Bistvo:** Vse je na enem mestu. Nič ne leti v oblak. En računalnik, ena aplikacija, ena baza.

---

## 2) Kaj rabiš — kontrola, preden začneš

Preden karkoli namestiš, preveri, ali imaš sledeče:

| Orodje                      | Zakaj ga rabiš?                                                                                                 | Kje ga dobiš?                                                         |
| --------------------------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **Python 3.11 ali novejši** | Aplikacija je napisana v Pythonu — to je "motor", ki poganja kodo. Brez njega ne gre.                           | [python.org](https://python.org) — prenesi in namesti.                |
| **Docker** (ni nujno)       | Docker zapakira aplikacijo v "zabojnik", ki vsebuje vse, kar rabi. Kot že pripravljena večerja — samo pogreješ. | [docker.com](https://docker.com)                                      |
| **Git**                     | Orodje za prenos kode iz spletnega repozitorija (GitHub). Kot Dropbox za programsko kodo.                       | `sudo apt install git` (Linux) ali [git-scm.com](https://git-scm.com) |
| **Brskalnik**               | Aplikacija je spletna — dostopaš do nje prek brskalnika (Chrome, Firefox, Edge...).                             | Verjetno ga že imaš.                                                  |

> **💡 Pomembno: izbira poti**
>
> **Git** v zgornji tabeli ni obvezen — kodo lahko preneseš tudi kot [ZIP arhiv](https://github.com/os-tc-jesenice/reservation_app/archive/refs/heads/main.zip) in jo ročno razpakiraš. Vendar **priporočam Git**, ker potem lažje prenašaš posodobitve (`git pull`). Brez Gita boš moral vsakič znova prenesti celoten ZIP in prepisati datoteke.
>
> **Dve poti, dve orodji:**
> - **Pot 1 — uvicorn** (priporočeno): rabiš **Python**, Dockerja **ne rabiš**.
> - **Pot 2 — Docker**: rabiš **Docker**, Python **ni potreben** (nameščen je znotraj containerja).
>
> Izberi eno — obojega **ni treba** nameščati.

### Kako preverim, ali imam Python nameščen?

Odpri **terminal** (Command Prompt v Windows, Terminal na Mac/Linux) in zaženi:

```bash
python3 --version
```

Če vidiš nekaj takega kot `Python 3.11.5` — si pripravljen. Če dobiš napako, ga moraš namestiti.

### Kako preverim, ali imam Docker?

```bash
docker --version
```

Če vidiš `Docker version 24.x.x` — super. Če ne, preskoči na [poglavje 5](#5-namestitev-brez-dockerja--na-roke-uvicorn-️-priporočeno) (namestitev brez Dockerja) ali pa si Docker namesti.

### Namestitev na Windows — WSL (Windows Subsystem for Linux)

Če uporabljaš **Windows**, je najlažje, da vse skupaj poženeš znotraj **WSL** (Windows Subsystem for Linux). To je kot majhen Linux znotraj tvojega Windowsa.

```powershell
# 1. Odpri PowerShell kot Administrator in zaženi:
wsl --install

# 2. Ko se namesti, zaženi WSL:
wsl

# 3. Znotraj WSL (linux terminal) namesti Git in Docker:
sudo apt update && sudo apt install -y git docker.io

# 4. Sledi navodilom spodaj — ukazi so enaki kot za Linux
```

> 💡 **WSL + Docker:** Če želiš uporabljati Docker prek WSL, namesti [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) in vklopi WSL2 backend (Settings → Resources → WSL Integration). Nato lahko Docker ukaze kličeš kar iz WSL terminala.
>
> 💡 **WSL + uvicorn:** Python lahko namestiš direktno znotraj WSL (`sudo apt install python3 python3-pip`) in slediš navodilom za Linux. Ničesar ti ni treba nameščati na Windows strani.

---

## 3) Kaj je Docker? (za tiste, ki prvič slišite)

> **Docker je kot embalaža za hrano:** predstavljaj si, da greš na piknik. Namesto da nosiš s seboj ločeno moko, jajca, maslo, sladkor, pekač in štedilnik, enostavno vzameš **že spečeno pito** v embalaži. Doma jo samo pogreješ in je pripravljena.

**Docker naredi isto za programsko opremo.** V "zabojnik" (container) zapakira:
- Python (prevajalnik)
- Vse knjižnice (dodatna orodja, ki jih Python rabi)
- Konfiguracijo (nastavitve)
- Sama aplikacija (kodo)

Ko to zaženeš, Docker vzame ta zabojnik in ga postavi v svoj "mikro-računalnik" — deluje popolnoma samostojno, ne glede na to, kaj je nameščeno na tvojem pravem računalniku.

### 🔥 Zakaj Docker?

1. **Ničesar ti ni treba nameščati na svoj računalnik.** Ne Python knjižnic, ne orodij — vse je že v zabojniku.
2. **Deluje povsod enako.** Ne glede na to, ali imaš Windows, Mac ali Linux — Docker zagotovi, da aplikacija vidi popolnoma isto okolje.
3. **Če ga zamočiš, ga enostavno zbrišeš.** `docker rm sola-app` in začneš znova — na tvojem računalniku ne ostane nobenih sledi.
4. **Izolacija.** Aplikacija ne more "pobrisati" tvojih pomembnih datotek — živi v svojem svetu znotraj Dockerja.

---

## 4) Namestitev prek Dockerja

### 4a) Priprava — prenesi kodo in nastavi konfiguracijo

> 🐳 **Docker brez sudo:** Če ob zagonu `docker` ukazov dobivaš napako "permission denied", dodaj svojega uporabnika v docker skupino: `sudo usermod -aG docker $USER` in se ponovno prijavi.

> 🪟 **Če si na Windowsu:** pred začetkom zaženi WSL (`wsl` v cmd/PowerShell) in nadaljuj znotraj WSL terminala. Vsi ukazi spodaj (git clone, cp, docker) delujejo enako kot na Linuxu.

Najprej moraš kodo aplikacije prenesti s spleta na svoj računalnik. To narediš z Gitom:

```bash
# 1. Kloniraj repozitorij (to pomeni: prenesi celotno mapo s kodo)
git clone https://github.com/os-tc-jesenice/reservation_app.git
cd sola-app
```

> 💡 **Nasvet:** `cd sola-app` pomeni "pojdi v mapo sola-app". Če ne veš, v kateri mapi si, zaženi `pwd` (Linux/Mac) ali `cd` (Windows) — pokaže pot.

Zdaj moramo ustvariti nastavitveno datoteko `.env`. To je kot "kontrolna plošča" — tam povemo aplikaciji, na katerih vratih naj posluša, kakšna je baza, itd.

```bash
# Vzemi zgled in ga preimenuj v pravo nastavitveno datoteko
cp .env.example .env
```

> 🧠 **Razlaga:** `.env.example` je predloga — vzorčna konfiguracija. Ukaz `cp` (copy) jo skopira v `.env`, ki je prava datoteka, ki jo aplikacija dejansko prebere. `.env.example` ostane nedotaknjena kot rezerva.

`.env` naj vsebuje sledeče (če je prazen, ga uredi z beležnico ali katerimkoli urejevalnikom):

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

> 📖 **Kaj pomenijo te nastavitve?**
> - `APP_HOST=0.0.0.0` — "poslušaj na vseh omrežnih vmesnikih" (tako lahko dostopaš tudi z drugih naprav v omrežju).
> - `APP_PORT=8001` — vrata, na katerih bo aplikacija dostopna (kot TV kanal — na 8001).
> - `BASE_URL=http://localhost:8001` — naslov, pod katerim je aplikacija vidna (localhost = ta računalnik).
> - `DATABASE_URL=sqlite:///./data/sola.db` — **kje je baza**. SQLite je preprosta baza v eni datoteki.
> - `TABLICE_MAX=28` — število vseh tablic
> - `SCHEDULE=...` — urnik (7:30-8:15 je 0. ura, itd.).
> - `RAZREDI=...` — seznam vseh razredov na šoli.
> - `PROSTORI=...` — seznam prostorov, ki jih lahko rezerviraš (in tablice).

### 4b) Zgradi Docker sliko in zaženi

**Docker slika** je kot "recept" — navodila, kako sestaviti zabojnik. **Docker zabojnik** je tisti, ki dejansko teče.

```bash
# Zgradi sliko (to traja nekaj minut ob prvem zagonu)
docker build -t sola-app .
```

> ⏳ **Prvi zagon traja dlje**, ker Docker prenese Python, namesti vse knjižnice... Naslednjič bo takoj.

Ko je slika zgrajena, jo zaženi:

```bash
docker run -d --name sola-app -p 8001:8002 \
  -v $(pwd)/data:/app/data \
  sola-app
```

> 🧠 **Razlaga parametrov:**
> - `-d` — **detached mode** (teče v ozadju, ne zaseda terminala).
> - `--name sola-app` — ime zabojnika (da ga lahko kasneje ustaviš z imenom).
> - `-p 8001:8002` — **port mapping**. "Če nekdo pokliče na vrata 8001 tvojega računalnika, preusmeri klic v zabojnik na ista vrata." Zunanja: notranja vrata.
> - `-v $(pwd)/data:/app/data` — **volume mount**. To je ključno! Tvoja mapa `./data` na računalniku je povezana z mapo `/app/data` v zabojniku. **Če zbrišeš zabojnik, baza ostane na tvojem disku.**
> - `sola-app` — ime slike, ki smo jo zgradili zgoraj.

✅ **Aplikacija je zdaj na:** [**http://localhost:8001**](http://localhost:8001)

Privzeti dostop: uporabniško ime `admin`, geslo `admin123` (**geslo takoj spremenite!**).

### 4c) Ustavitev in odstranitev

```bash
docker stop sola-app    # ustavi zabojnik
docker rm sola-app      # odstrani zabojnik (ne zbriše slike ali podatkov)
```

> 💡 Če želiš zbrisati tudi sliko (da prihraniš prostor): `docker rmi sola-app`

### 4d) Ponovni zagon (ko je slika že zgrajena)

```bash
docker start sola-app
```

---

## 5) Namestitev brez Dockerja — na roke (uvicorn) 

Če nimaš Dockerja ali ga nočeš nameščati (ali imaš težave z njim, npr. tmpfs overload med buildom), lahko aplikacijo poženeš neposredno s Pythonom. To je kot bi sestavljal jed iz sestavin — malo več dela, a bolj predvidljivo na starejših ali bolj omejenih računalnikih.

### 5a) Priprava okolja

> 🪟 **Če si na Windowsu:** priporočam uporabo WSL. Zaženi `wsl` v cmd/PowerShell in sledi navodilom spodaj — vsi ukazi delujejo enako kot na Linuxu. Če želiš pognati direktno na Windowsu, uporabi PowerShell/CMD in ustrezne Windows ukaze (npr. `venv\Scripts\activate` namesto `source venv/bin/activate`).

```bash
# 1. Prenesi kodo
git clone https://github.com/os-tc-jesenice/reservation_app.git
cd sola-app

# 2. Ustvari virtualno okolje
python3 -m venv venv
```


Aktiviraj virtualno okolje:

```bash
# Linux / Mac:
source venv/bin/activate

# Windows:
# venv\Scripts\activate
```

Ko je aktivirano, boš videl(a) `(venv)` na začetku vrstice v terminalu — to je znak, da deluješ znotraj svojega "ločenega prostora".

```bash
# 3. Namesti odvisnosti (vse Python knjižnice, ki jih aplikacija rabi)
pip install -r requirements.txt
```

> 📦 `requirements.txt` je seznam vseh knjižnic, ki jih aplikacija potrebuje. `pip` jih prebere in namesti eno za drugo, kot bi šel po nakupovalnem seznamu.

```bash
# 4. Ustvari nastavitveno datoteko
cp .env.example .env
# Uredi .env — poglej zgled v poglavju 4a zgoraj
```

### 5b) Zaženi aplikacijo

```bash
# Najprej ustvari mapo za podatke (baza bo shranjena sem)
mkdir -p data

# Poženi aplikacijo
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

> 🧠 **Kaj pomenijo ti parametri?**
> - `app.main:app` — **"V datoteki `app/main.py` poišči objekt `app`."** Uvicorn potrebuje vedeti, kje je vhodna točka v aplikacijo.
> - `--host 0.0.0.0` — poslušaj na vseh omrežnih vmesnikih.
> - `--port 8001` — vrata (če so zasedena, spremeni v 8002 ali kaj drugega).
> - **`--reload`** — to je **zlata vredno za razvoj**. Pomeni, da se aplikacija **samodejno znova zažene vsakič, ko spremeniš kodo**. Če urejaš kaj v mapi `app/`, Uvicorn to zazna in znova zažene aplikacijo. Kot da bi imel(a) avtomatsko "shrani in osveži" funkcijo. **V produkciji se --reload ne uporablja** — tam hočeš, da teče stabilno brez ponovnih zagonov.

✅ **Aplikacija je zdaj na:** [**http://localhost:8001**](http://localhost:8001)

Privzeti dostop: `admin` / `admin123`

### 5c) Ustavi aplikacijo

Pritisni **`Ctrl+C`** v terminalu. Aplikacija se bo lepo ustavila.

---

## 6) Po zagonu — preveri, ali aplikacija deluje

Ko zaženeš aplikacijo (bodisi prek Dockerja ali uvicorn), odpri brskalnik in pojdi na:

```
http://localhost:8001
```

### ✅ Kontrolna lista — kaj moraš videti:

1. **Prijavna stran** — vpraša za uporabniško ime in geslo. Privzeto: `admin` / `admin123`
2. **Rezervacije** — po prijavi vidiš zavihka **Rezervacije** in **Ocenjevanja**. Oba morata biti vidna.
3. **Tedenski pregled (Rezervacije)** — pod zavihkom Rezervacije se mora prikazati tedenska tabela s prostori in urami. Tudi če ni nobene rezervacije, se tabela izriše (prazna).
4. **Koledar (Ocenjevanja)** — pod zavihkom Ocenjevanja se mora prikazati mesečni koledar. Tudi če ni nobenega ocenjevanja, koledar mora biti viden.
5. **Prostori v zavihkih** — zgoraj pod Rezervacijami morajo biti vidni zavitki za vsak prostor (tablice, računalnica, ladja...).
6. **/health endpoint** — odpri `http://localhost:8001/health` v brskalniku. Videti moraš `{"status": "ok"}`.

> ⚠️ **Če kaj od tega manjka:** poglej terminal, kjer si zagnal aplikacijo — tam piše napaka. Najpogostejši vzroki so:
> - `--workers 2` z SQLite (baza se zaklene) — uporabi `--workers 1`
> - Manjka `.env` datoteka — aplikacija uporabi privzete vrednosti
> - Port 8001 je zaseden — spremeni v `.env`

---

## 7) Prvi zagon — kaj se zgodi v ozadju?

Ko prvič poženeš aplikacijo (bodisi prek Dockerja ali na roke), se zgodi več stvari **samodejno**:

1. **Ustvari se SQLite baza.** V mapi `data/` nastane datoteka `sola.db`. To je cela baza — ena sama datoteka na tvojem disku.
   > 🧠 **Kaj je SQLite?** Predstavljaj si Excel tabelo, ki je shranjena v eni datoteki. Samo namesto Excela uporabljaš programsko kodo za branje in pisanje. **SQLite je preprosta baza — kot Excel tabela, shranjena v eni datoteki.** Ne rabiš nameščati posebnega baznega strežnika (kot je PostgreSQL ali MySQL) — vse je v tisti datoteki.

2. **Doda se začetni admin uporabnik.** Uporabniško ime: `admin`, geslo: `admin123` (nujno spremeni takoj ob prvi prijavi!).

3. **Vse je pripravljeno za uporabo.** Baza je sicer prazna — ni rezervacij, ni ocenjevanj, ni učiteljev. To je kot nov zvezek: vse strani so prazne, čakajo, da jih napolniš.

---

## 7) Uvoz učiteljev iz spleta

Če ima tvoja šola **javno objavljen seznam zaposlenih** na svoji spletni strani, lahko učitelje uvoziš samodejno. Aplikacija bo šla na spletno stran, prebrala podatke in jih vnesla v bazo.

### 7a) Namesti dodatna orodja

Če uporabljaš Docker, se moraš povezati v zabojnik:
```bash
docker exec -it sola-app bash
```

Če uporabljaš lokalno namestitev, pa aktiviraj virtualno okolje in zaženi:

```bash
pip install requests beautifulsoup4 lxml
```

> 📖 **Kaj so te knjižnice?**
> - `requests` — Pythonov način, da "pokliče" spletno stran in prebere njeno vsebino.
> - `beautifulsoup4` — orodje za **razčlenjevanje HTML** (spletne strani). Kot bi imel(a) lupilnik za pomaranče — olupiš HTML in vzameš samo podatke, ki jih rabiš.
> - `lxml` — hiter bralnik HTML/XML (pospeši BeautifulSoup).

### 7b) Zaženi uvoz

```bash
# Če aplikacija teče na localhost:8001:
python3 scripts/import_teachers.py --base-url http://localhost:8001
```

> 💡 **Najprej preizkusi s --dry-run!** `--dry-run` pomeni "samo poglej, kaj bi se uvozilo, ne spreminjaj baze." Kot bi pogledal(a) v trgovini, kaj bi kupil(a), preden dejansko plačaš.

```bash
# Samo poglej, kdo bi se uvozil (brez spreminjanja baze):
python3 scripts/import_teachers.py --base-url http://localhost:8001 --dry-run
```

### 7c) Prilagodi za svojo šolo

Uredi datoteko `scripts/import_teachers.py` v beležnici ali urejevalniku:

1. **Spremeni `SCRAPE_URL`** — to je naslov spletne strani tvoje šole, kjer piše seznam zaposlenih.
2. **Po potrebi popravi `ROLE_MAP`** — preslikava nazivov.
3. **Po potrebi popravi `NON_TEACHING_TABS`** — zavihki na spletni strani, ki niso učitelji (npr. "Administracija").

### 7d) Kako učitelji dostopajo do aplikacije?

1. Gredo na **http://localhost:8001** (ali tvoj URL, če dostopajo iz drugega računalnika).
2. Kliknejo **"Pozabljeno geslo"**.
3. Vnesejo svoj email naslov.
4. Dobijo email s povezavo za nastavitev gesla.

> ⚠️ **Če nimaš email strežnika (SMTP):** Funkcija "Pozabljeno geslo" ne bo delovala, ker aplikacija ne more pošiljati emailov. V tem primeru lahko gesla nastaviš **ročno prek admin panela** — prijaviš se kot `admin` in urediš vsakega uporabnika posebej.

---

## 8) Pomembne razlike: Lokalno vs. Produkcija

### SQLite proti PostgreSQL

| Značilnost              | Lokalno (SQLite)                                                            | Produkcija (PostgreSQL na k3s)                                                              |
| ----------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **Kje je baza?**        | Ena datoteka: `data/sola.db`                                                | PostgreSQL strežnik v Kubernetes gruči                                                      |
| **Kako deluje?**        | Preprosto — datoteka se odpre, zapiše, zapre. Kot beležka.                  | Profesionalni strežnik — omogoča več sočasnih uporabnikov, boljšo zmogljivost.              |
| **Email**               | ❌ Ne deluje brez SMTP strežnika. "Pozabljeno geslo" ne bo poslalo emaila.   | ✅ Arnes mail ali drug SMTP — pošiljanje gesel deluje.                                       |
| **Število uporabnikov** | Manj uporabnikov                                                            | Več uporabnikov, visoka razpoložljivost (HA — High Availability), porazdelitev obremenitve. |
| **Varnost**             | Samo za lokalni ali intranet dostop. Brez HTTPS, brez Cloudflare varovanja. | HTTPS prek Cloudflare proxyja, zaščiteno pred zunanjimi napadi.                             |

> 🧠 **Zakaj SQLite za lokalno?** Ker ne rabiš strežnika. Baza je datoteka — kopiraš jo na USB ključek in jo odneseš na drug računalnik. Za testiranje in demonstracijo je popolnoma dovolj.
>
> 🧠 **Zakaj PostgreSQL v produkciji?** Ker zdrži več sočasnih poizvedb, ima boljšo varnost, podpira replikacijo (več kopij baze za zanesljivost) in je industrijski standard. Ko na šoli 30 učiteljev hkrati odpira rezervacije, SQLite začne zaostajati.

### Preglednica ključnih razlik

| Značilnost   | Lokalno (SQLite)       | Produkcija (PostgreSQL/k3s)   |
| ------------ | ---------------------- | ----------------------------- |
| Baza         | `data/sola.db`         | PostgreSQL v k3s              |
| Email        | Ne deluje brez SMTP    | Arnes mail                    |
| Vzdržljivost | Manj uporabnikov       | Več uporabnikov, HA           |
| Varnost      | Samo za lokalni dostop | HTTPS prek Cloudflare proxyja |

---

## 8.5) Dostop iz drugih naprav — nastavitev mDNS

Do zdaj aplikacijo odpiraš na `http://localhost:8001` — to deluje samo na računalniku, kjer aplikacija teče. Kaj pa, če želiš aplikacijo odpreti na telefonu, tablici ali drugem računalniku v istem omrežju?

Lahko bi v brskalnik vpisal(a) IP naslov računalnika (npr. `http://192.168.1.42:8001`), vendar se ta lahko spremeni ob vsakem ponovnem zagonu. Bolj elegantno je uporabiti **mDNS** (Multicast DNS).

### Kaj je mDNS?

mDNS je protokol, ki omogoča, da do računalnika dostopaš **po imenu namesto po IP naslovu** — podobno kot kličeš prijatelja po imenu, ne po številki osebne izkaznice.

Na Linuxu za mDNS skrbi storitev `avahi-daemon`. Ko ga namestiš, postane tvoj računalnik dosegljiv na naslovu `http://<ime-računalnika>.local:8001` — iz katerekoli naprave v istem omrežju.

### Namestitev

```bash
# Namesti avahi-daemon
sudo apt install avahi-daemon

# Zaženi in omogoči ob vsakem zagonu sistema
sudo systemctl enable --now avahi-daemon
```

### Kako ugotoviš ime računalnika?

```bash
hostname
```

Če ukaz vrne `šolski-pc`, je aplikacija dosegljiva na:

✅ **http://šolski-pc.local:8001**


Spremeni hostname:
```bash
sudo vim /etc/hostname
```

Spremeniš besedilo (v vimu pritisneš `Esc` + `i`, da začneš tipkati, nato pa `Esc` + `ZZ` oziroma `:wq`), ko je shranjeno, ponovno zaženi računalnik in ime bi moralo biti spremenjeno.
### Dostop iz drugih naprav

- **Linux:** namesti `avahi-daemon` (enako kot zgoraj)
- **Windows:** mDNS je vgrajen v Windows 10 in novejše — deluje brez posebne namestitve
- **Mac:** podpira mDNS vgrajeno (Apple ga imenuje Bonjour)
- **Android/iOS:** podpirajo `.local` naslove vgrajeno

> 💡 **Praktični nasvet:** Če ima šolski računalnik ime `sola-pc`, preprosto povej učiteljem: "Odprite brskalnik in pojte na `sola-pc.local:8001`." Deluje, tudi če se IP naslov čez noč spremeni.

---

## 9) Pogoste težave in kako jih rešiti

| ❌ Težava                                             | ✅ Rešitev                                                                                                                                                                                                                       |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`Port already in use`** (vrata so zasedena)        | Druga aplikacija že uporablja vrata 8001. Spremeni `APP_PORT=8002` v `.env` datoteki in poskusi znova. Z Dockerjem: dodaj drug port mapping (`-p 8002:8001`).                                                                   |
| **SQLite `database is locked`** (baza je zaklenjena) | **Najpogosteje:** uporabljaš `--workers 2` ali več. SQLite ne podpira več procesov hkrati. Popravi v Dockerfile ali v ukazu na `--workers 1`. **Rešitev:** ustavi aplikacijo, zbriši `data/sola.db`, zaženi z `--workers 1`. **Pozor:** S tem izgubiš vse podatke! |
| **Učitelji niso uvoženi**                            | Seznam zaposlenih na spletni strani je morda drugačne strukture. Najprej zaženi **`--dry-run`**, da vidiš, kaj skripta najde. Nato prilagodi `SCRAPE_URL` v `scripts/import_teachers.py`.                                       |
| **Ne vidim prostorov (tablice, računalnica, ladja)** | Preveri `PROSTORI` v `.env` datoteki. Če manjkajo, jih dodaj ločene z vejico: `PROSTORI=tablice,racunalnica,ladja,telovadnica`. Nato znova zaženi aplikacij. |                                                                   |
| **Aplikacije ne morem odpreti v brskalniku**         | Preveri: (1) Ali aplikacija sploh teče? (poglej terminal ali `docker ps`). (2) Ali si uporabil(a) pravi naslov? Običajno `http://localhost:8001`. (3) Ali si spremenil(a) vrata? Uporabi tista, ki si jih nastavil(a) v `.env`. |
| **Docker: `permission denied`**                      | Na Linuxu moraš imeti administratorske pravice. Poskusi `sudo docker ...` ali dodaj svoj uporabnik v `docker` skupino: `sudo usermod -aG docker $USER` (po tem se odjavi in prijavi nazaj).                                      |
| **`pip install` vrže napako**                        | Morda manjka kakšno sistemsko orodje (npr. Python dev headers). Na Linuxu poskusi: `sudo apt install python3-dev build-essential`. Nato ponovi `pip install -r requirements.txt`.                                               |
| **Koledarja ni, stran kaže "Nalaganje ..."**          | API klic se ni izvedel. Najpogosteje: `--workers 2` z SQLite, ali pa aplikacija sploh ni štartala (poglej terminal za napako). Popravi na `--workers 1` in ponovno zaženi.                                                         |
| **Docker build pade z napako**                         | Verjetno tmpfs overload — `/tmp` se je napolnil med gradnjo. Poskusi z `uvicorn` namesto Dockerja, ali povečaj tmpfs.                                                                                                            |

---

## Še zadnji nasveti

✅ **Priporočamo namestitev brez Dockerja (uvicorn).** Docker je sicer standardna izbira za produkcijo, vendar na starejših ali bolj omejenih računalnikih (zlasti tistih z majhno tmpfs particijo) lahko povzroči težave — `/tmp` se med buildom napolni in build pade. Neposredna namestitev z uvicorn te težave nima in je bolj predvidljiva.

> 🧠 **Težava s tmpfs (tmpfs overload):** Ko Docker gradi sliko, uporablja `/tmp` za začasne datoteke — pip prenose, WeasyPrint pisave, prevode. Če ima tvoj sistem majhno tmpfs particijo (manj kot 2 GB), to povzroči napako 'No space left on device'. Neposredna namestitev z uvicornom tega nima, ker uporablja običajen diskovni prostor.

✅ **Če imaš Docker in dovolj tmpfs prostora:** Lahko uporabiš Docker, navodila so v 4. poglavju. Za večino pa je uvicorn enostavnejša in bolj zanesljiva pot.

✅ **Ne uporabljaj `--reload` v produkciji.** Je super za razvoj (samodejni restart ob spremembah), ampak v produkciji povzroča nepotrebne ponovne zagone in lahko izgubiš podatke.

✅ **Redno varnostno kopiraj `data/sola.db`** (ali celotno `data/` mapo). To je tvoja baza — če jo izgubiš, izgubiš vse podatke. Kopiraj datoteko na USB ključek ali v oblak.

✅ **Geslo admin uporabnika takoj spremenite.** Privzeto geslo `admin123` ve vsak, ki prebere to dokumentacijo.

✅ **Če se kaj zalomi:** zbriši vse in začni znova. Pri Dockerju: `docker stop sola-app && docker rm sola-app && docker rmi sola-app`. Nato ponovi korake iz [poglavja 4](#4-namestitev-prek-dockerja). Pri lokalni namestitvi: zbriši mapo `venv/`, zbriši `data/sola.db`, in začni od [koraka 5a](#5a-priprava-okolja).

---


> **Avtor:** Matej Čušin  

