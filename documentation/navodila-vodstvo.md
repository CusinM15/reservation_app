🌐 **Jezik / Language:** [🇸🇮 Slovenščina](navodila-vodstvo.md) | [🇬🇧 English](en/navodila-vodstvo.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 👑 Navodila za vodstvo

> Namenjeno **ravnatelju, pomočnikom ravnatelja in svetovalnim delavcem**.  
> Vodstvo ima več moči kot učitelji — lahko brišete tudi tuje rezervacije, upravljate zasedene
> datume in nadzorujete ocenjevanje. S tem pride tudi **odgovornost**.
>
> ⚡ **Hitri začetek:** Vstopite v aplikacijo, prijavite se s svojim šolskim računom in
> uporabljajte meni na vrhu. Vse, kar ni omenjeno spodaj, je enako kot za učitelje.

---

## 📅 Rezervacije

Vodstvo ima na voljo **dve dodatni vrsti rezervacij**, ki ju učitelji nimajo.

### Tedenska serija

> **Ideja:** Kot ponavljajoči se dogodek v koledarju — enkrat nastaviš, velja za več tednov.

Namesto da ročno vnašaš isto rezervacijo 10 ponedeljkov zapored, nastaviš serijo in sistem
poskrbi za vse.

| Polje | Opis |
|---|---|
| Prostor | Kateri prostor rezervirate |
| Ura | Številka ure (0 = predura, 1–7 = ure) |
| Dan v tednu | 0 = ponedeljek, 1 = torek … 6 = nedelja |
| Od datuma | Prvi dan serije |
| Do datuma | Zadnji dan serije |
| Število tablic | Samo pri rezervaciji tablic |

### Celodnevna serija

Zasede cel dan (vse ure) za več dni zapored. Uporabno za zaključene izpite,
tekmovanja ali intenzivne programe.

| Polje | Opis |
|---|---|
| Prostor | Kateri prostor rezervirate |
| Od datuma | Datum začetka |
| Do datuma | Datum konca |
| Število tablic | Samo pri tablicah |
| Ure | Če prazno → zasede vse ure 0–7. Lahko naštejete samo določene: `1 3 5` |

### 🔥 Brisanje rezervacij

| Vloga | Lahko briše |
|---|---|
| Učitelj | Samo svoje rezervacije |
| **Vodstvo** | **Svoje + tuje** rezervacije |

**Vodstvo ima več moči — lahko brišete tudi tuje rezervacije. S tem pride
odgovornost.** Preden zbrišete učiteljevo rezervacijo, premislite, če jo
morda samo potrebuje prestaviti.

---

## 📝 Ocenjevanje

### Zasedeni datumi

> Ko označite dan kot zaseden, se vsa ocenjevanja za ta dan samodejno izbrišejo
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
| Od datuma | Prvi dan zasedenosti |
| Do datuma | Zadnji dan zasedenosti |

**Kaj se zgodi, ko shranite:**

1. Sistem **samodejno izbriše** vsa obstoječa ocenjevanja izbranih razredov v tem
   obdobju
2. Prizadeti učitelji **avtomatsko prejmejo email obvestilo**
3. Vse skupaj se zabeleži v dnevniku

Ni vam treba ničesar najavljati posebej — sistem obvesti namesto vas.

### Obvestila po e-pošti

Vsakič, ko vodstvo:
- prekliče rezervacijo,
- izbriše ocenjevanje,
- ali označi datum kot zaseden,

…aplikacija **samodejno pošlje email** prizadetemu učitelju. Ročno obveščanje ni
potrebno.

---

---

## 📥 **Izvoz podatkov v CSV**

> **Kaj je to?** Izvoz podatkov v CSV (Excelu prijazna oblika) — enostaven način, da podatke iz aplikacije prenesete na svoj računalnik in jih odprete v Excelu, Google Sheets ali podobnem programu.

### Kaj lahko izvozite?

| Vrsta izvoza | Kam kliknete | Kateri podatki |
|---|---|---|
| **Rezervacije prostorov** | 📥 Export rezervacij (v meniju) | Datum, ura, prostor, razred, učitelj |
| **Ocenjevanja** | 📥 Export ocenjevanj (v meniju) | Datum, razred, tip ocenjevanja, učitelj |

### Kako to naredite?

1. V zgornjem meniju kliknite **📥 Export rezervacij** ali **📥 Export ocenjevanj**
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

## 🛡️ Skrbniška plošča — SAMO ADMIN

> ⛔ **Vodstvo do tega dela nima dostopa.** Sledi samo za informacijo, kaj dela
> vaš administrator.

### Ročni vnos uporabnikov

**Priporočljivo samo med šolskim letom** — ko nastopi nov učitelj sredi leta in ga
je treba dodati sproti.

Na začetku šolskega leta je bolje:
1. Izbrisati vse uporabnike
2. Uvoziti jih na novo s skripto (glej spodaj)

### Uvoz zaposlenih s skripto

Skripta prebere seznam zaposlenih kar s šolske spletne strani — ni ročnega vnašanja.

```bash
cd /home/admin/ostc-app_deli
python3 scripts/import_teachers.py --base-url https://{{DOMAIN}}

# Preizkus (brez dejanskih sprememb):
python3 scripts/import_teachers.py --dry-run

# Z vključitvijo administracije in tehničnega osebja:
python3 scripts/import_teachers.py --base-url https://{{DOMAIN}} --include-all
```

### Upravljanje uporabnikov

**Dostop:** V zgornji navigaciji kliknite **Admin panel**.

| Funkcija | Opis |
|---|---|
| Dodajanje | Vnesete email, ime, priimek, geslo, vlogo |
| Pregled | Tabela vseh uporabnikov — klik na stolpec za razvrščanje |
| Urejanje | Kliknite »Uredi«. Če geslo pustite prazno, ostane nespremenjeno |
| Deaktivacija / Aktivacija | Uporabniku onemogočite ali ponovno omogočite dostop |
| Brisanje | Trajno izbriše uporabnika (admin z ID=1 je zaščiten) |
| Sprememba gesla | Admin lahko kadarkoli spremeni geslo uporabniku |

---

## 🎯 Priporočila za vloge

> Pravilna dodelitev vlog preprečuje težave in zlorabe.

| Vloga | Kdo naj jo ima | Pravice |
|---|---|---|
| **Admin** | Samo administrator sistema | Vse — skrbniška plošča, uporabniki, nastavitve |
| **Vodstvo** | Ravnatelj, pomočniki, svetovalni delavci | Rezervacije serij, brisanje tujih, zasedeni datumi |
| **Učitelj** | Vsi pedagoški delavci | Osnovne rezervacije in ocenjevanje |

**Z eno besedo:** Admin skrbi za sistem, vodstvo skrbi za urnik, učitelji
skrbijo za pouk.
