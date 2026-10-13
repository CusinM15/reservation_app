# Kritičen brainstorm: »open-source / zasebnosti prijazen konkurent Microsoft Intune«
### v kontekstu OSTC App (Python/FastAPI)

> Označevalnik: **[KODA]** = ugotovljeno iz repozitorija (z navedeno potjo) · **[SPLOŠNO]** = splošno tehnično dejstvo (ni iz repa) · **[OCENA]** = moja predpostavka/ocene · **[?]** = treba zunanje preveriti.
> Repo pregledan read-only; nič ni bilo spremenjeno, noben ukaz ni pisal v repo/oblak.

---

## 1. Povzetek ideje

**Kaj bi izdelek *lahko* bil:** razširitev skrbniškega portala OSTC App s funkcijo »upravljanje naprav« za šolske tablice/računalnike, ki bi temeljila na odprtih/standardnih protokolih (zlasti **Android Management API / Android Enterprise**) in bi šoli omogočila: evidenco naprav, katalog politik, osnovni kiosk način, dovoljen seznam aplikacij in oddaljeno ponastavitev.

**Česa NE smemo obljubljati:**
- Da je to »drugi Intune«. Intune pokriva Windows + Apple + Android **hkrati**, z lastnim MDM jedrom (OMA-DM/WinMDM, APNs, AMAPI), pogojnim dostopom, odjemalci in 20 let razvoja. [SPLOŠNO]
- Da bo isto kodo »samo dodali« obstoječi FastAPI aplikaciji. Spletni portal in MDM jedro sta različna razreda sistema (spodaj).
- Zasebnosti prijaznosti kot samoumevne — vsak MDM ima inherentno moč nad napravo (glej §4).

**Portal vs. pravi MDM (ključna razlika):**

| | Spletni skrbniški portal (kar OSTC App *je*) | Pravi MDM (kar Intune *je*) |
|---|---|---|
| Model | uporabnik → HTTP zahteva → odgovor | naprava je **vpisana (enrolled)**, ima identiteto in certifikat |
| Komunikacija | pasivno: brskalnik kliče strežnik | **obojestransko**: strežnik pošilja ukaze, naprava poroča |
| Ukaz | ni ukazov; uporabnik sam nekaj klikne | `wipe`, `lock`, `install app`, `set policy` — izvrši se **na napravi** |
| Odvisnost od platforme | nobena (deluje v brskalniku) | vezano na OS: Android (AMAPI/DPC), Apple (MDM protokol + APNs), Windows (OMA-DM/WinMDM + CSP) |
| Dokaz v repu | FastAPI routerji, seje, baza [KODA] | v repu **ne obstaja nič** takega [KODA — ni najdeno] |

**Bistvo:** ena dodatna HTTP stran v portalu še ne upravlja naprave. Za »dejanski MDM« potrebuješ **kanal do naprave** (vpis + identiteta + pošiljanje ukazov + poročanje). To je novo jedro, ne nova stran.

---

## 2. Pregled OSTC App (na podlagi pregledane kode)

### 2.1 FastAPI aplikacija
- Vstopna točka: **`app/main.py`** — `FastAPI(title="Šolski App")`, middleware za šolske URL-aliasе, GZip, auth middleware; routerji v **`app/routers/`** (rezervacije, ocenjevanja, auth, blocked_dates, audit_log, export, docs, dejavnosti, schools, subscription). [KODA]
- Seje: **piškotki, ne JWT** — namerno (komentarji v `app/main.py` in `app/routers/auth.py`). [KODA]

