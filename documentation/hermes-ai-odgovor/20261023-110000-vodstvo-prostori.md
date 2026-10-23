# Hermes AI odgovor — 2026-10-23 — Prostori »samo za vodstvo« (PROSTORI_VODSTVO)

Uporabnik: »Pri prostorih dodaj še en checkbox (naj bo ta prvi pri vsakem
prostoru) … če je označen, lahko ta prostor rezervirajo samo člani skupine
vodstvo in admin — običajen učitelj nima dostopa (sploh ne ve za ta prostor).«

## Kaj je bilo narejeno

Nova per-prostor kljukica **»🔒 vodstvo«** (PRVA kljukica v vrstici prostora v
Nastavitvah šole → Prostori). Označen prostor:

- ni viden navadnemu učitelju (in neprijavljenim) — niti v zavihkih, niti v
  padajočih seznamih, niti v seznamih rezervacij/serij;
- lahko ga rezervirajo/urejajo samo **vodstvo, šolski admin in glavni admin**;
- učitelj dobi **403** tudi, če omejen prostor kliče neposredno prek API-ja
  (omejitve se ne da zaobiti z ročnim URL-jem).

Možnost je **per-šola** (kot PROSTORI_POPOLDAN): nova nastavitev
`PROSTORI_VODSTVO` (vejica-ločena imena prostorov) v tabeli `school_settings`.

## Spremenjene datoteke

- **app/tenancy.py**
  - `SCHOOL_SETTING_KEYS`: dodan `PROSTORI_VODSTVO` (PUT allowlist).
  - `env_default_settings()`: privzeta prazna vrednost.
  - `SchoolConfig`: property `PROSTORI_VODSTVO` (get_list) + `je_vodstvo_prostor()`.
  - Nova pomočnika: `user_may_see_prostor(user, prostor, config)` (True za
    admin/vodstvo/main_admin na omejenih prostorih) in `vidni_prostori(config, user)`.
- **app/main.py** — javni API za konfiguracijo filtrira po vlogi prijavljenega:
  - `GET /api/prostori` → `vidni_prostori(cfg, user)`;
  - `GET /api/prostori-qty` → samo vidni QTY-prostori (+ limits);
  - `GET /api/popoldan` → `prostori` filtrirani (urnik nespremenjen).
- **app/routers/rezervacije.py**
  - `_require_prostor_access(user, prostor, config)` → 403 za navadne učitelje.
  - `POST /api/rezervacije`: preverba takoj po `_validate_prostor`.
  - `GET /api/rezervacije`: (a) neposredno poizvedovanje po omejenem prostoru →
    403; (b) seznam filtriran na vidne prostore.
  - `DELETE /api/rezervacije/{id}`: učitelj ne sme brisati rezervacij v
    omejenih prostorih (tudi če bi kako postal avtor).
  - `GET /api/rezervacije/series` in `GET /series/{series_id}`: filtrirano.
  - Serije (weekly/full-day) so že tako samo admin/vodstvo → nespremenjeno.
- **app/routers/schools.py** — `prostori_rows` vključi `vodstvo` zastavico.
- **app/templates/school_settings.html**
  - `prostorRowHtml` dobi četrti arg in izriše kljukico **»🔒 vodstvo« kot PRVO**
    (pred »popoldanski urnik« in »število«) + `title` razlaga;
  - `collectProstori()` zbira tudi `vodstvo[]`; shranjevanje pošlje
    `values['PROSTORI_VODSTVO'] = pr.vodstvo.join(',')`;
  - nov hint pod Prostori razlaga kljukico.
- **tests/test_vodstvo_prostori.py** — novih 8 regresijskih testov:
  shranjevanje nastavitve, neznani ključ → 400, vidnost po vlogah za
  `/api/prostori`, `/api/prostori-qty`, `/api/popoldan`, 403 pri rezervaciji
  kot učitelj, 201 kot vodstvo, seznam rezervacij skrije/vidi + 403 pri
  neposredni poizvedbi.

## Verifikacija

- `py_compile` vseh spremenjenih .py → OK.
- `node --check` JS iz school_settings.html (Jinja `{{…}}` maskiran) → OK.
- Ciljni testi (78 obstoječih: test_rezervacije, test_popoldan,
  test_rooms_qty, test_tenancy, test_ui_aliases_and_settings) → passed.
- Novi `tests/test_vodstvo_prostori.py` → 8 passed.
- Celotna suite: **379 passed, 13 failed** — vseh 13 je **pre-existing**,
  nepovezanih s tem feature-jem:
  - 12× `test_subscriptions.py` — `jinja2 TemplateAssertionError: No filter
    named 'eur'` (pade tudi na čistem HEAD worktree; nakup.html/narocnina.html
    rabita filter, ki ni na voljo na tej veji);
  - 1× `test_school_backup.py::test_backup_endpoint_reports_result_and_logs` —
    odvisen od `.env` (lokalni `.env` ima `ADMIN_EMAIL=`/`BACKUP_EMAIL=`
    prazno → endpoint vrne drug razlog kot test pričakuje; z .env na HEAD
    faila enako).

## Varnostni vidik

Ključno: UI skrivanje ni edina zaščita — vsi API-ji (prostori, qty, popoldan,
rezervacije, serije, brisanje) vračajo 403 ali filtrirajo, tako da se omejenega
prostora ne da dobiti z direktnim klicem. Učitelj »sploh ne ve« za prostor.
