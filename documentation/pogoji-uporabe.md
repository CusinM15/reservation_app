
---

# 📜 Pogoji uporabe (Terms of Service)

> **Različica:** 1.0 · **Datum:** 5. 10. 2026
>
> Ti pogoji veljajo za uporabo šolske aplikacije za rezervacije, dneve dejavnosti in
> ocenjevanja (v nadaljevanju »aplikacija«). Z uporabo aplikacije se šola in njeni
> uporabniki strinjajo s spodnjimi pogoji.

---

## 1. Kdo je kdo

| Izraz | Pomen |
|---|---|
| **Ponudnik** | Avtor aplikacije (glavni admin). Skrbi za delovanje sistema — strežnik, baza, varnost. **Ni del šole** in **nima obveznosti podpore** (glej poglavje 7). |
| **Naročnik (šola)** | Šola, ki aplikacijo uporablja. Ob registraciji ustvari svoj račun in **šolskega admina**. |
| **Uporabniki** | Osebje šole: **šolski admin**, **vodstvo**, **učitelji**. |

---

## 2. Kaj je aplikacija

Aplikacija šoli omogoča:
- **rezervacije prostorov in opreme** (računalnice, tablice in drugi prostori) za vse učitelje,
- **dneve dejavnosti** (termini po razredih, prostori, urnik),
- **ocenjevanja** (napovedani datumi z omejitvami, ponavljanja, izvoz),
- **ločene račune** za učitelje, vodstvo in šolskega admina.

Aplikacija je **večšolska**: vsaka šola vidi samo svoje podatke.

---

## 3. Naročnina

- **Vedno velja do 1. 9.** (začetek šolskega leta). Naročnina se sklene za obdobje do
  **1. 9.** — če se začne sredi leta, velja do  1. 9.;
  velja do 1. 9., do katere velja, in se nato obnovi ali pa preprosto poteče.
- **Obnova je ročna.** Šolski admin jo obnovi **od 15. 8. dalje**; po obnovi
  velja do **1. 9. naslednje leto**. Aplikacija sama ne obnavlja ničesar.
- **Cena.** Trenutno aplikacija stane **50 €**. Če se bo kdaj zaračunavala, velja:
  - cena je **letna** in se nanaša na polno leto (1. 9. → 1. 9.);
  - če šola začne **sredi leta**, plača **sorazmerni del** do 1. 9. — npr. **če je do 1. 9.
    še 5 mesecev, plača 5/12 letne cene**;
  - podrobnosti (znesek, način plačila) so vidne na strani naročnine ob sklenitvi.

> 💡 Brez veljavne naročnine se lahko v aplikacijo prijavi **le šolski admin** (da uredi
> naročnino); učitelji in vodstvo do takrat nimajo dostopa.

---

## 4. Podatki in varstvo osebnih podatkov (GDPR)

- Šola v aplikacijo vnaša **izključno podatke o osebju (zaposlenih)** — npr. ime in priimek
  zaposlenega, **uradni šolski e-naslov** in vlogo (učitelj/vodstvo/admin).
- **Prepovedano je vnašati imena ali osebne podatke otrok (učencev).** Aplikacija jih ne
  potrebuje in naj jih šola v nobenem polju ne vnaša (npr. v rezervacije, ocenjevanja,
  dneve dejavnosti, opombe).
- Vsi osebni podatki, ki jih šola vnese, so **podatki osebja, ki so javno dostopni tudi
  drugje** (npr. uradni šolski e-naslovi zaposlenih so objavljeni na spletni strani šole).
  Zato ob običajni uporabi **ni težav z GDPR** — aplikacija ne zbira in ne hrani občutljivih
  osebnih podatkov.
- Vsaka šola vidi **samo svoje podatke**; podatki različnih šol so med seboj ločeni.

---

## 5. Brisanje podatkov

- **Nič se ne izbriše samodejno.** Nobenih podatkov aplikacija ne briše po svoje (npr. starih
  rezervacij, ocenjevanj ali uporabnikov) — vse ostane, dokler jih nekdo ne izbriše.
- **Vse izbriše šolski admin.** Samo šolski admin (ali glavni admin) lahko izbriše podatke
  svoje šole:
  - **uporabnika** (ob brisanju se izbrišejo tudi njegove rezervacije in ocenjevanja),
  - **rezervacijo**, **ocenjevanje**, **dan dejavnosti**, **blokiran datum**.
- **Brisanje je trajno.** Kar se izbriše, se **dejansko odstrani iz baze PostgreSQL** in s tem
  takoj tudi iz aplikacije — ni »skritega« ali poenostavljenega brisanja, obnovitev je mogoča
  le iz vnaprej shranjene varnostne kopije (.sql), če jo šola ima.
- **Deaktivacija uporabnika** (začasna onemogočitev prijave) je **ločena** od brisanja — to je
  priročno, ko želite nekomu začasno zapreti dostop, podatkov pa še ne brisati.
- Brisanje celotnega **računa šole** (celotne šole z vsemi podatki) izvede **ponudnik
  (glavni admin)** na zahtevo šole.

> 🔐 Objavljeno/prijavljeno geslo se v aplikaciji **nikoli ne izpiše**; uporabnik ga nastavi
> sam prek »Pozabljeno geslo?«.

---