### 2.2 Avtentikacija
- Podpisan piškotek `user_id`: **`app/security.py`** (itsdangerous `URLSafeTimedSerializer`, salt `sola-auth`, `SESSION_MAX_AGE = 30 dni`). Prijavljeno v komentarju: prej je bil piškotek nepodpisan → auth bypass. [KODA]
- Gesla: **bcrypt** (`passlib.context.CryptContext(schemes=["bcrypt"])`) v `app/routers/auth.py`. [KODA]
- **MFA/TOTP/2FA: v repozitoriju nisem našel** (iskal `totp|mfa|2fa|otp` → 0 zadetkov). [KODA]
- Komentar v `app/routers/auth.py` navaja privzeti admin račun z geslom `admin123`, ki ga je treba takoj zamenjati — **tveganje privzetih poverilnic** (ne citiram vrednosti iz drugih virov).
- **CSRF zaščita, rate limiting, CORS: v repozitoriju nisem našel** (iskal `csrf|ratelimit|throttle|slowapi|CORS|SameSite` → 0 zadetkov). [KODA]

### 2.3 Uporabniške vloge
- **`app/models.py`** (`RoleEnum`) in **`app/tenancy.py`**: `main_admin`, `admin` (šolski admin), `vodstvo`, `teacher`. [KODA]
- `main_admin` ni vezan na šolo (`school_id = NULL`), vidi vse šole. [KODA]

### 2.4 Podatkovna shramba
- **PostgreSQL obvezen**; SQLite ni podprt (`app/config.py` fail-fast brez `DATABASE_URL`; `app/database.py`). Shema se vzdržuje z **idempotentnimi `ALTER TABLE` v `init_db()`**, brez Alembica (`app/database.py`). [KODA]
- Večšolskost: `School`, `SchoolAlias`, `SchoolSetting` (`app/models.py`); izolacija prek `user.school_id` iz baze, **ne** iz piškotka (`app/tenancy.py`). [KODA]
- Revizijska sled: model `AuditLog` + **`app/audit.py`** (`log_audit`, commit na klic) + router `app/routers/audit_log.py`. [KODA]
- Naročnine: `app/subscriptions.py`, `app/routers/subscription.py`, `app/app_settings.py` (stikalo `SUBSCRIPTION_SELLING`; privzeta cena `SUBSCRIPTION_PRICE_EUR = 150` za leto). [KODA]

### 2.5 Namestitev (deployment)
- **Docker**: `Dockerfile` (python:3.11-slim, non-root `appuser`, uvicorn na 8002). [KODA]
- **k3s/k8s**: `k8s/app/base/sola-deployment.yaml` (3 replike, `topologySpreadConstraints`, probes, `envFrom` → ConfigMap + Secret), `sola-service.yaml`, `sola-hpa.yaml`, `sola-backup-cronjob.yaml`; `k8s/cluster/sola-cnpg-cluster.yaml` (CNPG), `metallb-config.yaml`. [KODA]
- **Argo CD**: `k8s/argocd/application-sola-app.yaml`. [KODA]
- **Oracle VM (Always Free)**, ena VM za vse šole: `deploy/oracle/README.md`, `docker-compose*.yml`, `Caddyfile`, `backup.sh`, `bootstrap.sh`. [KODA]
- Skrivnosti: k8s `Secret sola-secrets` + `k8s/README.md`; repo pravi »občutljivih vrednosti ne shranjujemo v repo« — **a v repu so prisotne config/secret datoteke; ravnanje s skrivnostmi je treba posebej preveriti** (ne navajam vsebine). [KODA + opozorilo]

### 2.6 Obstoječi Hermes agent
- **`deploy/oracle/HERMES.md`** in **`deploy/oracle/install-hermes.sh`** (ter `bootstrap.sh`): na VM se namesti **Hermes agent** (`hermes-agent.nousresearch.com/install.sh`), poveže na model (ključ v `~/.hermes/.env`), opcijsko gateway (Discord) + pairing, `loginctl enable-linger`. [KODA]
- Namen: agent **s polnim dostopom do strežnika** (bere loge, lahko sam posodablja app). To je operativni agent, **ne** agent na napravi uporabnika/tablice. [KODA]
- Pomembno: »Hermes agent« tu ni del aplikacijske logike — je ločen orodni sloj na VM.

