# Navodila za uporabo Šolskega App-a

## 📋 Vsebina

1. [Prijava](#prijava)
2. [Vloge uporabnikov](#vloge-uporabnikov)
3. [Rezervacije prostorov](#rezervacije-prostorov)
4. [Ocenjevanja](#ocenjevanja)
5. [Zasedeni datumi](#zasedeni-datumi)
6. [Upravljanje uporabnikov (samo admin)](#upravljanje-uporabnikov-samo-admin)
7. [Sprememba gesla](#sprememba-gesla)

---

## Prijava

1. Odprete spletno stran aplikacije.
2. Vnesete **AAI uporabniško ime** (oz. email) in **geslo**.
3. Po prijavi se v zgornjem desnem kotu izpiše vaše ime in vloga (učitelj / vodstvo / admin).
4. Ob kliku na **Odjava** se izpišete.
5. Če ste dlje časa neaktivni (1 ura), vas aplikacija samodejno odjavi.

---

## Vloge uporabnikov

| Funkcija | Učitelj | Vodstvo | Admin |
|---|---|---|---|
| Rezervacija prostorov | ✅ | ✅ | ✅ |
| Brisanje lastne rezervacije | ✅ | ✅ | ✅ |
| Brisanje tuje rezervacije | ❌ | ✅ | ✅ |
| Napoved ocenjevanja | ✅ | ✅ | ✅ |
| Brisanje lastnega ocenjevanja | ✅ | ✅ | ✅ |
| Brisanje tujega ocenjevanja | ❌ | ✅ | ✅ |
| Upravljanje zasedenih datumov | ❌ | ✅ | ✅ |
| Admin panel (uporabniki) | ❌ | ❌ | ✅ |

---

## Rezervacije prostorov

### Prostori
- **Tablice** – didaktične tablice (kapaciteta: 28 kosov). Rezervirate lahko poljubno število, tudi več učiteljev v isti uri.
- **Računalnica** – računalniška učilnica (samo en učitelj na uro).
- **Ladja** – učilnica ladja (samo en učitelj na uro).

### Kako rezervirati

1. Odprete zavihek **Rezervacije** (privzet pogled).
2. Izberete **začetek tedna** (privzeto je trenutni teden, ponedeljek).
3. Kliknete **Osveži**, da se naloži pregled tedna.
4. Izberete želen prostor s klikom na zavihek (**Tablice**, **Računalnica** ali **Ladja**).
5. Pregled tedna prikazuje tabelo: vrstice so ure (0–7), stolpci so dnevi (pon–pet).
   - **Zelen "Prosto"** – termin je prost, lahko rezervirate.
   - **Zaseden termin** – prikazuje ime osebe, ki je rezervirala.
6. Rezervirate na dva načina:
   - Kliknete **+** v želeni celici (hitra rezervacija).
   - Ali kliknete **+ Nova rezervacija** zgoraj in izpolnite obrazec.
7. Pri **Tablicah** vnesete še **število tablic** (koliko kosov potrebujete).
8. Kliknete **Shrani**.

### Kako izbrisati rezervacijo
- Kliknite rdeč **✕** gumb poleg rezervacije v tabeli.
- **Učitelj**: lahko brišete samo svoje rezervacije.
- **Vodstvo / Admin**: lahko brišete tudi tuje rezervacije.

### Omejitve pri rezervaciji

| Prostor | Omejitev |
|---|---|
| **Tablice** | Skupno število rezerviranih tablic na isto uro ne sme preseči **28**. Več učiteljev si lahko deli tablice v isti uri. |
| **Računalnica** | Samo **ena rezervacija** na uro (kdor prvi pride, prvi melje). |
| **Ladja** | Samo **ena rezervacija** na uro. |

### Pomembno
- Rezervirate lahko samo za **delavnike** (pon–pet). V tabeli so prikazani samo pon–pet.
- Če dva učitelja istočasno klikneta "Shrani" za isti termin, bo eden od njiju dobil sporočilo, da je prišlo do sočasne rezervacije. V tem primeru poskusite znova.

---

## Ocenjevanja

### Kako napovedati ocenjevanje

1. Odprete zavihek **Ocenjevanje**.
2. V spustnem meniju **Razred** izberete razred:
   - **"Vsi razredi"** – prikaže vsa ocenjevanja v mesecu.
   - **"🗂️ 8. razred (vsi)"** / **"🗂️ 9. razred (vsi)"** – prikaže vse oddelke 8. oz. 9. razreda.
   - Posamezen razred (npr. `8.a`, `9.b`).
3. Kliknete **Osveži**.
4. Pregledujete mesečni koledar. Na dnevu, kamor želite dodati ocenjevanje, kliknite **+** ali kliknite na prazen dan.
5. Izpolnite obrazec:
   - Izberite **razred**.
   - Izberite **datum**.
   - Označite **"Ponavljanje"** (🔄), če gre za ponavljalno ocenjevanje (neobvezno).
6. Kliknite **Shrani**.

### Kako izbrisati ocenjevanje
- Kliknite **✕** poleg ocenjevanja v koledarju.
- **Učitelj**: lahko brišete samo svoja ocenjevanja.
- **Vodstvo / Admin**: lahko brišete tudi tuja ocenjevanja.

### Pravila in omejitve

| Pravilo | Opis |
|---|---|
| **Največ 3 ocenjevanja na teden** | V enem tednu (pon–ned) lahko ima razred največ **3 ocenjevanja** skupaj. |
| **Največ 2 običajni ocenjevanji na teden** | Od treh so lahko največ **2 običajni** (neponavljalni). Ponavljanje ne šteje v to omejitev. |
| **Prepoved istega dne** | V istem tednu ne morete imeti dveh ocenjevanj na **isti dan**. |
| **Prepoved 3 zaporednih dni** | Ocenjevanja **ne smejo** biti na **3 zaporedne dni** (npr. ponedeljek + torek + sreda). To velja za vsa ocenjevanja, ne glede na vrsto. |
| **Vrstni red ni pomemben** | Pravila veljajo ne glede na vrstni red dodajanja. Če najprej dodate ponavljanje in nato dva običajna testa – vseeno veljajo ista pravila. |

### Legenda v koledarju
- **🔵 Običajno ocenjevanje** – moder značek.
- **🔄 Ponavljanje** – rdeč značek s simbolom 🔄.
- **🟣 Zaseden datum** – vijoličen značek (razred ima ta dan dejavnost).

### Kaj se zgodi, če dodate ocenjevanje na zaseden datum?
Če razred označite kot zaseden (blokiran) in nekdo kasneje doda ocenjevanje na isti dan, bo ustvarjalec zasedenih datumov prejel email obvestilo.

---

## Zasedeni datumi

**Kdo lahko upravlja:** Vodstvo in Admin.

### Namen
Ko ima razred **dejavnost** (npr. športni dan, kulturni dan, ekskurzija, tehniški dan), lahko te datume označite kot "zasedene". To prepreči, da bi učitelji na ta dan napovedovali ocenjevanja.

### Kako dodati zasedene datume

1. Odprete zavihek **Ocenjevanje**.
2. Kliknete **🚫 Zasedeni datumi**.
3. Izberete **razred(e)** (držite Ctrl za izbor več razredov).
4. Vnesete **datum OD** in **datum DO**.
5. Kliknete **Dodaj zasedene datume**.
6. Sistem:
   - Doda zasedene datume (samo delavniki).
   - **Samodejno izbriše vsa obstoječa ocenjevanja** za ta razred v tem obdobju.
   - Pošlje **email obvestila** učiteljem, katerih ocenjevanja so bila izbrisana (če imajo vnešen email).

### Kako odstraniti zaseden datum
V oknu "Zasedeni datumi" se v spodnjem delu prikaže seznam obstoječih blokad. Kliknite **✕** poleg tiste, ki jo želite odstraniti.

---

## Upravljanje uporabnikov (samo admin)

**Dostop:** V zgornji navigacijski vrstici se adminu prikaže gumb **Admin panel**.

### Funkcije
- **Dodajanje uporabnikov** – vnesete AAI uporabniško ime, ime, priimek, geslo, vlogo (učitelj / vodstvo / admin).
- **Pregled uporabnikov** – tabela z vsemi uporabniki, ki jo lahko razvrščate s klikom na ime stolpca (ID, uporabniško ime, email, ime, priimek, vloga, aktiven).
- **Urejanje uporabnika** – kliknite "Uredi" ob uporabniku, spremenite podatke in shranite. Če pustite polje za geslo prazno, geslo ostane nespremenjeno.
- **Deaktivacija / Aktivacija** – onemogočite ali ponovno omogočite dostop uporabniku. Deaktiviran uporabnik se ne more prijaviti.
- **Brisanje uporabnika** – trajno izbriše uporabnika in vsa njegova ocenjevanja ter rezervacije. Admina z ID=1 ni mogoče izbrisati.

---

## Sprememba gesla

1. V zgornji navigaciji kliknite **Spremeni geslo**.
2. Vnesite **trenutno geslo** in **novo geslo** dvakrat.
3. Kliknite **Spremeni geslo**.
4. Ob uspehu se okno samodejno zapre po 1,5 sekunde.

---

## Tehnične podrobnosti

- **Samodejna odjava:** Po 1 uri neaktivnosti.
- **Sočasni dostop:** Sistem preprečuje dvojne rezervacije in podvojena ocenjevanja v istem trenutku (race condition detection).
- **Email obvestila:** Pošiljajo se preko Arnesovega SMTP strežnika. Če email ni poslan (npr. ni vnešenega email naslova), aplikacija deluje normalno naprej.
