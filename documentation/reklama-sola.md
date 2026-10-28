# 🏫 Rezervacijska aplikacija za šole

## Vse šolske prostore, ocenjevanja in načrtovanje — na enem mestu, pripravljeno za vsako šolo.

Aplikacijo, ki jo uporabljamo tudi na šoli, kjer sem zaposlen, smo zasnovali čim bolj
pregledno in razumljivo — tudi za manj IT-pismene uporabnike. Združuje **rezervacijo
prostorov**, **napovedovanje ocenjevanj** s pravili (kakor veleva zakon), **pregled
dejavnosti**, **digitalne zaslone za nadomeščanja** in **najave na govorilne ure** —
v eni preprosti, hitri spletni rešitvi. Brez namestitve na računalnike, brez samodejnih
podaljšanj in skritih stroškov.

---

## 💰 Zakaj se splača? 150 € na leto, vse vključeno

- **150 € na leto** — to je le **12,50 € na mesec** za celotno rešitev. Gostovanje,
  vzdrževanje, posodobitve in varnostne kopije (e-poštni backup 1-klik) so že v ceni;
  ničesar ni treba kupovati ali plačevati posebej.
- **Proporcionalni obračun** — če se šola priključi sredi šolskega leta, se zaračuna le
  **sorazmerni (proporcionalni) delež** do 1. 9., ne celo leto.
- **Za čisti self hosting imajo šole tri možnosti** — vse **cenejše od 100 € na leto** za
  samo delovanje (izjema je enkratni nakup stroja):
    - **1. Stari prenosniki (najcenejše)** — aplikacijo poganjajo **stari prenosniki,
      preslabi za Windows 11** (ta zahteva TPM 2.0 in podprt procesor, Windows 10 pa je
      oktobra 2025 ostal brez varnostnih posodobitev). Za ~100–200 uporabnikov zadostuje že
      **1 CPU in 1 GB RAM** — v avtorjevi produkciji aplikacija dejansko teče na HP ProBook
      prenosnikih. Stroj stane **0 €** (šola ga že ima — namesto v smeti dobi novo
      življenje), strošek je samo elektrika:
        - **Primer: 3 stari prenosniki** — povprečno ~15 W vsak, prižgani 24/7 skozi leto →
          ≈ 400 kWh/leto; ob slovenski ceni elektrike (~0,15–0,20 €/kWh) je to
          **≈ 60–80 €/leto — manj kot 100 €**.
    - **2. Nakup strežnika (enkratni strošek)** — majhen, tih in varčen namenski stroj v
      obsegu 110–200 € (enkratno); od takrat naprej je strošek samo elektrika (~10–20 €/leto):
        - **Intel N100 mini-PC** (8 GB RAM + 256 GB SSD): **~150–200 €** — zelo varčen (6 W), več kot dovolj za 100–200 uporabnikov.
        - **Raspberry Pi 5 (8 GB)** + napajalnik + ohišje + shramba: **~120–160 €** — ARM,
          poln nadzor nad podatki.
        - **Prenovljen rabljen mini/stolpni računalnik** (npr. Dell OptiPlex / HP EliteDesk,
          i5/i7, 8–16 GB RAM): **~110–160 €** — najcenejši x86 z dobrim procesorjem.
    - **3. Gostovanje v oblaku (nič strojne opreme)** — najem virtualnega strežnika (VPS)
      od **~3–8,50 €/mesec (~36–99 €/leto)**, brez skrbi za strojno opremo:
        - **Hetzner** (EU regiji: Nemčija in Finska — vedno izberi EU regijo): od
          **~5,99 €/mesec (~72 €/leto)**.
        - **Netcup** (Nemčija, samo EU): od **~8,26 €/mesec (~99 €/leto)** pri letni pogodbi.
        - **Scaleway** (Francija/Nizozemska/Poljska, samo EU): od **~3–4,50 €/mesec**.
        - ⚠️ **Pomembno za podatke šole:** nekateri ponudniki (npr. Contabo, IONOS, OVH,
          DigitalOcean) imajo podatkovne centre **tudi zunaj EU** — ob naročilu **vedno
          izberi EU regijo**, po možnosti pa **samo-EU ponudnika** (Netcup, Scaleway).
          Shranjevanje podatkov učencev v državi zunaj EU/EGP sproži zahtevnejši
          GDPR postopek (poglavje V) — **ne-EU gostovanje zato zelo odsvetujem**.
