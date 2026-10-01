# 👑 Navodila za vodstvo

> Namenjeno **ravnatelju in pomočnikom ravnatelja**.  
> Vodstvo ima več moči kot učitelji — lahko brišete tudi tuje rezervacije, upravljate dneve dejavnosti in
> nadzorujete ocenjevanje. S tem pride tudi **odgovornost**.
>
> ⚡ **Hitri začetek:** Vstopite v aplikacijo, prijavite se s svojim šolskim računom in
> uporabljajte meni na vrhu. Vse, kar ni omenjeno spodaj, je enako kot za učitelje.

---

## 📅 Rezervacije

Vodstvo ima na voljo **dve dodatni vrsti rezervacij**, ki ju učitelji nimajo.

### Tedenska serija

> **Ideja:** Kot ponavljajoči se dogodek v koledarju — enkrat nastavite, velja za več tednov.

Namesto da ročno vnašate isto rezervacijo 10 ponedeljkov zapored, nastavite serijo in sistem
poskrbi za vse.

| Polje | Opis |
|---|---|
| Ime rezervacije | Zakaj rezervirate, npr. izbirni predmet, tehnični dan |
| Prostor | Kateri prostor rezervirate |
| Ura | Številka ure (0 = predura, 1–7 = ure) |
| Dan v tednu | 0 = ponedeljek, 1 = torek … 6 = nedelja |
| Od datuma | Prvi dan serije |
| Do datuma | Zadnji dan serije |
| Število | Samo pri rezervaciji tablic. Če se polje ne prikaže takoj, zamenjajte prostor in nato znova izberite tablice |

### Celodnevna serija

Zasede cel dan (vse ure) za več dni zapored.

| Polje | Opis |
|---|---|
| Ime rezervacije | Zakaj rezervirate, npr. izbirni predmet, tehnični dan |
| Prostor | Kateri prostor rezervirate |
| Od datuma | Datum začetka |
| Do datuma | Datum konca |
| Število | Samo pri tablicah |
| Ure | Če prazno → zasede vse ure 0–7. Lahko naštejete samo določene: `1 3 5` |

### 🔥 Brisanje rezervacij

| Vloga | Lahko briše |
|---|---|
| Učitelj | Samo svoje rezervacije |
| **Vodstvo** | **Svoje + tuje** rezervacije |

**Vodstvo ima več moči — lahko brišete tudi tuje rezervacije. S tem pride
odgovornost.** Preden zbrišete učiteljevo rezervacijo, premislite.

---

## 📝 Ocenjevanje in dnevi dejavnosti

### Dnevi dejavnosti

> Ko označite dan kot dan dejavnosti, se vsa ocenjevanja za ta dan samodejno izbrišejo
> in učitelji dobijo email — **sistem poskrbi za obveščanje**.

To uporabite za:
- Športne dneve
- Ekskurzije
- Kulturne dneve
- Tehniške dneve
- Druge šolske prireditve, ko pouka (in ocenjevanja) ni

| Polje | Opis |
|---|---|
| Razred | Izberite enega ali več (držite **Ctrl** za več) |
| Od datuma | Prvi dan dejavnosti |
| Do datuma | Zadnji dan dejavnosti |

### Razredi (skupine) od 1. do 9. razreda

Dejavnosti so urejene **po razredih (generacijah) od 1. do 9. razreda** — vsak
razred ima na strani *Vnos dejavnosti* svoj zavihek. V vsaki vrstici termina
izberete, za katere **razrede (skupine)** dejavnost velja: posamezne črkovne
oddelke (npr. `3. a`, `3. b`) ali kar **»Vsi razredi generacije«**.

> ℹ️ Za **8. in 9. razred** se pogosto uporabljajo skupinsko-razredne oznake
> (npr. `8. a` in `8. 1`), kjer številka pomeni skupino.

### Večdnevna dejavnost (npr. ekskurzija za več dni)

1. V razdelku **Datumi** kliknite **＋ Dodaj datum**.
2. Vpišite **Od** (prvi dan).
3. Obkljukajte **»Več dni«** in v polje **Do** vpišite **zadnji dan**.
4. Shranite — dejavnost velja za **vsak zaporedni dan v tem obsegu**; vsak dan se
   zablokira za ocenjevanja in (ob izbranih prostorih) rezervira ure 1–5.

> 💡 Za isto dejavnost lahko dodate tudi **več ločenih datumov** — kliknete
> **＋ Dodaj datum** tolikokrat, kolikor terminov potrebujete.

### Celi dan ali krajša dejavnost

- **»Celoten dan«** (obkljukano): dan se zablokira za ocenjevanja, obstoječa se
  izbrišejo (učitelji dobijo e-pošto), ob izbranih prostorih se rezervirajo ure 1–5.
- **Brez kljukice**: krajša dejavnost — ocenjevanja **niso** blokirana.

Prav tako učitelji ne morejo napovedati ocenjevanja na dan, ko ima razred dan dejavnosti.