### 2.7 Kaj bi se morda dalo ponovno uporabiti (brez trditev o ustreznosti/varnosti)
- [OCENA] **Vloge + `school_id` izolacija** (`tenancy.py`) bi lahko bile osnova za »kdo sme upravljati katere naprave«.
- [OCENA] **`AuditLog`** bi se dal uporabiti za sled ukazov (kdo je kaj ukazal) — a trenutni model ni narejen za »ukazno« zakonodajo (stanje ukaza, potrditev izvršitve).
- [OCENA] **Secret/ConfigMap vzorec, Docker, k3s, CNPG, backup cron** so uporabna infrastrukturna osnova.
- [OCENA] **Avtentikacija s podpisanim piškotkom** je sprejemljiva za človeške uporabnike, **ni** primerna za naprave/agente (ti potrebujejo lastno identiteto/certifikat/žeton).
- ⚠️ Nič od tega **ni dokaz, da je primerno ali varno** za MDM. Vsaka ponovna uporaba bi zahtevala ločeno presojo.

---

## 3. Platforme in tehnična izvedljivost

### 3.1 Android
- [SPLOŠNO] **Kiosk / dedicated mode, fully managed (device-owner) vpis, distribucija aplikacij, blokada trgovine, oddaljena ponastavitev** so dosegljivi prek **Android Management API (AMAPI)** — a le, če naprava teče **stock Android z Google Mobile Services (GMS)**.
- [SPLOŠNO] Za AMAPI ne pišeš lastnega DPC: privzeto to opravi **Google-ova app »Android Device Policy«**. Tvoj strežnik **kliče Google API** (enterprise, enrollment token, policy, commands) in prejema **webhook (Pub/Sub) obvestila**. To je *strežniška* integracija → **konceptualno se ujema s FastAPI backendom**.
- [SPLOŠNO/?] Potrebuješ: **Google enterprise** (managed Google Play account), ki ga v praksi vežeš na Google Workspace ali Google račun; AMAPI je brezplačen, a **zahteva Googlove storitve**. **Zero-touch enrollment** (škatla vnaprej vpisana) zahteva **prodajalca/resellerja**. Točne pogoje in omejitve je treba preveriti.
- [SPLOŠNO] **Lasten DPC/agent** je potreben, če hočeš naprave **brez GMS** (de-Googled/AOSP) — takrat pišeš app z `DevicePolicyManager` (device owner) in lastno komunikacijo. To je bistveno težje (podpisovanje, distribucija izven trgovine, OTA posodobitve agenta).
- **[OCENA]** Za šolske tablice z GMS je **Android-only prek AMAPI realistična niša**. Brez GMS je projekt za red velikosti težji.

### 3.2 Windows
- [SPLOŠNO] Pravi sistemski MDM je **OMA-DM / WinMDM enrollment** z MDM certifikati, **CSP-ji** in **registracijo naprave (Entra/AD)**. To **ni** običajna FastAPI spletna aplikacija — potrebuješ MDM strežnik, certifikatno verigo (SCEP/PKCS), push (WNS) in CSP podporo.
- [OCENA] »Windows podpora« v obliki, ki bi jo šola pričakovala od Intune, je **ločen, težak projekt**. Lahko pa portal *evidentira* računalnike in *prikaže* stanje, če naprave poročajo po lastnem agentu (ne standardni MDM).

### 3.3 Apple / iPadOS
- [SPLOŠNO] Apple ima **ločen MDM protokol** (APNs push → naprava se odzove na `/mdm/` endpoint, zahteve z `CheckIn`/`Command`), **zahteva APNs potisni certifikat** iz **Apple Developer Program**, in sledenje **DEP/ADE** + **VPP** za distribucijo. Obstajajo odprtokodni strežniki (npr. MicroMDM/NanomDM) kot predhodna umetnost. [SPLOŠNO — preveriti licence in zrelost]
- [OCENA] Apple/iPadOS je **realen, a zahteven** dodatek; brez iOS naprav v ciljni publiki ga takoj izpustimo.

