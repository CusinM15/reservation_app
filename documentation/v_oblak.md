🌐 **Jezik / Language:** 🇸🇮 Slovenščina

---

> ⚠️ **Opomba:** IP naslovi, gesla, e-pošta in domena so v tej dokumentaciji zamenjani z
> zgledi (npr. `{{DOMAIN}}`, `{{LB_IP}}`). Za dejanske vrednosti preveri Kubernetes
> Secrets in Cloudflare.

---

# ☁️ V oblak — Hetzner

Ta dokument odgovori na tri vprašanja:

1. **Kateri** Hetzner strežnik izbrati (in zakaj).
2. **Kako** prestaviti aplikacijo (ostc-app / sola-app) iz domačega k3s clustra v Hetzner.
3. **Koliko** to stane (mesečno **in letno**) in **kdaj** vzeti 1 ali 3 strežnike (2 strežnika **nista** HA).

Za splošno primerjavo vseh možnosti (Railway, Coolify, managed k8s …) glej `migracija_oblak.md`.
Ta dokument se ukvarja samo s Hetznerjem, ker je najcenejši "svoj strežnik" v EU.

---

## 1. Kateri strežnik izbrati?

Hetzner ima tri družine **Cloud** strežnikov:

| Družina | Vrsta CPU | Za kaj je | Naša uporaba |
|---------|-----------|-----------|--------------|
| **CX / CAX** (Cost-Optimized) | deljen CPU (Intel/AMD) oz. ARM (Ampere) | test, spletne strani | ❌ **trenutno ni na voljo** (Hetzner jih ne prodaja) |
| **CPX** (Regular Performance) | deljen AMD | male baze, app z nizko/srednjo obremenitvijo | ✅ **to izberi** |
| **CCX** (General Purpose) | **namenjen** CPU | visoka, stalna obremenitev | ❌ predrago za šolsko app |

> 💡 **ELI5:** CPX je kot najem avta v skupni rabi (deljen motor z "sosedi"), CCX je kot lasten
> avto (motor je samo tvoj, zato 2–5× dražji). Za eno šolsko aplikacijo s ~100–200 uporabniki
> je CPX več kot dovolj.

### Cenik CPX (deljen AMD, 20 TB prometa vključenega)

| Plan | vCPU | RAM | Disk (NVMe) | Cena/mesec (brez DDV) | Cena/leto (brez DDV) |
|------|------|-----|-------------|------------------------|-----------------------|
| CPX02 | 1 | 1 GB | 20 GB | €5.99 | €71.88 |
| CPX12 | 1 | 2 GB | 40 GB | €11.49 | €137.88 |
| **CPX22** | **2** | **4 GB** | **80 GB** | **€19.49** | **€233.88** |
| CPX32 | 4 | 8 GB | 160 GB | €35.49 | €425.88 |
| CPX42 | 8 | 16 GB | 320 GB | €69.49 | €833.88 |

Za referenco, namenski CPU (CCX13 = 2 vCPU, 8 GB, 80 GB) = **€42.99/mesec** oz. **€515.88/leto** —
toliko dražje samo za namenski CPU, kar za nas ni potrebno.

### 🎯 Priporočilo

- **CPX22** (2 vCPU, 4 GB, 80 GB) — sladka točka. Dovolj za k3s + app + PostgreSQL.
- Lokacija: **NBG1 / FSN1 (Nürnberg / Falkenstein, Nemčija)** ali **HEL1 (Helsinki)**.
  Vse je v EU → GDPR. Vzemi nemško lokacijo (bližje Sloveniji, nižja latenca).
- Operacijski sistem: **Ubuntu 24.04 LTS** (isto kot zdaj na k3s-1/k3s-2 — navodila v
  `k3s-setup.md` in `dodajanje-noda.md` ostanejo nespremenjena).
- Vzemi **isto lokacijo in isto zasebno mrežo (private network)** za vse node, da se
  pogovarjajo po internem IP-ju in ne po internetu.

---

## 2. Kako prestaviti aplikacijo v Hetzner?

Aplikacija je že pripravljena za k3s (isti YAML-i, isti `deploy-prod.sh`, isti Argo CD). Zato
**ničesar v aplikaciji ne spreminjamo** — samo znova postavimo k3s cluster v cloudu in prenesemo
podatke.

