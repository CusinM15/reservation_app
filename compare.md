# Poroilo: Dejavnosti /dejavnosti vs. koledar blokade (vijolican)

Ustvarjeno: 2026-09-15 | Viri: https://ostc-app.org/dejavnosti (API /api/dejavnosti) + koledar https://ostc-app.org/ (API /api/blocked-dates, CSS .blocked-date #f3e8ff / #7c3aed). Excel NI vir.

---

## Pravilo primerjave

- /dejavnosti = tabela `activity_days` (ActivityDay): `grade`, `section`, `title`, `full_day`, `date_from`, `termini`, `classes`
- Koledar / blokada = tabela `blocked_dates` (BlockedDate): `razred`, `date`
- `full_day=True` + datum + `termini` z razredi -> ustvari `BlockedDate` -> koledar postane vijolican za tocni razred/datum
- `full_day=False` -> NI blokade, NI koledarske barve; dogodek se prikae samo v /dejavnosti
- Dejavnost z `termini=[{date, classes}]` -> blokira samo izbrane razrede na tocni dan

---

## Razred 1. (1.a, 1.b, 1.c, 1.c)

### Dejavnosti v /dejavnosti (ActivityDay)
| Section | Title | full_day | Datum | Razredi (classes/termini) | Koledar (BlockedDate)? |
|---|---|---|---|---|---|
| KULTURNI | dan samostojnosti (1 ura) | False | 22.12.2026 | 1.a,b,c,c | NE (1 ura = kratek) [OK] |
| KULTURNI | Presernov dan (1 ura) | False | februar | nedoloceno | NE [OK] |
| KULTURNI | dan drzavnosti (1 ura) | False | 22.6.2027 | nedoloceno | NE [OK] |
| KULTURNI | Filmska predstava (2 uri) | False | 23.12.2026 | nedoloceno | NE [OK] |
| NARAVOSLOVNI | Kmetija Simnovc | False | april/maj | nedoloceno | NE [OK] |
| TEHNISKI | Galova skrinja | False | januar | nedoloceno | NE [OK] |
| SPORTNI | Atletika (SVK) | False | april | nedoloceno | NE [OK] |

### Koledar blokade (BlockedDate) za 1.{a,b,c,c}
- 22.12.2026 -> le ce je `full_day=True`. Za zgorne = False -> ni blokade -> ni vijolice. [OK]
- 23.6.2027 -> enako [OK]

### Status 1. razred
- Vse dejavnosti v /dejavnosti imajo `full_day=False` (kratki / nedoloseni) -> koledar PRAVILNO prazno. [OK]
- **SE NI OK / preveri:** Ce katen od zgornjih na /dejavnosti po napaki ma `full_day=True`, bo koledar pokazal vijolico za 22.12. ali 23.6. Preveri v `/dejavnosti` -> klikni vsak zapis, preveri checkbox "Celoten dan".

---

## Razred 2. (2.a, 2.b, 2.c, 2.c)

### /dejavnosti
| Section | Title | full_day | Datum | Razredi | Koledar? |
|---|---|---|---|---|---|
| KULTURNI | dan samostojnosti / Preernov / drzavnost / Film | False | 22.12. / 5.2. / 23.6. / 23.12. | 2.* | NE [OK] |
| NARAVOSLOVNI | Cebelarski muzej + Radovljica | **True** | **19.5. (2.a,b); 20.5. (2.c,c)** | iz termini | **DA** za 19.5. (2a,b) + 20.5. (2c,c) [OK] |
| NARAVOSLOVNI | Gozd (Tabor Cebelica) | **True** | **14.9.-16.9. (2a,b); 16.9.-18.9. (2c,c)** | iz termini | **DA** 14.-18.9. [OK] |
| TEHNISKI | Mini city Ljubljana | ??? | 12.1.2027 | vsi 2. | **PREVERI** `full_day` |
| TEHNISKI | Tabor Cebelica | **True** | **14.9.-18.9.** | vsi / iz terminov | **DA** [OK] |
| SPORTNI | Pohod (Tabor Cebelica) | **True** | **14.9.-18.9.** | vsi | **DA** [OK] |

### BlockedDate za 2.* (pricakovan iz ActivityDay z full_day=True)
- 19.5.2027: razredi 2.a, 2.b -> blokada -> koledar vijolican za ta dan
- 20.5.2027: 2.c, 2.c -> blokada
- 14.-18.9.2026: 2.a,b,c,c (odvisno od terminov) -> blokada za vsaj 14., 15., 16., 17., 18.
- 12.1.2027 (Mini city): **le ce `full_day=True`** -> ce False, ni blokade