### 3.4 Zakaj univerzalni večplatformski MDM ni »še ena stran«
- [SPLOŠNO] Vsaka platforma ima **drug enrollment protokol, drugo push storitev, druge certifikate in drug model politik**. Skupna jim ni koda, temveč *koncept*. Enotni sloj je mogoče narediti nad **abstrakcijo** (naprava, politika, ukaz, rezultat), a vsak »gonilnik« platforme je sam zase velik.
- [KODA] V obstoječi aplikaciji ni **nobenega** elementa za katerikoli izmed teh protokolov (ni enrollmenta, ni push, ni certifikatov, ni ukazne vrste, ni poročanja naprav).

**Ločnica preverjeno/splošno/neznano:**
- **Preverjeno iz repa:** aplikacija je spletni portal brez kakršnegakoli upravljanja naprav. [KODA]
- **Splošno tehnično dejstvo:** AMAPI/Android Enterprise, Apple MDM protokol, Windows OMA-DM — ter njihove zahteve po Googlovih/Appleovih/Microsoftovih storitvah. [SPLOŠNO]
- **Zahteva zunanje preverjanje:** točni pogoji Google enterprise / zero-touch, Apple certifikati in cene, licence odprtokodnih MDM jeder, ali ciljne šole sploh imajo nadzor nad Google računom naprav. [?]

---

## 4. Zasebnost, varnost in odgovornost

### 4.1 Predlagana načela (ne trdim, da so že v kodi)
- **Najmanjše zbiranje:** inventar = identifikator naprave, model, stanje OS, zadnja sinhronizacija. **Nič** vsebine zaslona, **nič** osebnih sporočil, **nič** lokacije/preklicnega nadzora.
- **Omejeno hranjenje:** dnevniki ukazov z **vnaprej določeno retencijo** (npr. 30–90 dni), samodejno brisanje. [KODA] Trenutni `AuditLog` nima vidne politike retencije/brisanja → **novo.**
- **Šifriranje:** v tranzitu (TLS + HSTS) in v mirovanju (disk/volume). [KODA] V app sloju ni najdenega šifriranja; to bi bilo na ravni diska/DB in **je treba preveriti**.
- **Revizijski dnevniki:** obstoječi `AuditLog` je dober temelj, a za ukaze MDM je treba **ločeno evidenco ukazov** (kdo, kaj, kdaj, kateri napravi, izid).
- **MFA + RBAC + tenant izolacija:** RBAC in izolacija **obstajata** [KODA]; **MFA ne obstaja** [KODA] — za skrbništvo naprav bi bila **nujna**.
- **Varno upravljanje skrivnosti:** ugotovljeno k8s Secret/.env; **ravnanje s skrivnostmi je treba revidirati** (opozorilo).
- **Podpisani ukazi + zaščita pred ponovitvijo (replay):** za naprave bi morali biti ukazi **podpisani, z nonce/ID in rok trajanja**. [KODA] Ni najdeno; v repu ni nobenega ukaznega kanala.
- **Varnostne posodobitve + varnostne kopije:** backup cron obstaja [KODA]; politika posodobitev odvisnosti (**[KODA]** ni najdenega Renovate/Dependabot) in redno nameščanje je treba vzpostaviti.

### 4.2 Tveganja (oddaljene akcije)
- **Zaklep/brisanje:** napačen ukaz ali kompromitiran skrbniški račun → **izguba podatkov / neuporabne tablice v celotni šoli**. Potreben je »dvostezni« proces (potrditev + možnost razveljavitve, kjer jo platforma dopušča).
- **Namestitev aplikacij:** pot v šolo za neželeno/zlonamerno app (»supply chain«).
- **Prevzem skrbniškega računa:** ker skrbnik naprav **upravlja vse tablice**, je to najprivlačnejša tarča → MFA + ločeni admin računi + princip najmanjših pravic so **nujni**.
- **Prehod na Googlove/Apple storitve:** AMAPI/APNs pomenita, da del nadzora in metapodatkov (npr. zadnja sinhronizacija, model) prehaja prek Google/Apple infrastrukture — **»open-source« ne pomeni »brez velikih ponudnikov«**. [SPLOŠNO]

