
---

> 🛠️ **Namenjeno izključno administratorju šole** (skrbniku sistema).
> Vodstvo in učitelji tega dokumenta ne vidijo.
>
> Administrator skrbi za **nastavitve šole, uporabnike, e-pošto, naročnino in
> varnostne kopije**. Za vsakodnevno delo (rezervacije, ocenjevanja, dnevi
> dejavnosti) glejte *Navodila za vodstvo* in *Navodila za učitelje*.

---

# 🛠️ Navodila za administratorja — OŠ Toneta Čufarja Jesenice

---

## 1. Kje je kaj

| Kaj | Kje |
|---|---|
| 👥 **Uporabniki** (računi učiteljev, vodstva) | Zgornji meni → **Admin panel** (ali <code>/auth/admin/users</code>) |
| ⚙️ **Nastavitve šole** (razredi, prostori, števila, urnik, e-pošta) | Zgornji meni → **⚙️ Nastavitve šole** (ali <code>/settings</code>) |
| 🧭 **Navodila za nastavitev šole** (kaj še urediti) | <code>/nastavitev</code> |
| 💶 **Naročnina šole** | ⚙️ Nastavitve šole → razdelek *Naročnina šole* (ali <code>/narocnina</code>) |
| 💾 **Varnostna kopija in obnova** | ⚙️ Nastavitve šole → *Varnostna kopija* / *Obnova* |
| 📋 **Dnevnik sprememb (audit log)** | Zgornji meni → **📋 Audit log** |

> 💡 **Namig:** Skoraj vse administratorjeve nastavitve so na enem mestu —
> v **Nastavitvah šole**. Spremembe veljajo takoj po shranjevanju.

---

## 2. Uporabniki

Uporabniško ime uporabnika je **njegov šolski e-poštni naslov**. Gesla se
**nikjer ne izpisujejo** — vsak uporabnik si ga nastavi sam prek gumba
**Pozabljeno geslo?** na prijavni strani.

### Ročno urejanje (Admin panel)

| Funkcija | Opis |
|---|---|
| Dodajanje | Vnesete e-pošto, ime, priimek in vlogo |
| Pregled | Tabela vseh uporabnikov (klik na stolpec za razvrščanje) |
| Urejanje | »Uredi« — če geslo pustite prazno, ostane nespremenjeno |
| Deaktivacija / Aktivacija | Uporabniku onemogočite ali ponovno omogočite dostop |
| Brisanje | Trajno izbriše uporabnika (glavni admin, ID=1, je zaščiten) |

### Uvoz iz CSV datoteke

Na strani **Uporabniki** izberete CSV datoteko in kliknete **📥 Uvozi CSV**.
Glava stolpcev ni obvezna; privzeti vrstni red je
`uporabniško ime, email, ime, priimek, vloga, geslo`. Geslo lahko izpustite —
aplikacija si ga izmisli in ga **ne pokaže**. Obstoječa uporabniška imena se
preskočijo.

### Uvoz zaposlenih s skripto

Skripta prebere seznam zaposlenih kar s šolske spletne strani (samo bere, nič
ne spreminja):

```bash
cd /home/admin/reservation_app
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Preizkus (brez dejanskih sprememb):
python3 scripts/import_teachers.py --dry-run

# Z administracijo in tehničnim osebjem:
python3 scripts/import_teachers.py --base-url https://ostc-app.org --include-all
```

---

## 3. Nastavitve šole

Na strani **⚙️ Nastavitve šole** uredite vse, kar določa delovanje za vašo
šolo. Po vsaki spremembi kliknite **Shrani nastavitve**.

| Razdelek | Kaj urejate |
|---|---|
| **Razredi** | Seznam oddelkov (npr. `1. a`). Vsak razred v svoji vrstici; dodate z **＋ Dodaj razred** |
| **Števila** | Imenovane številske spremenljivke (npr. `Število tablic = 28`) |
| **Prostori** | Prostori za rezervacijo. Kljukica **»število«** poveže prostor s številsko spremenljivko — tak prostor si lahko izposodi več učiteljev hkrati (vsak navede količino) |
| **Urnik** | Ure pouka (npr. `07:30-08:15`) |
| **Pravila ocenjevanja** | Največ ocenjevanj na teden / dan / z ponavljanjem / zaporednih dni |
| **E-pošta (SMTP)** | Naslov admina, naslov pošiljatelja (From), naslov za varnostne kopije, SMTP strežnik, uporabniško ime in geslo |

> 🔒 **Geslo SMTP se nikoli ne izpiše.** Če polje pustite prazno, se obstoječe
> geslo **ohrani**. Novo geslo vpišete le, ko ga želite zamenjati.

### Prostor z več enotami (npr. 5 računalnikov)

1. V razdelku **Števila** dodajte spremenljivko `Število računalnikov = 5`.
2. V razdelku **Prostori** dodajte prostor in obkljukajte **»število«** ter ga
   povežite s to spremenljivko.
