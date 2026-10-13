# 🧠 Brainstorm zapis 2 — Vrstni red, urejevalnik tablic (LAN/offline), cene in zaslužek

> Zapis pogovora (2026-10-13). **Brainstorm — ni odločitev, ni sprememb kode.**
> Dopolnjuje `brainstorm-2026-10-13.md`, `v_oblak.md`, `intune_konkurenca.md` (teh ne spreminja).

---

## 1. Vrstni red (priporočeno zaporedje)

1. **Plačaj Hetzner sam (kot s.p.) in preveri DDV** — ker si zavezanec, odbijaš
   vstopni DDV, zato so spodnje cene **brez DDV** relevantne.
2. **Začni z 1 nodom** (CPX22) — ni HA, a pokrije vse šole do točke, ko app
   postane kritičen. Vzemi lokacijo NGB1 (Nemčija).
3. **Preseli app** (isti koraki kot `v_oblak.md`, §2: k3s → CCM/CSI → CNPG →
   `pg_dump`/`pg_restore` → DNS preklop).
4. **Dokler je < ~5 šol:** 1 node zadostuje. Ko app postane kritičen (vsakodnevna
   uporaba med šolskim letom) → **nadgradi na 3 node** (prava HA).
5. **Urejevalnik tablic** kot dokup — začni z **Fazo 0** (inventar) in šele ko je
   dokup plačan, dodaj Faze 1–5.

**Kdaj 1 → 3 node:** prag 3-node breakeven je **~7 šol** (brez dokupa za tablice)
oz. **~5 šol** (z dokupom 50 €). Pred tem je 1 node finančno pametnejši.

---

## 2. Urejevalnik tablic — kakšen je želeni model?

**Želje (iz pogovora):**
- deluje **samo, če je zagnan iz istega omrežja** (lokalno / LAN),
- enostavno **nadziranje, kaj je naloženo** (inventar aplikacij),
- možnost **nastaviti edine dovoljene appe** in to **izvesti brez povezave**
  (brez interneta, samo v šolskem LAN),
- možnost **spreminjanja nastavitev aplikacij**,
- dokup: **+50 €/šola/leto**.

**Kaj to pomeni tehnično (bistveno — spremeni arhitekturo):**

- **»Samo iz istega omrežja« + »izvede brez povezave« NI standardni Android
  Enterprise / AMAPI.** Google AMAPI (iz `intune_konkurenca.md` §3.1) zahteva
  **internet** in **Googlove storitve** — torej **ne** deluje zares offline in
  **ne** je omejen na lokalni LAN.
- Opisana funkcija je bližje **lastnemu agentu/DPC na napravi (device owner alias
  DevicePolicyManager)** + **lokalnemu strežniku v šolskem omrežju**:
  - agent na tablici uveljavi politiko **lokalno** (dovoljeni app-i, blokada
    namestitve drugih, nastavitve) — to deluje brez interneta;
  - nadzorna konzola teče v šolskem LAN (npr. prenosnik/strežnik v šoli) in
    komunicira z agenti po lokalnem omrežju.
- **Posledice:** to je **ločen razvoj** (svoj agent, podpisovanje, namestitev
  izven trgovine, posodobitve agenta), a **prednost**: brez Google/Apple
  odvisnosti, brez oblaka, zasebnost ostane v šoli. V skladu s `intune_konkurenca.md`
  §3.1 (»lasten DPC je bistveno težji«).
- **Omejitev, ki jo moraš ponudniku jasno povedati:** če je vezano na LAN in
  offline, **ni** oddaljenega upravljanja iz pisarne — tablice se urejajo **na
  licu mesta** (v šolskem omrežju).
- **Kaj (še) določiti:** kdo gostuje lokalni strežnik (šolski PC? majhen NUC?),
  kako se agenti posodabljajo brez interneta (USB / lokalna različica), in ali
  »dovoljeni app-i« pomeni sistemsko blokado namestitve ali le opozorilo.

> ⚠️ Ker gre za offline/LAN funkcijo, **odpade** večina prednosti AMAPI; to je
> bolj »mali self-hosted MDM«. To je legitimen in zasebnosti prijazen izbor, a
> zahteva resen razvoj agenta.

---

## 3. Stroški infrastrukture (Hetzner, EUR **brez DDV**, 2026)

Osnova (iz `v_oblak.md`, §3): CPX22 = €233.88/leto, LB11 = €89.88/leto,
IPv4 = €6/leto, backup = +20 % cene strežnikov.

