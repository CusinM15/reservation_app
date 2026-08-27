# Graph Report - reservation_app  (2026-08-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 714 nodes · 1710 edges · 33 communities (30 shown, 3 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 186 edges (avg confidence: 0.83)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b6e254c6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- sola-db (CNPG PostgreSQL cluster)
- Sola App (FastAPI rezervacijski sistem)
- rezervacije.py
- auth.py
- ocenjevanja.py
- daily_report.py
- Local App Setup Documentation (EN)
- test_series.py
- make_user
- Reservations API (/api/rezervacije)
- docs.py
- test_auth.py
- RoleEnum
- create_blocked_dates
- import_teachers.py
- get_current_user_id
- Repository Structure Diagram (SVG)
- login
- test_ocenjevanja.py
- User
- _require_admin
- _require_admin_or_vodstvo
- sync-env-to-prod.py
- Šolski App – README
- conftest.py
- loadLog
- sync_env_to_configmap.sh
- replace-ips.sh
- clean_test_data.sh
- login
- _send_email

## God Nodes (most connected - your core abstractions)
1. `make_user()` - 59 edges
2. `login()` - 58 edges
3. `User` - 45 edges
4. `get_current_user_id()` - 32 edges
5. `RoleEnum` - 31 edges
6. `sola-db (CNPG PostgreSQL cluster)` - 29 edges
7. `sola-app (FastAPI application)` - 28 edges
8. `Šolski App (OŠ Toneta Čufarja Jesenice)` - 25 edges
9. `Reservation` - 24 edges
10. `Application documentation (reservations & assessments)` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Audit log page` --implements--> `Šolski App (OŠ Toneta Čufarja Jesenice)`  [INFERRED]
  app/templates/audit_log.html → README.md
- `Kubernetes Python client` --conceptually_related_to--> `k3s (Kubernetes)`  [AMBIGUOUS]
  requirements.txt → documentation/admin-devops-navodila.md
- `Diagram: CNPG cluster (PostgreSQL)` --references--> `sola-db (CNPG PostgreSQL cluster)`  [INFERRED]
  documentation/diagrams/cnpg-cluster.png → documentation/en/HA.md
- `Diagram (drawio izvorna): CNPG cluster` --references--> `sola-db (CNPG PostgreSQL cluster)`  [INFERRED]
  documentation/diagrams/cnpg-cluster.drawio.png → documentation/en/HA.md
- `SVG diagram: CNPG cluster (prazna vsebina)` --references--> `CloudNativePG (CNPG) operator`  [AMBIGUOUS]
  documentation/diagrams/cnpg-cluster.svg → documentation/k3s-setup.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Komponente visoke razpoložljivosti (HA architecture)** — concept_k3s, concept_cnpg, concept_metallb, concept_longhorn, concept_cloudflare, concept_etcd [EXTRACTED 0.85]
- **Installation method options (local vs mDNS vs k3s) for non-expert admins** — concept_local, concept_mdns, concept_k3s [EXTRACTED 0.85]
- **Production request path (user → Cloudflare → MetalLB → app pod → database)** — concept_cloudflare, concept_metallb, concept_sola_app, concept_sola_db [EXTRACTED 0.85]
- **sola-app Kubernetes Runtime Stack** — k8s_app_base_sola_deployment, k8s_app_base_sola_service, k8s_app_base_sola_hpa, k8s_app_base_sola_configmap, k8s_sola_secrets, k8s_app_base_namespace, k8s_app_overlays_production_lb_service_loadbalancer_patch, k8s_cluster_metallb_config [EXTRACTED 0.85]
- **CNPG-managed PostgreSQL primary/replica replication and failover** — concept_cnpg, concept_sola_db, concept_sola_db_1, concept_sola_db_2 [EXTRACTED 0.90]
- **Potek ob izpadu noda (HA failover)** — documentation_k3s_setup_k3s_1, documentation_k3s_setup_k3s_2, documentation_k3s_setup_metallb, documentation_k3s_setup_cnpg, documentation_main_sola_app, concept_sola_db, documentation_k3s_setup_longhorn [EXTRACTED 0.90]
- **Jedrne komponente k3s clustra (2 noda, HA)** — documentation_k3s_setup_k3s_1, documentation_k3s_setup_k3s_2, documentation_k3s_setup_metallb, documentation_k3s_setup_longhorn, documentation_k3s_setup_cnpg, documentation_main_sola_app [EXTRACTED 0.90]
- **Opcije migracije v oblak (alternative trenutnemu k3s)** — documentation_migracija_oblak_railway, documentation_migracija_oblak_fly_io, documentation_migracija_oblak_render, documentation_migracija_oblak_coolify, documentation_migracija_oblak_docker_compose, documentation_migracija_oblak_managed_k8s, documentation_migracija_oblak_serverless [EXTRACTED 0.90]
- **Model vlog in pravic uporabnikov (teacher/vodstvo/admin)** — concept_role_teacher, concept_role_vodstvo, concept_role_admin [EXTRACTED 0.90]
- **Načini namestitve aplikacije (deployment modes)** — concept_deploy_lokalno, concept_deploy_mdns, concept_k3s [INFERRED 0.75]

## Communities (33 total, 3 thin omitted)

### Community 0 - "sola-db (CNPG PostgreSQL cluster)"
Cohesion: 0.05
Nodes (103): Admin users API (/auth/admin/users), Auth API (/auth/*), Docs API (/docs/html/*, /docs/download/*), Export API (/api/export/*), Admin panel – user management, loadPreviewContent(), Main app page (SPA), Login page (+95 more)

### Community 1 - "Sola App (FastAPI rezervacijski sistem)"
Cohesion: 0.06
Nodes (65): Diagram: k3s arhitektura (Internet → Cloudflare → MetalLB → 2 noda), Diagram: celotna k3s arhitektura clustra, Posnetek zaslona: gumb za audit log, Posnetek zaslona: audit log pregled (filter, tabela, iskanje), Diagram: CNPG cluster (PostgreSQL), Diagram (drawio izvorna): CNPG cluster, SVG diagram: CNPG cluster (prazna vsebina), Diagram: domena in prometni tok (+57 more)

### Community 2 - "rezervacije.py"
Cohesion: 0.07
Nodes (62): Reservation, _check_tablice_capacity(), _check_unique_space(), _commit_series(), create_full_day_series(), create_rezervacija(), create_weekly_series(), delete_rezervacija() (+54 more)

### Community 3 - "auth.py"
Cohesion: 0.10
Nodes (43): log_audit(), Session, Zapiši dogodek v audit log. Args: db: SQLAlchemy seja (mora biti aktivna).…, activate_user(), admin_users_page(), change_password(), create_user(), deactivate_user() (+35 more)

### Community 4 - "ocenjevanja.py"
Cohesion: 0.09
Nodes (42): log_audit(), Session, Zapiši dogodek v audit_log tabelo. Kličeš pred commitom. Zakaj se ta funkcija…, Assessment, check_and_raise(), cleanup(), _cleanup_intents(), _cleanup_resource() (+34 more)

### Community 5 - "daily_report.py"
Cohesion: 0.09
Nodes (36): _check_consecutive_days(), collect_app_data_agent(), collect_k3s_agent(), collect_longhorn_agent(), condition_map(), condition_status(), estimate_node_lifetime(), fmt_age() (+28 more)

### Community 6 - "Local App Setup Documentation (EN)"
Cohesion: 0.12
Nodes (34): SQLite Database File (data/sola.db), sola-app Docker Image, Local App Setup Documentation (EN), Screenshot: Teacher Import UI (img_1), Screenshot: Teacher Import UI (img_2), Screenshot: Teacher Import UI (img_3), Screenshot: Teacher Import UI (img_4), Screenshot: Teacher Import UI (img_5) (+26 more)

### Community 7 - "test_series.py"
Cohesion: 0.11
Nodes (30): _admin_login(), _count_in_db(), _make_weekly_series(), Če razpon pade na vikend, se vikend dnevi preskočijo., REGRESIJA: serija z qty > TABLICE_MAX mora biti zavrnjena PRED brisanjem…, Učitelj ima qty=20, serija qty=15 → 35 > 28 → učiteljeva se pobriše., Ustvari tedensko serijo (3 datumi) in vrne series_id., Enodnevni razpon z napačnim weekday (ni v razponu) → ni terminov. (+22 more)

### Community 8 - "make_user"
Cohesion: 0.15
Nodes (27): make_user(), Ustvari uporabnika z znanim geslom in vrne User objekt., _create(), Client poskuša poslati tuj teacher_id — server ga mora ignorirati., Dan dejavnosti (blokada) za razred → ocenjevanje na ta dan zavrnjeno (400)., Admin lahko briše tujo rezervacijo (učitelj ne sme)., 20 + 15 = 35 > 28 → drugi poskus zavrnjen., Dva učitelja lahko hkrati rezervirata tablice (dokler je kapaciteta). (+19 more)

### Community 9 - "Reservations API (/api/rezervacije)"
Cohesion: 0.14
Nodes (27): Blocked dates API (/api/blocked-dates), Assessments API (/api/ocenjevanja), Reference data API (/api/schedule, /api/razredi, /api/prostori), Reservations API (/api/rezervacije), addBlockedDates(), changeMonth(), deleteAssessment(), deleteBlockedDate() (+19 more)

### Community 10 - "docs.py"
Cohesion: 0.12
Nodes (24): emoji_img_tag(), _find_font(), _load(), <img> tag z data URI za emoji sekvenco (ali original, če ne gre)., Zamenja vse emoji sekvence v HTML-ju z <img> tagi (za weasyprint)., Poišči Noto Color Emoji (CBDT). Najprej znane poti, potem fc-match., Vrne glyph id za emoji sekvenco (uharfbuzz upošteva ZWJ ligature)., Vrne PNG bajte (barvni emoji) ali None, če glifa ni mogoče izvleči. (+16 more)

### Community 11 - "test_auth.py"
Cohesion: 0.13
Nodes (20): verify_password(), get_user_from_db(), Pomožnik za direktno preverjanje stanja v bazi., _get_reset_token(), Po uspešni ponastavitvi je token pobrisan — drugi poskus pade., Token s preteklim časom poteka (unix=1 → 1970) mora biti zavrnjen., change-password je zaščiten z middleware-om — brez prijave 307., test_change_password() (+12 more)

### Community 12 - "RoleEnum"
Cohesion: 0.34
Nodes (6): Settings, get_db(), FastAPI dependency, ki ustvari in zapre DB sejo. Zakaj uporabljamo yield…, AuditLog, RoleEnum, str

### Community 13 - "create_blocked_dates"
Cohesion: 0.13
Nodes (19): BlockedDate, BlockedDateOut, BlockedDatesCreate, _check_allowed(), create_blocked_dates(), delete_blocked_date(), list_blocked_dates(), BaseModel (+11 more)

### Community 14 - "import_teachers.py"
Cohesion: 0.21
Nodes (16): create_user(), generate_password(), list_users(), login(), main(), Session, 7 znakov, garantirano >=1 mala, >=1 velika, >=1 številka. Izognemo se…, Vsaka tabela na strani je en tab. Naslove tabov najdemo v gumbu/labelu Divi… (+8 more)

### Community 15 - "get_current_user_id"
Cohesion: 0.23
Nodes (14): admin_users_redirect(), AuthMiddleware, get_prostori(), get_razredi(), get_schedule(), health(), history_page(), get (+6 more)

### Community 16 - "Repository Structure Diagram (SVG)"
Cohesion: 0.17
Nodes (15): Repository Structure Diagram (SVG), Repository Structure Diagram (PNG), app/ (Python FastAPI application), app/config.py (settings: IPs, passwords), app/database.py (DB connection), app/main.py (entry point), app/models.py (data organization), app/race.py (double-click protection) (+7 more)

### Community 17 - "login"
Cohesion: 0.28
Nodes (13): login(), Prijava prek /auth/login — piškotki ostanejo v client cookie jar., Učitelj naredi rezervacijo + ocenjevanje, da imamo kaj izvoziti., _setup_data(), test_export_date_range_invalid(), test_export_invalid_date(), test_export_ocenjevanja_csv(), test_export_rezervacije_csv() (+5 more)

### Community 18 - "test_ocenjevanja.py"
Cohesion: 0.22
Nodes (10): _block(), _next_weekday(), date, Vodstvo/admin blokira dan za razrede (dan dejavnosti)., Brez blokade učitelj normalno napove ocenjevanje (201)., Dan dejavnosti velja le za svoj razred — 5.a lahko napove, če je blokiran 6.a., Če ima razred na ta dan dejavnost, API ocenjevanje zavrne s 400., test_ocenjevanje_na_prostem_datumu_ok() (+2 more)

### Community 19 - "User"
Cohesion: 0.29
Nodes (9): Preveri moč gesla po pravilih šole. Zakaj ta pravila? Šola zahteva minimalno…, validate_password_strength(), init_db(), Ustvari vse tabele in izvede lahke idempotentne migracije. Zakaj ne uporabljamo…, on_startup(), User, on_event, Import users from uporabniki.csv into the database. Usage: python -m… (+1 more)

### Community 20 - "_require_admin"
Cohesion: 0.36
Nodes (9): audit_log_page(), list_audit_log(), get, Request, Session, Preveri, da je uporabnik admin. Vrne uporabnika. Samo admin lahko vidi audit…, JSON endpoint — vrni zadnje vnose v audit logu. Podpira paginacijo…, HTML stran za ogled audit loga (samo admin). (+1 more)

### Community 21 - "_require_admin_or_vodstvo"
Cohesion: 0.36
Nodes (9): export_ocenjevanja(), export_rezervacije(), get, Request, Session, Izvozi ocenjevanja v CSV za izbrani razred in obdobje. CSV vsebuje: Datum,…, Preveri, da je uporabnik admin ali vodstvo., Izvozi rezervacije v CSV za izbrano obdobje in prostor. CSV vsebuje: Datum,… (+1 more)

### Community 22 - "sync-env-to-prod.py"
Cohesion: 0.36
Nodes (7): Path, kubectl(), main(), mask_db_url(), parse_env(), Robustno prebere .env (KEY=VALUE, vrednost lahko vsebuje '=' in navednice)., Prikaze samo host:port/db iz DATABASE_URL (kredenciali maskirani).

### Community 23 - "Šolski App – README"
Cohesion: 0.33
Nodes (7): Cloud deployment (SaaS), Linux Mint, Local server from old PCs, Zorin OS, Main documentation (Slovenian), Cloud migration documentation, Šolski App – README

### Community 24 - "conftest.py"
Cohesion: 0.33
Nodes (6): fixture, TestClient, clean_db(), client(), Svež TestClient na testno bazo (startup zažene init_db + bootstrap admina)., Po vsakem testu počisti VSE tabele (tudi users) — testi so hermetični,…

### Community 25 - "loadLog"
Cohesion: 0.40
Nodes (3): Audit log API (/api/audit-log), loadLog(), Audit log page

### Community 31 - "login"
Cohesion: 0.40
Nodes (5): login(), Obdelava prijave — preveri username/email in geslo, nastavi piškotke. Dovoljena…, Podpiši user_id v varen cookie string., sign_user_id(), Response

### Community 32 - "_send_email"
Cohesion: 0.50
Nodes (4): Pošlji email preko Arnes SMTP. Best-effort — napake se ignorirajo., _send_email(), Database backup script. Runs as a Kubernetes CronJob to dump the PostgreSQL…, run()

## Ambiguous Edges - Review These
- `Main Documentation (entry point)` → `K3s Architecture Diagram (PNG)`  [AMBIGUOUS]
  documentation/en/main.md · relation: references
- `k3s (Kubernetes)` → `Kubernetes Python client`  [AMBIGUOUS]
  requirements.txt · relation: conceptually_related_to
- `PDF generation for docs` → `python-docx`  [AMBIGUOUS]
  requirements.txt · relation: conceptually_related_to
- `CloudNativePG (CNPG) operator` → `SVG diagram: CNPG cluster (prazna vsebina)`  [AMBIGUOUS]
  documentation/diagrams/cnpg-cluster.svg · relation: references

## Knowledge Gaps
- **52 isolated node(s):** `Settings`, `replace-ips.sh script`, `clean_test_data.sh script`, `Main documentation (Slovenian)`, `Daily cluster status report (cron)` (+47 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Main Documentation (entry point)` and `K3s Architecture Diagram (PNG)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `k3s (Kubernetes)` and `Kubernetes Python client`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `PDF generation for docs` and `python-docx`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `CloudNativePG (CNPG) operator` and `SVG diagram: CNPG cluster (prazna vsebina)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **Why does `User` connect `User` to `rezervacije.py`, `auth.py`, `ocenjevanja.py`, `make_user`, `test_auth.py`, `RoleEnum`, `create_blocked_dates`, `get_current_user_id`, `_require_admin`, `_require_admin_or_vodstvo`, `conftest.py`, `login`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `make_user()` connect `make_user` to `test_series.py`, `test_auth.py`, `RoleEnum`, `login`, `test_ocenjevanja.py`, `User`, `conftest.py`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `RoleEnum` connect `RoleEnum` to `rezervacije.py`, `auth.py`, `ocenjevanja.py`, `make_user`, `create_blocked_dates`, `get_current_user_id`, `User`, `_require_admin`, `_require_admin_or_vodstvo`, `conftest.py`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._