### 4.3 Pravno/organizacijsko (brez dokončnega pravnega mnenja)
- [SPLOŠNO/?] Šolske naprave in podatki učencev so **občutljivi**: GDPR, nacionalna pravila, pogodbe o obdelavi z Google/Apple/Hetzner. Vsak MDM zbira **metapodatke o napravah**, zato so potrebni: namen obdelave, pravna podlaga, **DPIA (ocena učinka)** in politika hrambe.
- ❌ **Nikoli ne predlagati** zbiranja vsebine sporočil, prikritega nadzora zaslona ali lokacijskega sledenja učencev. Če se takšna zahteva pojavi, je treba **zavrniti / eskalirati pravniku**.
- **Ne dajem dokončnega pravnega mnenja** — te točke mora potrditi pooblaščena oseba/DPO.

---

## 5. Realističen MVP

### Faza 0 — Inventar + katalog politik (brez upravljanja naprav) — *najvarnejši začetek*
- **Kaj:** portal le **evidentira** naprave (ročni vnos ali CSV), hrani katalog politik kot besedilo, **ne pošilja nobenih ukazov**.
- **Odvisnosti:** obstoječi FastAPI + baza + RBAC [KODA]. Nič platformsko specifičnega.
- **Tveganja:** minimalna (ni moči nad napravo). Glavno tveganje = **vat »MDM« v imenu**, ki ustvari napačna pričakovanja.
- **Kriterij uspeha:** šola vidi seznam svojih naprav in politike; **ni enega ukaza**, ki bi spremenil napravo.

### Faza 1 — Android-only pilot: testne naprave
- **Kaj:** 2–5 testnih tablic z GMS, ločen testni Google enterprise, ročni vpis (enrollment token).
- **Odvisnosti:** Google enterprise + AMAPI omogočen; testne naprave; HTTPS endpoint + Pub/Sub webhook. [?] pogoji Google.
- **Tveganja:** izguba/napačna nastavitev na pravih tablicah; **podatki izven šolske meje** (Google).
- **Kriterij uspeha:** naprava se pojavi v inventarju z realnimi metapodatki; brez kakršnegakoli ukaza, ki bi »zaklenil« živo napravo.

### Faza 2 — Vpis + osnovna politika
- **Kaj:** fully-managed (device-owner) vpis, minimalna politika (geslo, posodobitve).
- **Odvisnosti:** Faza 1; jasna politika hrambe; MFA za skrbnike (4.1). [KODA] MFA je **treba dodati**.
- **Tveganja:** slaba politika → neuporabne naprave; potreben **načrt za izhod / obnovitev**.
- **Kriterij uspeha:** testna naprava dobi politiko, ki jo je mogoče **v celoti razveljaviti**.

### Faza 3 — Kiosk način
- **Kaj:** dedicated/kiosk mode za izbrano aplikacijo, izhod iz kioska z geslom/skrbniko.
- **Odvisnosti:** Faza 2; definiran postopek izhoda.
- **Tveganja:** **zaklenjena tablica** brez poti ven = »opeka« → obvezen preizkušen »unlock« postopek.
- **Kriterij uspeha:** kiosk se da vklopiti **in** izklopiti brez fizičnega posega.

### Faza 4 — Dovoljen seznam aplikacij + posodobitve
- **Kaj:** whitelist aplikacij, nadzor posodobitev OS/app.
- **Odvisnosti:** Faza 3; distribucija app (upravljani Google Play / zasebna app).
- **Tveganja:** blokirana legitimna aplikacija; **prevelike pravice** do trgovine.
- **Kriterij uspeha:** neželena app se ne da namestiti; posodobitve tečejo nadzorovano.

### Faza 5 — Izbris / ponovni vpis / obnovitev
- **Kaj:** remote wipe, ponovni vpis, obnovitev po izgubi.
- **Odvisnosti:** Faza 4; **potrditev + revizijska sled** ukaza; MFA.
- **Tveganja:** **najvišje** tveganje podatkov (napačen wipe). Obvezna dvojna potrditev + zakasnitev + log.
- **Kriterij uspeha:** wipe se izvede **in** je viden v reviziji; postopek obnovitve preizkušen.

