
---

# 📜 Pogoji uporabe (Terms of Service)

> **Različica:** 2.0 · **Datum:** 4. 11. 2026
>
> Ti pogoji veljajo za uporabo šolske aplikacije za **rezervacije prostorov in opreme,
> dneve dejavnosti, ocenjevanja, digitalni zaslon z nadomeščanji in prijave na
> govorilne ure** (v nadaljevanju »aplikacija«). Z uporabo aplikacije se šola in njeni
> uporabniki strinjajo s spodnjimi pogoji.

---

## 1. Kdo je kdo

| Izraz | Pomen |
|---|---|
| **Ponudnik** | Ponudnik storitve gostovanja. Skrbi **izključno za delovanje strežnika** (aplikacija in baza). **Ni del šole**, ne odloča o vsebini podatkov in **nima obveznosti podpore** (glej 1.1 in poglavje 7). |
| **Naročnik (šola)** | Šola, ki aplikacijo uporablja. Ob registraciji ustvari svoj račun in **šolskega admina**. |
| **Uporabniki** | Osebje šole: **šolski admin**, **vodstvo**, **učitelji**. |

### 1.1 Obseg dela ponudnika (kaj dela in česa ne)

**Ponudnik opravlja izključno:**

- gostovanje aplikacije in baze podatkov na strežniku,
- nameščanje posodobitev in vzdrževanje delovanja strežnika,
- pripravo kode za **varnostne kopije po e-pošti** — kopije se pošiljajo **samo, če jih šola vklopi in uredi v Nastavitvah šole** (glej 5.1 Varnostne kopije).

**Ponudnik NE opravlja in ni dolžan opravljati:**

- vnosa, urejanja ali preverjanja podatkov šole (rezervacij, ocenjevanj, dni dejavnosti, nadomeščanj, uporabnikov, nastavitev),
- preverjanja pravilnosti, popolnosti ali zakonitosti vsebine, ki jo vnese šola,
- uporabniške podpore, pomoči, usposabljanja ali svetovanja (razen če se izrecno in pismeno dogovori drugače),
- skrbništva nad dostopi in gesli uporabnikov šole,
- **varnostnih kopij namesto šole** in **obnovitve (recoveryja) podatkov** — za to poskrbi šolski admin (glej 5.1).

Kako je aplikacija videti in kaj vsebuje, je odvisno **od šole same** (npr. nastavitve e-pošte/SMTP, seznami razredov in prostorov, urniki, uporabniški računi, vneseni termini, slike za zaslon). Za vse te vsebine in nastavitve odgovarja **šola**.

---

## 2. Kaj je aplikacija

Aplikacija šoli omogoča:

- **rezervacije prostorov in opreme** (računalnice, tablice in drugi prostori) za vse učitelje, tudi popoldanski urnik in serijske rezervacije za vodstvo,
- **dneve dejavnosti** (termini po razredih, prostori, urnik, celodnevne in krajše dejavnosti),
- **ocenjevanja** (napovedani datumi z omejitvami — na teden, na dan, zaporedni dnevi — ponavljanja in izvoz),
- **digitalni zaslon z nadomeščanji** (javna stran `/nadomescanja_<kratica>` za TV-zaslone: nadomeščanja in slike, ki jih šola nastavi),
- **prijave staršev na govorilne ure** (javna prijavna stran: izbor učitelja in termina; učitelji si sami uredijo svoje dopoldanske termine, vodstvo popoldanske; trajanje termina nastavi šola v Nastavitvah),
- **ločene račune** za učitelje, vodstvo in šolskega admina (ravnatelj = vodstvo),
- **e-poštna obvestila** (preklicane rezervacije, ocenjevanja, ponastavitev gesla, varnostne kopije — delujejo le, če šola nastavi e-poštni strežnik/SMTP v Nastavitvah šole),
- **dnevnik sprememb** (audit log) — kdo je kaj spremenil,
- **nastavitve šole** na enem mestu (razredi, prostori, urnika, pravila ocenjevanja, e-pošta, govorilne, zaslon, varnostne kopije, časovni pas),
- **dvojezičnost** (slovenščina/angleščina).

Aplikacija je **večšolska**: vsaka šola vidi samo svoje podatke.

---

## 3. Naročnina in plačilo