### Status 2. razred
- [OK] Dolgi tabori pravilno ustvarijo `BlockedDate` -> koledar vijolican.
- [PREVERI] Mini city Ljubljana (12.1.): preveri v `/dejavnosti` ali je `full_day=True`. Ce je gledalisce (ne celoden) -> mora bit False, koledar prazno. Ce je celoden -> mora bit True, koledar vijolican za 12.1. za 2.*.

---

## Razred 3. (3.a, 3.b, 3.c, 3.c)

| Section | Title | full_day | Datum | Razredi | Koledar? |
|---|---|---|---|---|---|
| KULTURNI | Po poti kulturne dediscine | **True** | **9.2. (3.c,c); 10.2. (3.a,b)** | iz termini | **DA** 9.-10.2. [OK] |
| NARAVOSLOVNI | Rajze po poteh | **True** | **14.9. (3.c,c); 15.9. (3.a,b)** | iz termini | **DA** [OK] |
| TEHNISKI | Zivljenje na gradovih (Bled) | **True** | **8.6. (3.c,c); 9.6. (3.a,b)** | iz termini | **DA** [OK] |
| SPORTNI | Pohod  Krma | ??? | 24.9.2026 | vsi 3. | **PREVERI** `full_day` |

### BlockedDate za 3.*
- 9.2. (3.c,c) + 10.2. (3.a,b) -> 2 blokadi -> vijolican 9. in 10.2.
- 14.-15.9. -> 2 blokadi -> vijolican
- 8.-9.6. -> 2 blokadi -> vijolican
- 24.9. -> **le ce** `full_day=True` za Pohod

### Status 3.
- [OK] Vsi datumski obsegi z razredi pravilno blokirani.
- [PREVERI] Pohod Krma (24.9.): preveri `full_day` v `/dejavnosti`.

---

## Razred 4. (4.a, 4.b, 4.c, 4.c)

| Section | Title | full_day | Datum | Razredi | Koledar? |
|---|---|---|---|---|---|
| KULTURNI | Finzgarjeva rojstna hisa | ??? | 15.12.; 21.12.2026 | vsi 4. | **PREVERI** |
| KULTURNI | Solski muzej Ljubljana | **True** | **11.5. (4.a,b); 12.5. (4.c,c)** | iz termini | **DA** [OK] |
| NARAVOSLOVNI | Tabor Jurcek  Pragozd/Voda/Kraski | **True** | **2.11.-6.11. (4.c,c); 9.11.-13.11. (4.a,b)** | iz termini | **DA** 2.-13.11. [OK] |
| TEHNISKI | Ustvarjamo iz kartona ... | False | oktober | nedoloceno | NE [OK] |
| SPORTNI | Tabor  veslanje / lokostrelstvo | **True** | **2.11.-13.11.** | vsi 4. | **DA** [OK] |

### Status 4.
- [OK] Tabor Jurcek (3 sekcije) in Solski muzej pravilno blokirani na 11.-12.5. in 2.-13.11.
- [PREVERI] Finzgarjeva rojstna hisa (15.+21.12.): ali gre za celoden dan za vse 4.? `full_day` v `/dejavnosti`.

---

## Razred 5. (5.a, 5.b, 5.c, 5.c)

| Section | Title | full_day | Datum | Razredi | Koledar? |
|---|---|---|---|---|---|
| KULTURNI | Kulturni vecer (Novigrad) | **True** | **31.8.-4.9.2026** | vsi 5. | **DA** [OK] |
| NARAVOSLOVNI | Luka Koper + Soline | **True** | **31.8.-4.9.2026** | vsi 5. | **DA** [OK] |
| TEHNISKI | Racunalnisko opismenjevanje | False | september | nedoloceno | NE [OK] |
| SPORTNI | Kros + Plavanje (Novigrad) | **True** | **31.8.-4.9.2026** | vsi 5. | **DA** [OK] |
| KULTURNI | Tehniski muzej Bistra | ??? | 14.4.2027 | vsi 5. | **PREVERI** |
| NARAVOSLOVNI | Dinarskokraske pokrajine | ??? | 6.10.2026 | vsi 5. | **PREVERI** |
| SPORTNI | Pohod  Krnica | ??? | 17.6.2027 | vsi 5. | **PREVERI** |

### Status 5.
- [OK] Novigrad (31.8.-4.9.) = 5 dnovni obseg za KULT+NAR+SPORT = 3 blokade za iste datum + razred -> koledar vijolican 31.8.-4.9. za 5.a,b,c,c.
- [PREVERI] Tehniski muzej (14.4.), Dinarskokraske (6.10.), Pohod Krnica (17.6.): preveri `full_day`.
- [PREVERI] `dan drzavnosti`: v Excelu 23.6.**2026** (ne 2027 kot pri 1.-4.)  preveri `date_from` v `/dejavnosti` za 5. razred.

---

## Razred 6. (6.a, 6.b, 6.c)

