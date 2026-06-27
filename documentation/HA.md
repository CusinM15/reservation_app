🌐 **Jezik / Language:** [🇸🇮 Slovenščina](HA.md) | [🇬🇧 English](en/HA.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# HA arhitektura — ostc-app (sola-app)

## Pregled

Aplikacija ostc-app teče v **k3s** Kubernetes clusterju na dveh nodih:
- **k3s-1** ({{K3S_1_IP}}) — HP ProBook 455 G5
- **k3s-2** ({{K3S_2_IP}}) — HP ProBook 450 G5

Cilj: ob izpadu kateregakoli noda aplikacija ostane dostopna v nekaj minutah brez ročnega posredovanja.

## Visoka razpoložljivost

### 1. Aplikacija (sola-app)

- **2 poda** — eden na vsakem nodu
- **Deployment** s `replicas: 2`
- Podi so razporejeni prek standardnega k3s schedulerja
- Ob izpadu noda k3s avtomatsko reschedule-a pod na preživeli node
- **Health check** — `/health` endpoint, 200 OK ⇒ pod je ready

```
Kubernetes Deployment sola-app
├── Pod k3s-1 (10.42.0.x)
└── Pod k3s-2 (10.42.1.x)
```

### 2. Dostop (omrežje)

```
Internet → {{DOMAIN}} (Cloudflare)
                │
                ▼
   Service LoadBalancer {{LB_IP}}:{{LB_PORT}} (MetalLB)
                │
        ┌───────┴───────┐
        ▼               ▼
   app pod (k3s-1)  app pod (k3s-2)
```

- **Cloudflare** proxy-a na LoadBalancer IP `{{LB_IP}}` (MetalLB, port 80)
- **Service tip LoadBalancer** (MetalLB) — fiksen IP, layer2 failover
- Ob izpadu enega noda MetalLB prevzame promet na drugem nodu

### 3. PostgreSQL baza — CloudNativePG (CNPG)

Najpomembnejši del HA. Uporabljamo **CloudNativePG** operator.

```
CNPG Cluster "sola-db"
├── sola-db-1 (primary)  → k3s-1
│   └── Storage: Longhorn PVC (1Gi)
├── sola-db-2 (replica)  → k3s-2
│   └── Storage: Longhorn PVC (1Gi)

Services:
├── sola-db-rw → vedno na primary (pisanje + branje)
├── sola-db-ro → na vse ready instance (samo branje)
└── sola-db-r  → na vse instance
```

**Kako delujejo:**

|  | Service | Cilj | Namen | Uporaba v appu |
|---|---|---|---|---|
|| `sola-db-rw` | **Samo primary** (npr. `sola-db-1`) | Pisanje + branje — edini service, ki sprejema `INSERT`/`UPDATE`/`DELETE`. Vedno kaže na trenutni primary, tudi po failoverju. | `DATABASE_URL` — glavna povezava za vse operacije |
|| `sola-db-ro` | **Vse ready instance** (primary + replica) | **Samo branje** — Kubernetes Service porazdeljuje bralne zahtevke (`SELECT`) med primary in repliko. Uporabno za obremenitve z veliko branja. | `DATABASE_URL_RO` — redko rabljen, večinoma za poročila |
|| `sola-db-r` | **Vse instance** (tudi tiste, ki še niso ready) | **Samo branje** — podobno kot `ro`, a vključuje tudi instance, ki še niso označene kot ready. Manj relevanten za vsakodnevno uporabo. | — |

Primarna razlika: `sola-db-rw` je **edini**, ki sprejema zapisovanje. `sola-db-ro` in `sola-db-r` sta samo za branje in se uporabljata, če želiš razbremeniti primary z bralnimi poizvedbami. V praksi app uporablja izključno `sola-db-rw` prek `DATABASE_URL`.

#### Auto-failover (vgrajen)

- **`failoverDelay: 30`** — če primarni pod pade, CNPG počaka 30s in nato promovira repliko v primary
- **`enablePDB: true`** — PodDisruptionBudget preprečuje hkratni izpad obeh podov
- **Replikacija** — streaming replication, asinhrona (OK za to aplikacijo)
- **Storage** — Longhorn, vsaka instanca ima svoj PVC
- **Node anti-affinity** — `podAntiAffinityType: preferred` na `kubernetes.io/hostname`

#### Potek failoverja

1. K3s-1 crkne → primarni pod `sola-db-1` postane nedosegljiv
2. CNPG operator zazna izpad (30s `failoverDelay`)
3. CNPG promovira `sola-db-2` (na k3s-2) v primary (~2 minuti)
4. Service `sola-db-rw` se avtomatsko preusmeri na `sola-db-2`
5. App na k3s-1: pod je mrtev → k3s ga reschedule-a na k3s-2
6. App na k3s-2: poveže se na `sola-db-rw` (ki kaže na `sola-db-2`) → deluje naprej

**Skupni čas izpada:** ~1–2 minuti (30s failover delay + ~30s za promocijo + čas, da k3s zazna mrtvi node)

#### Recovery po popravilu noda

Ko k3s-1 spet pride gor:
1. CNPG samodejno opazi, da je na voljo nov node
2. `sola-db-1` se samodejno pridruži kot **replika** (brez ročnega posega!)
3. CNPG upravlja celoten proces — ni potreben ročen `cnpg` ukaz

### 4. Konfiguracija

**App povezava na bazo:**
```
DATABASE_URL=postgresql://sola:PASSWORD@sola-db-rw.sola:{{K8S_DB_PORT}}/sola
```
Uporablja Service `sola-db-rw`, ki vedno kaže na trenutni primary.

**Aplikacijski secret:**
- Namespace: `sola-app`
- Secret: `sola-secrets`
- Vsebuje: `DATABASE_URL`, `MAIL_*`, `BACKUP_EMAIL`

**CNPG Cluster:**
- Namespace: `sola`
- Ime: `sola-db`
- 2 instance, vsaka na svojem nodu
- Longhorn storage (1Gi)
- Auto-failover: 30s

**Operator:**
- Namespace: `cnpg-system`
- Ime: `cnpg/cloudnative-pg`
- Verzija: helm chart, najnovejša stabilna

### 5. Testiranje HA

Za simulacijo izpada:
```bash
# Ugasni en node (npr. k3s-1)
ssh k3s-1 "sudo poweroff"

# Preveri, da app ostane dostopen
curl -I https://{{DOMAIN}}

# Po ~2 min preveri stanje
kubectl get pods -n sola -o wide      # sola-db-2 naj bo primary
kubectl get pods -n sola-app -o wide  # sola-app pod na k3s-2

# Ko je node spet gor, preveri stanje
kubectl get cluster -n sola sola-db    # CNPG naj ima 2 ready instance
```

### 6. Pomembne opombe

- **Cloudflare** kaže na LoadBalancer IP `{{LB_IP}}` — če se ta IP spremeni, je treba posodobiti Cloudflare DNS
- **Longhorn** poskrbi za PVC-je — podatki so varni tudi ob izgubi enega noda
- **Ni custom failover skript** — vse upravlja CNPG operator
- **Failover je popolnoma avtomatski** — ni potrebno ročno posredovanje
- **Stara Bitnami PostgreSQL** je bila odstranjena po migraciji na CNPG