- **Naročnina vedno velja do 1. 9.** (začetek šolskega leta). Sklenjena je za obdobje do **1. 9.** — tudi če se začne sredi leta, velja le do 1. 9.; nato se obnovi ali preprosto poteče.
- **Obnova je ročna.** Šolski admin jo obnovi **od 15. 8. dalje**; po obnovi velja do **1. 9. naslednje leto**. Aplikacija sama ne obnavlja ničesar.
- **Cena.** Aplikacija stane **150 €** (z DDV). Velja:

  - cena je **letna** in se nanaša na polno leto (1. 9. → 1. 9.),
  - če šola začne **sredi leta**, plača **sorazmerni del** do 1. 9. — npr. **če je do 1. 9. še 5 mesecev, plača 5/12 letne cene**,
  - podrobnosti (znesek, način plačila) so vidne na strani nakupa (`/nakup`) ob sklenitvi.

- **Plačilo in e-račun.** Nakup poteka prek strani **`/nakup`**. Po plačilu ponudnik izstavi **e-račun (B2G)** in ga pošlje šoli; **plačilo potrdi ponudnik**, nato je naročnina aktivna.
- **Brez veljavne naročnine** se lahko v aplikacijo prijavi **le šolski admin** (da uredi naročnino); učitelji in vodstvo do takrat nimajo dostopa.
- **Nova šola, ki v 28 dneh ne sklene naročnine**, se z vsemi podatki samodejno izbriše (avtomatski postopek za preprečevanje zlorab). Za podaljšanje ali vprašanja se šola pred iztekom obrne na ponudnika.

> 💡 Brez veljavne naročnine se lahko v aplikacijo prijavi **le šolski admin** (da uredi naročnino); učitelji in vodstvo do takrat nimajo dostopa.

---

## 4. Podatki in varstvo osebnih podatkov (GDPR)

- Šola v aplikacijo vnaša **izključno podatke o osebju (zaposlenih)** — npr. ime in priimek zaposlenega, **uradni šolski e-naslov** in vlogo (učitelj/vodstvo/admin).
- **Prepovedano je vnašati imena ali osebne podatke otrok (učencev).** Aplikacija jih ne potrebuje in naj jih šola v nobenem polju ne vnaša (npr. v rezervacije, ocenjevanja, dneve dejavnosti, opombe).
- Vsi osebni podatki, ki jih šola vnese, so **podatki osebja, ki so javno dostopni tudi drugje** (npr. uradni šolski e-naslovi zaposlenih so objavljeni na spletni strani šole). Zato ob običajni uporabi **ni težav z GDPR** — aplikacija ne zbira in ne hrani občutljivih osebnih podatkov.
- Vsaka šola vidi **samo svoje podatke**; podatki različnih šol so med seboj ločeni.

### 4.1 Vloge po GDPR

- **Šola je upravljavec osebnih podatkov.** Šola določi, katere podatke vnaša, za kakšen namen in koliko časa jih hrani, ter je odgovorna za **zakonitost** obdelave (ustrezno pravno podlago, seznanitev zaposlenih).
- **Ponudnik je obdelovalec.** Aplikacijo (in strežnik) ponudnik upravlja **izključno po navodilih šole** in podatkov **ne uporablja za svoje namene** (npr. ne prodaja, ne oglašuje, ne združuje s podatki drugih šol).
- Ponudnik vodi **evidence obdelav** in podatke obdeluje le toliko, kolikor je potrebno za delovanje storitve. Podatki se hranijo v **EU**.

### 4.2 Varnostni ukrepi in obveščanje o incidentu

- Ponudnik izvaja ustrezne **tehnične in organizacijske ukrepe** za zaščito podatkov (ločeni računi in vloge, gesla shranjena zgolj zgoščeno, ločenost podatkov med šolami, šifriran prenos).
- Če ponudnik zazna **vdor oziroma kršitev osebnih podatkov**, šolo o tem obvesti **brez nepotrebnega odlašanja, najpozneje v 72 urah** od zaznave, in ji pomaga pri izpolnitvi obveznosti prijave nadzornemu organu (Informacijski pooblaščenec).
- Ob prenehanju naročninske pogodbe se po dogovoru s šolo podatki **izbrišejo** oziroma **vrnejo** šoli (izvoz).

### 4.3 Pogodba o obdelavi osebnih podatkov (DPA)

- Ponudnik šoli na zahtevo predloži **pogodbo o obdelavi osebnih podatkov**, ki podrobneje uredi zgoraj našteto (predmet in trajanje obdelave, vrste podatkov, obveznosti in pomoč šoli, obveščanje o vdoru, ukrepe ob prenehanju). Šola jo podpiše (elektronsko zadošča).
- Za pridobitev DPA se šola obrne na ponudnika.

### 4.4 Prijave staršev na govorilne ure

