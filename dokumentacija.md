# 🚀 **ostc-app — Rezervacijski sistem**
## **OŠ Toneta Čufarja — Testna produkcija (2026)**

---

## 📑 **Kazalo**
1. [Arhitektura sistema](#arhitektura-sistema)
2. [Kubernetes cluster (k3s)](#kubernetes-cluster-k3s)
3. [Aplikacija (sola-app)](#aplikacija-sola-app)
4. [PostgreSQL baza (CloudNativePG)](#postgresql-baza-cloudnativepg)
5. [Visoka razpoložljivost (HA)](#visoka-razpoložljivost-ha)
6. [Konfiguracija in secreti](#konfiguracija-in-secreti)
7. [Dostop do aplikacije](#dostop-do-aplikacije)
8. [Redna opravila](#redna-opravila)
9. [Docker build in deploy](#docker-build-in-deploy)
10. [Pogosti ukazi](#pogosti-ukazi)
11. [Checklista stanja](#checklista-stanja)

---

## 🏗️ **Arhitektura sistema**

### **Strojna oprema**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        K3S KUBERNETES CLUSTER                       │
│                                                                     │
│  ┌─────────────────────────┐    ┌──────────────────────────┐        │
│  │   k3s-1 (MASTER+ETCD)   │    │   k3s-2 (MASTER+ETCD)   │        │
│  │   193.2.171.250         │◄──►│   193.2.171.249          │        │
│  │   HP ProBook 455 G5     │    │   HP ProBook 450 G5      │        │
│  │   CPU: 8c/16t, 16GB     │    │   CPU: 8c/16t, 16GB     │        │
│  │   SSD: 512GB            │    │   SSD: 512GB            │        │
│  │                         │    │                          │        │
│  │   ┌── sola-app pod     │    │   ┌── sola-app pod      │        │
│  │   └── sola-db-1 (prim) │    │   └── sola-db-2 (repl)  │        │
│  └───────────▲─────────────┘    └───────────▲──────────────┘        │
│              │                              │                        │
│              └──────────────┬───────────────┘                        │
│                             │                                        │
│                    LoadBalancer IP                                   │
│                    193.2.171.200                                     │
│                             │                                        │
│                             │    MetalLB (layer2)                    │
│                             ▼                                        │
│                    ┌──────────────┐                                  │
│                    │  Cloudflare  │                                  │
│                    │ ostc-app.org │                                  │
│                    └──────────────┘                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### **Pregled komponent**

| Komponenta | Lokacija | Namen |
|---|---|---|
| **k3s-1** | k3s-1 (250) | Control plane, primarna DB, app pod |
| **k3s-2** | k3s-2 (249) | Control plane, read replica, app pod |
| **sola-app** | Oba noda (2 poda) | FastAPI + Jinja2 template app |
| **PostgreSQL** | CloudNativePG (2 instance) | Baza podatkov (78 users, 294 rezervacij) |
| **MetalLB** | Oba noda | LoadBalancer IP 193.2.171.200 |
| **Nginx** | Oba noda | Reverse proxy + SSL (port 443/8080) |
| **Cloudflare** | Zunanji | DNS, proxy (ostc-app.org) |
| **Longhorn** | Oba noda | Repliciran distributed storage |

---

## ☸️ **Kubernetes cluster (k3s)**

### **Namestitev**

K3S je bil nameščen z `INSTALL_K3S_EXEC` nastavitvami za simetrično konfiguracijo:

```bash
# Na prvem nodu (k3s-1) — inicializacija
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=servicelb" sh -

# Na drugem nodu (k3s-2) — join
curl -sfL https://get.k3s.io | K3S_URL=https://193.2.171.250:6443 K3S_TOKEN=<token> sh -
```

### **Stanje nodov**

```bash
kubectl get nodes -o wide

# Izhod
# NAME    STATUS   ROLES                INTERNAL-IP     OS-IMAGE
# k3s-1   Ready    control-plane,etcd   193.2.171.250   Ubuntu 24.04
# k3s-2   Ready    control-plane,etcd   193.2.171.249   Ubuntu 24.04
```

### **Namespaca**

| Namespace | Vsebina |
|---|---|
| `sola-app` | Deployment, Service, Secret, ConfigMap, CronJobs |
| `sola` | CloudNativePG cluster, Longhorn PVC, service |
| `longhorn-system` | Longhorn distributed storage |

---

## 🐍 **Aplikacija (sola-app)**

### **Opis**

FastAPI aplikacija za rezervacijo učilnic in opreme:
- **Prostori:** tablice, računalnica, ladja, gospodinjska-ucilnica
- **Razredi:** 1.a–9.5 (IP/NIP/ID)
- **Urnik:** 8 terminov (07:30–14:45)
- **Avtentikacija:** email geslo + reset

### **Deployment**

```yaml
# Deployment sola-app
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sola-app
  namespace: sola-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sola-app
```

### **Stanje podov**

App podi so porazdeljeni na oba noda:

```bash
kubectl get pods -n sola-app -o wide

# NAME                        READY   STATUS    IP            NODE
# sola-app-6d76cfcfb7-n2w8x   1/1     Running   10.42.0.93    k3s-1
# sola-app-6d76cfcfb7-v8rmm   1/1     Running   10.42.1.109   k3s-2
```

### **Health check**

Aplikacija ima `/health` endpoint (vrača 200 OK). Kubernetes ga uporablja za readiness probe.

---

## 🗄️ **PostgreSQL baza (CloudNativePG)**

### **Cluster konfiguracija**

Namesto klasičnega Bitnami Helm charta uporabljamo **CloudNativePG** operator za visoko razpoložljivost.

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: sola-db
  namespace: sola
spec:
  instances: 2
  failoverDelay: 30          # Auto-failover po 30s
  enablePDB: true
  storage:
    size: 1Gi
    storageClass: longhorn   # Repliciran storage
  bootstrap:
    initdb:
      database: sola
      owner: sola
      secret:
        name: sola-db-creds
  affinity:
    enablePodAntiAffinity: true
    podAntiAffinityType: preferred
    topologyKey: kubernetes.io/hostname
```

### **Stanje clusterja**

```bash
kubectl get pods -n sola -o wide

# NAME                    READY   STATUS    IP            NODE
# sola-db-1 (primary)     1/1     Running   10.42.0.85    k3s-1
# sola-db-2 (replica)     1/1     Running   10.42.1.106   k3s-2
```

### **Service-i**

CNP avtomatsko ustvari servise za dostop:

| Service | Namen | Endpoint |
|---|---|---|
| `sola-db-rw` | Read-write (vedno na primary) | `sola-db-rw.sola:5432` |
| `sola-db-ro` | Read-only (vse ready instance) | `sola-db-ro.sola:5432` |
| `sola-db-r` | Vse instance | `sola-db-r.sola:5432` |

### **Kako deluje failover**

```
Normalno stanje:
  sola-db-1 (primary, k3s-1)  ← streaming replication →  sola-db-2 (replica, k3s-2)
         └── ha/active=true
    
Ob izpadu k3s-1:
  1. CNP zazna, da primary ni odziven (30s failoverDelay)
  2. CNP promovira sola-db-2 v primary (SELECT pg_promote())
  3. Service sola-db-rw se preusmeri na sola-db-2
  4. App na k3s-2 deluje naprej (povezava na sola-db-rw)
  
  ⏱ Skupni čas izpada: ~1–2 minuti
```

---

## 🔄 **Visoka razpoložljivost (HA)**

### **Kako je postavljeno**

```
Cloudflare → ostc-app.org
  │
  ▼
  ├── k3s-1:443 (nginx SSL)    ─┐
  │                              ├── Service LoadBalancer 193.2.171.200:8002
  └── k3s-2:8080 (nginx)       ─┘          │
                                            ▼
                                     ┌──────────────┐
                                     │  MetalLB     │  (layer2 failover)
                                     └──────┬───────┘
                                            │
                            ┌───────────────┴───────────────┐
                            ▼                                ▼
                     Pod k3s-1 (app)                   Pod k3s-2 (app)
                            │                                │
                            └──────────┬────────────────────┘
                                       ▼
                                sola-db-rw.sola:5432
                                       │
                                       ├── Primary (k3s-1) — če je živ
                                       └── Replica promovirana (k3s-2) — če primary pade
```

### **Sloji odpornosti**

| Sloj | Mehanizem | Čas okvare |
|---|---|---|
| **Aplikacija** | 2 poda na različnih nodih | ~5 min (k3s reschedule) |
| **Omrežje** | MetalLB layer2 failover | ~10–30s |
| **Baza** | CNP auto-failover (30s delay) | ~1–2 min |
| **Storage** | Longhorn replikacija | Podatki varni tudi ob izgubi noda |
| **DNS** | Cloudflare proxy | Takoj (če je IP živ) |

---

## 🔐 **Konfiguracija in secreti**

### **ConfigMap (`sola-config`)**

Vsebuje nastavitve aplikacije:

```yaml
APP_HOST: "0.0.0.0"
APP_PORT: "8002"
BASE_URL: "https://ostc-app.org"
PROSTORI: "tablice,racunalnica,ladja,gospodinjska-ucilnica"
RAZREDI: "IP/NIP/ID,1.a,...,9.5"
SCHEDULE: '{"0":"07:30-08:15",...,"7":"12:50-13:35"}'
TABLICE_MAX: "28"
```

### **Secret (`sola-secrets`)**

Vsebuje občutljive podatke:

```
DATABASE_URL=postgresql://sola:***@sola-db-rw.sola:5432/sola
MAIL_FROM=os-toneta.cufarja-jesenice@guest.arnes.si
MAIL_SERVER=mail.arnes.si
MAIL_PORT=587
MAIL_USERNAME=oscuf
MAIL_PASSWORD=***
BACKUP_EMAIL=matej.cusin2@guest.arnes.si
```

### **CNP Secret (`sola-db-creds`)**

Geslo za bazo:

```
username: sola
password: ***
```

---

## 🌐 **Dostop do aplikacije**

### **URL-ji**

| URL | Opis |
|---|---|
| `https://ostc-app.org` | Produkcija (Cloudflare → nginx) |
| `http://193.2.171.200:8002` | LoadBalancer IP (direct) |
| `http://k3s-1:443` | Prek nginx SSL na k3s-1 |
| `http://k3s-2:8080` | Prek nginx na k3s-2 |

### **Nginx konfiguracija**

Na obeh nodih nginx proxy-pass-a na `193.2.171.200:8002`:

```nginx
location / {
    proxy_pass http://193.2.171.200:8002;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### **Cloudflare**

- **DNS:** `ostc-app.org` → A record na `193.2.171.200`
- **Proxy:** Enabled (Cloudflare ščiti origin IP)
- **SSL:** Full (strict) — Cloudflare → nginx na k3s-1

---

## ⏰ **Redna opravila**

### **Dnevno poročilo**

CronJob v Kubernetes, ki vsak dan ob **04:00 Europe/Ljubljana** pošlje email s povzetkom rezervacij.

```bash
# Preveri zadnje poročilo
kubectl logs -n sola-app -l job-name=sola-daily-report --tail=20
```

### **Backup baze**

CronJob za dnevni dump PostgreSQL baze.

```bash
# Preveri backup
kubectl logs -n sola-app -l job-name=sola-db-backup --tail=20
```

---

## 🐳 **Docker build in deploy**

### **Build slike**

```bash
cd /home/admin_os/reservation_app
docker build -t mato12345/sola-app:latest -f k8s/Dockerfile .
docker push mato12345/sola-app:latest
```

### **Deploy na k3s**

Po build-u in push-u:

```bash
kubectl rollout restart -n sola-app deployment/sola-app
kubectl rollout status -n sola-app deployment/sola-app
```

### **Dodajanje novega prostora**

1. Dodaj v `ConfigMap sola-config` (ključ `PROSTORI`)
2. Dodaj labelo v frontend `app/templates/index.html` (funkcija `prostorLabel`)
3. Dodaj akuzativ v backend `app/routers/rezervacije.py` (če je potrebno)
4. Restartaj app: `kubectl rollout restart -n sola-app deployment/sola-app`

---

## 📝 **Pogosti ukazi**

### **Splošno**
```bash
# Stanje clusterja
kubectl get nodes
kubectl get pods -A
kubectl get svc -A

# App
kubectl get pods -n sola-app -o wide
kubectl logs -n sola-app deployment/sola-app --tail=50
kubectl logs -n sola-app -l job-name=sola-daily-report --tail=20

# Baza
kubectl get pods -n sola -o wide
kubectl get cluster -n sola sola-db
kubectl exec -n sola sola-db-1 -- bash -c "PGPASSWORD=*** psql -h localhost -U sola -d sola -Atc 'SELECT count(*) FROM users'"

# Storage
kubectl get pvc -n sola
kubectl get storageclass

# Failover test
ssh k3s-1 "sudo poweroff"
# Počakaj 2 min, preveri
kubectl get pods -n sola -o wide  # sola-db-2 naj bo primary
curl -I https://ostc-app.org      # app naj dela
```

### **Docker & Git**
```bash
# Build in push
cd /home/admin_os/reservation_app
docker build -t mato12345/sola-app:latest -f k8s/Dockerfile .
docker push mato12345/sola-app:latest
kubectl rollout restart -n sola-app deployment/sola-app

# Git
cd /home/admin_os/reservation_app
git add -A
git commit -m "sprememba"
git push origin main
```

### **Nginx**
```bash
# Konfiguracija
cat /etc/nginx/sites-available/default

# Test in reload
sudo nginx -t && sudo systemctl reload nginx
```

### **Longhorn**
```bash
# Dashboard (port-forward)
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# Odpri: http://localhost:8080
```

---

## ✅ **Checklista stanja**

- [x] K3S cluster (2 noda, oba Ready)
- [x] sola-app deployment (2 poda, oba Running)
- [x] CloudNativePG cluster (2 instance, primary + replica)
- [x] Podatki v bazi (78 users, 294 rezervacij)
- [x] LoadBalancer (193.2.171.200, MetalLB)
- [x] Nginx na obeh nodih (proxy_pass na LB IP)
- [x] Cloudflare DNS (ostc-app.org → 193.2.171.200)
- [x] Auto-failover (CNP, 30s delay)
- [x] Dnevno poročilo (CronJob, 04:00)
- [x] Backup baze (CronJob)
- [x] Repo na obeh nodih (git@github.com:os-tc-jesenice/reservation_app.git)
- [x] HA.md dokumentacija pushana

---

## 🔧 **Odpravljanje težav**

### **App se ne zažene (CrashLoopBackOff)**

```bash
# Preveri loge
kubectl logs -n sola-app deployment/sola-app --tail=50

# Pogosti vzroki:
# - Napačno geslo v DATABASE_URL (secret sola-secrets)
# - Baza ni dosegljiva (sola-db-rw service)
# - Manjkajoče tabele (restart bi jih moral ustvariti)

# Popravi geslo če je potrebno
kubectl delete secret -n sola-app sola-secrets
kubectl create secret generic sola-secrets -n sola-app \
  --from-literal=DATABASE_URL="postgresql://sola:***@sola-db-rw.sola:5432/sola"
```

### **Nginx vrne 502**

```bash
# Preveri če LoadBalancer IP odgovarja
curl -I http://193.2.171.200:8002

# Preveri nginx config
sudo nginx -t

# Preveri če app podi tečejo
kubectl get pods -n sola-app
```

### **Baza pade v neskladje po failoverju**

Ko se k3s-1 vrne po izpadu:
1. CNP poskusi obnoviti replikacijo
2. Če ne gre, izbriši stari PVC na k3s-1
3. CNP bo recreiral pod kot replico

```bash
# Počisti staro primary instanco (samo če CNP ne zmore sam)
kubectl delete pvc -n sola data-sola-db-1
# CNP bo recreiral
```

---