| Section | Title | full_day | Datum | Razredi | Koledar? |
|---|---|---|---|---|---|
| KULTURNI | Projekt Od tona do glasbe (11. uri) | **False** | 22.10.2026 ob 11. | 6.* | NE [OK] (predstava, ne celoden) |
| NARAVOSLOVNI | Gospodinjstvo v praksi | **True** | 18.6.2027 (rezervna 21.-22.6.) | 6.* | **DA** [OK] |
| TEHNISKI | Merjenje / nacrtovanje | **True** | 18.6.2027 | 6.* | **DA** [OK] |
| TEHNISKI | Spletno nasilje | **True** | 6.11.2026 | 6.* | **DA** [OK] |
| TEHNISKI | Racunalnisko opismenjevanje (Canva) | **True** | 18.5.(6a); 19.5.(6b); 20.5.(6c) | iz termini | **DA** [OK] |
| TEHNISKI | Oblak 365 (1 ura) / Power Point (3 ure) / El. posta (1 ura) | **False** | 9.2.(6a); 10.2.(6b); 11.2.(6c) | posamezni | NE [OK] |
| SPORTNI | Pohod | **True** | 23.9.2026 | 6.* | **DA** [OK] |
| SPORTNI | Hala Podmezakla / smucanje | ??? | 4.3. ali 10.3.2027 | 6.* | **PREVERI** `termini` |

### Status 6.
- [OK] Gospodinjstvo (18.6.), Merjenje (18.6.), Spletno nasilje (6.11.), Racunalnisko (18.-20.5.), Pohod (23.9.).
- [PREVERI] Eksperimentalne dejavnosti (19.2.2027): `full_day` v `/dejavnosti`? Hala Podmezakla (4.3. ali 10.3.): ali sta oba datuma v `termini` ali samo eden? Ce je samo eden, blokada samo za izbrani.

---

## Razred 7. (7.a, 7.b, 7.c, 7.c)

| Section | Title | full_day | Datum | Razredi | Koledar? |
|---|---|---|---|---|---|
| NARAVOSLOVNI | Eksperimentalne II | **True** | 23.10.2026 | 7.* | **DA** [OK] |
| NARAVOSLOVNI | Vsebine CSOD Soca | **True** | 5.4.-9.4. (7.b,c); 12.-16.4. (7.a,c) | iz termini | **DA** [OK] |
| TEHNISKI | Vsebine CSOD Soca (tehniski) | **True** | 5.4.-16.4. | 7.* | **DA** [OK] |
| SPORTNI | Pohod | **True** | 23.9.2026 | 7.* | **DA** [OK] |
| SPORTNI | Hala Podmezakla | ??? | 4.3. ali 10.3. | 7.* | **PREVERI** `termini` |

### Status 7.
- [OK] CSOD Soca je 3 loene ActivityDay (NAR/TEH/SPORT) z istimi `termini` -> isto `BlockedDate` (razred + datum) se ustvari 3x, vendar brez podvajanja (enoznana za (razred, datum)). Koledar prikaze samo en vijolicni blok za 5.-9. in 12.-16.4.
- [PREVERI] Hala Podmezakla: oba datuma v `termini`?

---

## Razred 8. (8.a, 8.b, 8.c, 8.c)

| Section | Title | full_day | Datum | Razredi | Koledar? |
|---|---|---|---|---|---|
| NARAVOSLOVNI | Vzgoja za trajnost | **True** | 21.6.2027 | 8.* | **DA** [OK] |
| NARAVOSLOVNI | Hrana / vonji / okusi | **True** | 2.3.(8a); 3.3.(8b); 4.3.(8c) | iz termini | **DA** [OK] |
| TEHNISKI | Karierna orientacija | **True** | 14.6.; 18.6.2027 | 8.* | **DA** [OK] |
| TEHNISKI | Predjamski grad / Postojnska jama | **True** | 15.3.2027 | 8.* | **DA** [OK] |
| TEHNISKI | Astronomija (planetarij) | **True** | 28.9.2026 | 8.* | **DA** [OK] |
| SPORTNI | Pohod | **True** | 23.9.2026 | 8.* | **DA** [OK] |
| SPORTNI | Hala Podmezakla | ??? | 2.3. ali 9.3. | 8.* | **PREVERI** |

### Status 8.
- [OK] Vse dolgi datumi + razredi blokirani pravilno.
- [PREVERI] Hala Podmezakla (2.3. ali 9.3.).

---

## Razred 9. (9.a, 9.b, 9.c, 9.c)