| Postavitev | Sestava | **Leto (brez DDV)** |
|---|---|---|
| **1 node (ni HA)** | CPX22 + IPv4 + backup | **~€287** |
| **3 node (HA)** | 3× CPX22 + LB11 + 3× IPv4 + backup | **~€950** |
| 1 node + Storage Box + domena | + Storage Box + domena | ~€345 |
| 3 node + Storage Box + domena | + Storage Box + domena | ~€1.008 |

> Fiksni strošek je **skupen za vse šole** — ena šola porabi ~0,2 GB RAM in
> <1 GB diska (`v_oblak.md`), zato strošek **ne raste** linearno s šolami.

---

## 4. Zaslužek / izguba v odvisnosti od števila šol

**Cene:** app = **150 €/šola/leto**; tablice (dokup) = **+50 €/šola/leto** →
skupaj 200 €/šola/leto, če vzamejo oboje.
**Enak šolski set:** vsaka šola vzame ali samo app (150) ali app+tablice (200).

### 4a. 1 node (fiksni strošek ~€287/leto)

| Šol | app 150 € | app+tablice 200 € |
|---:|---:|---:|
| 1 | **−137** | −87 |
| 2 | **+13** | +113 |
| 3 | +163 | +313 |
| 4 | +313 | +513 |
| 5 | +463 | +713 |
| 6 | +613 | +913 |
| 7 | +763 | +1.113 |
| 8 | +913 | +1.313 |
| 9 | +1.063 | +1.513 |
| 10 | +1.213 | +1.713 |
| 12 | +1.513 | +2.113 |
| 15 | +1.963 | +2.713 |
| 20 | +2.713 | +3.713 |

**Breakeven 1 node:** ~**2 šoli** (app 150 € → 1,91; app+tablice → 1,43).

### 4b. 3 node HA (fiksni strošek ~€950/leto)

| Šol | app 150 € | app+tablice 200 € |
|---:|---:|---:|
| 1 | **−800** | −750 |
| 2 | **−650** | −550 |
| 3 | **−500** | −350 |
| 4 | **−350** | −150 |
| 5 | **−200** | **+50** |
| 6 | **−50** | +250 |
| 7 | **+100** | +450 |
| 8 | +250 | +650 |
| 9 | +400 | +850 |
| 10 | +550 | +1.050 |
| 12 | +850 | +1.450 |
| 15 | +1.300 | +2.050 |
| 20 | +2.050 | +3.050 |

**Breakeven 3 node:** ~**7 šol** (app 150 €) oz. ~**5 šol** (app+tablice 200 €).

### 4c. Povzetek pragov dobička

| Postavitev | Samo app (150 €) | App + tablice (200 €) |
|---|---|---|
| **1 node** | ~2 šoli | ~2 šoli |
| **3 node HA** | ~7 šol | ~5 šol |

**Kdaj se 3 node izplača pred 1 node?** Ko imaš ≥ 7 šol (samo app) ali ≥ 5 šol
(z dokupom tablic) — takrat lahko varno preideš na HA, ne da bi šel v minus.

---

## 5. Opozorila (nujno)

- **Zaslužek ≠ čisti dobiček.** Zgornje številke pokrivajo **samo infrastrukturo**.
  **Ne vključujejo**: razvoja (enkratno, veliko), podpore/vzdrževanja (trajno,
  največji realni strošek), davkov/DDV (tu upoštevano kot brez DDV) in **tvojega
  dela**.
- **Razvoj urejevalnika tablic je velik** (lasten DPC agent + lokalna konzola +
  varnost). Pri 20 šolah × 50 € = 1.000 €/leto **se razvoj težko povrne hitro** —
  dokup je smiseln predvsem kot **vzvod za zadržanje strank**, ne kot glavni
  vir dohodka na kratki rok.
- **Odprto ostaja** (iz `intune_konkurenca.md` §7): enota cene 150 €/leto (šola?
  organizacija?) in ali imajo šole nadzor nad napravami (za agenta/managed mode).

---

## Ena vrstica (TL;DR)

**1 node do ~5 šol (breakeven ~2 šoli), nato 3 node HA (breakeven ~5–7 šol).
Urejevalnik tablic kot dokup +50 €, a je LAN/offline → to je mali self-hosted MDM
(lasten agent), kar je velik razvoj; številke pokrivajo samo infrastrukturo, ne
razvoja in podpore.**
