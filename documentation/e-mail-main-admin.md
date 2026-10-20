# E-pošta (main admin) — nastavitev in povzetek seje

Datum: 2026-10-20 11:56 CEST

## Povzetek seje

Glavni admin želi, da aplikacija pošilja s svojega e-poštnega naslova
**reservation.app@proton.me** in da nastavitve ureja sam na strani
**Globalne nastavitve** (izključno main admin), kamor sodi tudi backup
varnostne kopije CELOTNE baze (vse šole).

### Kaj je bilo narejeno (v produkciji od 2026-10-20, commit 51f3c9b)

1. **Stran /global-settings** (samo glavni admin):
   - E-pošta (main admin SMTP): strežnik, vrata, uporabniško ime, geslo/SMTP token, pošiljatelj — shranjeno v tabeli `app_settings` (ključi `GLOBAL_MAIL_*`), fallback na vrednosti iz env/secretov.
   - BACKUP_EMAIL: prejemnik .sql celotne baze.
   - Gumb **📧 Pošlji backup cele baze**: `pg_dump` celotne baze (vse šole) → priloga `.sql` → pošlje z glavnega e-poštnega računa.
   - Gumb **🩺 Pošlji zdravje / stanje clustra**: snapshot (baza CNPG, število šol/uporabnikov, podi namespace `sola-app` prek Kubernetes API) → pošlje na BACKUP_EMAIL.
   - Oba dogodka se zapišeta v dnevnik dogodkov.
2. **Gumb na /schools** → 🌐 Globalne nastavitve (poleg menija zgoraj).
3. Vsi e-poštni odhodi, ki nimajo per-šolskega SMTP, uporabljajo globalne nastavitve iz strani Globalne nastavitve.

### Trenutne vrednosti v Globalnih nastavitvah (baza)

| Polje             | Vrednost                       |
|-------------------|--------------------------------|
| SMTP strežnik     | smtp.protonmail.ch             |
| Vrata             | 587                            |
| Uporabniško ime   | reservation.app@proton.me      |
| Pošiljatelj (From)| reservation.app@proton.me      |
| Geslo / token     | prazno (ni vnešeno)            |

## Napaka 535 (authentication failed)

Pri pošiljanju se je pojavilo:
```
(535, b'5.7.8 Error: authentication failed: authentication failed')
```

Vzrok: SMTP prijava na smtp.protonmail.ch je bila zavrnjena. Ker v Globalnih
nastavitvah ni bil vnešen veljaven SMTP token, app uporabi fallback geslo iz
secretov (Arnes mape), ki za Proton ne velja — zato 535.

## Kako do SMTP tokena pri Protonu

**Uradni postopek (velja za naslove na lastni domeni):**

1. Prijava na https://account.proton.me → Nastavitve → E-pošta → IMAP/SMTP.
2. Razdelek **SMTP token(s)** → **Generate token**.
3. Vpiši ime (npr. `sola-app`) in **izberi aktivni e-poštni naslov na lastni
   domeni** (custom domain).
4. Token (ena vrstica) se prikaže v oknu → skopiraj.
5. V aplikaciji: /global-settings → E-pošta → **Geslo / SMTP token** = token;
   Uporabniško ime = tisti naslov; strežnik `smtp.protonmail.ch`, vrata `587`.

**POMEMBNO — omejitev Protona:** SMTP tokeni so na voljo SAMO za naslove na
lastni domeni (custom domain). Za navaden **@proton.me** naslov (kot je
`reservation.app@proton.me`) Proton tokena ne da; SMTP prijava nanj ni mogoča
(nití z navadnim geslom, nití z app-password — tega Proton nima). Zato 535 ni
posledica napačno vpisanega gesla temveč politike Protona.

Možnosti za pošiljanje z naslova @proton.me:

| Možnost                        | Opis |
|--------------------------------|------|
| **Proton Mail Bridge**         | lokalni SMTP na 127.0.0.1:1025 (STARTTLS), deluje tudi za @proton.me; na k3s zahtevno (bridge mora teči v podu). |
| **Lastna domena**              | npr. `reservationapp.si` → SMTP token deluje; priporočeno. |
| **Arnes SMTP**                 | mail.arnes.si:587, od appa že uporabljen (os-toneta.cufarja-jesenice@guest.arnes.si) — deluje takoj; From ostane Arnes naslov. |

## Priporočilo

Če @proton.me ostane naslov glavnega admina:
- ali kupiti/dodati lastno domeno in nanjo vezati SMTP token,
- ali v Globalnih nastavitvah nastaviti Arnes SMTP (mail.arnes.si, 587),
  s čimer app takoj pošilja (backup/health/obvestila) — vrednosti si oglej v
  secretih (`kubectl -n sola-app get secret sola-secrets -o yaml` — ne objavljaj).

## Opombe o skritih podatkih

Gesla/tokeni v to dokumentacijo ne sodijo in niso zapisana. V aplikaciji se
vnašajo samo v UI (Globalne nastavitve), tu so mesta označena kot {{VAR}}.