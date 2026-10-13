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
3. **Koliko** to stane in **kdaj** vzeti 2 oz. 3 strežnike, da bo prava HA.

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

| Plan | vCPU | RAM | Disk (NVMe) | Cena/mesec (brez DDV) |
|------|------|-----|-------------|------------------------|
| CPX02 | 1 | 1 GB | 20 GB | €5.99 |
| CPX12 | 1 | 2 GB | 40 GB | €11.49 |
| **CPX22** | **2** | **4 GB** | **80 GB** | **€19.49** |
| CPX32 | 4 | 8 GB | 160 GB | €35.49 |
| CPX42 | 8 | 16 GB | 320 GB | €69.49 |

Za referenco, namenski CPU (CCX13 = 2 vCPU, 8 GB, 80 GB) = **€42.99/mesec** — toliko dražje samo
za namenski CPU, kar za nas ni potrebno.

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
- Ponovi za vsak node (nodi 2 in 3). Vsi v **isti lokaciji** in isto **private network**.
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
> Cene so okvirne; vedno preveri v Hetzner konzoli pred zakupom.

| Postavka | Cena/mesec |
|----------|-----------|
| CPX22 (2 vCPU, 4 GB, 80 GB) | €19.49 |
| CPX12 (1 vCPU, 2 GB, 40 GB) | €11.49 |
| Load Balancer LB11 (5 storitev, 25 tarč) | €7.49 |
| Dodaten IPv4 | €0.50 |
| IPv6 | €0 |
| Hetzner Backup | +20 % cene strežnika |
| Dodaten promet (nad 20 TB) | €1.00 / TB |
| Storage Box BX11 (1 TB, za backup baze) | ~€3.80 |

### Scenariji (skupni mesečni strošek)

| Scenarij | Sestava | Ocena/mesec |
|----------|---------|-------------|
| **A — 1 strežnik (ni HA)** | 1× CPX22 + IPv4 + backup | ~€24 |
| **B — 2 strežnika (skoraj-HA)** | 2× CPX22 + LB11 + 2× IPv4 + backup | ~€52 |
| **C — 3 strežniki (prava HA)** | 3× CPX22 + LB11 + 3× IPv4 + backup | ~€83 |
| **C-poceni** | 3× CPX12 + LB11 + backup | ~€56 |

(Na vse skupaj lahko dodaš še Storage Box ~€3.80 za backup baze.)

---

## 4. HA — kdaj 2, kdaj 3 strežniki?

Kratek odgovor: **za pravo HA vzemi 3.** Pojasnilo spodaj.

### Koliko vozlišč preživi izpad?

| Št. vozlišč (etcd) | Kvorum | Preživi izpad | HA? |
|--------------------|--------|---------------|-----|
| 1 | 1 | 0 vozlišč | ❌ SPOF |
| 2 | 2 | **0** (izgubiš kvorum za pisanje!) | ⚠️ ni prava HA |
| **3** | **2** | **1 vozlišče** | ✅ **ja** |

> 💡 **ELI5:** etcd je kot klub, kjer za vsako odločitev glasuje **večina**. Pri dveh članih
> večina pomeni *oba* → če eden zboli, klub ne more več odločati. Pri treh članih večina pomeni
> *dva* → eden lahko zboli, klub dela naprej. Zato je 3 "čarobno" število (2 ni, 1 seveda ne).

### Torej:

- **1 strežnik** = kvari se, ko se kvari. Primerno samo za test/dev ali za app, kjer je par ur
  izpada sprejemljivo.
- **2 strežnika** = **ni prave HA** za k3s. Pogosto napačen občutek varnosti: če crkne **app**
  node, drugi prevzame; če pa omrežje razdeli cluster na dvoje, ali če gresta v konflikt za
  tvorbo kvoruma, nastanejo težave. 2 strežnika sta smiselna le kot:
  - ločitev **app strežnik + baza strežnik** (a oba sta še vedno SPOF), ali
  - **produkcija + ločen staging/test**, ali
  - če za bazo uporabiš **zunanjo managed PostgreSQL** (in vozlišči ostaneta samo za app).
- **3 strežniki** = **najmanj za pravo HA**:
  - etcd kvorum 2/3 → cluster preživi izpad **enega** noda,
  - app teče v 2–3 replikah, ena na vsakem nodu,
  - CNPG primary + replike → failover na drugi node v ~1–2 min (`HA.md`),
  - Load Balancer sam preusmeri promet na živi node.

### Kdaj zakupiti kaj (priporočilo)

1. **Začni s 3× CPX22 takoj** — ker je "2 nodes" slabše kot "1 ali 3" z vidika kvoruma.
2. Če je proračun res omejen in toleriraš ~izpad ob izpadu enega noda: začni z **1× CPX22**
   (enostavno, poceni), nato **nadgradi na 3**, ko app postane kritičen (npr. med šolskim letom,
   ko se uporablja vsak dan).
3. Nikoli se ne ustavljaj pri **2** kot končni rešitvi za HA — to je najslabše razmerje
   varnost/cena.

### Kaj pa baza ločeno?

Če želiš manj skrbi z bazo, lahko PostgreSQL nadomestiš z **zunanjo managed bazo**
(Neon / Supabase / Railway Postgres, ~€0–20/mesec). Takrat imaš 2–3 vozlišča samo za app, baza pa
je skrb ponudnika. Prednost: manj vzdrževanja. Slabost: podatki so spet v tujem cloudu in dodaten
mesečni strošek.

---

## 🎯 Povzetek priporočila

| Vprašanje | Odgovor |
|-----------|---------|
| Kateri strežnik? | **CPX22** (2 vCPU, 4 GB, 80 GB), lokacija NGB1, Ubuntu 24.04 |
| Kako prestavim app? | Nov k3s (3-node, `--cluster-init`) + Hetzner CCM/CSI → isti manifesti → `pg_dump`/`pg_restore` → preklop DNS (koraki zgoraj) |
| Koliko stane? | HA postavitev (3× CPX22 + LB) ~**€83/mesec**; poceni 3-node ~€56; en strežnik ~€24 |
| Kdaj 2, kdaj 3? | **2 ni HA** (etcd kvorum). Vzemi **3** za pravo HA; 1 za test; nikoli 2 kot končno |

---

> **Avtor:** Matej Čušin