> Nobena faza ne vsebuje navodil, ki bi spreminjala naprave ali obstoječo kodo.

---

## 6. Stroški in trajnost

> Vse številke spodaj so **ocene [OCENA]** ali **obstoječi podatki iz repa [KODA]**; kjer ni preverjeno, piše **[?]**.
> Hetznerjeve cene spodaj so **navedene v `documentation/v_oblak.md`** [KODA — dokument v repu]; v tem dokumentu so bile preverjene pri Hetznerjevem ceniku (2026) in **jih je treba pred zakupom ponovno preveriti**. Aplikacija se po tvoji navedbi seli na Hetzner v ~1 mesecu.

### 6.1 Enkratni stroški razvoja [OCENA]
- **Faza 0 (inventar):** majhen obseg (dnevi dela) — največ dela je UI + shema.
- **Android pilot (Faze 1–5):** **velik** obseg; AMAPI integracija, enrollment, politike, ukazi, revizija, testiranje na pravih napravah.
- **Multiplatforma (Windows/Apple):** **zelo velik** obseg (praktično nov izdelek).

### 6.2 Mesečni/letni stroški delovanja — dodatni »MDM« del poleg obstoječe app
| Postavka | Vrsta | Ocena |
|---|---|---|
| Hetzner CPU/RAM/disk | stalno | Če »pritakneš« na obstoječi strežnik: **marginalno** [OCENA]. Osnovni HA stroj (3× CPX22 ≈ €83/mesec) je že v `v_oblak.md` [KODA-doc] |
| Omrežje | spremenljivo | 20 TB vključeno; MDM promet je majhen [OCENA] |
| Varnostne kopije | stalno | +20 % cena strežnika oz. Storage Box ~€3,80 [KODA-doc/?] |
| Monitoring | stalno | self-hosted (Grafana/Prometheus) → nekaj 100 MB RAM [OCENA] |
| Shranjevanje dnevnikov | **raste z uporabo** | vez ok. 0,5–1 KB/dogodek [OCENA] → pri 25.000 dog./mes ≈ 12–25 MB/mes |
| Domena | letno | ~€10–12/leto [KODA-doc/?] |
| E-pošta/obvestila | stalno | če ostaneš na ARNES SMTP, ~0; drugje [?] |
| Podpisovanje/distribucija app | letno/enkratno | Google Play račun (enkratno), Apple Developer Program + APNs (letno), Windows code-signing (letno) — **zneski [?] preveriti** |
| Zunanje storitve (FCM/APNs/AMAPI) | stalno | FCM/AMAPI načeloma brezplačni, a **zahtevajo Google enterprise**; APNs zahteva Apple [SPLOŠNO/?] |
| Testne naprave | enkratno | 2–5 tablic — **cena [?] / morda že imate** |
| Podpora in vzdrževanje | stalno | **največji trajni strošek** (tvoje delo) |

### 6.3 Scenariji (predpostavke jasno navedene)
| | S1 Pilot | S2 Manjša šola | S3 Več šol |
|---|---|---|---|
| Šol | 1 | 1 | 5 |
| Naprav | 10 | 50 | 250 |
| Dogodkov/ukazov na mesec | ~1.000 | ~5.000 | ~25.000 |
| Dodatni neposredni strošek/mesec | ~€0–2 [OCENA] | ~€2–5 [OCENA] | ~€5–15 [OCENA] |
| Dodatni strošek/leto | ~€0–25 | ~€25–60 | ~€60–180 |
| Dodatni strošek/šola/leto | ~€0–25 | ~€25–60 | ~€12–36 |
| Dodatni strošek/naprava/leto | ~€0–2,5 | ~€0,5–1,2 | ~€0,2–0,7 |
| Rastoče (usage) | logi, promet | logi, promet | logi, promet |
| Stalno (fixed) | monitoring, backup, domena | isto | isto |