Prijave staršev na govorilne ure delujejo kot **izjema** od zgornje prepovedi vnašanja podatkov otrok, in sicer **izključno** pod temi pogoji:

- Starš **sam vnese** ime in priimek otroka (ter po želji razred), svoje ime in priimek ter svoj e-naslov — šola teh podatkov ne vnaša.
- Namen obdelave je **izkazano le najava na govorilne ure** (predhodna najava), nič drugega.
- Podatki so **vidni samo izbranemu učitelju** (ter šolskemu adminu in vodstvu, ki skrbijo za delovanje sistema). Javno niso objavljeni nikjer.
- **Hramba je omejena:** prijave se **samodejno izbrišejo 24 ur po koncu govorilnih ur** (poglavje 5).
- Podlaga za obdelavo: izvedba obveznosti šole po organizaciji govorilnih ur ter soglasje starša, ki ga starš poda ob oddaji prijave s potrditvenim poljem.
- Prijave staršev **ne kreirajo uporabniškega računa** — starš nima dostopa v aplikacijo; učitelj vidi samo svoje prijave.

---

## 5. Brisanje podatkov in varnostne kopije

### 5.1 Varnostne kopije (backup) — odgovornost šole

- Ponudnik je pripravil **kodo za varnostne kopije**, ki posnamejo kopijo baze in jo pošljejo po e-pošti. **Toda brez nastavljenih stvari v Nastavitvah šole se ne zgodi nič samodejno** — kopije se pošiljajo **samo, če šolski admin v Nastavitvah šole uredi vse potrebno** (e-poštni strežnik/SMTP, naslov za varnostne kopije ipd.).
- **Brez nastavljenih nastavitev varnostne kopije ne delujejo** — aplikacija takrat ne more poslati nobene kopije, tudi če bi želela.
- **Ponudnik ne prevzema nikakršne odgovornosti**, če se podatki zbrišejo ali postanejo nedosegljivi (npr. okvara strežnika ali baze, človeška napaka, brisanje, izpad gostovanja).
- **Edini, ki mora poskrbeti za obnovitev podatkov (recovery), je šolski admin:** preveri, da so varnostne kopije nastavljene in da jih šola redno dobiva, jih hrani na varnem mestu in po potrebi izvede obnovo iz njih (Nastavitve šole → varnostne kopije/obnova).
- Ponudnik lahko šoli **prostovoljno pomaga** pri nastavitvi ali obnovi, vendar to ni njegova obveznost in ne ustvarja odgovornosti.

### 5.2 Brisanje podatkov

- **Nič se ne izbriše samodejno.** Nobenih podatkov aplikacija ne briše po svoje (npr. starih rezervacij, ocenjevanj ali uporabnikov) — vse ostane, dokler jih nekdo ne izbriše.
- **Izjema — prijave na govorilne ure:** prijave staršev se **samodejno izbrišejo 24 ur po koncu govorilnih ur** (4.4). S tem se izpolni zahteva o omejeni hrambi in te prijave ne obremenjujejo baze dlje, kot je potrebno.
- **Izjema — nova šola brez naročnine:** nov račun šole, ki v 28 dneh ne sklene naročnine, se samodejno izbriše (poglavje 3).
- **Vse izbriše šolski admin.** Samo šolski admin lahko izbriše podatke svoje šole:

  - **uporabnika** (ob brisanju se izbrišejo tudi njegove rezervacije in ocenjevanja),
  - **rezervacijo**, **ocenjevanje**, **dan dejavnosti**, **blokiran datum**.

- **Brisanje je trajno.** Kar se izbriše, se **dejansko odstrani iz baze PostgreSQL** in s tem takoj tudi iz aplikacije — ni »skritega« ali poenostavljenega brisanja; obnovitev je mogoča le iz vnaprej shranjene varnostne kopije (.sql), če jo ima šola (glej 5.1).
- **Deaktivacija uporabnika** (začasna onemogočitev prijave) je **ločena** od brisanja — to je priročno, ko želite nekomu začasno zapreti dostop, podatkov pa še ne brisati.
- Brisanje celotnega **računa šole** (celotne šole z vsemi podatki) izvede **ponudnik (glavni admin)** na zahtevo šole.

> 🔐 Objavljeno/prijavljeno geslo se v aplikaciji **nikoli ne izpiše**; uporabnik ga nastavi sam prek »Pozabljeno geslo?«.

---

## 6. Vloge in pravice — kaj kdo dela

### 👩‍🏫 Učitelj

