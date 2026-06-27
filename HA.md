# HA arhitektura — ostc-app (sola-app)

## Pregled

Aplikacija ostc-app teče v **k3s** Kubernetes clusterju na dveh nodih:
- **k3s-1** (193.2.171.250) — HP ProBook 455 G5
- **k3s-2** (193.2.171.249) — HP ProBook 450 G5

Cilj: ob izpadu kateregakoli noda aplikacija ostane dostopna v nekaj minutah brez ročnega posredovanja.

## Visoka razpoložljivost

### 1. Aplikacija (sola-app)

- **2 poda** — eden na vsakem nodu
- **Deployment** s `replicas: 2`
- Podi so razporejeni prek standardnega k3s schedulerja
- Ob izpadu noda k3s avtomatsko reschedule-a pod na preživeli node (čez ~5 min, odvisno od `pod-eviction-timeout`)
- **Health check** — `/health` endpoint, 200 OK ⇒ pod je ready

```
Kubernetes Deployment sola-app
├── Pod k3s-1 (10.42.0.x)
└── Pod k3s-2 (10.42.1.x)
```

### 2. Dostop (omrežje)

```
Internet → ostc-app.org (Cloudflare)
  ├── k3s-1:443 (nginx, SSL)  → Service LoadBalancer 193.2.171.200:8002 → app pod
  └── k3s-2:8080 (nginx)      → Service LoadBalancer 193.2.171.200:8002 → app pod
```

- **Cloudflare** kaže na LoadBalancer IP `193.2.171.200` (MetalLB)
- **Nginx** na obeh nodih proxy-pass-a na `193.2.171.200:8002`
- **Service tip LoadBalancer** (MetalLB) — fiksen IP, layer2 failover
- Ob izpadu enega noda MetalLB prevzame promet na drugem nodu

### 3. PostgreSQL baza — CloudNativePG (CNP)

Najpomembnejši del HA. Uporabljamo **CloudNativePG** operator.

```
CNP Cluster "sola-db"
├── sola-db-1 (primary)  → k3s-1  → ha/active=true
│   └── Storage: Longhorn PVC (1Gi, replicated)
└── sola-db-2 (replica)  → k3s-2
    └── Storage: Longhorn PVC (1Gi, replicated)

Services:
├── sola-db-rw → vedno na primary (pisanje + branje)
├── sola-db-ro → na vse ready instance (samo branje)
└── sola-db-r  → na vse instance
```

#### Auto-failover (vgrajen)

- **`failoverDelay: 30`** — če primarni pod pade, CNP počaka 30s in nato promovira replico v primary
- **`enablePDB: true`** — PodDisruptionBudget preprečuje hkratni izpad obeh podov
- **Replikacija** — streaming replication (sinhrona, `maxSyncReplicas: 0` = asinhrona, kar je OK za to aplikacijo)
- **Storage** — Longhorn (replicated volume, oba poda imata svoj PVC)

#### Potek failoverja

1. K3s-1 crkne → primarni pod `sola-db-1` postane nedosegljiv
2. CNP operator zazna izpad (30s `failoverDelay`)
3. CNP promovira `sola-db-2` (na k3s-2) v primary
4. Service `sola-db-rw` se avtomatsko preusmeri na `sola-db-2`
5. App na k3s-1: pod je mrtev → k3s ga reschedule-a na k3s-2
6. App na k3s-2: poveže se na `sola-db-rw` (ki kaže na `sola-db-2`) → deluje naprej

**Skupni čas izpada:** ~1–2 minuti (30s failover delay + ~30s za promocijo + čas, da k3s zazna mrtvi node)

#### Recovery po popravilu noda

Ko k3s-1 spet pride gor:
1. CNP samodejno opazi, da je na voljo nov node
2. Potreben je ročni `cnpg` ukaz ali pa se zna CNP sam popraviti (odvisno od konfiguracije)
3. Alternativa: izbriši stari `sola-db-1` PVC, CNP ga bo recreiral kot replico

### 4. Konfiguracija

**App povezava na bazo:**
```
DATABASE_URL=postgresql://sola:***@sola-db-rw.sola:5432/sola
```
Uporablja Service `sola-db-rw`, ki vedno kaže na trenutni primary.

**Aplikacijski secret:**
- Namespace: `sola-app`
- Secret: `sola-secrets`
- Vsebuje: `DATABASE_URL`, `MAIL_*`, `BACKUP_EMAIL`

**CNP Cluster:**
- Namespace: `sola`
- Ime: `sola-db`
- 2 instance, vsaka na svojem nodu
- Longhorn storage (1Gi)
- Auto-failover: 30s

### 5. Testiranje HA

Za simulacijo izpada:
```bash
# Ugasni en node (npr. k3s-1)
ssh k3s-1 "sudo poweroff"

# Preveri, da app ostane dostopen
curl -I https://ostc-app.org

# Po ~2 min preveri stanje
kubectl get pods -n sola -o wide      # sola-db-2 naj bo primary
kubectl get pods -n sola-app -o wide  # sola-app pod na k3s-2

# Ko je node spet gor, preveri stanje
kubectl get cluster -n sola sola-db    # CNP naj ima 2 ready instance
```

### 6. Pomembne opombe

- **Cloudflare** kaže na LoadBalancer IP `193.2.171.200` — če se ta IP spremeni, je treba posodobiti Cloudflare DNS
- **Nginx** na obeh nodih proxy-pass-a na LoadBalancer IP — če se IP spremeni, posodobi `/etc/nginx/sites-available/default`
- **Longhorn** replikacija PVC-jev — podatki so varni tudi ob izgubi enega noda (Longhorn replicira na oba noda)
- **Ni custom failover skript** — vse upravlja CNP operator
