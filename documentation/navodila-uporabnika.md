🌐 **Jezik / Language:** [🇸🇮 Slovenščina](navodila-uporabnika.md) | [🇬🇧 English](en/navodila-uporabnika.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 📖 Navodila za uporabo — aplikacija OSTC

> 🏫 **Dobrodošli!** To so navodila za aplikacijo, s katero boste lažje
> organizirali svoje delo — rezervacije prostorov, napovedi ocenjevanj in še kaj.
> Napisana so tako, da jih razume vsakdo. **Probajte, ne morete ničesar
> pokvariti!** 👍

---

## 🔐 Prijava — kot vstop v šolo

Prijava je podobna vstopu v šolo: **pokažete izkaznico (email)** in **poveste
geslo**. Aplikacija vas prepozna in prikaže vaše ime.

### Prvič se prijavljate?

1. **Odprite spletno stran:** [https://ostc-app.org](https://ostc-app.org)
2. **Vnesite svoj službeni email** (tistega, ki ga uporabljate v šoli)
3. **Vnesite geslo** — če ga dobite prvič, ga boste morda morali takoj
   spremeniti (glejte poglavje o geslih spodaj)
4. Kliknite **Prijava**
5. V zgornjem desnem kotu se izpiše **vaše ime** in **vloga** (npr. Učitelj,
   Vodstvo, Admin) — to pomeni, da ste uspešno noter! 🎉

### Kako se odjaviti?

- Kliknite **Odjava** v zgornjem desnem kotu.
- Aplikacija vas bo **samodejno odjavila** po **1 uri** nedejavnosti (če ste
  Vodstvo ali Admin, po **30 minutah**). To je varnostni ukrep — kot da bi se
  vrata za vami sama zaklenila.

### Pozabljeno geslo? 😰

Brez skrbi, to se zgodi najboljšim. Naredite tole:

1. Na prijavni strani kliknite **"Pozabljeno geslo?"**
2. Vnesite svoj **službeni email**
3. Preverite svoj email — v nekaj trenutkih boste dobili sporočilo s povezavo
4. Kliknite povezavo in **sledite navodilom**

Če emaila ne najdete, preverite še mapo **"Neželena pošta"** (Spam/Junk).

### Pravila za gesla — zakaj so taka?

Geslo mora vsebovati:
| Zahteva | Zakaj? |
|---|---|
| Vsaj **5 znakov** | Daljša gesla so težje uganljiva |
| Vsaj **ena mala črka** (a–z) | Za večjo varnost |
| Vsaj **ena velika črka** (A–Ž) | Za večjo varnost |
| Vsaj **ena številka** (0–9) | Za večjo varnost |

📝 **Nasvet:** Uporabite besedno zvezo, ki si jo lahko zapomnite, npr.
*MojRazred9a* — vsebuje vse zahtevane elemente, pa si jo boste zapomnili.

---

## 👥 Kdo lahko kaj počne? (Vloge uporabnikov)

Vsak ima svojo vlogo, tako kot v šoli. Tukaj je pregled, kaj kdo lahko počne:

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

✅ **Lahko** | ❌ **Ne more**

---

## 🏠 Rezervacije prostorov — kot rezervacija mize v restavraciji

Rezervacija prostora je podobna kot če si rezervirate mizo v restavraciji —
samo tokrat gre za **tablice**, **računalnico** ali **učilnico**. Preverite,
kaj je prosto, in si vzamete termin.

### Kateri prostori so na voljo?

| Prostor | Opis | Kapaciteta |
|---|---|---|
| **Tablice** 📱 | Didaktične tablice — največ 28 kosov na uro | 28 kosov |
| **Računalnica** 💻 | Računalniška učilnica — samo en učitelj na uro | 1 oseba na uro |
| **Ladja** 🚢 | Učilnica — samo en učitelj na uro | 1 oseba na uro |
| **Gospodinjska učilnica** 🧑‍🍳 | Učilnica — samo en učitelj na uro | 1 oseba na uro |

### Kako rezervirati — korak za korakom

1. **Odprite zavihek Rezervacije** (to je privzet pogled, ko se prijavite)
2. **Izberite začetek tedna** — privzeto je prikazan trenutni teden
3. Kliknite **Osveži** 🔄
4. **Izberite prostor** — kliknite na zavihek (Tablice, Računalnica itd.)
5. Pregled tedna prikazuje **tabelo**:
   - **Vrstice** so ure pouka (0–7)
   - **Stolpci** so dnevi (pon–pet)
   - **Zelen "Prosto"** — termin je na voljo ✅
   - **Zaseden termin** — prikazuje ime osebe, ki si ga je že rezervirala
6. Rezervirate lahko na **dva načina**:
   - **Hitra rezervacija:** kliknite **+** v želeni celici
   - **Podrobna rezervacija:** kliknite **+ Nova rezervacija** zgoraj
7. Če rezervirate **Tablice**, vnesite še **število tablic** (največ 28)
8. Kliknite **Shrani** ✅

🎉 **Rezervacija je narejena!**

### Kako izbrisati rezervacijo? 🗑️

- Kliknite rdeč **✕** gumb poleg rezervacije
- **Učitelj:** lahko brišete **samo svoje** rezervacije
- **Vodstvo / Admin:** lahko brišete **tudi tuje**

### Omejitve rezervacij — zakaj?

Omejitve so tu zato, da se prostori pravično porazdelijo med vse učitelje:

| Prostor | Omejitev | Razlog |
|---|---|---|
| **Tablice** | Skupaj max 28 na uro | Toliko tablic imamo na zalogi |
| **Računalnica** | Samo ena rezervacija na uro | Dva učitelja se ne moreta istočasno učiti v isti učilnici |
| **Ladja** | Samo ena rezervacija na uro | Isto kot zgoraj |
| **Gospodinjska učilnica** | Samo ena rezervacija na uro | Isto kot zgoraj |

---

## 📝 Ocenjevanja — napovedujte pametno in pravično

Ocenjevanja imajo omejitve z razlogom — **da učenci niso preobremenjeni** in da
se ocenjevanja ne kopičijo. Pomislite nase, ko ste bili v šoli — preveč testov
v enem tednu ni bilo prijetno za nikogar. 😅

### Kako napovedati ocenjevanje

1. **Odprite zavihek Ocenjevanje**
2. V spustnem meniju **Razred** izberite ustrezen razred
3. Kliknite **Osveži** 🔄
4. Na koledarju kliknite **+** na želeni dan
5. Izpolnite obrazec:
   - Izberite, ali gre za **običajno ocenjevanje** ali **ponavljanje**
   - Po potrebi dodajte še kakšno opombo
6. Kliknite **Shrani** ✅

### Kako izbrisati ocenjevanje 🗑️

- Kliknite **✕** poleg ocenjevanja v koledarju
- **Učitelj:** lahko brišete **samo svoja** ocenjevanja
- **Vodstvo / Admin:** lahko brišete **tudi tuja**

### Pravila in omejitve — zakaj?

| Pravilo | Podrobneje |
|---|---|
| **Največ 3 ocenjevanja na teden** 📅 | V enem tednu ne morete napovedati več kot 3 ocenjevanj za isti razred |
| **Največ 2 običajni na teden** 📋 | Ponavljanja ne štejejo v to omejitev — torej lahko imate 2 običajni + 1 ponavljanje |
| **Prepoved istega dne** 🚫 | Ne morete imeti dveh ocenjevanj na isti dan za isti razred |
| **Prepoved 3 zaporednih dni** 🚫 | Ocenjevanja se ne smejo vrstiti na 3 zaporedne dni — razred mora imeti vsaj en dan premora |

### Legenda v koledarju — barve povedo veliko

| Barva | Pomen |
|---|---|
| 🔵 **Moder značek** | Običajno ocenjevanje |
| 🔄 **Rdeč značek** | Ponavljanje |
| 🟣 **Vijoličen značek** | Zaseden datum (določilo vodstvo) |

---

## 🚫 Zasedeni datumi — ko ima razred druge načrte

**Kdo lahko upravlja:** Samo Vodstvo in Admin.

Ko ima razred kakšno dejavnost (športni dan, ekskurzija, kulturni dan, tehniški
dan...), lahko vodstvo te datume označi kot **"zasedene"**. To prepreči, da bi
učitelji na ta dan napovedovali ocenjevanja — saj bi bilo nesmiselno, če
učencev sploh ni v razredu. 😊

### Kako dodati zasedene datume

1. **Odprite zavihek Ocenjevanje**
2. Kliknite **🚫 Zasedeni datumi**
3. **Izberite razred(e)** — lahko jih izberete več naenkrat
4. **Vnesite datum OD in DO** — npr. od ponedeljka do petka, če gre za cel
   teden
5. Kliknite **Dodaj zasedene datume** ✅

### Kako odstraniti zaseden datum

V oknu **"Zasedeni datumi"** se v spodnjem delu prikaže seznam vseh blokad.
Kliknite **✕** poleg tiste, ki jo želite odstraniti.

---

## ⚙️ Upravljanje uporabnikov (samo za Admin)

**Dostop:** V zgornji navigaciji se adminu prikaže gumb **Admin panel**.

> 🔒 **To področje je namenjeno samo skrbnikom sistema.** Če niste Admin, boste
> ta gumb videli le, če vam ga kdo dodeli.

### Kaj lahko admin počne?

| Funkcija | Opis |
|---|---|
| **➕ Dodajanje uporabnikov** | Vnesete email, ime, priimek, geslo in vlogo |
| **👀 Pregled uporabnikov** | Tabela z vsemi uporabniki sistema |
| **✏️ Urejanje** | Kliknite "Uredi", spremenite podatke |
| **🔴 Deaktivacija / 🟢 Aktivacija** | Onemogočite ali omogočite dostop posamezniku |
| **🗑️ Brisanje** | Trajno izbriše uporabnika (admin z ID=1 ni mogoče izbrisati — zaščita!) |
| **🔑 Spremeni geslo** | Admin lahko spremeni geslo komurkoli (če uporabnik pozabi geslo) |

---

## 🔑 Sprememba gesla

### Ko še poznate svoje geslo

1. V zgornji navigaciji kliknite **Spremeni geslo**
2. Vnesite **trenutno geslo** (da vemo, da ste to res vi)
3. Vnesite **novo geslo** — dvakrat ga vpišite, da se izognete tipkarski napaki
4. Kliknite **Spremeni geslo** ✅

### Če ste geslo pozabili

1. Na prijavni strani kliknite **"Pozabljeno geslo?"**
2. Vnesite svoj **službeni email**
3. Preverite email in sledite povezavi v prejetem sporočilu
4. Če emaila ni v mapi "Prejeto", **preverite še mapo "Neželena pošta"** 📬

---

## 🛠️ Tehnične podrobnosti (za radovedne)

Ni se vam treba spoznati na tehnologijo, da bi uporabljali aplikacijo — ampak
če vas zanima, kaj se dogaja "pod pokrovom":

| Zadeva | Kaj to pomeni za vas? |
|---|---|
| **⏰ Samodejna odjava** | Po 1 uri nedejavnosti (30 min za admin/vodstvo). Če odidete od računalnika, se bo aplikacija sama zaklenila. |
| **👥 Sočasni dostop** | Sistem preprečuje dvojne rezervacije — tudi če dva učitelja rezervirata isto uro v istem trenutku, bo zmagal le eden. |
| **📧 Email obvestila** | Pošiljajo se prek Arnesovega SMTP strežnika. Ko pozabite geslo, vam pride email — to deluje prek Arnesa. |

---

## ❓ Še vedno imate težave?

Če vam kaj ni jasno ali naletite na težavo:

1. **Preberite ta navodila še enkrat** — morda je odgovor že kje zgoraj 😊
2. **Vprašajte sodelavca** — morda se je že srečal s podobno težavo
3. **Kontaktirajte administratorja** — to je oseba, ki skrbi za aplikacijo

> 🎯 **Ne pozabite: ne morete ničesar pokvariti!** Vse spremembe so varne in
> povratne. Probajte, kliknite, raziskujte — tako se najlažje naučite.

---

*Navodila so nastala z mislijo na vas — zadnja posodobitev: junij 2026.*