## 6. Vloge in pravice — kaj kdo dela

### 👩‍🏫 Učitelj
- Rezervira prostore in opremo (ob upoštevanju zasedenosti in omejitev).
- Napove ocenjevanja (sistem preverja omejitve: na teden, na dan, zaporedni dnevi).
- **Briše samo svoje** rezervacije.
- Bere dneve dejavnosti in ta navodila.

### 👑 Vodstvo (ravnatelj, pomočniki)
- **Vse, kar lahko učitelj**, in poleg tega:
- **serijske rezervacije** (tedenske in celodnevne serije),
- **briše tudi tuje** rezervacije (s tem pride odgovornost),
- **ureja dneve dejavnosti** (stran »Vnos dejavnosti«) in blokira datume.

### 🛠️ Šolski admin (administrator šole)
- **Vse, kar lahko vodstvo**, in poleg tega:
- **upravlja uporabnike** svoje šole (doda, uredi, deaktivira, izbriše) — uporabniško ime je
  šolski e-naslov, gesla se nikoli ne izpišejo,
- **ureja nastavitve šole**: razredi, prostori, urnik, števila, pravila ocenjevanja,
  **e-pošta/SMTP** (naslov admina, naslov pošiljatelja, varnostne kopije, strežnik, uporabniško
  ime in geslo),
- **naročnina**: vidi stanje, sporoči plačilo in jo **sam podaljša** (od 15. 8.),
- **varnostne kopije**: prenese/prejme .sql kopijo in obnovi podatke,
- pregleduje **dnevnik sprememb** (audit log).

### ⚙️ Glavni admin (ponudnik)
- **Ni del šole** in **ni vključen v vsakodnevno delo šole** — skrbi za delovanje sistema
  (strežnik, baza, posodobitve), potrjuje plačila in (na zahtevo) izbriše celotno šolo.
- **Nima obveznosti biti dosegljiv oz. nuditi podporo** (glej poglavje 7).

---

## 7. Podpora in dosegljivost ponudnika

- **Ponudnik (avtor/glavni admin) nima nikakršne obveznosti**, da je dosegljiv ali da nudi
  uporabniško podporo, pomoč, usposabljanje ali odgovarja na vprašanja.
- Tudi **če se ponudnik** kdaj odloči za pomoč/podporo, **to ne ustvari nobene obveznosti** —
  gre za prostovoljno dejanje, ki ga lahko kadarkoli preneha.
- Aplikacija je na voljo **»takšna, kot je«**. Ponudnik ne jamči neprekinjenega delovanja,
  brez napak ali neprekinjene dosegljivosti, in ne odgovarja za izgubo podatkov (šola naj
  redno preverja svoje varnostne kopije).

---

## 8. Soglasje s pogoji — kje in kdaj se prikaže

Strinjanje s temi pogoji je treba uporabnikom **prikazati in zabeležiti**:

1. **Ob registraciji šole** — šolski admin ob potrditvi registracije potrdi, da je seznanjen s
   pogoji v imenu šole.
2. **Ob prvi prijavi vsakega uporabnika** (učitelj, vodstvo, admin) — prikaže se pogovorno
   okno z pogoji in potrditvenim poljem (»Strinjam se s pogoji uporabe«); brez potrditve
   nadaljnja uporaba ni mogoča.
3. **Ob večjih spremembah pogojev** — ob prvi prijavi po spremembi se prikaže obvestilo o novi
   različici in zahteva ponovna potrditev.
4. **Obstoječi uporabniki:** aplikacija je **že v produkciji**, zato je treba **ob naslednji
   prijavi** vsakemu obstoječemu uporabniku prikazati pogoje in zahtevati potrditev —
   nikogar ne izključimo vnaprej, pač pa soglasje zberemo ob prvi prijavi po objavi teh pogojev.

**Kaj se zabeleži ob soglasju:** kdo (uporabnik), kdaj (čas) in različica pogojev (npr. 1.0) —
najbolje v bazi (tabela soglasij). Tako je razvidno, kdo je s katero različico soglašal.

> ℹ️ Pogoje je smiselno prikazati tudi na izbrani strani (npr. dno prijavne strani in gumb
> »Pogoji uporabe«), da so dosegljivi kadarkoli, ne le ob prijavi.

---

## 9. Spremembe pogojev

Ponudnik lahko te pogoje občasno posodobi. Ob pomembni spremembi se uporabnikom ob prijavi
prikaže nova različica in zahtevana je ponovna potrditev (glej poglavje 8). Različica in datum
sta vedno navedena na vrhu dokumenta.

---

## 10. Sprejeto in dogovorjeno

Z uporabo aplikacije šola in njeni uporabniki potrjujejo, da:
- so prebrali in sprejeli te pogoje,
- v aplikacijo vnašajo **zgolj podatke osebja** in **nobene** podatke otrok/osebnih podatkov
  učencev,
- se strinjajo, da naročnina **velja do 1. 9.** in je **ni mogoče prekiniti sredi obdobja**,
- razumejo, da **nič ne izgine samodejno** in da podatke briše **šolski admin**.

---

> **Avtor / ponudnik:** Matej Čušin
>
> Aplikacija je odprtokodna; če ti je v pomoč, lahko projekt podpreš z donacijo
> (povezava je v README repozitorija).
