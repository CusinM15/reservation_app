🌐 **Jezik / Language:** [🇸🇮 Slovenščina](navodila-vodstvo.md) | [🇬🇧 English](en/navodila-vodstvo.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 👑 Navodila za vodstvo in administratorja

> Ta dokument pokriva upravljanje aplikacije prek brskalnika — namenjeno vodstvu (dodatne funkcije) in adminu.

---

## Rezervacije

Vodstvo ima dodatne možnosti za ustvarjanje rezervacij.

### Tedenska serija

Omogoča rezervacijo istega termina za več dni zapored.

| Polje | Opis |
|---|---|
| Prostor | Prostor, ki ga želite rezervirati |
| Ura | Vrednost 0–7 (0 = predura) |
| Dan v tednu | Vrednost 0–6 (0 = ponedeljek) |
| Od datuma | Datum začetka serije |
| Do datuma | Datum konca serije |
| Število tablic | Samo pri tablicah |

### Celodnevna serija

Omogoča rezervacijo celotnega dneva (vse ure) za več dni.

| Polje | Opis |
|---|---|
| Prostor | Prostor, ki ga želite rezervirati |
| Od datuma | Datum začetka serije |
| Do datuma | Datum konca serije |
| Število tablic | Samo pri tablicah |
| Ura | Če prazno, vse ure 0–7. Lahko naštejete: `1 3 5` |

### Brisanje

Vodstvo lahko briše tudi **tuje** rezervacije (učitelji samo svoje).

---

## Ocenjevanje

### Zasedeni datumi

Vodstvo lahko označi dneve kot "zasedene" (športni dan, ekskurzija...).

| Polje | Opis |
|---|---|
| Razred | Izberite enega ali več (držite Ctrl za več) |
| Od datuma | Datum začetka |
| Do datuma | Datum konca |

Ko dodate zasedene datume:
1. Sistem samodejno izbriše vsa obstoječa ocenjevanja za ta razred v tem obdobju
2. Pošlje email obvestila prizadetim učiteljem

### Obvestila po e-pošti

Ko vodstvo prekliče rezervacijo ali ocenjevanje, aplikacija samodejno pošlje email obvestilo učitelju.

---

## Skrbniška plošča (samo admin)

> Dostopna samo administratorju — vodstvo do nje nima dostopa.

### Ročni vnos uporabnikov

Priporočljivo **samo med letom**, ko nastopi nov učitelj.

Na začetku šolskega leta priporočam:
1. Izbriši vse uporabnike
2. Uvozi jih na novo s skripto

### Uvoz učiteljev s skripto

Skripta prebere seznam zaposlenih s šolske spletne strani.

```bash
cd /home/admin/ostc-app_deli
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Dry-run (brez sprememb):
python3 scripts/import_teachers.py --dry-run

# Z administracijo/tehničnim osebjem:
python3 scripts/import_teachers.py --base-url https://ostc-app.org --include-all
```

### Upravljanje uporabnikov

**Dostop:** V zgornji navigaciji kliknite **Admin panel**.

Funkcije:
- **Dodajanje** — vnesete email, ime, priimek, geslo, vlogo
- **Pregled** — tabela z vsemi uporabniki (razvrščanje s klikom na stolpec)
- **Urejanje** — kliknite "Uredi", spremenite podatke. Če geslo pustite prazno, ostane nespremenjeno
- **Deaktivacija / Aktivacija** — onemogočite dostop uporabniku
- **Brisanje** — trajno izbriše uporabnika (admin z ID=1 ni mogoče izbrisati)
- **Spremeni geslo** — admin lahko spremeni geslo uporabniku

### Priporočila

- Vloga **Admin** naj bo dodeljena izključno administratorju
- Vloga **Vodstvo** za ravnatelja, pomočnike in svetovalne delavce
- Vloga **Učitelj** za vse pedagoške delavce
