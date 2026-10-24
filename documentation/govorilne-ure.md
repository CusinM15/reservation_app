# Prijave staršev na govorilne ure — /govorilne (stanje 23. 10. 2026)

## Kaj je bilo narejeno (commit a8b1896, veja `govorilne`)
- **Javna stran `/govorilne`** (brez prijave): starš izbere učitelja iz spustnega
  seznama, nato 15-minutni termin; obrazec zahteva ime starša, e-naslov in ime
  otroka + potrditveno polje (soglasje s pogoji). Po oddaji se prijava shrani.
- **`/govorilne/api/termini?ucitelj=…`** — JSON seznam PROSTIH terminov
  (zasedeni se izpustijo; dvojna prijava istega termina → 409).
- **`/govorilne/api/prijava`** — POST, shrani v tabelo `govorilne_prijave`
  (model `GovorilnaPrijava` v `app/models.py`).
- **`/govorilne/prijave`** — pregled (ZA PRIJAVLJENE): učitelj vidi samo svoje
  prijave (ujemanje po polnem imenu), vodstvo/šolski admin/glavni admin vse.
- **Pogoji uporabe → v1.3** (`documentation/pogoji-uporabe.md`): novo pogl. 4.4
  (prijave staršev kot izjema od prepovedi otrokovih podatkov), izjema v pogl. 5
  (samodejni izbris po 14 dneh), pogl. 8 + 10. Pogoji so dosegljivi tudi na
  `/docs/pogoji-uporabe` (dodano v docs whitelist).

## Vir podatkov o učiteljih in terminih
- **`app/govorilne_podatki.py`** (generirano iz HTML tabele; vir:
  https://ostcjesenice.splet.arnes.si/za-starse/govorilne-ure/ — posnetek
  23. 10. 2026). Vsebuje `UCITELJI` (ime, predmet, dan 0–4, šolska ura,
  prostor, po_dogovoru), `POPOLDAN_DATUMI` (uradni četrtki 17:30–18:30),
  `URA_ZACETKI` (začetek šolskih ur) in `GOVORILNE_DOPOLDAN_TEDEN`.
- **Dopoldanski termini SO TESTNI**: vsak učitelj z določenim dnem dobi
  termin v testnem tednu (26.–30. 10. 2026); 45-min šolska ura → 3×15 min.
  Uporabnik je prosil, naj si datum izmislimo za testiranje.
- **Popoldanski termini so uradni**: četrtki 17:30–18:30 → 4×15 min za VSE
  učitelje (tudi »po dogovoru«).
- Učitelja **Matej Čušin** smo dodali na konec seznama (testni učitelj).

## Kako spremeniti podatke (ko pridejo pravi datumi)
- Dopoldanski datum: spremeni `GOVORILNE_DOPOLDAN_TEDEN` v
  `app/govorilne_podatki.py` (ISO, ponedeljek testnega tedna).
- Ure: `URA_ZACETKI` (številka šolske ure → začetek).
- Popoldanski datumi: `POPOLDAN_DATUMI` (ISO seznam).
- Če se spletna stran spremeni: ponovno generiraj iz HTML (vzorec:
  tests/test_govorilne.py opisuje vir; generiranje je bilo narejeno s skripto
  v /tmp, ni shranjena v repo).

## GDPR / zakonitost
- Prijava ne kreira računa; ime otroka je NAVADEN osebni podatek (ne občutljiv).
- Pravna podlaga: organizacija govorilnih ur (šolska naloga) + soglasje starša.
- Hramba: `_pocisti_stare(db, rok)` briše prijave starejše od 14 dni po dnevu
  govorilnih ur (zažene se ob vsakem ogledu `/govorilne/prijave`).
- Ni potrebe po prijavi zbirke pri Informacijskem pooblaščencu (GDPR/ZVOP-2).

## Javna per-šola pot `/govorilne_<slug>` (commit 4c57e44)
- Vsaka šola dobi javni vhod `https://reservationapp.site/govorilne_<slug>`
  (npr. `/govorilne_ostcj`), ki se prevede v `/govorilne` TE šole — starši se ne
  prijavijo. Pot JE v seznamu javnih (AuthMiddleware); `/govorilne/prijave` ostane
  za prijavljene. Aliase generira `generate_aliases()` (backfill ob zagonu).
- Učitelj/dan termini se berejo iz URL-aliasa (`request_school_id`), ne samo
  privzete šole.

## Nova stran v appu: `/govorilne/ure` (»Moje govorilne ure«, 24. 10. 2026)
- V appu (po prijavi, povezava v glavni navigaciji) učitelj vidi SVOJ objavljeni
  urnik govorilnih ur: dopoldanski termin (dan/šolska ura/začetek/prostor + datum)
  in popoldanske četrtke 17:30–18:30, skupaj s **rezervacijami staršev** za svoje
  termine.
- Učitelj: samo svoj termin (ujemanje po polnem imenu iz `UCITELJI`).
  Vodstvo, šolski admin, glavni admin: pregled urnikov VSEH učiteljev.
- Neprijavljen → preusmeritev na `/auth/login` (ni javna stran).

## Deploy
- Zgrajeno na k3s nodu (podman `mato12345/sola-app:latest`), rollout
  `deployment/sola-app`; verifikacija:
  `curl https://reservationapp.site/govorilne` → 200 s seznamom učiteljev,
  `curl https://reservationapp.site/govorilne_ostcj` → 200 (javna).
- Tabela `govorilne_prijave` se ustvari sama ob zagonu (`create_all`).

## Testi
- `tests/test_govorilne.py` (13 testov): javnost strani in API-ja, 15-min
  termini, dvojna prijava → 409, neveljaven termin → 400, manjkajoči podatki → 400,
  pregled po vlogah (neprijavljen → login; učitelj samo svoje; admin vse), per-šola
  javni alias `/govorilne_<slug>` in nova stran `/govorilne/ure` (login obvezno,
  učitelj samo svoj urnik, admin vse, učitelj vidi svoje rezervacije).
- Kanonični set (tenancy + ui/aliases + routes + zasloni + govorilne): 88 zelenih.
