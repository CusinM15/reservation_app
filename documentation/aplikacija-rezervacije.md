🌐 **Jezik / Language:** [🇸🇮 Slovenščina](aplikacija-rezervacije.md) | [🇬🇧 English](en/aplikacija-rezervacije.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 📱 Aplikacija za rezervacije in napovedi ocenjevanja

## Kaj to sploh je? (za tiste, ki prvič slišite)

Predstavljajte si **spletno stran, kot je spletna banka** — samo namesto denarja učitelji prek nje **rezervirajo prostore** (računalnico, tablice, ladjo, gospodinjsko učilnico) in **napovedujejo pisna ocenjevanja**.

Namesto da bi se lovili po hodnikih, pošiljali deset emailov ali pisali v zvezek — vse narediš na enem mestu, s par kliki. Sistem pa poskrbi, da se nihče ne zaleti v drugega (dva učitelja ne moreta hkrati rezervirati iste računalnice, in ne moreš napovedati treh ocenjevanj v enem tednu).

## Zakaj smo to naredili?

**Problem (po domače):** Na šoli je bil kaos. Nihče ni vedel, kdo je kdaj v računalnici. Pisna ocenjevanja so se nabirala na isti dan. Učitelji so ugotavljali šele na hodniku, da ima nekdo drug že zasedeno.

**Rešitev:** Ena spletna stran, ki poveže vse — koledar rezervacij + napovednik ocenjevanj + avtomatska pravila (največ 3 na teden, ne smejo biti 3 dni zapored itd.). Vse skupaj pa teče na **starih računalnikih**, ki so bili prešvoh za Windows 11 — tako smo jih obudili v novo življenje. Win-win.

---

## 🧱 S čim je to narejeno? (tehnološki kupček, razložen po domače)

| Sloj | Tehnologija | Kaj to pomeni v prašičjem? |
|------|------------|---------------------------|
| **Backend** (možgani aplikacije) | Python 3.12, FastAPI, Uvicorn | **Python** je programski jezik, v katerem je aplikacija napisana — nekaj podobnega kot Lego kocke, iz katerih sestaviš hišo. **FastAPI** je ogrodje, ki poskrbi, da je aplikacija hitra in se z lahkoto pogovarja s spletnim brskalnikom. |
| **Podatkovna baza** (shramba vseh podatkov) | PostgreSQL | **Baza = digitalni arhiv.** Tukaj ležijo vse rezervacije, uporabniki, ocenjevanja, nastavitve. Če izklopiš elektriko, podatki niso izgubljeni — so varno zapisani na disku. Kot predal z mapami, samo da računalnik poišče stvar v 0.01 sekunde. |
| **Frontend** (kar vidiš v brskalniku) | Jinja2 template, HTML/CSS/JS | Ko odpreš stran v brskalniku — to kar vidiš (gumbi, tabele, barve) so HTML/CSS/JS. Jinja2 pa je pametni pomočnik, ki vstavi prave podatke v pravo obliko (tvoj email, tvoje rezervacije...). |
| **Avtentikacija** (prijava) | cookie-based session + bcrypt | Ko se prijaviš, ti da aplikacija piškotek (cookie) — kot vstopnica v zabaviščni park. Dokler imaš vstopnico, te sistem prepozna. Geslo pa je shranjeno v **bcrypt** obliki — to pomeni, da tudi če nekdo ukrade bazo, ne more prebrati tvojega gesla (zakodirano je v niz, ki ga ni mogoče obrniti nazaj). |
| **Email obveščanje** | SMTP prek Arnesa (mail.arnes.si) | Ko nekdo rezervira tvoj prostor ali ko vodstvo označi dan kot zaseden — sistem ti pošlje email. Pošiljanje gre prek Arnesovega strežnika (isto kot šolski email). |
| **Orkestracija** (pametno vodenje) | Kubernetes (k3s) | **To je najbolj fancy del.** K8s (kratko za Kubernetes) je kot **hišnik za aplikacijo** — če aplikacija "pade" (crash), K8s samodejno zažene novo kopijo. Če en računalnik v klastru crkne, drugi prevzame. Uporabnik nič ne opazi. K8s skrbi, da aplikacija TECŽI 24/7. |
| **Shranjevanje podatkov** (storage v ozadju) | Longhorn | Longhorn je kot **digitalni trezor z varnostno kopijo.** Vsak podatek (rezervacije, uporabniki) je shranjen v **dveh kopijah** na različnih računalnikih. Če en disk crkne — nobenega podatka ne izgubimo. Avtomatska restavracija. |
| **Omrežni uravnalnik** | MetalLB | Ko pride obiskovalec na spletno stran, MetalLB poskrbi, da ga aplikacija "pričaka na vratih" (dodeli IP naslov). Kot receptor v recepciji, ki vsako stranko usmeri k pravemu prostoru. |
| **Varnostna ograja pred spletom** | Cloudflare | Cloudflare je kot **varnostnik pred šolo** — vse kar pride iz spleta najprej gre skozi njega. Blokira napade (DDoS, brute force, hack poskuse). Hkrati skrbi za **ključavnico HTTPS** (tista zelena ključavnica v brskalniku). |

---

## ⚙️ Nastavitve aplikacije (.env)

To je datoteka, kjer so vse **skrivnosti in nastavitve na enem kupu** — gesla, naslovi, časovne omejitve, seznami. Kot tabla v kuhinji, kjer piše kdo kaj dela ta teden.

```bash
# App settings
APP_HOST=0.0.0.0
APP_PORT=port na katerem teče app

DATABASE_URL=postgresql url

# Email settings
MAIL_USERNAME=kratek ime maila
MAIL_PASSWORD=*** maila
MAIL_SERVER=mail.arnes.si
MAIL_PORT=587
MAIL_FROM=mail iz katerega aplikacija pošilja sporočila
BACKUP_EMAIL=mail ki dnevno dobi backup baze
STANJE_MAIL=mail ki dnevno dobi poročilo o stanju klastra

# App config
TABLICE_MAX=število vseh tablic
SCHEDULE={"številka ure":"časovni interval ure"}
RAZREDI=seznam razredov
PROSTORI=seznam prostorov

# Session timeout (teacher)
INACTIVITY_TIMEOUT_MINUTES=po koliko časa se učitelj izpiše ob nedejavnosti
# Session timeout (admin/vodstvo)
INACTIVITY_TIMEOUT_ADMIN_MINUTES=po koliko časa se vodstvo/admin izpiše
```

---

## 🎯 Kaj vse zna aplikacija?

### Rezervacije prostorov

Telefoni, hodniki, zvezki — pozabljeni. Tukaj je sistem:

- **Tablice** (28 kosov) — lahko si jih rezervira več učiteljev v isti uri (kot knjige v knjižnici, vsak vzame svojo).
- **Računalnica** — **samo eden** na termin. Kot frizer — samo ena stranka na stol.
- **Ladja** (pomivalni čoln) — ena rezervacija na termin.
- **Gospodinjska učilnica** — ena rezervacija na termin.

### Ocenjevanja

Napovedovanje pisnih ocenjevanj z **pametnimi pravili** (sistem sam pazi, da ne pretiravaš):

- Največ **3 ocenjevanja na teden** (da učenci niso preobremenjeni)
- Od tega največ **2 običajni** (neponavljalni) na teden
- **Prepoved 3 zaporednih dni** (ni šans, da imaš v sredo-četrtek-petek pisno)
- Za **1.–7. razred** sistem samodejno preveri, ali so pravila spoštovana

### Zasedeni datumi

Vodstvo označi dan kot zaseden (športni dan, ekskurzija, kulturni dan...). Sistem:
- **Samodejno izbriše** vsa ocenjevanja, ki so padla v ta dan
- **Vsem prizadetim učiteljem pošlje email** — "tvoj test v petek odpade, ker je športni dan"

### Admin panel

Upravljanje uporabnikov — dodajanje, urejanje, brisanje, deaktivacija. Preprosto.

---

## 👥 Kdo lahko kaj počne?

| Funkcija | Učitelj | Vodstvo | Admin |
|---------|:-------:|:-------:|:-----:|
| Rezervacija prostorov | ✅ | ✅ | ✅ |
| Brisanje lastne rezervacije | ✅ | ✅ | ✅ |
| Brisanje tuje rezervacije | ❌ | ✅ | ✅ |
| Napoved ocenjevanja | ✅ | ✅ | ✅ |
| Upravljanje zasedenih datumov | ❌ | ✅ | ✅ |
| Admin panel (uporabniki) | ❌ | ❌ | ✅ |

---

## 📋 Tehnični podatki na hitro

| Podatek | Vrednost |
|--------|---------|
| **Število strežnikov v klastru** | 2 (stara računalnika, predelana v Ubuntu Server) |
| **Disk** | 256 GB SSD vsak (dovolj za bazo in aplikacijo z rezervo) |
| **Podatkovna baza** | PostgreSQL — varna, zanesljiva, preverjena |
| **Varnost povezave** | HTTPS — zelena ključavnica v brskalniku (Cloudflare SSL/TLS) |
| **Avtomatske varnostne kopije** | Vsak dan backup baze na email vodstva |
| **Dnevno poročilo** | Vsak dan email o stanju klastra (diski, pomnilnik, delovanje) |
| **Pokritost ob izpadu** | Če en strežnik odpove, drugi drži aplikacijo pokonci (K8s + Longhorn replikacije) |

---

*Dokumentacijo vzdržuje avtor aplikacije. Za vprašanja, napake ali dodatne funkcionalnosti kontaktirajte administratorja.*
