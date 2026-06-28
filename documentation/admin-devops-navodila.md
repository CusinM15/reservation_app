🌐 **Jezik / Language:** [🇸🇮 Slovenščina](admin-devops-navodila.md) | [🇬🇧 English](en/admin-devops-navodila.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# ⚙️ Admin & DevOps navodila — priročnik za vzdrževanje šolskega sistema

**Celovita navodila za namestitev, vzdrževanje in odpravljanje težav** — napisana tako, da jih razume tudi učitelj, ki se šele spoznava z računalniki. Vsak ukaz in vsak pojem je razložen s preprostimi primerami iz vsakdanjega življenja.

> **Avtor:** Matej Čušin  
> **Šola:** OŠ Toneta Čufarja, Jesenice  
> **Aplikacija:** ostc-app — sistem za rezervacije, ocenjevanja in administracijo

---

## 📋 Kazalo vsebine

1. [Kaj aplikacija omogoča — čemu sploh služi?](#1-kaj-aplikacija-omogoča--čemu-sploh-služi)
2. [Namestitev Ubuntu Server 24.04 LTS — priprava računalnika na strežniško vlogo](#2-namestitev-ubuntu-server-2404-lts--priprava-računalnika-na-strežniško-vlogo)
3. [Načini namestitve — kako lahko zaženemo aplikacijo](#3-načini-namestitve--kako-lahko-zaženemo-aplikacijo)
4. [Vzdrževanje in avtomatizacija (cron jobi) — roboti, ki delajo namesto vas](#4-vzdrževanje-in-avtomatizacija-cron-jobi--roboti-ki-delajo-namesto-vas)
5. [AI agent Hermes — pametni pomočnik za vsakdanja opravila](#5-ai-agent-hermes--pametni-pomočnik-za-vsakdanja-opravila)
6. [Dodajanje novega računalnika v k3s cluster — širitev gruče](#6-dodajanje-novega-računalnika-v-k3s-cluster--širitev-gruče)
7. [Struktura repozitorija — mapa za mapo, kaj kje leži](#7-struktura-repozitorija--mapa-za-mapo-kaj-kje-leži)

---

## 1. Kaj aplikacija omogoča — čemu sploh služi?

Predstavljajte si elektronski oglasni desko in dnevnik v enem. Aplikacija **ostc-app** rešuje tri glavne težave, ki jih pozna vsaka šola:

### 📅 Rezervacije prostorov

Učitelji si lahko preko spleta rezervirajo prostore, ne da bi se podpisovali na papir ali klicali po hodniku. Sistem skrbi, da si prostorov ne rezervirata dva hkrati.

| Prostor | Kapaciteta | Kako deluje rezervacija |
|---------|-----------|------------------------|
| **Tablice** | 28 kosov | Več učiteljev si lahko tablice deli v isti šolski uri — vsak rezervira samo svoj delček ure |
| **Računalnica** | 1 učilnica | Samo en učitelj na uro — kot učilnica, kjer ne moreta hkrati poučevati dva |
| **Ladja** | 1 učilnica | Prav tako ena rezervacija na uro |
| **Gospodinjska učilnica** | 1 učilnica | Ena rezervacija na uro |

### 📝 Ocenjevanja — napovedovanje pisnih preverjanj

Učitelji vnesejo, kdaj bodo pisali test. Aplikacija sama poskrbi, da:
- **Ne bo več kot 3 ocenjevanja na teden** (preveč testov v enem tednu ni dobro za otroke)
- **Ne bo več kot 2 običajni ocenjevanji na teden** (poleg tega so še govorilne ure, nastopi ipd.)
- **Ne bo dveh ocenjevanj istega tipa na isti dan**

### 🚫 Zasedeni datumi

Vodstvo ali admin lahko označi dneve kot **zasedene** — recimo zaključne konference, prazniki, dnevi dejavnosti — takrat sistem ne dovoli novih ocenjevanj ali rezervacij.

### 👥 Admin panel — upravljanje uporabnikov

Skozi admin vmesnik lahko dodajate, brišete in urejate uporabnike. Nič več Excel tabel ali ročnega urejanja baze.

### 🔑 Pozabljeno geslo

Če učitelj pozabi geslo, lahko zahteva ponastavitev preko emaila. Sistem mu pošlje povezavo za nastavitev novega gesla — kot pri spletni banki.

---

## 2. Namestitev Ubuntu Server 24.04 LTS — priprava računalnika na strežniško vlogo

### Kaj sploh je "Ubuntu Server"?

Ubuntu Server je **operacijski sistem za strežnike**. Če je navaden Windows ali macOS kot osebni avto, je Ubuntu Server kot **tovornjak** — nima luksuzne opreme (kot je namizje z ikonami), je pa zanesljiv, varen in narejen za to, da deluje 24 ur na dan, 7 dni v tednu, brez ponovnega zagona.

**LTS** pomeni *Long Term Support* (dolgoročna podpora) — to je kot garancija: Ubuntu obljublja, da bo ta različica dobivala varnostne popravke kar **5 let**, brez da bi morali znova nameščati sistem.

### 2.1 Priprava namestitvenega medija — kako narediti "zagonski ključek"

```bash
# 1. Pojdi na https://ubuntu.com/download/server in prenesi Ubuntu Server 24.04 LTS
#    To je datoteka s končnico .iso — kot "slika" sistema, ki jo zapišemo na USB ključek.

# 2. Program Rufus (https://rufus.ie/) — orodje za Windows, ki naredi USB ključek zagonski.
#    Izberi preneseno .iso datoteko, ciljni USB ključek, in klikni "Start".
#    POZOR: Vsebina USB ključka se bo izbrisala!

# 3. Vstavi USB ključek v ciljni računalnik in ga vklopi.
#    Med zagonom pritisni tipko za vstop v BIOS (ponavadi F2, F10, F12 ali Delete).
#    V BIOSU nastavi USB kot prvi "boot device" — to pomeni: "ko se računalnik zažene,
#    naj najprej pogleda USB ključek in zažene tisto, kar je na njem."
```

### 2.2 Potek namestitve — korak za korakom

Ko se računalnik zažene z USB ključka, vas bo namestitveni program vodil skozi postopek. Tukaj so ključni koraki:

1. **Izberite English** — žal Ubuntu Server v slovenskem jeziku ne obstaja. Angleščina je enostavna in večina ukazov je v angleščini, tako da to ni težava.

2. **Omrežne nastavitve** — pozneje bomo nastavili statični IP (fiksni naslov). Med namestitvijo lahko pustite, da dobi IP samodejno preko DHCP (kot običajen računalnik v šolskem omrežju).

3. **Obvezno označite "Install OpenSSH server"** — to je ključnega pomena!
   - **Kaj je OpenSSH?** To je protokol za **oddaljen dostop** do strežnika. Predstavljajte si, da ima računalnik, ki ga nameščate, svoj daljinski upravljalnik. OpenSSH je ta daljinski upravljalnik — omogoča vam, da se s svojega prenosnika povežete na ta strežnik in upravljate z njim, ne da bi fizično sedeli pred njim.
   - **Zakaj je to pomembno?** Strežnik bo verjetno stal v omarici, brez monitorja in tipkovnice. Edini način, da kaj spremenite na njem, je preko SSH.

4. **Ustvarite uporabnika in geslo** — to bo vaš "skrbniški" dostop. Geslo shranite na varno mesto (npr. v sef za gesla kot je Bitwarden ali KeePass).

### 2.3 Nastavitev statičnega IP-ja — zakaj mora biti IP fiksen?

**Zakaj statični IP?** Predstavljajte si, da je IP naslov kot **hišna številka** vašega strežnika. Če ima strežnik dinamičen IP (kot večina domačih računalnikov), se lahko njegova "hišna številka" vsakič, ko se ponovno zažene, spremeni. Ko potem aplikacija išče bazo podatkov, je ne najde, ker je baza "preselila na drugo hišno številko". Statični IP pomeni: "ta računalnik bo vedno imel isti naslov" — kot pošta, ki vedno pride na pravi naslov.

**Netplan** je orodje v Ubuntuju, s katerim povemo operacijskemu sistemu, **kateri IP naj uporablja**. To je kot da bi hiši dali hišno številko in zemljevidu povedali, kje ta hiša stoji.

```bash
# Odpri datoteko z omrežnimi nastavitvami. nano je preprost urejevalnik besedila.
sudo nano /etc/netplan/00-installer-config.yaml
```

V datoteko vpišite sledeče. **Pozor:** {{LB_IP}}, {{K3S_1_IP}}, {{K3S_2_IP}} so **nadomestne oznake (placeholders)** — na njihovo mesto vpišite dejanske IP naslove vašega omrežja.

```yaml
network:
  ethernets:
    eth0:                              # eth0 je ime omrežne kartice (kot "LAN vrata")
      addresses:
        - {{LB_IP}}/24                 # Tukaj vpiši želeni statični IP. /24 pomeni "maska podomrežja"
      routes:
        - to: default                  # "default" pomeni "vsa promet, ki ni namenjen lokalnemu omrežju"
          via: {{K3S_1_IP}}            # to je vaš "gateway" — vrata v svet (ponavadi šolski usmerjevalnik)
      nameservers:
        addresses:
          - {{LB_IP}}                  # DNS strežnik — kot "telefonski imenik" za internet
          - 8.8.8.8                    # Googlov pomožni DNS — če prvi ne dela
  version: 2
```

```bash
# Po shranitvi datoteke moramo netplanu povedati, naj nove nastavitve uveljavi:
sudo netplan apply
```

**Kaj se zgodi zdaj?** Netplan prebere datoteko in nastavi omrežje na novo. Če se povezava izgubi (ker ste se prek SSH povezovali na stari IP), se preprosto povežite na novi IP.

### 2.4 Nastavitev laptopa kot strežnik — zankanje pokrova

Če kot strežnik uporabljate prenosnik (laptop), ima ta eno težavo: ko zaprete pokrov, gre v "spanje" (mirovanje). Strežnik pa mora delovati 24/7, tudi ko je pokrov zaprt.

```bash
# Odpri nastavitveno datoteko za upravljanje z energijo
sudo nano /etc/systemd/logind.conf

# Poišči vrstico: #HandleLidSwitch=ignore
# Odstrani # (začetni "klicaj") spredaj, tako da postane:
HandleLidSwitch=ignore

# To pomeni: "ko nekdo zapre pokrov, naj računalnik IGNORIRA to dejanje in ostane prižgan"

# Nato ponovno zaženi storitev, da se sprememba uveljavi:
sudo systemctl restart systemlog-ind
```

### 2.5 SSH — oddaljen dostop (če ga niste namestili med namestitvijo)

Če ste med namestitvijo pozabili označiti "Install OpenSSH server", nič hudega — lahko ga namestite naknadno:

```bash
# apt-get je "trgovina z aplikacijami" za Ubuntu. install pomeni "namesti".
# -y pomeni "ne sprašuj me, ali sem prepričan — kar naredi"
sudo apt install -y openssh-server

# systemctl je "upravitelj storitev" — kot stikalo za prižiganje/ugašanje programov.
# enable pomeni "naj se SSH zažene samodejno ob vsakem zagonu računalnika"
# --now pomeni "zaženi ga takoj, ne šele ob naslednjem zagonu"
sudo systemctl enable --now ssh
```

```bash
# Na svojem prenosniku (Windows, Mac ali Linux) odprite terminal in vpišite:
ssh {{SSH_USER}}@{{LB_IP}} -p {{LB_PORT}}
```
Zamenjajte {{SSH_USER}} z imenom uporabnika, ki ste ga ustvarili med namestitvijo, {{LB_IP}} z IP naslovom strežnika in {{LB_PORT}} z vrati, na katerih SSH posluša (privzeto je 22).

---

## 3. Načini namestitve — kako lahko zaženemo aplikacijo

Aplikacijo lahko zaženemo na tri načine, odvisno od tega, koliko računalnikov imamo na voljo in kako zanesljiv sistem potrebujemo.

| Način | Zahtevnost | Za kaj je primeren | Kako deluje |
|------|-----------|-------------------|-------------|
| **Lokalno (uvicorn)** | ⭐ Enostavno | En računalnik v zbornici | Aplikacija teče neposredno na enem računalniku. Najbolj preprosto, a če ta računalnik crkne, aplikacije ni več. |
| **mDNS** | ⭐⭐ Srednje | Več računalnikov znotraj šolskega omrežja | Več enakih kopij aplikacije teče na različnih računalnikih. Če eden pade, drugi še vedno delajo. Napredno: vsak najde drugega samodejno. |
| **Kubernetes (k3s)** | ⭐⭐⭐ Zahtevno | Visoka razpoložljivost, 2+ računalnikov | Prava "industrijska" rešitev. Kubernetes (k3s je lažja različica) je kot **pametni krmilnik prometa** — samodejno usmerja delo na tiste računalnike, ki imajo proste zmogljivosti. Če en računalnik crkne, prestavi vse na drugega, brez izpada. |

> **Podrobna navodila za vsak način:**
> - **Lokalno:** [postavi-lokalni-app.md](postavi-lokalni-app.md) — najlažji način, primeren za testiranje in manjše šole.
> - **k3s (Kubernetes):** [k3s-setup.md](k3s-setup.md) — za resno uporabo v produkciji.
> - **HA arhitektura (High Availability = Visoka Razpoložljivost):** [HA.md](HA.md) — kako dosežemo, da je sistem na voljo tudi če odpove en računalnik.

---

## 4. Vzdrževanje in avtomatizacija (cron jobi) — roboti, ki delajo namesto vas

### Kaj sploh je "cron job"?

**Cron** je star, a zelo uporaben mehanizem v Linuxu, ki omogoča **samodejno izvajanje opravil ob določenem času**. To je kot **budilka z opravilom**: ob določeni uri pozvoni in namesto, da bi vas zbudila, zažene določen program ali skripto.

Cron job torej pomeni: *"ob uri X zaženi nalogo Y, brez da bi se kdo usedel pred računalnik in to naredil ročno."*

### Zakaj so cron jobi pomembni?

Ker pozabljamo. Ker smo utrujeni. Ker gremo na dopust. **Cron jobi poskrbijo, da se določene stvari zgodijo vedno ob istem času** — tudi ko vas ni v službi.

### 4.1 Dnevna varnostna kopija baze (`sola-db-backup`)

**Zakaj potrebujemo varnostne kopije?** Predstavljajte si bazo podatkov kot **šolski dnevnik, ki obstaja samo v enem izvodu**. Kaj se zgodi, če:
- Crkne trdi disk? → Dnevnik je izgubljen.
- Kdo pomotoma zbriše podatke? → Dnevnik je izgubljen.
- Požar, vlom, poplava? → Dnevnik je izgubljen.
- Programska napaka pobriše tabele? → Dnevnik je izgubljen.

**Varnostna kopija (backup) je fotokopija tega dnevnika, shranjena na drugi lokaciji.** Če se original uniči, vzamete fotokopijo in nadaljujete, kjer ste končali. To ni vprašanje "če" se bo kaj zgodilo, ampak "kdaj".

**Kako to deluje v praksi?** Vsako noč ob 4:00 (ko nihče ne uporablja aplikacije) se zažene ukaz `pg_dump`, ki **naredi posnetek celotne baze podatkov** — vse rezervacije, vsi uporabniki, vsa ocenjevanja — in to pošlje na vnaprej določen email naslov (BACKUP_EMAIL).

- **Schedule:** `0 4 * * *` (dnevno ob 4:00 zjutraj — to je slovenski zapis za "vsak dan ob štirih")
- **Kaj se zgodi:** pg_dump izvozi bazo → skripta zapakira v datoteko → pošlje na email

```bash
# Če želite ročno preveriti, ali backup deluje:
# Poiščite cron job v Kubernetes:
kubectl get cronjob sola-db-backup

# Ali pa zaženite backup takoj (za test):
kubectl create job --from=cronjob/sola-db-backup manual-backup-test
```

### 4.2 Dnevno poročilo o stanju (`sola-daily-report`)

To je kot **jutranji pregled** za strežnike. Vsako noč ob 4:00 sistem preveri:
- Ali so vsi računalniki (node-i) v gruči živi in zdravi? (Če je eden crknil, boste vedeli prvi.)
- Ali Longhorn replike (shramba podatkov) delujejo pravilno? (Če se podatki ne replicirajo, ste v nevarnosti.)
- Ali aplikacije tečejo brez napak?

**Zakaj je to pomembno?** Strežniki lahko crknejo kadarkoli — tudi sredi noči. Vi pa boste zjutraj v emailu prebrali: *"Vse je v redu"* ali pa *"Pozor: node-2 ni dosegljiv!"* in se boste lahko takoj lotili težave, namesto da bi čakali, da uporabniki (učitelji) pokličejo in rečejo "aplikacija ne dela".

- **Schedule:** `0 4 * * *` (dnevno ob 4:00 — istočasno kot backup, ker gresta z roko v roki)

---

## 5. AI agent Hermes — pametni pomočnik za vsakdanja opravila

### Kaj je Hermes Agent?

[Hermes Agent](https://github.com/NousResearch/hermes-agent) je **pametni asistent v ukazni vrstici**. Predstavljajte si, da imate svojega IT strokovnjaka, ki ga pokličete kar preko terminala. Hermes razume **navaden jezik (slovenščino)** in lahko namesto vas izvaja ukaze na strežniku.

**Ne znate kubectl ukazov? Ni problema.** Hermesu povejte v slovenščini, kaj želite, in on bo poskrbel za ustrezne ukaze.

### Primeri uporabe — kaj lahko Hermes naredi za vas

```bash
# 1. "Preveri, ali je vse v redu s strežniki"
# Hermes bo samodejno pognal:
#   - kubectl get nodes (seznam vseh računalnikov v gruči)
#   - kubectl get pods -n longhorn-system (preveril, ali Longhorn deluje)
#   - In vam vrnil povzetek v slovenščini
hermes "kubectl get nodes, preveri longhorn in povej stanje"

# 2. "Dodaj novega učitelja v aplikacijo"
# Hermes bo poiskal pravi API klic ali podatkovni vnos
# in dodal uporabnika brez da bi se ukvarjali z bazo
hermes "dodaj uporabnika Ana Zupančič v aplikacijo, email ana@sola.si, vloga teacher"

# 3. "Nastavi dnevno varnostno kopijo"
# Če želite spremeniti uro backupa ali dodati nov cron job:
hermes "nastavi cronjob za dnevno backup baze ob 3h zjutraj"

# 4. "Zakaj aplikacija ne deluje?"
# Namesto da brskate po log datotekah, vprašajte Hermesa:
hermes "poglej loge sola-app podov in ugotovi zakaj se restartajo"
```

### Namestitev Hermesa

```bash
# Hermes se namesti z enim samim ukazom.
# curl prenese namestitveni skript s spleta
# sh ga zažene
curl -fsSL https://hermes-agent.io/install.sh | sh
```

---

## 6. Dodajanje novega računalnika v k3s cluster — širitev gruče

### Kaj pomeni "dodati računalnik v cluster"?

Predstavljajte si, da vaša k3s gruča (cluster) deluje kot **ekipa delavcev, ki skupaj nosijo težko breme**. Vsak računalnik je en delavec. Če potrebujete več zmogljivosti ali če želite, da sistem ostane delujoč tudi če en delavec zboli (crkne), dodate novega delavca v ekipo.

### 6.1 Priprava novega računalnika

Preden lahko računalnik postane del gruče, mora biti pravilno nameščen:

1. **Namestite Ubuntu Server 24.04** na nov računalnik (glejte poglavje 2 zgoraj)
2. **Nastavite statičen IP** — vsak računalnik v gruči potrebuje svoj fiksen naslov, da ga ostali vedno najdejo (glejte [2.3 Nastavitev statičnega IP-ja](#23-nastavitev-statičnega-ip-ja))
3. **Omogočite SSH** — potrebovali boste oddaljen dostop do novega računalnika (glejte [2.5 SSH](#25-ssh--oddaljen-dostop))

### 6.2 Pridobitev tokena — ključ za vstop v gručo

Vsaka k3s gruča ima **skrivni ključ (token)**, ki ga mora nov računalnik pokazati, preden ga gruča sprejme. To je kot **članska izkaznica** — brez nje ne morete vstopiti.

```bash
# Na kateremkoli obstoječem master računalniku (glavnem vozlišču) zaženite:
# cat prebere vsebino datoteke, sudo pa da skrbniška dovoljenja
sudo cat /var/lib/rancher/k3s/server/token

# Izpiše se dolg niz črk in številk — to je vaš token.
# Kopirajte ga v beležko, potrebovali ga boste v naslednjem koraku.
```

### 6.3 Priključitev novega računalnika kot dodatni master (glavno vozlišče)

Nov računalnik lahko postane **master** (glavni) ali **worker** (delavec). Masterji upravljajo gručo, workerji poganjajo aplikacije. Če dodajate master, gruča postane bolj odporna na izpade — če en master crkne, drugi prevzamejo njegovo vlogo.

```bash
# Na NOVEM računalniku zaženite ta ukaz (v eni vrstici):
# curl -sfL https://get.k3s.io | sh -s - server \
#   --server https://<IP_MASTERJA>:6443 \
#   --token <TOKEN> \
#   --node-ip <NOVI_IP> \
#   --disable traefik --disable=servicelb

# Razlaga parametrov (del za delom):
# curl -sfL https://get.k3s.io  →  Prenesi namestitveni skript s spleta
# sh -s - server                →  Zaženi skript v načinu "server" (master)
# --server https://...:6443     →  Poveži se na obstoječo gručo (na vratih 6443)
# --token <TOKEN>               →  Pokaži skrivni ključ (člansko izkaznico)
# --node-ip <NOVI_IP>           →  Povej, kateri IP ima ta novi računalnik
# --disable traefik             →  Ne nameščaj novega usmerjevalnika prometa
# --disable=servicelb           →  Ne nameščaj novega krmilnika bremena
```

**Zamenjajte:**
- `<IP_MASTERJA>` → IP naslov katerega koli obstoječega master računalnika
- `<TOKEN>` → token, ki ste ga pridobili v prejšnjem koraku
- `<NOVI_IP>` → statični IP naslov tega novega računalnika

### 6.4 Kar mora vsebovati vsako vozlišče — kaj se namesti na nov računalnik

Vsak računalnik v gruči lahko opravlja več vlog hkrati:

| Vloga | Opis | Ali je obvezna? |
|-------|------|----------------|
| **Control-plane** | Upravlja gručo — odloča, kje se bodo izvajale aplikacije | ✅ Da (vsaj 1 vozlišče mora biti master) |
| **Worker** | Poganja zabojnike (aplikacijo) — kot "delavec", ki opravlja delo | ✅ Da (sicer aplikacija nima kje teči) |
| **Longhorn** | Shranjuje podatke (baza, datoteke) na dodaten disk | ⚠️ Potreben dodaten disk (ne samo sistemski) |
| **MetalLB speaker** | Omogoča, da aplikacije dobijo javni IP naslov (LoadBalancer) | ⚠️ Potreben za dostop do aplikacije |

### 6.5 Po dodajanju — končni pregled

Ko se nov računalnik uspešno priključi, moramo namestiti še nekaj dodatnih komponent in preveriti, ali je vse v redu.

```bash
# 1. Namesti Longhorn predpogoje (potrebne knjižnice za deljenje diska)
#    open-iscsi: orodje za povezovanje z oddaljenimi diski
#    nfs-common: orodje za deljenje datotek preko omrežja
sudo apt-get install -y open-iscsi nfs-common

# 2. Omogoči in zaženi iscsi storitev
sudo systemctl enable --now iscsid

# 3. Preveri, ali je nov računalnik viden in pripravljen
#    kubectl get nodes prikaže vse računalnike v gruči
#    Nov node mora imeti status "Ready" (Pripravljen)
kubectl get nodes

# Če piše "Ready" — čestitamo, nov računalnik je uspešno dodan!
# Če piše "NotReady" — počakajte minuto ali dve in poskusite znova.
```

---

## 7. Struktura repozitorija — mapa za mapo, kaj kje leži

Repozitorij (mapa z vsemi datotekami aplikacije) je organiziran tako, da je vsaka stvar na svojem mestu. Spodaj je zemljevid celotne strukture.

```
reservation_app/                    # Glavna mapa projekta (koren repozitorija)
│
├── app/                            # Jedro aplikacije — Python koda (FastAPI)
│   ├── main.py                     # Vstopna točka — tukaj se aplikacija zažene
│   ├── config.py                   # Nastavitve (gesla, povezave, skrivnosti)
│   ├── database.py                 # Povezava z bazo podatkov
│   ├── models.py                   # Modeli podatkov (kako izgleda tabela v bazi)
│   ├── schemas.py                  # API sheme (kako izgleda sporočilo med aplikacijami)
│   ├── race.py                     # Zaščita pred "race condition" — ko dva uporabnika
│   │                               #   hkrati rezervirata isti termin
│   ├── routers/                    # API endpointi — "naslovi" za posamezne funkcije
│   │   ├── auth.py                 #   Prijava, registracija, gesla
│   │   ├── rezervacije.py          #   Rezervacije prostorov
│   │   ├── ocenjevanja.py          #   Napovedovanje ocenjevanj
│   │   └── blocked_dates.py        #   Zasedeni datumi
│   └── templates/                  # HTML predloge (kako izgleda spletna stran)
│
├── scripts/                        # Pomožni skripti (avtomatizacija, backup, obnova)
├── k8s/                            # Kubernetes konfiguracija (navodila za k3s gručo)
├── documentation/                  # Dokumentacija (tukaj ste zdaj)
├── Dockerfile                      # Navodila za izdelavo "zabojnika" (Docker image)
└── requirements.txt                # Seznam potrebnih knjižnic (kot nakupovalni listek)
```

### Ključne informacije

> **⚠️ Privzeti admin uporabnik:** `admin`, geslo `admin123`  
> **⚠️ Takoj po namestitvi spremenite geslo!** Privzeta gesla so kot da bi hišo pustili odklenjeno — vsak, ki pozna naslov, lahko vstopi.

### Kako se znajti v mapah

- Potrebujete spremeniti, kako izgleda spletna stran? → Pojdite v `app/templates/`
- Aplikacija ne zna več dostopati do baze? → Preverite `app/database.py` in privzete nastavitve v `app/config.py`
- Želite dodati nov API klic? → Ustvarite nov router v `app/routers/`
- Kubernetes (k3s) nastavitve? → Vse je v `k8s/`
- Manjka vam kakšna knjižnica? → Preverite `requirements.txt` in po potrebi dodajte vrstico

---

> **Kaj pa, če gre kaj narobe?**  
> 1. Najprej preverite dnevno poročilo (`sola-daily-report`) — morda je težava že zabeležena.  
> 2. Zaženite `kubectl get pods` in `kubectl get nodes` — kateri del sistema ne deluje?  
> 3. Vprašajte Hermesa: *"hermes preveri zakaj app ne dela"* — pametni agent pogleda loge in vam pove.  
> 4. Če vse drugo odpove, ponovno zaženite storitve ali kontaktirajte administratorja.
