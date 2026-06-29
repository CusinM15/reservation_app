     1|🌐 **Jezik / Language:** [🇸🇮 Slovenščina](navodila-vodstvo.md) | [🇬🇧 English](en/navodila-vodstvo.md)
     2|
     3|---
     4|
     5|> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
     6|> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
     7|> Secrets ali kontaktirajte administratorja.
     8|
     9|---
    10|
    11|# 👑 Navodila za vodstvo
    12|
    13|> Namenjeno **ravnatelju, pomočnikom ravnatelja in svetovalnim delavcem**.  
    14|> Vodstvo ima več moči kot učitelji — lahko brišete tudi tuje rezervacije, upravljate zasedene
    15|> datume in nadzorujete ocenjevanje. S tem pride tudi **odgovornost**.
    16|>
    17|> ⚡ **Hitri začetek:** Vstopite v aplikacijo, prijavite se s svojim šolskim računom in
    18|> uporabljajte meni na vrhu. Vse, kar ni omenjeno spodaj, je enako kot za učitelje.
    19|
    20|---
    21|
    22|## 📅 Rezervacije
    23|
    24|Vodstvo ima na voljo **dve dodatni vrsti rezervacij**, ki ju učitelji nimajo.
    25|
    26|### Tedenska serija
    27|
    28|> **Ideja:** Kot ponavljajoči se dogodek v koledarju — enkrat nastaviš, velja za več tednov.
    29|
    30|Namesto da ročno vnašaš isto rezervacijo 10 ponedeljkov zapored, nastaviš serijo in sistem
    31|poskrbi za vse.
    32|
    33|| Polje | Opis |
    34||---|---|
    35|| Prostor | Kateri prostor rezervirate |
    36|| Ura | Številka ure (0 = predura, 1–7 = ure) |
    37|| Dan v tednu | 0 = ponedeljek, 1 = torek … 6 = nedelja |
    38|| Od datuma | Prvi dan serije |
    39|| Do datuma | Zadnji dan serije |
    40|| Število tablic | Samo pri rezervaciji tablic |
    41|
    42|### Celodnevna serija
    43|
    44|Zasede cel dan (vse ure) za več dni zapored. Uporabno za zaključene izpite,
    45|tekmovanja ali intenzivne programe.
    46|
    47|| Polje | Opis |
    48||---|---|
    49|| Prostor | Kateri prostor rezervirate |
    50|| Od datuma | Datum začetka |
    51|| Do datuma | Datum konca |
    52|| Število tablic | Samo pri tablicah |
    53|| Ure | Če prazno → zasede vse ure 0–7. Lahko naštejete samo določene: `1 3 5` |
    54|
    55|### 🔥 Brisanje rezervacij
    56|
    57|| Vloga | Lahko briše |
    58||---|---|
    59|| Učitelj | Samo svoje rezervacije |
    60|| **Vodstvo** | **Svoje + tuje** rezervacije |
    61|
    62|**Vodstvo ima več moči — lahko brišete tudi tuje rezervacije. S tem pride
    63|odgovornost.** Preden zbrišete učiteljevo rezervacijo, premislite, če jo
    64|morda samo potrebuje prestaviti.
    65|
    66|---
    67|
    68|## 📝 Ocenjevanje
    69|
    70|### Zasedeni datumi
    71|
    72|> Ko označite dan kot zaseden, se vsa ocenjevanja za ta dan samodejno izbrišejo
    73|> in učitelji dobijo email — **sistem poskrbi za obveščanje**.
    74|
    75|To uporabite za:
    76|- Športne dneve
    77|- Ekskurzije
    78|- Kulturne dneve
    79|- Tehniške dneve
    80|- Druge šolske prireditve, ko pouka (in ocenjevanja) ni
    81|
    82|| Polje | Opis |
    83||---|---|
    84|| Razred | Izberite enega ali več (držite **Ctrl** za več) |
    85|| Od datuma | Prvi dan zasedenosti |
    86|| Do datuma | Zadnji dan zasedenosti |
    87|
    88|**Kaj se zgodi, ko shranite:**
    89|
    90|1. Sistem **samodejno izbriše** vsa obstoječa ocenjevanja izbranih razredov v tem
    91|   obdobju
    92|2. Prizadeti učitelji **avtomatsko prejmejo email obvestilo**
    93|3. Vse skupaj se zabeleži v dnevniku
    94|
    95|Ni vam treba ničesar najavljati posebej — sistem obvesti namesto vas.
    96|
    97|### Obvestila po e-pošti
    98|
    99|Vsakič, ko vodstvo:
   100|- prekliče rezervacijo,
   101|- izbriše ocenjevanje,
   102|- ali označi datum kot zaseden,
   103|
   104|…aplikacija **samodejno pošlje email** prizadetemu učitelju. Ročno obveščanje ni
   105|potrebno.
   106|
   107|---
   108|
   109|## 📥 **Izvoz podatkov v CSV**
   110|## 📥 **Izvoz podatkov v CSV**
   111|
   112|> **Kaj je to?** Izvoz podatkov v CSV (Excelu prijazna oblika) — enostaven način, da podatke iz aplikacije prenesete na svoj računalnik in jih odprete v Excelu, Google Sheets ali podobnem programu.
   113|
   114|### Kaj lahko izvozite?
   115|
   116|| Vrsta izvoza | Kam kliknete | Kateri podatki |
   117||---|---|---|
   118|| **Rezervacije prostorov** | 📥 Export rezervacij (v meniju) | Datum, ura, prostor, razred, učitelj |
   119|| **Ocenjevanja** | 📥 Export ocenjevanj (v meniju) | Datum, razred, tip ocenjevanja, učitelj |
   120|
   121|### Kako to naredite?
   122|
   123|1. V zgornjem meniju kliknite **📥 Export rezervacij** ali **📥 Export ocenjevanj**
   124|2. Izberite **obdobje** (privzeto zadnji mesec):
   125|   - **Od datuma** — začetek obdobja
   126|   - **Do datuma** — konec obdobja
   127|3. Pri rezervacijah lahko izberete tudi **prostor** (ali pustite "Vsi prostori")
   128|4. Kliknite **📥 Prenesi CSV**
   129|
   130|> **ELI5:** Kot da bi iz knjižnice izposodili knjigo in si naredili kopijo strani, ki vas zanimajo. CSV je univerzalni jezik, ki ga razumejo vsi pisarniški programi.
   131|
   132|### Kaj narediti s CSV?
   133|
   134|- Odprite v **Excelu** (File → Open)
   135|- Odprite v **Google Sheets** (File → Import)
   136|- Uvozite v **katerikoli podatkovni program**
   137|
   138|> **Namig:** CSV uporablja podpičje (`;`) kot ločilo, kar Excel v slovenščini samodejno prepozna. Če se vam zdi zmešano v en stolpec, pri uvozu izberite **ločilo: podpičje**.
   139|
   140|---
   141|
   142|## 🛡️ Skrbniška plošča — SAMO ADMIN
   143|
   144|> ⛔ **Vodstvo do tega dela nima dostopa.** Sledi samo za informacijo, kaj dela
   145|> vaš administrator.
   146|
   147|### Ročni vnos uporabnikov
   148|
   149|**Priporočljivo samo med šolskim letom** — ko nastopi nov učitelj sredi leta in ga
   150|je treba dodati sproti.
   151|
   152|Na začetku šolskega leta je bolje:
   153|1. Izbrisati vse uporabnike
   154|2. Uvoziti jih na novo s skripto (glej spodaj)
   155|
   156|### Uvoz zaposlenih s skripto
   157|
   158|Skripta prebere seznam zaposlenih kar s šolske spletne strani — ni ročnega vnašanja.
   159|
   160|```bash
   161|cd /home/admin/ostc-app_deli
   162|python3 scripts/import_teachers.py --base-url https://{{DOMAIN}}
   163|
   164|# Preizkus (brez dejanskih sprememb):
   165|python3 scripts/import_teachers.py --dry-run
   166|
   167|# Z vključitvijo administracije in tehničnega osebja:
   168|python3 scripts/import_teachers.py --base-url https://{{DOMAIN}} --include-all
   169|```
   170|
   171|### Upravljanje uporabnikov
   172|
   173|**Dostop:** V zgornji navigaciji kliknite **Admin panel**.
   174|
   175|| Funkcija | Opis |
   176||---|---|
   177|| Dodajanje | Vnesete email, ime, priimek, geslo, vlogo |
   178|| Pregled | Tabela vseh uporabnikov — klik na stolpec za razvrščanje |
   179|| Urejanje | Kliknite »Uredi«. Če geslo pustite prazno, ostane nespremenjeno |
   180|| Deaktivacija / Aktivacija | Uporabniku onemogočite ali ponovno omogočite dostop |
   181|| Brisanje | Trajno izbriše uporabnika (admin z ID=1 je zaščiten) |
   182|| Sprememba gesla | Admin lahko kadarkoli spremeni geslo uporabniku |
   183|
   184|---
   185|
   186|## 🎯 Priporočila za vloge
   187|
   188|> Pravilna dodelitev vlog preprečuje težave in zlorabe.
   189|
   190|| Vloga | Kdo naj jo ima | Pravice |
   191||---|---|---|
   192|| **Admin** | Samo administrator sistema | Vse — skrbniška plošča, uporabniki, nastavitve |
   193|| **Vodstvo** | Ravnatelj, pomočniki, svetovalni delavci | Rezervacije serij, brisanje tujih, zasedeni datumi |
   194|| **Učitelj** | Vsi pedagoški delavci | Osnovne rezervacije in ocenjevanje |
   195|
   196|**Z eno besedo:** Admin skrbi za sistem, vodstvo skrbi za urnik, učitelji
   197|skrbijo za pouk.
   198|