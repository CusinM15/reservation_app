🌐 **Jezik / Language:** [🇸🇮 Slovenščina](navodila-vodstvo.md) | [🇬🇧 English](en/navodila-vodstvo.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 👑 Navodila za vodstvo in administratorja

Ta dokument je namenjen vodstvu (ravnatelj, pomočniki, svetovalni delavci) in adminu. Če si učitelj, so zate [navodila za učitelje](navodila-ucitelji.md) — tam je vse, kar rabiš.

> **Kaj vodstveni vidi drugače?** Isti vmesnik kot učitelji, plus dodatni gumbi. Vodstvo lahko briše tuje rezervacije in ocenjevanja ter upravlja zasedene datume. Admin pa ima še Admin panel za upravljanje uporabnikov.

---

## Rezervacije — napredne možnosti

Poleg običajne rezervacije (kot jo poznaš iz navodil za učitelje) ima vodstvo na voljo **serijske rezervacije** — to so orodja za ustvarjanje več rezervacij naenkrat.

### 📅 Tedenska serija

**Kaj je to?** Če imaš pouk vsak ponedeljek ob isti uri skozi cel mesec, lahko to narediš z enim klikom — namesto da 4-krat ponavljaš isto rezervacijo.

| Polje | Opis |
|---|---|
| Prostor | Kateri prostor želiš rezervirati |
| Ura | Številka ure (0 = predura, 1–7) |
| Dan v tednu | 0 = ponedeljek, 1 = torek, ..., 5 = sobota |
| Od datuma | Prvi dan serije (npr. 2. 9. 2025) |
| Do datuma | Zadnji dan serije (npr. 30. 9. 2025) |
| Število tablic | Samo pri rezervaciji tablic |

> **💡 Kako to deluje v praksi?** Recimo, da imaš angleščino v ladji vsak torek ob 3. uri. Izpolniš: Prostor = Ladja, Ura = 3, Dan = 1 (torek), Od = 1. 9., Do = 30. 6. Klikneš Shrani in sistem ustavi vse rezervacije za celo šolsko leto naenkrat. Prihraniš si 40 klikov.

### 📆 Celodnevna serija

**Kaj je to?** Ko imaš celodnevno dejavnost (športni dan, kulturni dan, ekskurzija), lahko rezerviraš cel dan z enim obrazcem — vse ure 0–7 naenkrat.

| Polje | Opis |
|---|---|
| Prostor | Kateri prostor |
| Od datuma | Prvi dan |
| Do datuma | Zadnji dan |
| Število tablic | Samo pri tablicah |
| Ura | Če pusti prazno, rezervira **vse ure 0–7**. Lahko pa našteješ: `1 3 5` (samo 1., 3. in 5. uro) |

> **💡 Zakaj bi to uporabil?** Športni dan traja od 1. do 5. ure. Namesto da 5-krat kilkaš "+" za vsako uro posebej, izpolniš en obrazec in sistem naredi 5 rezervacij naenkrat. Prihraniš čas in se izogneš napaki (da bi recimo pozabil 4. uro).

### Brisanje

Vodstvo lahko briše **tudi tuje** rezervacije (učitelji lahko brišejo samo svoje). Rdeč **✕** gumb ob vsaki rezervaciji.

> **💡 To pride prav, ko učitelj ni več na šoli ali ko je pomotoma rezerviral napačen termin in ga ne more popraviti sam.**

---

## Ocenjevanje

### 🚫 Zasedeni datumi

**To je najmočnejše orodje vodstva.** Z njim označiš dneve, ko razred **ne sme** imeti ocenjevanj — športni dan, ekskurzija, zaključna ekskurzija, karkoli.

> **💡 Kako to deluje od A do Ž?**
>
> 1. **Označiš dan kot zaseden** — sistem na koledar prilepi vijoličen značek
> 2. **Sistem sam izbriše vsa ocenjevanja** za ta razred v tem obdobju — tudi če so jih učitelji že vpisali
> 3. **Sistem pošlje email obvestila** prizadetim učiteljem: "Vaše ocenjevanje 2. 10. je preklicano, ker ima razred 2a športni dan."
>
> Zakaj je to bolje kot reči učiteljem na zboru? Ker učitelji pozabijo. In ker se potem znajdejo v situaciji, ko imajo napovedano ocenjevanje na dan športnega dne in morajo prestavljati. Ta mehanizem to prepreči **avtomatsko** — ni treba, da se kdo spomni.

| Polje | Opis |
|---|---|
| Razred | Izberi enega ali več (drži **Ctrl** za več razredov hkrati) |
| Od datuma | Prvi dan blokade |
| Do datuma | Zadnji dan blokade |

**Dodajanje:**
1. Odpri zavihek **Ocenjevanje**
2. Klikni **🚫 Zasedeni datumi**
3. Izberi razred(e), vnesi obdobje, klikni **Dodaj zasedene datume**

**Odstranjevanje:** V oknu Zasedeni datumi se na dnu prikaže seznam blokad. Klikni **✕** ob tisti, ki jo želiš odstraniti.

### Obvestila po e-pošti

Ko vodstvo prekliče rezervacijo ali ocenjevanje, aplikacija **samodejno** pošlje email obvestilo prizadetemu učitelju. Ni treba, da kličeš ali pišeš posebej — sistem to naredi namesto tebe.

> **💡 A sistem res pošlje email?** Ja. Ko klikneš "Shrani" pri brisanju, sistem v ozadju pošlje sporočilo na učiteljev službeni email. Če učitelj reče "Nisem vedel, da je moje ocenjevanje preklicano", mu lahko mirno rečeš: "Preveri e-pošto — dobil si obvestilo."

---

## Skrbniška plošča (samo admin)

> ⛔ Dostopna **samo administratorju** — vodstvo do nje nima dostopa. Če si vodstvo in rabiš kaj s tega seznama, kontaktiraj admina.

**Dostop:** V zgornji navigaciji se adminu prikaže gumb **Admin panel**.

### Upravljanje uporabnikov

Admin panel je nadzorna plošča za uporabnike. Tukaj dodaš novega učitelja, deaktiviraš tistega, ki je odšel, ali spremeniš geslo.

| Funkcija | Kaj naredi |
|---|---|
| **Dodajanje** | Vneseš email, ime, priimek, geslo in vlogo. Uporabi, ko sredi leta pride nov učitelj. |
| **Pregled** | Tabela z vsemi uporabniki. Klikni na stolpec za razvrščanje (npr. klikni "Ime" za abecedni vrstni red). |
| **Urejanje** | Klikni "Uredi" pri uporabniku. Spremeniš lahko vse podatke. Če geslo pusti prazno, ostane nespremenjeno. |
| **Deaktivacija / Aktivacija** | Uporabniku onemogočiš dostop — ne more se prijaviti, ampak njegove rezervacije ostanejo v sistemu. |
| **Brisanje** | Trajno izbriše uporabnika iz baze. Admin z ID=1 (glavni admin) se ne da izbrisati — zaščita pred tem, da bi kdo pomotoma izbrisal edinega admina. |
| **Spremeni geslo** | Admin lahko nastavi novo geslo kateremu koli uporabniku. Uporabi, ko učitelj pozabi geslo in ne more več dostopati do e-pošte. |

> **💡 Zakaj ne morem izbrisati admina z ID=1?** Predstavljaj si, da nekdo pomotoma izbriše edinega administratorja. Aplikacija nima več nikogar, ki bi lahko dodajal uporabnike ali reševal težave. Admin z ID=1 je "nepremičljiv" — kot varnostna varovalka. Tudi če ga poskusiš izbrisati, sistem reče "ne".

### Ročni vnos uporabnikov

Priporočljivo **samo med letom**, ko nastopi nov učitelj. Na začetku šolskega leta je bolje uporabiti uvozno skripto (glej spodaj).

### Priporočila za vloge

| Vloga | Komu dati |
|---|---|
| **Admin** | Izključno administratorju sistema (ena oseba). |
| **Vodstvo** | Ravnatelj, pomočniki ravnatelja, svetovalni delavci. |
| **Učitelj** | Vsi pedagoški delavci. |

> **💡 Če daš preveč ljudi v vlogo "Vodstvo", imajo vsi dostop do brisanja tujih rezervacij in upravljanja zasedenih datumov. To je uporabno, ampak več ljudi kot ima dostop, večja je možnost, da kdo kaj pomotoma klikne. Zato daj "Vodstvo" samo tistim, ki to res rabijo za svoje delo.**

---

## Uvoz učiteljev s skripto (samo admin)

Na začetku šolskega leta priporočam:
1. Izbriši vse uporabnike
2. Uvozi jih na novo s skripto

Skripta prebere seznam zaposlenih s šolske spletne strani.

```bash
cd /home/admin/ostc-app_deli
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Dry-run (samo pregled, brez sprememb):
python3 scripts/import_teachers.py --dry-run

# Z administracijo/tehničnim osebjem:
python3 scripts/import_teachers.py --base-url https://ostc-app.org --include-all
```

> **💡 Kaj je "dry-run"?** To je vaja brez posledic. Skripta pregleda, katere učitelje bi uvozila, ampak **ne spremeni ničesar** v bazi. Dobiš poročilo: "Našel sem 45 učiteljev, 42 že obstaja, 3 so novi." Šele ko poženeš brez `--dry-run`, dejansko doda uporabnike. Tako lahko preveriš, preden klikneš.