3. Zdaj si lahko več učiteljev hkrati izposodi isto enoto — skupna vsota na uro
   je omejena s spremenljivko. Brez kljukice je prostor ekskluziven (ena
   rezervacija na uro).

---

## 4. E-pošta (SMTP)

Brez pravilno nastavljene e-pošte **obvestila in obnovitev gesla ne delujeta**.

| Nastavitev | Kaj je |
|---|---|
| **ADMIN_EMAIL** | Naslov šolskega admina — prejema obvestila in povezavo za obnovitev gesla |
| **MAIL_FROM** | Naslov pošiljatelja (From). Nova šola dobi testni naslov `test@example.invalid` — zamenjajte ga s svojim, sicer pošte ni mogoče dostaviti |
| **BACKUP_EMAIL** | Kam naj gre nočna varnostna kopija |
| **MAIL_SERVER / MAIL_USERNAME / MAIL_PASSWORD** | Podatki SMTP strežnika (če šola uporablja Arnes, vpišite podatke Arnesa) |

---

## 5. Naročnina šole

Šola potrebuje **veljavno naročnino** (tudi pri ceni 0 € jo je treba redno
obnoviti), sicer se učitelji ne morejo prijaviti — prijavi se lahko le
administrator šole.

- V **Nastavitvah šole → Naročnina šole** vidite stanje in veljavnost.
- Gumb **Kupi / Podaljšaj naročnino** vodi na stran naročnine, kjer izberete
  obdobje, plačate in **sporočite plačilo**.
- Naročnino potrdi ponudnik aplikacije, ko je nakazilo prejeto.
- **Samodejno obnavljanje:** če ga vklopite in uredite plačilo prek PayPala, se
  naročnina obnavlja sama ob vsakem obdobju.

> 💶 Trenutno je na voljo **letni** plan (12 mesecev).

---

## 6. Varnostna kopija in obnova

### Naredi backup

V **Nastavitvah šole → Varnostna kopija šole** kliknite **📧 Naredi backup**.
Aplikacija sestavi `.sql` kopijo podatkov **samo te šole** in jo pošlje na
**E-pošto za varnostne kopije** (BACKUP_EMAIL). Poleg tega se vsako noč pripravi
samodejna kopija.

### Obnova iz kopije

V **Nastavitvah šole → Obnova iz varnostne kopije** naložite `.sql` datoteko in
izberite, kaj naj se obnovi. Podatki izbrane skupine **za to šolo** se zamenjajo
s podatki iz kopije; podatki drugih šol ostanejo nedotaknjeni.

| Gumb | Kaj obnovi |
|---|---|
| 👥 Uporabniki | Račune šole (z gesli) |
| ⚙️ Nastavitve | Razrede, prostore, urnik, števila |
| 📋 Dejavnosti | Dneve dejavnosti + zasedene datume |
| 📅 Rezervacije | Rezervacije prostorov |
| 📝 Ocenjevanje | Ocenjevanja |
| ♻️ Celotna šola (vse) | Ponovno postavi vso šolo iz kopije |

> ⚠️ Obnova **zamenja** obstoječe podatke izbrane skupine. Vsaka obnova se
> zabeleži v dnevnik dogodkov.

---

## 7. Dnevi dejavnosti in zasedeni datumi

Urejajo se **v koledarju** (glavna stran aplikacije) oziroma na strani
**Vnos dejavnosti** — **ne** v Nastavitvah šole. Podrobno je opisano v
*Navodilih za vodstvo* (razdelek *Ocenjevanje in dnevi dejavnosti*).

---

## 8. Audit log (dnevnik sprememb)

**📋 Audit log** omogoča pregled vseh pomembnih sprememb — kdo je kaj naredil in
kdaj (rezervacije, serije, ocenjevanja, dnevi dejavnosti, uporabniki, spremembe
gesel, nastavitve prodaje …). Uporabno za sledljivost in odpravljanje napak.

---

## 9. Priporočila za vloge

| Vloga | Kdo naj jo ima | Pravice |
|---|---|---|
| **Admin** | Samo administrator sistema | Vse — skrbniška plošča, uporabniki, nastavitve, naročnina, kopije |
| **Vodstvo** | Ravnatelj, pomočniki | Rezervacije serij, brisanje tujih rezervacij, dnevi dejavnosti |
| **Učitelj** | Vsi pedagoški delavci | Osnovne rezervacije in ocenjevanja |

**Z eno besedo:** admin skrbi za sistem, vodstvo za urnik, učitelji za pouk.

---

> 🛠️ **Opomba:** Pravih gesel in e-naslovov v teh navodilih ni — vse primere
> zamenjajte s svojimi. Gesla se v aplikaciji nikjer ne izpisujejo.
>
> **Avtor:** Matej Čušin