**Kaj se zgodi, ko shranite:**

1. Sistem **samodejno izbriše** vsa obstoječa ocenjevanja izbranih razredov v tem
   obdobju
2. Prizadeti učitelji **avtomatsko prejmejo email obvestilo**
3. Vse skupaj se zabeleži v dnevniku

Ni vam treba ničesar najavljati posebej — sistem obvesti namesto vas.

### Obvestila po e-pošti

Sistem **samodejno pošilja email obvestila** vedno, ko vodstvo:

| Akcija | Kdo dobi email | Zakaj? |
|--------|---------------|--------|
| ✅ Označi datum kot **dan dejavnosti** | Vsi učitelji, katerih rezervacija se je odpovedala | Da vedo, da morajo najti drug datum |
| ✅ Ustvari **serijsko rezervacijo** | Učitelji s konfliktnimi rezervacijami | Dobijo obvestilo, da je njihova rezervacija prestavljena/odpovedana |
| ✅ Izbriše **serijsko rezervacijo** | Učitelji s konfliktnimi rezervacijami | Enako kot zgoraj |

> **⚠️ Pomembno:** Če posamezno rezervacijo izbrišete kar z `✕`, **nihče ne dobi obvestila**. Za avtomatska obvestila vedno uporabite **serijske rezervacije** ali **dneve dejavnosti** — sistem sam obvesti vse prizadete.

**ELI5:** Serijske rezervacije in dnevi dejavnosti so kot javni razglas na tabli — vsi vidijo in vsi so obveščeni. Brisanje posamezne rezervacije je kot da tiho zbrišeš nekaj s table — nihče ne ve, zakaj je izginilo.


---

## 📥 **Izvoz podatkov v CSV**

> **Kaj je to?** Izvoz podatkov v CSV (Excelu prijazna oblika) — enostaven način, da podatke iz aplikacije prenesete na svoj računalnik in jih odprete v Excelu, Google Sheets ali podobnem programu.

### Kaj lahko izvozite?

| Vrsta izvoza | Kam kliknete | Kateri podatki |
|---|---|---|
| **Rezervacije prostorov** | 📥 Izvoz rezervacij (v meniju) | Datum, ura, prostor, razred, učitelj |
| **Ocenjevanja in dnevi dejavnosti** | 📥 Izvoz ocenjevanj (v meniju) | Datum, razred, tip ocenjevanja, učitelj |

### Kako to naredite?

1. V zgornjem meniju kliknite **📥 Izvoz rezervacij** ali **📥 Izvoz ocenjevanj**
2. Izberite **obdobje** (privzeto zadnji mesec):
   - **Od datuma** — začetek obdobja
   - **Do datuma** — konec obdobja
3. Pri rezervacijah lahko izberete tudi **prostor** (ali pustite "Vsi prostori")
4. Kliknite **📥 Prenesi CSV**

> **ELI5:** Kot da bi iz knjižnice izposodili knjigo in si naredili kopijo strani, ki vas zanimajo. CSV je univerzalni jezik, ki ga razumejo vsi pisarniški programi.

### Kaj narediti s CSV?

- Odprite v **Excelu** (File → Open)
- Odprite v **Google Sheets** (File → Import)
- Uvozite v **katerikoli podatkovni program**

> **Namig:** CSV uporablja podpičje (`;`) kot ločilo, kar Excel v slovenščini samodejno prepozna. Če se vam zdi zmešano v en stolpec, pri uvozu izberite **ločilo: podpičje**.

## Navodila

Uporaba teh navodil je enaka kot pri navodilih za učitelje (razložena v tistih navodilih), le da ima vodstvo na voljo tudi ta navodila — običajen učitelj jih ne vidi.


---

## 🛡️ Skrbniška plošča — SAMO ADMIN

> ⛔ **Vodstvo do tega dela nima dostopa.** Sledi samo za informacijo, kaj dela
> vaš administrator.
>
> 📄 **Podrobna navodila za administratorja** so v ločenem dokumentu
> **»Navodila za administratorja«** — v aplikaciji je zanj gumb **🛠️ Admin** na
> desni strani, ki ga vidi **samo admin** (nastavitve šole, uporabniki, e-pošta,
> naročnina, varnostne kopije, audit log).

---

## 🎯 Priporočila za vloge

> Pravilna dodelitev vlog preprečuje težave in zlorabe.

| Vloga | Kdo naj jo ima | Pravice |
|---|---|---|
| **Admin** | Samo administrator sistema | Vse — skrbniška plošča, uporabniki, nastavitve |
| **Vodstvo** | Ravnatelj, pomočniki | Rezervacije serij, brisanje tujih, dnevi dejavnosti |
| **Učitelj** | Vsi pedagoški delavci | Osnovne rezervacije in ocenjevanje |

**Z eno besedo:** Admin skrbi za sistem, vodstvo skrbi za urnik, učitelji
skrbijo za pouk.

> **Avtor:** Matej Čušin  
