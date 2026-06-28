🌐 **Jezik / Language:** [🇸🇮 Slovenščina](navodila-uporabnika.md) | [🇬🇧 English](en/navodila-uporabnika.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 📖 Navodila za uporabo

## Prijava

1. Odprete spletno stran aplikacije: [https://ostc-app.org](https://ostc-app.org)
2. Vnesete **AAI uporabniško ime** (oz. email) in **geslo**
3. Po prijavi se v zgornjem desnem kotu izpiše vaše ime in vloga
4. Ob kliku na **Odjava** se izpišete
5. **Samodejna odjava:** Po **1 uri** brez premikanja miške te aplikacija samodejno odjavi.

> **💡 Zakaj?** To je varnostni ukrep — če pozabiš zakleniti računalnik, ne more nihče drug delati v tvojem imenu. Predstavljaj si, da odpreš aplikacijo, greš na kosilo in pozabiš zapreti. Brez samodejne odjave bi lahko kdorkoli sedel za tvoj računalnik in rezerviral ali brisal stvari v tvojem imenu. To preprečimo. Ena ura je dovolj, da greš na malico in se vrneš brez ponovne prijave, a dovolj malo, da si po kosilu verjetno že odjavljen.

### Pozabljeno geslo

Kliknite **"Pozabljeno geslo?"** na prijavni strani, vnesite svoj službeni email in sledite povezavi v prejetem sporočilu.

### Pravila za gesla

- Vsaj **5 znakov** dolžine
- Vsaj **ena mala črka** (a–z)
- Vsaj **ena velika črka** (A–Ž)
- Vsaj **ena številka** (0–9)

> **💡 Zakaj taka pravila?** Preprečujejo lažje ugibanje gesel. Če bi dovolili samo "12345", bi vsak uganil. Kombinacija malih črk, velikih črk in številk ustvari ogromno možnih gesel — tudi pri samo 5 znakih jih je več sto tisoč. Hekerji se zanašajo na to, da ljudje izbirajo preprosta gesla; ta pravila poskrbijo, da je tvoje geslo vsaj malo boljše od "geslo1".

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

> **💡 Kaj to pomeni v praksi?** Vsaka vloga ima dostop do drugačnih gumbov. Učitelj vidi samo svoje rezervacije in ocenjevanja — ne more pomotoma izbrisati nečesa, kar je naredil drug učitelj. Vodstvo ima več pooblastil, ker mora usklajevati urnik. Admin pa ima ključe od vsega, ampak tega dostopa ne rabi vsak dan. Manj gumbov kot vidiš, manj možnosti imaš, da klikneš kaj narobe.

---

## Rezervacije prostorov

### Prostori

- **Tablice** – didaktične tablice (kapaciteta: 28 kosov)
- **Računalnica** – računalniška učilnica (samo en učitelj na uro)
- **Ladja** – učilnica (samo en učitelj na uro)
- **Gospodinjska učilnica** – (samo en učitelj na uro)

> **💡 Zakaj "samo en učitelj na uro"?** V računalnici, ladji in gospodinjski učilnici je fizično prostora samo za en razred. Če bi si dve učiteljici rezervirali računalnico ob isti uri, bi bile tablice na istih mizah — kar ne gre. Sistem to prepreči tako, da po prvi rezervaciji termin postane rdeč in se gumb "+" ne prikaže več.

### Kako rezervirati

1. Odprete zavihek **Rezervacije** (privzet pogled)
2. Izberete **začetek tedna** (privzeto trenutni teden)
3. Kliknete **Osveži**
4. Izberete želen prostor s klikom na zavihek
5. **Kako brati tabelo:**
   - **Vrstice so ure** (0 = predura, 1 = 1. ura, ..., 7 = 7. ura)
   - **Stolpci so dnevi** (pon–pet)
   - **🟢 Zelen "Prosto"** — termin je prost, lahko rezerviraš
   - **Zaseden termin** — prikazuje ime osebe, ki ga je rezervirala

> **💡 Tabelo beri kot vozni red.** Stolpci so dnevi v tednu, vrstice so ure. Kjer se ura in dan sekata, je celica. Zelena = še nihče ni rezerviral. Modra z imenom = nekdo je že prej. To je tvoj pogled na to, kaj je prosto v celem tednu naenkrat.

6. Rezervirate na dva načina:
   - Kliknete **+** v želeni celici (hitra rezervacija)
   - Kliknete **+ Nova rezervacija** zgoraj
7. Pri **Tablicah** vnesete še **število tablic**
8. Kliknete **Shrani**

> **💡 Zaščita pred dvojno rezervacijo.** Sistem preprečuje, da bi dva hkrati rezervirala isti termin. Če ti in še en učitelj istočasno klikneta "Shrani" za isto celico, bo samo eden od vaju dobil termin. Drugi bo videl opozorilo: "Ta termin je že zaseden." Prvi, ki klikne Shrani, dobi termin — ostali ga zamudijo. Ampak to se zgodi zelo redko, ker morata oba klikniti v isti mikrosekundi.

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

> **💡 Zakaj ta pravila?** Predstavljaj si, da imajo učenci v ponedeljek, torek in sredo pisne ocenjevanja iz treh predmetov. V četrtek imajo še eno. Učenec je izčrpan, starši so jezni, kakovost znanja je slaba. Ta pravila poskrbijo, da so ocenjevanja razporejena in da imajo učenci čas za učenje. **3 na teden** = ne več kot trije pisni preizkusi v enem tednu. **2 običajni** = samo dve "klasični" oceni (ponavljanje, kot je ustno ocenjevanje, ne šteje). **Prepoved istega dne** = ne moreš napovedati dveh pisnih za isti dan (učenci ne morejo pisati dveh testov hkrati). **3 zaporedni dnevi** = izogneš se situaciji, ko so trije testi v pon, tor, sre.

### Legenda v koledarju

- **🔵 Običajno ocenjevanje** – moder značek
- **🔄 Ponavljanje** – rdeč značek
- **🟣 Zaseden datum** – vijoličen značek

---

## Zasedeni datumi

**Kdo lahko upravlja:** Vodstvo in Admin.

Ko ima razred dejavnost (športni dan, ekskurzija...), lahko vodstvo te datume označi kot "zasedene". To prepreči, da bi učitelji na ta dan napovedovali ocenjevanja.

> **💡 Zamisli si, kot da na koledar napišeš "DRUGO" s krepkim rdečim flomastrom.** Ko vodstvo označi dan kot zaseden, se na koledarju prikaže vijoličen značek in gumb "+" za ocenjevanje izgine. Učitelji fizično ne morejo napovedati ocenjevanja na ta dan — ni treba, da si zapomnijo, da je športni dan. Sistem to naredi namesto njih. In če so že imeli kakšno ocenjevanje napovedano, ga sistem sam izbriše in jih obvesti po emailu.

### Kako dodati zasedene datume

1. Odprete zavihek **Ocenjevanje**
2. Kliknete **🚫 Zasedeni datumi**
3. Izberete razred(e)
4. Vnesete datum OD in DO
5. Kliknete **Dodaj zasedene datume**

### Kako odstraniti zaseden datum

V oknu "Zasedeni datumi" se v spodnjem delu prikaže seznam blokad. Kliknite **✕** poleg tiste, ki jo želite odstraniti.

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

## Tehnične podrobnosti

- **Samodejna odjava:** Po 1 uri neaktivnosti
- **Sočasni dostop:** Sistem preprečuje dvojne rezervacije (race condition detection)

> **💡 "Race condition" — kaj to pomeni?** Predstavljaj si, da dva človeka istočasno poskušata sesti na isti stol. Oba mislita, da je prazen. Sistem prepreči to tako, da prvi, ki klikne "Shrani", dobi termin, drugi pa vidi sporočilo: "Termin je že zaseden." V ozadju sistem uporablja zaklepanje (locking) — ko nekdo začne rezervirati, se termin zaklene za vse ostale, dokler ni rezervacija potrjena ali preklicana. To se zgodi v milisekundah in ti tega ne vidiš, ampak zato nihče ne more "ukrasti" tvojega termina v zadnjem trenutku.

- **Email obvestila:** Pošiljajo se prek Arnesovega SMTP strežnika
