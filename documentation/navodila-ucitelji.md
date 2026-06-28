🌐 **Jezik / Language:** [🇸🇮 Slovenščina](navodila-ucitelji.md) | [🇬🇧 English](en/navodila-ucitelji.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 👩‍🏫 Navodila za učitelje

Skrajšana različica, ki te spravi noter v 5 minutah. Če rabiš več podrobnosti, preveri [celotna navodila](navodila-uporabnika.md).

---

## Prvič v aplikaciji? Dobi geslo

1. Odpri [aplikacijo](https://ostc-app.org)
2. Klikni **"Pozabljeno geslo?"**
3. Vnesi svoj **šolski e-poštni naslov**
4. Preveri e-pošto — dobil boš sporočilo od `sola@example.com`

> **💡 Ne dobiš e-pošte?** To ponavadi pomeni, da tvoj email naslov v bazi ni pravilen. Javi administratorju, naj preveri, ali si vnešen prav. Ne pošiljaj prošnje za geslo večkrat — če ga ni v bazi, ga tudi 10. poskus ne bo čarobno ustvaril.

Če sporočila ne prejmeš niti v mapi "Vsiljena pošta" (Spam), kontaktiraj administratorja.

---

## Nastavi geslo

V e-pošti klikni povezavo in nastavi geslo po teh pravilih:

- Vsaj **5 znakov** dolžine
- Vsaj **ena mala črka** (a–z)
- Vsaj **ena velika črka** (A–Ž)
- Vsaj **ena številka** (0–9)

> **💡 Zakaj ravno to?** Če bi dovolili samo "abc", bi vsak uganil. Kombinacija velikih/malih črk in številk naredi tudi kratko geslo veliko težje za ugibanje. Ampak ne skrbi — ni treba, da je "T4bL1c@2024!?xY". Dovolj je nekaj takega kot **Poletje1** ali **Sola2025**.

---

## Prijava

- **Uporabniško ime:** tvoj šolski e-poštni naslov
- **Geslo:** geslo, ki si ga nastavil/a

Po prijavi se odpre stran **Rezervacije**. V desnem kotu zgoraj vidiš svoje ime — če ga vidiš, si notri. Če ne, se poskusi znova prijaviti.

---

## Rezervacije

### Kateri prostori so na voljo?

| Prostor | Pomembno |
|---|---|
| **Računalnica** | Samo en učitelj na termin — prvi rezervira, drugi zamudi |
| **Ladja** | Samo en učitelj na termin |
| **Tablice** | Več učiteljev lahko rezervira, skupaj max 28 tablic na uro |
| **Gospodinjska učilnica** | Samo en učitelj na termin |

> **💡 Zakaj "samo en" za večino prostorov?** Ker gre za fizične učilnice. Dva razreda ne moreta biti v računalnici hkrati — ni dovolj računalnikov in prostora. Pri tablicah pa jih lahko več učiteljev uporablja hkrati, dokler ne presežejo skupnega števila.

### Kako rezervirati?

**S klikom na `+` v tabeli:** Izbereš celico (dan + uro) in datum se samodejno nastavi. Najhitrejši način.

**S klikom na `Nova rezervacija`:** Odpre se obrazec, kjer ročno vneseš vse podatke. Uporabi, če želiš rezervirati termin, ki ni v trenutnem tednu.

> **💡 Kako brati tabelo?** Vrstice so šolske ure (0 = predura, 1 = 1. ura, itd.). Stolpci so dnevi (pon–pet). Zeleno = prosto, lahko klikneš. Ime = nekdo je že rezerviral. Tabela ti pokaže cel teden na en pogled — ni treba listati po dnevih.

Pri tablicah vnesi tudi **število tablic**, ki jih potrebuješ.

### Brisanje rezervacije

- Klikni rdeč **✕** gumb poleg rezervacije v tabeli
- **Lahko brišeš SAMO svoje** rezervacije

> **💡 Zakaj ne morem izbrisati tuje?** Da ne pride do pomot. Če nekdo pomotoma izbriše tvojo rezervacijo, si jezen in kličeš podporo. Vsak briše samo svoje — enostavno in pošteno. Če rabiš izbrisati tujo, pokliči vodstvo.

---

## Ocenjevanje

### Kako napovedati ocenjevanje?

1. Odpri zavihek **Ocenjevanje**
2. Izberi **razred** v spustnem meniju in klikni **Osveži**
3. Na koledarju klikni **+** na želeni dan
4. Izpolni obrazec in klikni **Shrani**

### Omejitve — zakaj jih sistem ne pusti mimo?

| Pravilo | Opis | Zakaj? |
|---|---|---|
| Največ 3 ocenjevanja na teden | V enem tednu max 3 skupaj | Da učenci niso preobremenjeni |
| Največ 2 običajni na teden | Ponavljanje ne šteje v to omejitev | Ponavljanje (ustno) je manj stresno kot pisni test |
| Prepoved istega dne | Ne moreš dati dveh na isti dan | Učenec ne more pisati dveh testov hkrati |
| Prepoved 3 zaporednih dni | Ne smejo biti na 3 zaporedne dni | Da ni pon/ tor/ sre test za testom |

### Legenda

- **🔵 Modro** – običajno ocenjevanje
- **🔄 Rdeče** – ponavljanje
- **🟣 Vijolično** – zaseden datum (razred ima dejavnost — ne moreš napovedati ocenjevanja)

---

## Zasedeni datumi

Vodstvo označi dneve, ko ima razred dejavnost (športni dan, ekskurzija...). Na te dni **ne moreš napovedovati ocenjevanj** — gumb "+" na koledarju ne bo na voljo.

> **💡 Ni se ti treba spomniti, kdaj je športni dan.** Če je dan zaseden, ga sistem blokira. Če si že imel/a napovedano ocenjevanje na ta dan, ga sistem sam izbriše in dobiš obvestilo po emailu. Vse pod kontrolo.

---

## Sprememba gesla

1. Klikni **Spremeni geslo** v meniju
2. Vnesi trenutno in novo geslo
3. Klikni **Spremeni geslo**

### Če si pozabil/a geslo

1. Na prijavni strani klikni **"Pozabljeno geslo?"**
2. Vnesi svoj službeni email
3. Sledi povezavi v prejetem emailu

---

## ❗ Troubleshooting — Aplikacija ne dela?

| Težava | Verjeten vzrok | Rešitev |
|---|---|---|
| Stran se ne naloži | Nimaš internetne povezave | Preveri Wi-Fi / mobilne podatke. Odpri google.com — če tudi to ne dela, je internet kriv. |
| Stran je čudna, gumbi ne delajo | Star brskalnik ali počasna povezava | Poskusi v **Chrome** ali **Firefox** (zadnja različica). Osveži stran s **F5**. |
| "Napačno uporabniško ime ali geslo" | Napačno geslo ali napačen email | Klikni "Pozabljeno geslo?" in ponastavi. |
| "Ta termin je že zaseden" | Nekdo je bil hitrejši | Izberi drug termin ali uro. |
| Ne vidim gumba, ki ga iščem | Nimaš dovoljenja za to funkcijo | Npr. "Zasedeni datumi" so samo za vodstvo. Preveri tabelo vlog v celotnih navodilih. |
| Drugo | Neznano | Kontaktiraj administratorja. Po možnosti pošlji **posnetek zaslona (screenshot)** — to pove več kot 100 besed. |

---

> **Še vedno težave?** Kontaktiraj administratorja. Če si vzameš minuto in opišeš, kaj si kliknil/a in kaj se je zgodilo (namesto "ne dela"), bo rešitev hitrejša.