### Korak 0 — Preden začneš
- Hetzner račun (https://www.hetzner.com — registracija, plačilo s kartico).
- V konzoli **naredi projekt** in **naloži svoj javni SSH ključ** (`.pub`). Zasebni ključ ostane
  pri tebi.
- Zmanjšaj TTL na DNS zapisu domene (npr. na 300 s) dan prej — da bo preklop hiter.

### Korak 1 — Zakup strežnikov
- V konzoli: **Add Server** → lokacija NBG1 → **CPX22** → image **Ubuntu 24.04** → dodaj SSH ključ
  → ustvari.
- Za HA ponovi za vsak node (**skupaj 3**). Vsi v **isti lokaciji** in isto **private network**.
- Vklopi **Backups** (Hetzner sam dela posnetke, +20 % cene strežnika).

### Korak 2 — Firewall
V Hetzner konzoli → **Firewalls**, dovoli:
- `22/tcp` (SSH) — omeji na svoj IP, če se da,
- `80/tcp`, `443/tcp` (splet),
- `6443/tcp` in etcd/K8s porte **samo med nodi** (interno).

### Korak 3 — k3s cluster (3-node HA)
Na **node1**:
```bash
curl -sfL https://get.k3s.io | sh -s - server --cluster-init
```
Na **node2 in node3** (token preberi na node1: `sudo cat /var/lib/rancher/k3s/server/node-token`):
```bash
curl -sfL https://get.k3s.io | K3S_URL=https://{{NODE1_IP}}:6443 K3S_TOKEN={{TOKEN}} sh -s - server
```
Preveri (na node1): `kubectl get nodes`
```
NAME    STATUS   ROLES                VERSION
k3s-1   Ready    control-plane,etcd   v1.35.5+k3s1
k3s-2   Ready    control-plane,etcd   v1.35.5+k3s1
k3s-3   Ready    control-plane,etcd   v1.35.5+k3s1
```
> To je praktično isto kot v `dodajanje-noda.md`, samo da je treba `--cluster-init` na prvem.

### Korak 4 — Load Balancer + storage (Hetzner CCM + CSI)
V domačem clustru uporabljamo **MetalLB** in **Longhorn**. V Hetznerju to zamenjamo:
- **hcloud-cloud-controller-manager** — da Kubernetes `type: LoadBalancer` sam ustvari Hetzner
  Load Balancer (namesto MetalLB).
- **hcloud CSI driver** — za `PersistentVolumeClaim` → Hetzner Volume (namesto Longhorn).

```bash
# cloud-controller-manager (LoadBalancer) in CSI (volumes) — helmet po uradnih navodilih Hetznerja
# (glej https://github.com/hetznercloud/hcloud-cloud-controller-manager)
```

> ⚠️ **Pomembno za bazo:** Hetzner Volume je **ReadWriteOnce** in se pripne na **en** node. Ob
> failoverju CNPG volumen odklopi in pripne na nov node — deluje, a failover je malo počasnejši
> (par sekund več). Alternativa je ostati na **Longhorn** (replikacija čez node), a Longhorn v
> cloudu rabi dodaten disk — manj priporočljivo. Za začetek: **hcloud CSI + CNPG**.

### Korak 5 — Namespace, secrets, baza, app
```bash
kubectl create namespace sola-app
kubectl create namespace sola
```
- Ustvari **Secret `sola-secrets`** (`DATABASE_URL`, `MAIL_*`, `BACKUP_*`) — enako kot zdaj.
- Namesti **CNPG operator** in `sola-db` cluster. Za resno HA: **3 instance** (vsaka na svojem
  nodu) → baza preživi izpad enega noda.
- Deploy app (isti manifesti kot v `k8s/`, ali prek **Argo CD** — `k8s/cluster/...`).
- TLS: Cloudflare origin cert ali `cert-manager` (Let's Encrypt).

### Korak 6 — Prenos podatkov (baze)
Na **starem** clustru:
```bash
kubectl exec -n sola deploy/sola-db-1 -- pg_dump -U sola sola > sola-dump.sql
```
Prenesi na nov cluster in uvozi:
```bash
kubectl exec -i -n sola <novi-primary-pod> -- psql -U sola sola < sola-dump.sql
```
Preveri (isti poizvedbi kot v `HA.md`): število rezervacij, `SELECT MIN/MAX FROM reservations;`.

### Korak 7 — Preklop
1. Preveri, da nov cluster dela prek `curl -I https://{{LB_IP}}` (še brez domene).
2. V Cloudflare usmeri domeno `{{DOMAIN}}` na nov **LB IP**.
3. Opazuj par dni. Stari cluster pusti prižgan (samo kot rezervo), potem ugasni.

### Korak 8 — Backup
- **Hetzner Backups** (posnetki celih strežnikov, +20 %).
- **pg_dump** po cronu na **Hetzner Storage Box** (npr. BX11, 1 TB) — za dolgoročne kopije baze.

---

## 3. Cene (Hetzner cenik, 2026, EUR brez DDV, 20 TB prometa vključenega)

> Kot zavezanec za DDV (s.p.) si DDV odbijaš → relevantna je cena **brez DDV**.
> Cene so okvirne; vedno preveri v Hetzner konzoli pred zakupom. **Letni znesek = mesečni × 12.**

| Postavka | Cena/mesec | Cena/leto |
|----------|-----------|-----------|
| CPX22 (2 vCPU, 4 GB, 80 GB) | €19.49 | €233.88 |
| CPX12 (1 vCPU, 2 GB, 40 GB) | €11.49 | €137.88 |
| Load Balancer LB11 (5 storitev, 25 tarč) | €7.49 | €89.88 |
| Dodaten IPv4 | €0.50 | €6.00 |
| IPv6 | €0 | €0 |
| Hetzner Backup | +20 % cene strežnika | +20 % cene strežnika |
| Dodaten promet (nad 20 TB) | €1.00 / TB | €12.00 / TB |
| Storage Box BX11 (1 TB, za backup baze) | ~€3.80 | ~€45.60 |
| Domena | ~€1.00 | ~€12.00 |

### Scenariji (skupni strošek)

| Scenarij | Sestava | Ocena/mesec | **Ocena/leto** |
|----------|---------|-------------|-----------------|
| **A — 1 strežnik (ni HA)** | 1× CPX22 + IPv4 + backup | ~€24 | **~€287** |
| **C — 3 strežniki (prava HA)** | 3× CPX22 + LB11 + 3× IPv4 + backup | ~€79 | **~€950** |
| **C-poceni (3-node)** | 3× CPX12 + LB11 + backup | ~€50 | **~€604** |

(Če dodaš še Storage Box za backup baze: +€3.80/mesec = +€45.60/leto.)

> ℹ️ **Zakaj ni scenarija z 2 strežnikoma?** Ker **2 strežnika nista HA** — glej razdelek 4.
> 2 vozlišči v etcd pomenita kvorum 2; ko en odpove, izgubiš kvorum za pisanje. Zato izbiramo
> **1 (test/poceni, ni HA)** ali **3 (prava HA)** — 2 je najslabše razmerje varnost/cena.

### 💶 Letni stroški in primerjava z zdajšnjo postavitvijo

- **Ena šola porabi zelo malo:** ~**0,2 GB RAM**, ~**0,2 vCPU**, **< 1 GB diska**
  (`deploy/oracle/README.md`) — torej strošek **ne raste** linearno s številom šol.
- **Ena šola porabi približno toliko, kot se trenutno porablja na 2 HP prenosnikih** — trenutna
  celotna postavitev (k3s na 2 prenosnikih) teče za oceno **~€15–25/mesec** (elektrika +
  amortizacija strojne opreme) = **~€180–300/leto** (`migracija_oblak.md`).
- **Primerjava letno:**
  | Postavitev | Letni strošek | HA? |
  |------------|---------------|-----|
  | Zdaj (2 HP prenosnika doma) | ~€180–300 | ⚠️ odvisno od doma |
  | Hetzner 1 strežnik + backup | ~€287 | ❌ ne |
  | Hetzner 3 strežniki (HA) | ~€950 | ✅ ja |
  | + Storage Box (backup baze) | +€45.60 | – |
  | + domena | +€12 | – |

### 💰 Zaslužek glede na število šol

Predpostavka: **naročnina 150 €/šola/leto** (privzeto v `app_settings.py`). Fiksni letni strošek
za HA postavitev ≈ **€1.000/leto** (3× CPX22 + LB + Storage Box + domena). Prihodek je samo od
naročnin.

| Šol | Prihodek/leto (150/šola) | Letni strošek (HA) | **Zaslužek (bruto)** |
|-----|--------------------------|--------------------|-----------------------|
| 1 | €150 | ~€1.000 | **−€850** |
| 3 | €450 | ~€1.000 | **−€550** |
| 5 | €750 | ~€1.000 | **−€250** |
| **7** | **€1.050** | **~€1.000** | **≈ €0 (prag)** |
| 10 | €1.500 | ~€1.000 | **+€500** |
| 20 | €3.000 | ~€1.000 | **+€2.000** |
| 50 | €7.500 | ~€1.000 | **+€6.500** |

**Prag dobička (HA):** ~**7 šol**. **Prag dobička (1 strežnik, ~€345/leto):** ~**3 šole**.

> ⚠️ **Zaslužek ≠ čisti dobiček.** Zneski **ne vključujejo**: razvoja, podpore, davkov/DDV in
> tvojega dela. Prihodek pokrije **le infrastrukturo**; razvoj in podpora sta ločena postavka.
> Zneski so ocene (brez DDV) in jih je treba preveriti pred odločitvijo o ceni.

---

## 4. HA — kdaj 1, kdaj 3 strežniki?

Kratek odgovor: **za pravo HA vzemi 3. 2 strežnika nista HA.**

### Koliko vozlišč preživi izpad?

| Št. vozlišč (etcd) | Kvorum | Preživi izpad | HA? |
|--------------------|--------|---------------|-----|
| 1 | 1 | 0 vozlišč | ❌ SPOF |
| 2 | 2 | **0** (izgubiš kvorum za pisanje!) | ⚠️ **ni HA** |
| **3** | **2** | **1 vozlišče** | ✅ **ja** |

> 💡 **ELI5:** etcd je kot klub, kjer za vsako odločitev glasuje **večina**. Pri dveh članih
> večina pomeni *oba* → če eden zboli, klub ne more več odločati. Pri treh članih večina pomeni
> *dva* → eden lahko zboli, klub dela naprej. Zato je 3 "čarobno" število (2 ni, 1 seveda ne).

### Torej:

- **1 strežnik** = kvari se, ko se kvari. Primerno samo za test/dev ali za app, kjer je par ur
  izpada sprejemljivo.
- **2 strežnika = NI HA.** Kvorum 2 pomeni, da ob izpadu enega vozlišča ostaneš brez kvoruma za
  pisanje — torej nimaš HA, imaš pa dvakratni strošek. **Ne uporabljaj 2 kot končno rešitev.**
- **3 strežniki** = **najmanj za pravo HA**:
  - etcd kvorum 2/3 → cluster preživi izpad **enega** noda,
  - app teče v 2–3 replikah, ena na vsakem nodu,
  - CNPG primary + replike → failover na drugi node v ~1–2 min (`HA.md`),
  - Load Balancer sam preusmeri promet na živi node.

### Kdaj zakupiti kaj (priporočilo)

1. **Začni s 3× CPX22 takoj** — ker je 3 edino pravo število za HA (1 ali 3; nikoli 2).
2. Če je proračun res omejen in toleriraš ~izpad ob izpadu enega noda: začni z **1× CPX22**
   (enostavno, poceni, **ni HA**), nato **nadgradi na 3**, ko app postane kritičen (npr. med
   šolskim letom, ko se uporablja vsak dan).

### Kaj pa baza ločeno?

Če želiš manj skrbi z bazo, lahko PostgreSQL nadomestiš z **zunanjo managed bazo**
(Neon / Supabase / Railway Postgres, ~€0–20/mesec oz. ~€0–240/leto). Takrat imaš 3 vozlišča samo
za app, baza pa je skrb ponudnika. Prednost: manj vzdrževanja. Slabost: podatki so spet v tujem
cloudu in dodaten mesečni strošek.

---

## 🎯 Povzetek priporočila

| Vprašanje | Odgovor |
|-----------|---------|
| Kateri strežnik? | **CPX22** (2 vCPU, 4 GB, 80 GB), lokacija NGB1, Ubuntu 24.04 |
| Kako prestavim app? | Nov k3s (3-node, `--cluster-init`) + Hetzner CCM/CSI → isti manifesti → `pg_dump`/`pg_restore` → preklop DNS (koraki zgoraj) |
| Koliko stane (leto)? | HA (3× CPX22 + LB) ~**€950/leto**; poceni 3-node ~€604/leto; 1 strežnik (ni HA) ~€287/leto |
| Kdaj 1, kdaj 3? | **2 ni HA** (etcd kvorum). Za pravo HA vzemi **3**; 1 le za test/poceni |
| Kdaj dobiček? | Prag ~**7 šol** (HA) oz. ~**3 šole** (1 strežnik), pri 150 €/šola/leto |

---

> **Avtor:** Matej Čušin