- Rezervira prostore in opremo (ob upoštevanju zasedenosti in omejitev).
- Napove ocenjevanja (sistem preverja omejitve: na teden, na dan, zaporedni dnevi).
- **Briše samo svoje** rezervacije; vidi in (za svoje ure) ureja najave staršev na govorilne.
- Uredi **svoje dopoldanske govorilne ure** (dan, ura, predmet, razred, prostor) na strani »Moje govorilne ure«.
- Bere dneve dejavnosti in navodila.

### 👑 Vodstvo (ravnatelj, pomočniki)

- **Vse, kar lahko učitelj**, in poleg tega:

  - **serijske rezervacije** (tedenske in celodnevne serije),
  - **briše tudi tuje** rezervacije (s tem pride odgovornost),
  - **ureja dneve dejavnosti** (stran »Vnos dejavnosti«) in blokira datume,
  - ureja **popoldanske govorilne ure** (kdaj so; termini) ter najave staršev.

### 🛠️ Šolski admin (administrator šole)

- **Vse, kar lahko vodstvo**, in poleg tega:

  - **upravlja uporabnike** svoje šole (doda, uredi, deaktivira, izbriše) — uporabniško ime je šolski e-naslov, gesla se nikoli ne izpišejo,
  - **ureja nastavitve šole**: razredi, prostori, urnika (dopoldan/popoldan), števila, pravila ocenjevanja, **e-pošta/SMTP** (naslov admina, naslov pošiljatelja, varnostne kopije, strežnik, uporabniško ime in geslo), **govorilne ure** (omogočene, vloge, trajanje termina), **digitalni zaslon** (slike, nadomeščanja, osvežitev),
  - **naročnina**: vidi stanje, sporoči plačilo in jo **sam podaljša** (od 15. 8.),
  - **varnostne kopije**: nastavi jih v Nastavitvah šole (5.1), prenese/prejme .sql kopijo in obnovi podatke (recovery),
  - pregleduje **dnevnik sprememb** (audit log).

### ⚙️ Glavni admin (ponudnik)

- **Ni del šole** in **ni vključen v vsakodnevno delo šole** — skrbi za delovanje sistema (strežnik, baza, posodobitve), potrjuje plačila in (na zahtevo) izbriše celotno šolo.
- **Nima obveznosti biti dosegljiv oz. nuditi podporo** (glej poglavje 7); ne prevzema odgovornosti za varnostne kopije šole (5.1).

---

## 7. Podpora in dosegljivost ponudnika

- **Ponudnik (avtor/glavni admin) nima nikakršne obveznosti**, da je dosegljiv ali da nudi uporabniško podporo, pomoč, usposabljanje ali odgovarja na vprašanja.
- Tudi **če se ponudnik** kdaj odloči za pomoč/podporo, **to ne ustvari nobene obveznosti** — gre za prostovoljno dejanje, ki ga lahko kadarkoli preneha.
- Aplikacija je na voljo **»takšna, kot je«**. Ponudnik ne jamči neprekinjenega delovanja, brez napak ali neprekinjene dosegljivosti, in **ne odgovarja za izgubo podatkov** (šola naj redno preverja svoje varnostne kopije — 5.1).

### 7.1 Omejitev odgovornosti

- Ponudnik skrbi **zgolj za delovanje strežnika**. Za vsebino aplikacije, za podatke, ki jih vnese šola, in za posledice uporabe odgovarja **šola**.
- Ponudnik **ne odgovarja** za:

  - pravilnost, popolnost ali zakonitost podatkov, ki jih vnese šola,
  - odločitve šole ali njenih uporabnikov, sprejete na podlagi podatkov iz aplikacije,
  - škodo, nastalo zaradi napačnih, nepopolnih ali nepravočasnih vnosov šole,
  - izgubo ali nedosegljivost podatkov zaradi **višje sile**, izpada ponudnika strežnika ali internetne povezave, kibernetskega napada, okvare strojne opreme ali načrtovanega vzdrževanja,
  - **izgubo podatkov zaradi nedelujočih ali nenastavljenih varnostnih kopij** — varnostne kopije so odgovornost šole (5.1),
  - **posredno škodo**, izgubljeni dobiček ali izgubo podatkov (šola naj redno preverja svoje varnostne kopije),
  - ravnanje tretjih ponudnikov (npr. ponudnik strežnika, ponudnik e-pošte, ponudnik plačil).