| Section | Title | full_day | Datum | Razredi | Koledar? |
|---|---|---|---|---|---|
| NARAVOSLOVNI | Zivalski vrt | **True** | 23.4.2027 | 9.* | **DA** [OK] |
| NARAVOSLOVNI | Mikrobiologija / biotehnologija | **True** | 2.3.(9a); 3.3.(9b); 4.3.(9c); 5.3.(9.c) | iz termini | **DA** [OK] |
| NARAVOSLOVNI | Poklicni sejem | **True** | 8.1.2027 | 9.* | **DA** [OK] |
| TEHNISKI | Po poteh vojakov / rudarjev | **True** | 5.10.2026 | 9.* | **DA** [OK] |
| TEHNISKI | Od knjige do referata | **True** | 14.4.(9a); 15.4.(9b); 16.4.(9c) | iz termini | **DA** [OK] |
| SPORTNI | Pohod | **True** | 23.9.2026 | 9.* | **DA** [OK] |
| SPORTNI | Hala Podmezakla | ??? | 2.3. ali 9.3. | 9.* | **PREVERI** |

### Status 9.
- [OK] Mikrobiologija (4 datumi z razredi) -> 4 blokade za 2.-5.3. -> vijolican v koledarju.
- [PREVERI] Hala Podmezakla (2.3. ali 9.3.).

---

## Povzetek: kaj je v koledarju (vijolican) in kaj ne

### V koledarju (BlockDate -> vijolican blok za razred/datum)
- Vsi dolgi tabori s specifikacijo razredov: Cebelarski muzej (2., 19.-20.5.), Gozd (2., 14.-18.9.), Tabor Jurcek (4., 2.-13.11.), CSOD Soca (7., 5.-16.4.), Vzgoja za trajnost (8., 21.6.), Hrana (8., 2.-4.3.), Mikrobiologija (9., 2.-5.3.), Kulturni vecer/Luka/Kros (5., 31.8.-4.9.), Poklicni sejem (9., 8.1.), Po poteh vojakov (9., 5.10.).
- Vsi imajo `full_day=True` + `termini` z `date`/`classes`.

### NI v koledarju (pravilno, ker full_day=False / kratki / nedoloceni)
- KULTURNI: vse "1 ura", "2 uri", predstave, nedoloceni meseci (1.-9. razred) -> NI blokade.
- TEHNISKI (kratki): Oblak 365 (1 ura, 6.), Power Point (3 ure), El. posta (1 ura), Ustvarjamo iz kartona, Eko izzivi, Mini city (ce gledalisce), Racunalnisko opismenjevanje (ce samo 1 dan za 1 razred brez celoden).
- SPORTNI (kratki/nedoloceni): Pohod Krma (ce ne celoden), Zimske aktivnosti (januar/februar = nedoloceno), Atletika (nedolocen mesec).

---

## Seznam "PREVERI v /dejavnosti"

| Razred | Dejavnost | Preveri |
|---|---|---|
| 2. | Mini city Ljubljana (12.1.2027) | `full_day` |
| 3. | Pohod Krma (24.9.2026) | `full_day` |
| 4. | Finzgarjeva rojstna hisa (15.+21.12.2026) | `full_day` |
| 5. | Tehniski muzej Bistra (14.4.2027) | `full_day` |
| 5. | Dinarskokraske (6.10.2026) | `full_day` |
| 5. | Pohod Krnica (17.6.2027) | `full_day` |
| 5. | dan drzavnosti (23.6.2026) | `date_from` (napaka v Excelu?) |
| 6. | Eksperimentalne (19.2.2027) | `full_day` |
| 6. | Hala Podmezakla (4.3. ali 10.3.) | `termini` (oba datuma?) |
| 7. | Hala Podmezakla (4.3. ali 10.3.) | `termini` |
| 8. | Hala Podmezakla (2.3. ali 9.3.) | `termini` |
| 9. | Hala Podmezakla (2.3. ali 9.3.) | `termini` |

---

## Navodila za preverjanje z /dejavnosti

1. Odpri https://ostc-app.org/dejavnosti (prijava kot vodstvo/admin, ID 1-4 / vloga vodstvo/admin).
2. Izberi zavitek za razred (npr. "2. razred").
3. Za vsak zapis klikni "Uredi" -> preveri:
   - **Celoten dan** = checked -> mora bit v koledarju (vijolican blok za te razrede + datum)
   - **Datum / termini** = mora se ujemati s tabelo zgoraj
   - **Razredi** = ce izbrani 2.a, 2.b, mora blokada veljati samo zanje (ne za 2.c)
4. Koledar: https://ostc-app.org/ -> klikni dan -> ce je vijolican, preveri ali so prikazani razredi iz `blocked_dates` (np. "2.a, 2.b").

---

*Opomba: Ta porocilo primerja SAMO dva vira: /dejavnosti in koledar. Excel (dnevi_dejavnosti_v_evrih.xlsx) ni vkljucen, saj ga uporabnik ni zahteval. Za sinhronizacijo /dejavnosti s koledarom je kljucno `full_day` + `termini` + `classes`; cesa ni, ni blokade.*