> Poudarek: **marginalni neposredni strošek gostovanja je majhen** — ker MDM »pritakneš« na obstoječi Hetzner strežnik. **Pravi stroški so razvoj, podpisovanje/distribucija, testne naprave in tvoja podpora** [OCENA]. Hetzner **ne odpravi** stroškov Googla/Appla/Microsofta (računi, certifikati, morebitne licence). [SPLOŠNO]

### 6.4 Doplačilo za MDM (letno) — kaj pomeni bruto razlika
Osnova: privzeta cena **150 €/leto** [KODA — `app_settings.py`], a **enota ni definirana** (glej §6.6). Prikaz scenarijev doplačil glede **le na neposredne stroške** (brez dobička):

| Doplačilo | Prihodek/šola/leto | Δ prihodka | Ocenjeni dodaten neposredni strošek | **Bruto razlika (pred davki/delom)** |
|---|---|---|---|---|
| +0 € (vključeno) | 150 € | 0 € | ~0–60 €/šola | lahko **negativna** |
| +25 % (≈ +37,50 €) | ~187,50 € | +37,50 €/šola | ~0–60 €/šola | približno na ničlu |
| +50 % (≈ +75 €) | ~225 € | +75 €/šola | ~0–60 €/šola | pozitivna, a majhna |
| Fiksno +€3/naprava/leto | 150 € + 3×N | npr. 50 naprav = +150 € | ~25–60 €/šola | pozitivna |

> ⚠️ To **ni čisti dobiček**: ne vključuje razvoja, podpore, davkov in tvojega dela. **Razvoj je enkraten in velik** — povrne se šele pri mnogih šolah/letih. DDV in davčna obravnava **[?] preveriti**.

### 6.5 Najvplivnejše predpostavke
1. **Ali MDM pritakneš na obstoječi strežnik ali rabiš ločenega** (vpliv na fiksne stroške).
2. **Ali ciljne šole imajo GMS in nadzor nad Google računom** (odloči Android-only izvedljivost).
3. **Obseg razvoja** (Faza 0 vs. 1–5 vs. multiplatforma) — daleč največji dejavnik.
4. **Retencija dnevnikov** (vpliv na shranjevanje in GDPR).
5. **Cena podpisovanja/distribucije** (Google/Apple/Windows) — **[?] preveriti**.

### 6.6 Podatki, ki jih moraš pridobiti pred določitvijo cene
- **Enota 150 €/leto** (šola / organizacija / uporabnik / instanca) — **odprto vprašanje**, brez tega cena ni smiselna.
- Aktualne Hetzner cene (pred zakupom), aktualne Google/Apple/Windows cene in pogoji.
- Ali obstajajo iOS/Windows naprave v ciljni publiki.
- Koliko šol in naprav realistično v 12–24 mesecih.

---

## 7. Konkurenca ja/ne

**Ali je realno ciljati celotno paleto Intune?** **Ne** — [OCENA] to je večletni, večplatformski produkt z lastnim MDM jedrom. Realno je ciljati **nišo**: *»zasebnosti prijazno upravljanje **samo Android šolskih tablic**, ki se upravljajo prek standardnega Android Enterprise, brez lastnega odjemalca in brez zbiranja vsebine.«*

**Največ 5 ključnih odprtih vprašanj (lastnik jih mora rešiti pred razvojem):**
1. **Enota in model cene** (150 €/leto = kaj?) in ali MDM pomeni +X.
2. **GMS in Google enterprise:** ali imajo šole nadzor nad Google računom naprav (brez tega AMAPI ni mogoč)?
3. **Posledice in odgovornost:** kdo nosi odgovornost, če oddaljeni ukaz (wipe/kiosk) uniči tablico?
4. **Pravna podlaga:** DPIA, hramba metapodatkov, pogodbe z Google/Apple/Hetzner za podatke učencev.
5. **Kapaciteta vzdrževanja:** kdo bo 24/7 podpiral upravljanje naprav in varnostne posodobitve tvojega sistema?

---

## Ocena tehnične izvedljivosti in učinkovitosti