- Aplikacija je **pomoč pri organizaciji**, ne uradna evidenca ali pravni vir; šola je odgovorna za skladnost z lastnimi pravili, predpisi in za svoje notranje procese.
- **Skupna odgovornost ponudnika** je v vsakem primeru omejena na znesek, ki ga je šola plačala za tekoče naročninsko obdobje.
- Ponudnik lahko z gostovanjem **kadarkoli preneha** ob koncu plačanega obdobja; šoli omogoči izvoz njenih podatkov.

---

## 8. Soglasje s pogoji — kje in kdaj se prikaže

Strinjanje s temi pogoji je treba uporabnikom **prikazati in zabeležiti**:

1. **Ob registraciji šole** — šolski admin ob potrditvi registracije potrdi, da je seznanjen s pogoji v imenu šole.
2. **Ob prvi prijavi vsakega uporabnika** (učitelj, vodstvo, admin) — prikaže se pogovorno okno s pogoji in potrditvenim poljem (»Strinjam se s pogoji uporabe«); brez potrditve nadaljnja uporaba ni mogoča.
3. **Ob večjih spremembah pogojev** — ob prvi prijavi po spremembi se prikaže obvestilo o novi različici in zahteva ponovna potrditev.
4. **Obstoječi uporabniki:** aplikacija je **že v produkciji**, zato je treba **ob naslednji prijavi** vsakemu obstoječemu uporabniku prikazati pogoje in zahtevati potrditev — nikogar ne izključimo vnaprej, pač pa soglasje zberemo ob prvi prijavi po objavi teh pogojev.
5. **Starš ob prijavi na govorilne ure:** na javni prijavni strani starš pred oddajo prijave **potrdi strinjanje s pogoji** (potrditveno polje ob obrazcu). S tem potrjuje, da se podatki (ime starša, e-naslov, ime otroka) uporabijo izključno za najavo na govorilne ure, da jih vidi samo izbrani učitelj in da se samodejno izbrišejo 24 ur po koncu govorilnih ur.

**Kaj se zabeleži ob soglasju:** kdo (uporabnik), kdaj (čas) in različica pogojev (npr. 2.0) — najbolje v bazi (tabela soglasij). Tako je razvidno, kdo je s katero različico soglašal.

> ℹ️ Pogoje je smiselno prikazati tudi na izbrani strani (npr. dno prijavne strani in gumb »Pogoji uporabe«), da so dosegljivi kadarkoli, ne le ob prijavi.

---

## 9. Spremembe pogojev

Ponudnik lahko te pogoje občasno posodobi. Ob pomembni spremembi se uporabnikom ob prijavi prikaže nova različica in zahtevana je ponovna potrditev (glej poglavje 8). Različica in datum sta vedno navedena na vrhu dokumenta.

---

## 10. Sprejeto in dogovorjeno

Z uporabo aplikacije šola in njeni uporabniki potrjujejo, da:

- so prebrali in sprejeli te pogoje,
- v aplikacijo vnašajo **zgolj podatke osebja** in **nobene** podatke otrok/osebnih podatkov učencev — **razen podatkov, ki jih ob prijavi na govorilne ure vnese starš sam** (4.4),
- se strinjajo, da naročnina **velja do 1. 9.** in je **ni mogoče prekiniti sredi obdobja**,
- razumejo, da **nič ne izgine samodejno** in da podatke briše **šolski admin** (izjema: prijave staršev na govorilne se samodejno izbrišejo 24 ur po koncu govorilnih ur; nova šola brez naročnine se po 28 dneh samodejno izbriše),
- **varnostne kopije in obnovitev (recovery) podatkov so izključno odgovornost šolskega admina** — brez nastavitev v Nastavitvah šole se kopije ne pošiljajo samodejno; ponudnik ne prevzema odgovornosti za izgubo podatkov (5.1),
- **šola je odgovorna** za pravilnost in zakonitost vnesenih podatkov ter za svoje uporabnike (dostope, gesla, pravice),
- **šola sama** poskrbi za svoje varnostne kopije in za nastavitve e-pošte/SMTP,
- razumejo, da ponudnik skrbi **zgolj za delovanje strežnika** in **ni odgovoren** za vsebino aplikacije, za odločitve šole ali za posledice uporabe (poglavji 1.1 in 7.1).

---

> **Avtor aplikacije:** Matej Čušin — skrbi **zgolj za delovanje strežnika** (poglavje 1.1); za vsebino, uporabo in **varnostne kopije podatkov** odgovarja šola (poglavji 5.1 in 7.1).
>
> Aplikacija v polni obliki **ni odprtokodna**. Odprtokodna je zgolj starejša, poenostavljena različica z **manj funkcijami**.
