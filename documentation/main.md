🌐 **Jezik / Language:** [🇸🇮 Slovenščina](main.md) | [🇬🇧 English](en/main.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

> 🛠️ **Prilagodi dokumentacijo svojim IP-jem**
>
> Vsa dokumentacija uporablja centralno datoteko `.env.ip`, kjer so definirani
> vsi IP-naslovi, porti in domene. Želiš dokumentacijo s svojimi podatki?
>
> ```bash
> cd documentation
> nano .env.ip                          # vnesi svoje IP-je
> ./replace-ips.sh                      # dokumentacija se prilagodi
> ```
>
> Skripta zamenja vse IP-je v `.md` datotekah. Po zagonu lahko komande
> neposredno kopiraš in prilepiš v terminal — delujejo brez spreminjanja.

---

# 🚀 **ostc-app — Rezervacijski sistem**
## **OŠ Toneta Čufarja — Dokumentacija**

---

## 📚 **Kazalo dokumentacije**

Ta datoteka je **glavni vstopni dokument**. Spodaj so povezave na specializirane poddokumente:

| Dokument | Opis |
|---|---|
| [🏗️ **HA arhitektura**](HA.md) | CloudNativePG, avtomatski failover, potek ob izpadu noda |
| [🌞 **Poletna pavza**](POLETNA_PAVZA.md) | Varen izklop k3s clustra čez poletje in ponoven vklop jeseni |
| [☁️ **Domena in DNS**](domena.md) | Nastavitev domene, Cloudflare, DNS zapisi |
| [🐍 **Postavi lokalni app**](postavi-lokalni-app.md) | Namestitev na enem računalniku (brez Kubernetes) |
| [☸️ **K3s setup**](k3s-setup.md) | Namestitev k3s clustra iz nič |
| [⚙️ **Admin/devops navodila**](admin-devops-navodila.md) | Vzdrževanje, posodabljanje, odpravljanje težav |
| [👩‍🏫 **Navodila za učitelje**](navodila-ucitelji.md) | Uporaba aplikacije — rezervacije in ocenjevanja |
| [👑 **Navodila za vodstvo**](navodila-vodstvo.md) | Upravljanje prek brskalnika (serije, zasedeni datumi) |
| [📱 **Opis aplikacije**](aplikacija-rezervacije.md) | Kaj aplikacija omogoča, namen, funkcionalnosti |
| [📖 **Navodila za uporabnika**](navodila-uporabnika.md) | Prijava, gesla, dnevna uporaba |

---

## 📑 **Kazalo vsebine** (ta dokument)
1. [Arhitektura sistema](#arhitektura-sistema)
2. [Strojna oprema in omrežje](#strojna-oprema-in-omrežje)
3. [Kubernetes (k3s) Cluster](#kubernetes-k3s-cluster)
4. [Aplikacija Sola App](#aplikacija-sola-app)
5. [PostgreSQL HA — CloudNativePG](#postgresql-ha--cloudnativepg)
6. [MetalLB LoadBalancer](#metallb-loadbalancer)
7. [Cloudflare DNS](#cloudflare-dns)
8. [Longhorn Storage](#longhorn-storage)
9. [Dnevni backup in reporti](#dnevni-backup-in-reporti)
10. [Vzdrževanje in okvare](#vzdrževanje-in-okvare)
11. [Celoten sklic ukazov](#celoten-sklic-ukazov)

---

## 🏗️ **Arhitektura sistema**

### **Strojna in omrežna shema**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         K3S KUBERNETES CLUSTER (2 noda)                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────┐    ┌──────────────────────────┐            │
│  │    k3s-1                 │    │    k3s-2                 │            │
│  │    HP ProBook 455 G5     │    │    HP ProBook 450 G5     │            │
│  │    IP: {{K3S_1_IP}}      │    │    IP: {{K3S_2_IP}}      │            │
│  │    control-plane,etcd    │    │    control-plane,etcd    │            │
│  │                          │    │                          │            │
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ sola-app Pod 1    │   │    │  │ sola-app Pod 2    │   │            │
│  │  │ (app.{{DOMAIN}})  │   │    │  | (app.{{DOMAIN}})  │   │            │
│  │  └───────────────────┘   │    │  └───────────────────┘   │            │
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ sola-db-1         │   │    │  │ sola-db-2         │   │            │
│  │  │ (PG PRIMARY)      │◄──┼────┼──┤ (PG REPLICA)      │   │            │
│  │  │ CNPG Instance     │   │    │  │ CNPG Instance     │   │            │
│  │  └───────────────────┘   │    │  └───────────────────┘   │            │
│  │                          │    │                          │            │
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ Longhorn          │   │    │  │ Longhorn          │   │            │
│  │  │ Instance Manager  │   │    │  │ Instance Manager  │   │            │
│  │  └───────────────────┘   │    │  └───────────────────┘   │            │
│  │                          │    │                          │            │
│  │  └───────────────────┘   │    │  └───────────────────┘   │            │
│  └──────────────────────────┘    └──────────────────────────┘            │
│                    ┌─────────────┘                                       │
│                    │                                                     │
│  ┌─────────────────▼────────────────────────────────────────────┐        │
│  │        Service LoadBalancer (MetalLB, {{LB_IP}}:{{LB_PORT}}) │        │
│  │        → sola-app Pod 1 ali Pod 2                            │        │
│  └──────────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────────────────┐
                    │  Cloudflare DNS               │
                    │  {{DOMAIN}}                   │   
                    │  → {{LB_IP}}:{{LB_PORT}}  │  📡 Cloudflare proxy
                    │    (LoadBalancer)          │
                    └───────────────────────────────┘
                              │
                              │  Internet
                              ▼
```

> **Opomba:** Oba noda sta `control-plane, etd` — ni ločenih worker nodov. k3s poganjanje uporabniških podov tudi na control-plane nodih.

### **Prometni tok**

```
🌐 Uporabnik
  → Cloudflare (SSL, proxy, {{DOMAIN}})
    → Service LoadBalancer (MetalLB, {{LB_IP}})
      → sola-app Pod (k3s-1 ali k3s-2)

Alternativna pot (interno omrežje):
  → http://{{LB_IP}}:{{LB_PORT}} → direkt na LoadBalancer
```

> **Cloudflare proxy** kaže direktno na **LoadBalancer (`{{LB_IP}}`, port 80)**.
> **HA zagotavlja MetalLB** — layer2 failover: če node z LB IP-jem crkne, drug
> node avtomatsko prevzame IP v nekaj sekundah.
### **Pregled komponent**

| Komponenta | Lokacija | Namen |
|---|---|---|
| **k3s-1** | HP ProBook 455 G5 ({{K3S_1_IP}}) | Control-plane, app pod, PG primary |
| **k3s-2** | HP ProBook 450 G5 ({{K3S_2_IP}}) | Control-plane, app pod, PG replica |
| **Sola App (FastAPI)** | 2 poda (oba noda) | Rezervacije, ocenjevanje, prijava |
| **Longhorn** | Oba noda | Distribuirano shranjevanje (PVC-ji) |
| **MetalLB** | Oba noda | LoadBalancer IP ({{LB_IP}}) |
| **Cloudflare** | Zunanji | DNS, SSL, proxy |

---

## 💻 **Strojna oprema in omrežje**

### **Specifikacije**

| Node | Model | CPU | RAM | Disk | Vloga |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Control-plane,etcd, app, PG primary |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Control-plane,etcd, app, PG replica |

### **Omrežne nastavitve**

```bash
# Lokalno omrežje (Arnes)
k3s-1: {{K3S_1_IP}}/24
k3s-2: {{K3S_2_IP}}/24
Gateway: {{K3S_2_IP}}54
DNS: {{K3S_2_IP}}53

# Kubernetes Pod CIDR
10.42.0.0/16

# Kubernetes Service CIDR
10.43.0.0/16

# LoadBalancer IP pool (MetalLB)
{{METALLB_RANGE_START}} - {{METALLB_RANGE_END}}
```

### **Dostop**

```bash
# SSH v oba noda
ssh admin@{{K3S_1_IP}}    # k3s-1
ssh admin@{{K3S_2_IP}}    # k3s-2

# Kubernetes (k3s) — kubeconfig je na obeh nodih
kubectl get nodes -o wide
kubectl get pods -A -o wide

# Aplikacija v brskalniku
https://{{DOMAIN}}          # prek Cloudflare + LoadBalancer
http://{{LB_IP}}:{{LB_PORT}}     # direkt (samo interno omrežje)
```

---

## ☸️ **Kubernetes (k3s) Cluster**

### **Stanje nodov**

```bash
kubectl get nodes -o wide

# NAME    STATUS   ROLES                       AGE   VERSION        INTERNAL-IP      EXTERNAL-IP
# k3s-1   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_1_IP}}    <none>
# k3s-2   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_2_IP}}    <none>
```

### **Namestitev k3s**

```bash
# Na k3s-1 (prvi node)
curl -sfL https://get.k3s.io | sh -s - server \
  --cluster-init \
  --disable=traefik \
  --node-ip={{K3S_1_IP}} \
  --flannel-iface=eth0

# Na k3s-2 (drugi node)
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://{{K3S_1_IP}}:6443 \
  --disable=traefik \
  --node-ip={{K3S_2_IP}} \
  --flannel-iface=eth0 \
  --token <NODE_TOKEN>
```

Token dobite z: `sudo cat /var/lib/rancher/k3s/server/node-token` (na k3s-1).

> **Opomba:** `--disable=traefik` izklopi vgrajeni ingress, ker uporabljamo MetalLB LoadBalancer.

---

## 🚀 **Aplikacija Sola App**

### **Deployment**

Namespace: `sola-app`

```bash
kubectl get deployments -n sola-app
kubectl get pods -n sola-app -o wide
kubectl get services -n sola-app
```

Aplikacija teče v **dveh podih** (ena na vsakem nodu):

```bash
kubectl get pods -n sola-app -o wide

# NAME                        READY   STATUS    RESTARTS   AGE   IP           NODE
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.0.x    k3s-1
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.1.x    k3s-2
```

### **Docker Image**

- **Image:** `sola-app:latest`
- **Dockerfile:** `reservation_app/k8s/Dockerfile`
- **Deployment YAML:** `reservation_app/k8s/sola-app.yaml`

### **Posodobitev aplikacije**

```bash
cd reservation_app
git pull
# Počakaj, da se CI build konča (GitHub Actions)
# al pa ročno:
kubectl rollout restart deployment -n sola-app sola-app
kubectl rollout status deployment -n sola-app sola-app
```

---

## 🗄️ **PostgreSQL HA — CloudNativePG**

### **Stanje**

```bash
kubectl get pods -n sola-app -o wide | grep db

# NAME                    READY   STATUS    IP            NODE
# sola-db-1 (primary)     1/1     Running   10.42.0.x     k3s-1
# sola-db-2 (replica)     1/1     Running   10.42.1.x     k3s-2
```

Zgrajena z **CloudNativePG** operatorjem. Primary vedno na k3s-1, replica na k3s-2.

### **Failover**

Ob izpadu k3s-1:
1. Primarni pod `sola-db-1` postane nedosegljiv
2. CNPG operator zazna izpad (30s `failoverDelay`)
3. CNPG promovira `sola-db-2` (na k3s-2) v primary
4. Service `sola-db-rw` se avtomatsko preusmeri na `sola-db-2`
5. App pod na k3s-1 je mrtev → k3s ga reschedule-a na k3s-2
6. App na k3s-2 se poveže na `sola-db-rw` (ki kaže na `sola-db-2`) → deluje naprej

**Skupni čas izpada:** ~1–2 minuti (30s failover delay + ~30s za promocijo + čas, da k3s zazna mrtvi node)

### **Dostop**

```bash
# Primarna baza (rw)
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL

# Replica (read-only)
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL_RO
```

### **Servisni endpointi (CNPG)**

CNPG samodejno ustvari tri Kubernetes Services za dostop do baze:

| Service | Vloga |
|---|---|
| `sola-db-rw.sola:5432` | **Read-Write** — vedno na primary (uporablja ga app) |
| `sola-db-ro.sola:5432` | Read-Only — samo replica (za poročila, analitiko) |
| `sola-db-r.sola:5432` | Read — katerakoli instance (primary ali replica) |

`DATABASE_URL` v aplikaciji kaže na `sola-db-rw` — ob failoverju se avtomatsko preusmeri na nov primary, app ne izve za spremembo.

---

## ☁️ **Cloudflare DNS**

### **DNS zapisi**

| Tip | Ime | Vrednost | Proxy |
|---|---|---|---|
| A | `@` ({{DOMAIN}}) | {{LB_IP}} | ✅ Cloudflare proxy (LoadBalancer) |
| A | `www` | {{LB_IP}} | ✅ Cloudflare proxy |

### **SSL/TLS**

Cloudflare skrbi za:
- **Edge certifikat** — med uporabnikom in Cloudflare (HTTPS)
- **Flexible SSL** — Cloudflare → {{LB_IP}} (port 80) prek HTTP (brez certifikata na originu)

Nastavitve v Cloudflare dashboard:
- **SSL/TLS encryption mode:** `Flexible`
- **Always Use HTTPS:** ON
- **Minimum TLS Version:** 1.2

---

## 💾 **Longhorn Storage**

### **Stanje**

```bash
kubectl get pvc -n sola-app
kubectl get volumes.longhorn.io -n longhorn-system
```

### **PVC-ji**

| PVC | Size | Access Mode | Uporaba |
|---|---|---|---|
| `sola-postgresql` | 5Gi | RWO | PG data |
| `sola-postgresql-wal` | 2Gi | RWO | WAL logi |

**Razlaga PVC-jev:**

| PVC | Kaj shranjuje | Zakaj je pomembno |
|---|---|---|
| `sola-postgresql` (5Gi) | **Podatki PG baze** — vse tabele, indeksi, uporabniki, rezervacije, ocene. To je "glavni" PVC. | Brez tega ni baze. 5Gi zadostuje za celotno šolsko leto. |
| `sola-postgresql-wal` (2Gi) | **Write-Ahead Logs (WAL)** — dnevnik vsake spremembe, preden se zapiše v podatkovne datoteke. | Brez WAL-a replica ne more slediti primaryju. Uporablja se za crash recovery, streaming replikacijo in point-in-time recovery. |

**Zakaj dva ločena PVC-ja?** PostgreSQL vsako spremembo najprej zapiše v WAL, šele nato v glavne podatkovne datoteke. Ločena PVC-ja omogočata različne I/O profile — WAL je zaporedno pisanje (hitro), podatki so naključni bralno-pisalni dostopi. Prav tako omogoča ločeni backup strategiji: WAL se arhivira sproti, podatki se periodično snapshottajo.

**Longhorn replikacija** (2 kopiji) zagotavlja, da tudi ob izgubi enega noda podatki ostanejo. Oba PVC-ja imata dve repliki — vsaka na svojem k3s nodu.

---

## 📅 **Dnevni backup in reporti**

### **Dnevni app report**

```bash
# Cron: 04:00 vsak dan (Europe/Ljubljana)
# Pošlje summary na Discord — število rezervacij, prijavljenih, itd.
kubectl logs -n sola-app job/sola-report
```

Posodobi se **samodejno** preko Hermes cron joba. Poročilo vključuje:
- Število aktivnih rezervacij
- Število prijavljenih uporabnikov
- Stanje ocenjevanj
- Morebitne napake

---

## 🔧 **Vzdrževanje in okvare**

### **Dnevne operacije**

```bash
# Preveri stanje nodov
kubectl get nodes -o wide

# Preveri pode v sola-app
kubectl get pods -n sola-app -o wide

# Preveri stanje Longhorn
kubectl get volumes.longhorn.io -n longhorn-system

# Preveri CloudNativePG
kubectl get cluster -n sola-app

# Preveri LoadBalancer
kubectl get svc -n sola-app sola-app
```

### **Ob izpadu noda**

1. **Ostali node prevzame** — app pod se preseli, PG failover
2. **Počakaj 30s** — CNP failover in Longhorn se rekonfigurirata
3. **Preveri** — `kubectl get pods -n sola-app -o wide`
4. **Popravi** izpadli node po potrebi

### **Popolna zaustavitev (poletna pavza)**

Glej [🌞 Poletna pavza](POLETNA_PAVZA.md).

---

## 📋 **Celoten sklic ukazov**

```bash
# === Stanje ===
kubectl get nodes -o wide
kubectl get pods -n sola-app -o wide
kubectl get services -n sola-app
kubectl get pvc -n sola-app
kubectl get cluster -n sola-app
kubectl get events -n sola-app --sort-by='.lastTimestamp'

# === Upravljanje aplikacije ===
kubectl rollout restart deployment -n sola-app sola-app
kubectl rollout status deployment -n sola-app sola-app
kubectl logs -n sola-app deployment/sola-app --tail=50
kubectl logs -n sola-app deployment/sola-app --previous

# === Upravljanje baze ===
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL -c "SELECT * FROM users;"

# === Longhorn ===
kubectl get volumes.longhorn.io -n longhorn-system
kubectl get engineimages.longhorn.io -n longhorn-system
kubectl get nodes.longhorn.io -n longhorn-system

# === Git (na k3s-2) ===
cd /home/admin/reservation_app
git pull
```

---

*Dokumentacija za ostc-app — OŠ Toneta Čufarja Jesenice*
*Zadnja posodobitev: 27. junij 2026*