**1. Ali je obstoječo OSTC App/FastAPI mogoče razširiti?**
- [KODA] Aplikacija je **čisti spletni portal**: FastAPI + PostgreSQL + piškotne seje + RBAC + audit + multi-tenant. V njej **ni nobenega** elementa za upravljanje naprav (ni enrollmenta, push, certifikatov, ukazne vrste, poročanja naprav) — `app/` in `k8s/` to potrjujeta.
- **Kaj je smiselno dodati *aplikaciji*:** Faza 0 iz §5 (inventar + katalog politik + revizija). To je **dopolnilna funkcija** in se ujema s 4.1 (najmanjše zbiranje).
- **Kaj mora biti *ločeno*:** Android integracija (AMAPI → Googlove storitve) je smiselna kot **ločen modul/storitev** z lastnim varnostnim modelom (žetoni, webhook preverjanje, revizija ukazov), ne kot nekaj v obstoječih routerjih. Windows/Apple morata biti **ločena sistema** — ne dopolnilo iste kode.

**2. Učinkovitost glede na število naprav, pogostost ukazov, odzivnost, vzdrževanje, delo skrbnika:**
- [OCENA] **1–50 naprav, ukazi občasno:** obvladljivo, tudi na skromnem strežniku (marginalni strošek majhen).
- [OCENA] **Več šol, stotine naprav:** zahteva **fronto vrsto/workerje**, obdelavo webhookov, idempotentnost, revizijo in **opazovalnost**. Odzivnost je odvisna od **platforme (Google/Apple push)**, ne le od tvoje app — **ne moreš obljubiti takojšnje izvršitve**.
- [OCENA] **Vzdrževanje je bistveno težje kot pri današnji app**: OS/platformske spremembe (AMAPI različice), certifikati, varnostne posodobitve, 24/7 pričakovanja.

**3. Ozka grla in varnostna tveganja pri rasti 1 → več šol:**
- **Enrollment token** je deljiva skrivnost; **identiteta naprave** in **preklic** sta nujna.
- **Prevzem skrbniškega računa** = nadzor nad vsemi tablicami → MFA + ločeni računi [KODA: MFA manjka].
- **Revizija in zaščita pred replay** ukazov [KODA: ne obstaja].
- **Shramba dnevnikov** raste; **GDPR/DPIA** postane nujna.
- **Odvisnost od Googla/Appla** (»open-source« ne pomeni »brez velikih ponudnikov«).

**4. Končna ocena:**
> **Izvedljivo kot majhna dopolnilna funkcija** (Faza 0: inventar + katalog politik + revizija) — varno, poceni, ujema se z obstoječo arhitekturo.
> **Izvedljivo le kot večji, ločen MDM-produkt** za **Android-only prek AMAPI** (Faze 1–5) — tehnično izvedljivo, a zahteva nov varnostni model, MFA, revizijo ukazov, Googlove storitve in resno vzdrževanje.
> **Trenutno nerealistično** kot **univerzalni Intune-ov konkurent** (Windows + Apple + Android) — vsaka platforma je samostojen MDM projekt; obstoječa koda tega ne pokriva in je ni mogoče »samo dodati«.

---

### Kratek povzetek (za odločitev)
- **Ne obljubljaj** MDM, dokler ni enrollmenta, identitete naprave, ukaznega kanala in revizije — tega v repu **ni**. [KODA]
- **Najboljši prvi korak:** Faza 0 (inventar + katalog politik), ki je varen, poceni in uporaben tudi brez upravljanja naprav.
- **Realna niša:** Android-only prek Android Enterprise — **če** šole obvladajo Google račun naprav (GMS), sicer stroški eksplodirajo.
- **Gostovanje (Hetzner)** zmanjša stroške infrastrukture, **ne** odpravi stroškov Googla/Appla/Microsofta, razvoja, podpore in pravne skladnosti.
- **Pred razvojem nujno:** razrešiti 5 odprtih vprašanj iz §7 (predvsem **enoto cene 150 €/leto** in **nadzor nad Google enterprise**).
