🌐 **Jezik / Language:** [🇸🇮 Slovenščina](aplikacija-rezervacije.md) | [🇬🇧 English](en/aplikacija-rezervacije.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 📱 Aplikacija za rezervacije in napovedi ocenjevanja

## Namen — čemu sploh služi ta aplikacija?

Preden je nastala ta aplikacija, je na šoli potekalo vse po starem: učitelji so hodili po hodnikih, se ustavljali pred zbornico in drug drugega spraševali »Kdaj boš pisal test?«, »Si že zasedel računalnico?«, »A so tablice proste?«. Nastajali so lističi, koledarji na tablah in zmeda. Potem je nekdo pozabil vnesti ocenjevanje v redovalnico, pa so učenci v enem tednu pisali štiri teste — in pobesneli so starši, ravnatelj in zakon.

**Aplikacija rešuje dva ključna problema:**

1. **Mrežni diagram ocenjevanj** — učitelji vnesejo, kdaj bodo pisali test, aplikacija pa sama poskrbi, da ne pride do prekrivanj in kršitev pravilnik (največ 3 ocenjevanja na teden, največ 2 običajni, prepoved treh zaporednih dni ...). Namesto listkov na tabli — en klik.
2. **Rezervacija prostorov** — tablice, računalnica, ladja (pomivalni čoln) in gospodinjska učilnica. Vsak učitelj vidi v realnem času, kaj je prosto in kaj zasedeno.

Aplikacija je razvita za **OŠ Toneta Čufarja Jesenice**. Namenoma je narejena čim bolj preprosto — ker avtor ne bo večno na šoli. Ko bo nekega dne odšel, naj bi jo lahko vzdrževal in uporabljal vsak, ki mu ni tuje delo z računalnikom. Nič zapletenega, nič skrivnostnega.

**Strežnik:** Aplikacija teče na **Ubuntu Server** na starih računalnikih, ki so preslabi za Windows 11, a še vedno povsem dovolj zmogljivi za to delo. Strojna oprema, ki bi sicer romala v smeti, dobi novo, uporabno življenje. Trajnostno in praktično.

---

## Tehnologije — kaj vse poganja to aplikacijo?

Spodaj so tehnologije, ki jih aplikacija uporablja. Za računalničarja so to domače besede, za vse ostale pa sledi kratek opis — vsaka tehnologija ima svoj namen, kot ima na šoli vsak učitelj svoj predmet.

### Kako si sledijo plasti (sloji)?

Ko vi odprete aplikacijo v brskalniku, se zgodi tole:
1. Brskalnik pošlje zahtevo po omrežju
2. **MetalLB** poskrbi, da zahteva najde pravi strežnik na pravem naslovu
3. **k3s (Kubernetes)** pove, kateri del aplikacije naj zahtevo obdela
4. **FastAPI (Python)** obdela zahtevo — pogleda, kaj hočete, in pripravi odgovor
5. Če so potrebni podatki (ocene, uporabniki, rezervacije), jih **PostgreSQL** ali **SQLite** priskrbi iz baze

| Sloj | Tehnologija | Kaj to pomeni za laika |
|------|------------|------------------------|
| **Backend (ozadje)** | Python 3.12, FastAPI, Uvicorn | **Python** je programski jezik — niz navodil, ki jih računalnik izvaja. **FastAPI** je programsko ogrodje, ki pove aplikaciji, kako naj odgovarja na klike (kot recepcija, ki usmerja klice na prave ljudi). **Uvicorn** je stražar, ki čaka na dohodne zahteve in jih posreduje naprej. |
| **Podatkovna baza** | PostgreSQL (produkcija) / SQLite (razvoj) | **PostgreSQL** je digitalni arhiv — tja se shranjujejo vsi podatki: kdo je kaj rezerviral, kdaj je ocenjevanje, katera gesla ... V produkciji (ko aplikacija res deluje v živo) uporabljamo PostgreSQL, ker je zanesljiv in zmogljiv. Med razvojem (ko avtor kaj popravlja in testira) pa zadošča **SQLite**, ki je lažji in ne potrebuje strežnika. |
| **Frontend (vidni del)** | Jinja2 predloge, HTML/CSS/JS | Ko aplikacija pripravi odgovor, ga zavije v **HTML** (spletna stran), olepša z **CSS** (barve, pisave, postavitev) in poživi z **JavaScriptom** (gumbi, pojavna okna). **Jinja2** pa je predloga — kot šablona za dokument, kamor aplikacija samo vstavi podatke (ime učitelja, seznam rezervacij ...). |
| **Avtentikacija (prijava)** | piškotki (cookies) z bcrypt | Ko se prijavite, aplikacija v vaš brskalnik shrani **piškotek** — majhen košček podatka, s katerim vas prepozna ob naslednjem kliku. Gesla so zakodirana z **bcrypt** (matematični mlinček, ki iz gesla naredi nepovratno kodo — tudi če nekdo ukrade bazo, ne more prebrati gesel). |
| **Email** | SMTP prek Arnesa (mail.arnes.si) | Kadar aplikacija pošilja obvestila (npr. »Vaše ocenjevanje je bilo prestavljeno, ker je športni dan«), uporablja Arnesov poštni strežnik — enako, kot če bi poslali email iz šolskega računa. |
| **Orkestracija (povezovanje)** | Kubernetes — natančneje **k3s** | Predstavljajte si, da imate zabojnik (container) z aplikacijo, ki živi v virtualnem svetu. **Kubernetes** (k3s) je dirigent, ki poskrbi, da ti zabojniki delujejo usklajeno: če eden crkne, ga zažene na novo; če prihaja preveč obiskovalcev, jih razporedi med več zabojnikov. **k3s** je lažja različica Kubernetes, narejena prav za take manjše sisteme. |
| **Shramba (disk)** | **Longhorn** | **Longhorn** je distribuiran blokovni storage — oziroma po domače: pameten virtualni disk. Podatki so shranjeni na **obeh** računalnikih hkrati, tako da če eden crkne (se sesuje ali izklopi), drugi še vedno ima vse podatke. Brez izgube, brez panike. |
| **Omrežni naslov** | **MetalLB** | **MetalLB** skrbi, da ima aplikacija **fiksni naslov v omrežju**. Tako kot ima šolska knjižnica vedno isti prostor v stavbi, ima aplikacija vedno isti IP-naslov — tudi če se strežniki zamenjajo ali prestavijo. Učitelji vedno odprejo isti naslov in aplikacija je tam. |

---

## Spremenljivke za celotno aplikacijo — .env

V datoteki `.env` so shranjeni vsi pomembni nastavitveni podatki. To je kot **nadzorna plošča** aplikacije — če hočete kaj spremeniti (npr. dodati nov prostor, spremeniti uro pošiljanja pošte, povečati število tablic), to naredite tukaj. Nobene potrebe po brskanju po kodi.

```bash
# App settings
APP_HOST=0.0.0.0
APP_PORT=port na katerem teče app

DATABASE_URL=naslov podatkovne baze (postgresql)

# Email settings
MAIL_USERNAME=kratek naziv maila (uporabniško ime)
MAIL_PASSWORD=*** geslo maila
MAIL_SERVER=mail.arnes.si
MAIL_PORT=587
MAIL_FROM=naslov, s katerega aplikacija pošilja sporočila
BACKUP_EMAIL=email, ki dnevno dobi varnostno kopijo baze
STANJE_MAIL=email, ki dnevno dobi poročilo o stanju klastra

# App config
TABLICE_MAX=največje število vseh tablic (trenutno 28)
SCHEDULE={"številka ure":"časovni interval ure"}
RAZREDI=seznam vseh razredov na šoli
PROSTORI=seznam vseh prostorov, ki jih je mogoče rezervirati

# Session timeout (teacher)
INACTIVITY_TIMEOUT_MINUTES=po koliko minutah nedejavnosti se učitelj samodejno odjavi
# Session timeout (admin/vodstvo)
INACTIVITY_TIMEOUT_ADMIN_MINUTES=po koliko minutah nedejavnosti se vodstvo/admin samodejno odjavi
```

---

## Funkcionalnosti — kaj vse aplikacija zmore?

### 📌 Rezervacije prostorov

Aplikacija omogoča rezervacijo štirih vrst prostorov/stvari:

| Prostor | Opis | Pravilo |
|---------|------|---------|
| **Tablice** | 28 kosov prenosnih tablic | Več učiteljev si jih lahko deli v isti uri — vsak dobi svoj košček |
| **Računalnica** | Učilnica z računalniki | **Ena** rezervacija na termin — kdor prvi pride, prvi melje |
| **Ladja** (pomivalni čoln) | Poseben pripomoček za praktični pouk | **Ena** rezervacija na termin |
| **Gospodinjska učilnica** | Učilnica za gospodinjstvo | **Ena** rezervacija na termin |

Rezervacije so prikazane v preglednem koledarju. Vsak učitelj vidi, kaj je prosto, kaj zasedeno in kdo je zasedel. Brez listkov, brez spraševanja.

### 📝 Napovedovanje ocenjevanj

Učitelji vnesejo datum in razred, aplikacija pa **samodejno preveri vsa pravila** — tako da do kršitev sploh ne more priti.

**Pravila, ki jih sistem uveljavlja:**

- **Največ 3 ocenjevanja na teden** — ne glede na vrsto
- **Največ 2 običajni (neponavljalni) ocenjevanji na teden** — da učencev ne preobremenjujemo
- **Prepoved treh zaporednih dni** — noben razred ne sme pisati testa tri dni zapored
- **Samodejno preverjanje pravil za 1.–7. razred** — mlajši učenci so dodatno zaščiteni

Če učitelj poskuša vnesti ocenjevanje, ki bi kršilo pravila, ga aplikacija **ne pusti**. Pokaže opozorilo in pojasni, zakaj termin ni mogoč. Ni več »nisem vedel, da že imate test«.

### 🚫 Zasedeni datumi

Vodstvo ali admin lahko označi poljubne dneve kot **zasedene** — to so dnevi, ko ocenjevanja **niso dovoljena** (športni dan, ekskurzija, kulturni dan, nastopi ...).

Ko vodstvo označi zasedeno obdobje:

1. **Sistem samodejno pobriše** vsa obstoječa ocenjevanja, ki so padla v to obdobje
2. **Pošlje email obvestila** vsem prizadetim učiteljem — natančno pove, katero ocenjevanje je bilo preklicano in zakaj
3. V koledarju se obdobje prikaže kot **rdeče** (zasedeno)

Ni več potrebe, da ravnatelj pošilja okrožnice in prosi učitelje, naj ročno brišejo termine. Vse naredi aplikacija.

### ⚙️ Admin panel

**Samo za administratorja.** Tu se upravljajo uporabniki:

- **Dodajanje** novih uporabnikov (novi učitelji, novo vodstvo)
- **Urejanje** obstoječih (sprememba imena, vloge, emaila)
- **Brisanje** uporabnikov (ko odidejo iz šole)
- **Deaktivacija** (začasno onemogoči dostop, ne da bi izbrisali podatke)

Admin panel je preprost in pregleden — nobenih skritih menijev ali zapletenih nastavitev.

---

## Vloge uporabnikov — kdo sme kaj početi?

Šola ima tri vrste uporabnikov. Vsaka ima svoje pravice — podobno kot imajo učenci, učitelji in ravnatelj različne ključe od različnih omar.

| Funkcija | Učitelj | Vodstvo | Admin |
|----------|:-------:|:-------:|:-----:|
| **Rezervacija prostorov** | ✅ Da | ✅ Da | ✅ Da |
| **Brisanje lastne rezervacije** | ✅ Da | ✅ Da | ✅ Da |
| **Brisanje tuje rezervacije** | ❌ Ne | ✅ Da | ✅ Da |
| **Napoved ocenjevanja** | ✅ Da | ✅ Da | ✅ Da |
| **Upravljanje zasedenih datumov** | ❌ Ne | ✅ Da | ✅ Da |
| **Admin panel (uporabniki)** | ❌ Ne | ❌ Ne | ✅ Da |

**Učitelj** — lahko rezervira prostore, napoveduje ocenjevanja in briše samo svoje vnose. Ne more posegati v delo drugih.

**Vodstvo** (ravnatelj, pomočnik) — lahko počne vse, kar učitelj, **poleg tega** pa lahko briše tuje rezervacije (če je treba kaj nujno prestaviti) in označuje zasedene datume. Edino česar ne more: upravljati uporabnikov.

**Admin** — najvišja raven dostopa. Lahko počne čisto vse, vključno z dodajanjem in brisanjem uporabnikov. Običajno je to ena do dve osebi na šoli (računalnikar, skrbnik informacijskega sistema).

---

## Zakaj je vse skupaj tako preprosto?

Avtor aplikacije se zaveda, da ne bo večno na šoli. Zato je vsaka odločitev pri razvoju sledila trem načelom:

1. **Enostavnost** — če lahko nekaj narediš na preprost način, ni razloga za zapletenega
2. **Vzdržljivost** — aplikacija mora delovati tudi, ko avtorja ni več
3. **Preglednost** — vsak, ki zna odpreti datoteko `.env` in brati dokumentacijo, mora razumeti, kako stvari delujejo

Zato so tehnologije izbrane premišljeno in dokumentacija napisana v čim bolj razumljivem jeziku. Če vam je kaj nejasno, vprašajte administratorja — in če tudi on ne ve, imate vsaj točno vedenje, kje iskati.

---

> **Avtor:** Matej Čušin  
> **Šola:** OŠ Toneta Čufarja, Jesenice