- **Bi se raje lotili sami?** Aplikacija je **odprtokodna** — koda je na voljo na GitHubu:
  [github.com/CusinM15/reservation_app](https://github.com/CusinM15/reservation_app).
  Odprtokodna različica vsebuje **manj funkcij** kot plačljiva storitev; samo delovanje
  strežnika vas bo stalo **manj kot 100 €/leto** (stari prenosniki ali nizek VPS). Vse
  ostalo bo moral prevzeti šolski administrator:
    - postavitev strežnika in namestitev aplikacije,
    - redne posodobitve in varnostne kopije (backupe si mora šolski administrator
      nastaviti sam — ni avtomatskega nočnega cronjoba; če jih admin ne nastavi,
      varnostnih kopij ni),
    - nastavitev e-pošte (SMTP) in SSL-potrdila,
    - varnost, spremljanje delovanja in skrb za podatke (GDPR).
  Pri odprtokodni različici so na voljo le **podrobno pisana navodila** (dokumentacija);
  vzdrževanje, odgovornost in skrb za podatke so povsem na šoli.

---

## ✅ Kaj aplikacija reši?

### 🗓️ Rezervacija prostorov in opreme
- Rezervirajte **katerikoli prostor ali opremo** (računalnica, telovadnica, tablice …)
  v nekaj klikih.
- **Ekskluzivni prostori** (samo en učitelj na termin) ali **prostori z več enotami**
  (tablice, kjer več učiteljev rezervira hkrati, ob upoštevanju kapacitete).
- Tedenski koledar + okno za novo rezervacijo, ki samodejno ponuja proste termine.
- **Serijske rezervacije** za vodstvo in administratorje (teden ali cel dan vnaprej).
- **Dnevi dejavnosti** so povezani s koledarjem za ocenjevanje in rezervacijami — z enim
  korakom lahko npr. rezervirate računalnico in hkrati blokirate ocenjevanje za določen razred.

### ✏️ Napovedovanje ocenjevanj (pisnih testov)
- Napovedite pisni test z **dvema klikoma** — iz koledarja ali ročno.
- **Nastavljiva pravila**, ki jih ureja šola: največ testov na dan/teden, prepoved
  ponavljanj, vrstni red. Če se zakon ali pravilnik spremeni, **pravila samo
  posodobite v nastavitvah** — nič se ne podira, aplikacija ostane v skladu z novimi
  predpisi.
- **Pravila se upoštevajo samodejno** (1.–7. razred), za višje razrede (8.–9.)
  ostanejo fleksibilna. Zaradi skupin pri višjih razredih (npr. 8. razredi so 8. 1,
  8. 2, 8. 3, 8. 4 ter 8. a, 8. b, 8. c) pravila delujejo za vsak razred posebej —
  aplikacija ne ve, da 8. 1 sestavljajo učenci iz 8. a, saj imena otrok niso vnesena,
  zato skupine obravnava kot ločene razrede.
- Oznake za **ponavljanje (PIP)**, izbirne predmete in barvne prikaze ocenjevanj.

### 🎒 Dnevi dejavnosti
- Vodstvo označi dan kot **dan dejavnosti** (npr. športni dan) brez zapletov.
- **Šola označi, ali dejavnost traja cel dan ali le del** — aplikacija to upošteva:
  celodnevna dejavnost **zapre** prostor za teste, krajša pa ga pusti odprtega.
- Če imate za ta dan že napovedano ocenjevanje, dobite **samodejno obvestilo**,
  vi pa ste na varnem.
- Če je označen celoten dan in je izbran prostor (npr. računalnica), se ta samodejno
  rezervira (npr. od 1. do 5. šolske ure).

### 🖥️ Digitalni zasloni z nadomeščanji
- Nadomeščanja iz **eAsistenta** prikazujte na zaslonih šole (ali prek spleta).
- Obvestila (slike in besedila) dodajate v vmesniku; na zaslonu se **vrtijo s
  tempom, ki ga izberete**.
- Nastavljiv časovni pas, hitrost drsenja, interval prikaza in gumb
  **„Osveži vse naprave“** — spremembo vidi vsak zaslon v nekaj sekundah.
- Ta stran je dostopna brez prijave v aplikacijo.

### 🗓️ Najave na govorilne ure (dodatna funkcija)
- Starši **najavijo termin** za govorilne ure sami, prek spleta — brez telefonskih
  klicev in brez iskanja terminov.
- Učitelji svoj urnik **objavijo sami** (dopoldanski termin, predmet, prostor),
  vodstvo vidi vse rezervacije.
- **24-urna hramba prijav** za varovanje podatkov, enostavno brisanje.
- Ker so na šoli trije različni urniki za prve tri ure, si učitelj izbere, kateremu
  pripada — termini so tako vedno ob pravem času glede na njegov urnik.

### 📄 Obrazci, obvestila in navodila
- Lepo oblikovana **obvestila za starše in učitelje** (A4, lahko jih natisnete ali
  pošljete prek eAsistenta).
- Navodila za uporabo so vgrajena v aplikacijo, po vlogah (učitelji/vodstvo/admin).

---

## 🎯 Kdo ga uporablja in zakaj vam bo všeč?

- **Učiteljem** prihrani vsakodnevno poganjanje „kdo je zasedel telovadnico“ — vse
  vidijo v enem koledarju.
- **Vodstvu** daje nadzor: serijske rezervacije, dnevi dejavnosti, pregled
  ocenjevanj in dejavnosti.
- **Administratorjem** poenostavi uvoz uporabnikov, nastavitve in varnostne kopije
  (e-poštni backup 1-klik).

### 🔒 Varnost
- Vsaka šola ima **svoje podatke** — druge šole jih ne vidijo.
- **GDPR-pripravljena**: aplikacija hrani le podatke osebja, prijave staršev se
  samodejno čistijo; na zahtevo nadzornega organa (DPA).
- Vsi dostopi so **beleženi** (audit log) in pregledni za šolske in glavne administratorje.

---

## 🚀 Kako začeti?

1. **Šola si sama ustvari račun** — na strani za registracijo vpišete ime šole in takoj
   dobite **administratorski račun** (račun ustvari administrator sam, ne čaka na nas).
    - **1.a** Najprej nastavite **SMTP-nastavitve** za pošiljanje e-pošte, nato si
      določite **admin geslo** (prek možnosti »pozabljeno geslo«).
    - **1.b** Pred plačilom se lahko prijavita zgolj **vodstvo in admin šole**.
2. **Administrator in vodstvo pripravita vse** — nastavita e-pošto za pošiljanje (SMTP),
   razrede, prostore, urnik in pravila ocenjevanja — **še preden začnejo uporabljati učitelji**.
3. **Uredite naročnino** — velja vedno **do 1. 9.**; za naslednje leto jo lahko sklenete
   **šele od 15. 8. dalje**. Naročnina **se ne da prekiniti** pred iztekom (do 1. 9.) —
   sklenete jo za celo šolsko leto.
4. **Uvozite učitelje** in začnite uporabljati — učitelji in vodstvo se prijavijo, ko je
   naročnina urejena in potrjena.

> ⚠️ **Naročnino je treba skleniti v 28 dneh** od ustvaritve računa. Če je v tem roku
> ne sklenete, se šola **samodejno izbriše**.

> Aplikacija teče na hitrem, zanesljivem strežniku v EU. Prilagoditve po dogovoru.

---

*Rezervacijska aplikacija za šole — vse načrtovanje šolskega dne na enem mestu.*
