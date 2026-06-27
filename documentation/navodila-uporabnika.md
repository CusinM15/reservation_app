# 📖 Navodila za uporabo

## Prijava

1. Odprete spletno stran aplikacije: [https://ostc-app.org](https://ostc-app.org)
2. Vnesete **AAI uporabniško ime** (oz. email) in **geslo**
3. Po prijavi se v zgornjem desnem kotu izpiše vaše ime in vloga
4. Ob kliku na **Odjava** se izpišete
5. Po 1 uri neaktivnosti vas aplikacija samodejno odjavi

### Pozabljeno geslo

Kliknite **"Pozabljeno geslo?"** na prijavni strani, vnesite svoj službeni email in sledite povezavi v prejetem sporočilu.

### Pravila za gesla

- Vsaj **5 znakov** dolžine
- Vsaj **ena mala črka** (a–z)
- Vsaj **ena velika črka** (A–Ž)
- Vsaj **ena številka** (0–9)

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

- **Tablice** – didaktične tablice (kapaciteta: 28 kosov)
- **Računalnica** – računalniška učilnica (samo en učitelj na uro)
- **Ladja** – učilnica (samo en učitelj na uro)
- **Gospodinjska učilnica** – (samo en učitelj na uro)

### Kako rezervirati

1. Odprete zavihek **Rezervacije** (privzet pogled)
2. Izberete **začetek tedna** (privzeto trenutni teden)
3. Kliknete **Osveži**
4. Izberete želen prostor s klikom na zavihek
5. Pregled tedna prikazuje tabelo: vrstice so ure (0–7), stolpci so dnevi (pon–pet)
   - **Zelen "Prosto"** – termin je prost
   - **Zaseden termin** – prikazuje ime osebe
6. Rezervirate na dva načina:
   - Kliknete **+** v želeni celici (hitra rezervacija)
   - Kliknete **+ Nova rezervacija** zgoraj
7. Pri **Tablicah** vnesete še **število tablic**
8. Kliknete **Shrani**

### Kako izbrisati rezervacijo

- Kliknite rdeč **✕** gumb poleg rezervacije
- **Učitelj**: lahko brišete samo svoje rezervacije
- **Vodstvo / Admin**: lahko brišete tudi tuje

### Omejitve

| Prostor | Omejitev |
|---|---|
| **Tablice** | Skupaj max 28 na uro |
| **Računalnica** | Samo ena rezervacija na uro |
| **Ladja** | Samo ena rezervacija na uro |
| **Gospodinjska učilnica** | Samo ena rezervacija na uro |

---

## Ocenjevanja

### Kako napovedati ocenjevanje

1. Odprete zavihek **Ocenjevanje**
2. V spustnem meniju **Razred** izberete razred
3. Kliknete **Osveži**
4. Na koledarju kliknite **+** na želeni dan
5. Izpolnite obrazec in kliknite **Shrani**

### Kako izbrisati ocenjevanje

- Kliknite **✕** poleg ocenjevanja v koledarju
- **Učitelj**: lahko brišete samo svoja
- **Vodstvo / Admin**: lahko brišete tudi tuja

### Pravila in omejitve

| Pravilo | Opis |
|---|---|
| Največ 3 ocenjevanja na teden | V enem tednu max 3 |
| Največ 2 običajni na teden | Ponavljanje ne šteje v to omejitev |
| Prepoved istega dne | Ne morete imeti dveh na isti dan |
| Prepoved 3 zaporednih dni | Ne smejo biti na 3 zaporedne dni |

### Legenda v koledarju

- **🔵 Običajno ocenjevanje** – moder značek
- **🔄 Ponavljanje** – rdeč značek
- **🟣 Zaseden datum** – vijoličen značek

---

## Zasedeni datumi

**Kdo lahko upravlja:** Vodstvo in Admin.

Ko ima razred dejavnost (športni dan, ekskurzija...), lahko vodstvo te datume označi kot "zasedene". To prepreči, da bi učitelji na ta dan napovedovali ocenjevanja.

### Kako dodati zasedene datume

1. Odprete zavihek **Ocenjevanje**
2. Kliknete **🚫 Zasedeni datumi**
3. Izberete razred(e)
4. Vnesete datum OD in DO
5. Kliknete **Dodaj zasedene datume**

### Kako odstraniti zaseden datum

V oknu "Zasedeni datumi" se v spodnjem delu prikaže seznam blokad. Kliknite **✕** poleg tiste, ki jo želite odstraniti.

---

## Upravljanje uporabnikov (samo admin)

**Dostop:** V zgornji navigaciji se adminu prikaže gumb **Admin panel**.

### Funkcije

- **Dodajanje uporabnikov** – vnesete email, ime, priimek, geslo, vlogo
- **Pregled uporabnikov** – tabela z vsemi uporabniki
- **Urejanje** – kliknite "Uredi", spremenite podatke
- **Deaktivacija / Aktivacija** – onemogočite ali omogočite dostop
- **Brisanje** – trajno izbriše uporabnika (admin z ID=1 ni mogoče izbrisati)
- **Spremeni geslo** – admin lahko spremeni geslo uporabniku

---

## Sprememba gesla

### Ko še poznate geslo

1. V zgornji navigaciji kliknite **Spremeni geslo**
2. Vnesite trenutno geslo in novo geslo dvakrat
3. Kliknite **Spremeni geslo**

### Če ste pozabili geslo

1. Na prijavni strani kliknite **"Pozabljeno geslo?"**
2. Vnesite svoj službeni email
3. Sledite povezavi v prejetem emailu

---

## Tehnične podrobnosti

- **Samodejna odjava:** Po 1 uri neaktivnosti (30 min za admin/vodstvo)
- **Sočasni dostop:** Sistem preprečuje dvojne rezervacije (race condition detection)
- **Email obvestila:** Pošiljajo se prek Arnesovega SMTP strežnika
