# 🚀 **ostc-app — Rezervacijski sistem**
## **OŠ Toneta Čufarja — Dokumentacija**

---

> **To je glavni dokument celotne dokumentacije.**  
> Od tu vodijo povezave na vsa področja — arhitekturo, HA, admin navodila, navodila za učitelje, vzdrževanje in več.

---

## 📑 **Kazalo dokumentacije**

### ⚙️ Arhitektura in namestitev

| Dokument | Opis |
|---|---|
| [**HA arhitektura**](ha.md) | Visoka razpoložljivost — CloudNativePG, MetalLB, failover |
| [**K3S cluster setup**](k3s_setup.md) | Namestitev in konfiguracija k3s na obeh nodih |
| [**Domena in omrežje**](domena.md) | DNS, Cloudflare, nginx, SSL |
| [**Lokalni zagon**](lokalni_zagon.md) | Kako zagnati app lokalno (uvicorn) ali prek mDNS |
| [**Admin/devops navodila**](admin_devops.md) | Celotna admin navodila za vzdrževanje |

### 🧑‍🏫 Uporabniška navodila

| Dokument | Opis |
|---|---|
| [**Navodila za učitelje**](ucitelji_report.md) | Prijava, rezervacije, napoved ocenjevanj |
| [**Navodila za vodstvo/admin**](vodstvo_report.md) | Upravljanje prek UI — serije, zasedeni datumi, admin panel |

### 🔧 Vzdrževanje

| Dokument | Opis |
|---|---|
| [**Poletna pavza**](poletna_pavza.md) | Ugašanje in zagon ob poletnih počitnicah |
| [**Navodila za admin**](navodila.md) | Splošna admin navodila (odpravljanje težav, obnova) |

---

## 🏗️ **Arhitektura sistema**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        K3S KUBERNETES CLUSTER                       │
│                                                                     │
│  ┌─────────────────────────┐    ┌──────────────────────────┐        │
│  │   k3s-1 (250)           │    │   k3s-2 (249)            │        │
│  │   HP ProBook 455 G5     │◄──►│   HP ProBook 450 G5      │        │
│  │   Ubuntu 24.04, 16GB    │    │   Ubuntu 24.04, 16GB     │        │
│  │                         │    │                          │        │
│  │   ┌─ sola-app pod      │    │   ┌─ sola-app pod       │        │
│  │   └─ sola-db-1 (prim)  │    │   └─ sola-db-2 (repl)   │        │
│  └───────────▲─────────────┘    └───────────▲──────────────┘        │
│              │                              │                        │
│              └──────────────┬───────────────┘                        │
│                             │                                        │
│                    LoadBalancer IP                                   │
│                    193.2.171.200                                     │
│                             │    MetalLB (layer2)                    │
│                             ▼                                        │
│                    ┌──────────────┐                                  │
│                    │  Cloudflare  │                                  │
│                    │ ostc-app.org │                                  │
│                    └──────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### **Pregled komponent**

| Komponenta | Lokacija | Namen |
|---|---|---|
| **k3s-1** (193.2.171.250) | fizični HP ProBook 455 G5 | Control plane, primarna DB, app pod |
| **k3s-2** (193.2.171.249) | fizični HP ProBook 450 G5 | Control plane, read replica, app pod |
| **sola-app** | Oba noda (2 poda) | FastAPI + Jinja2 template app |
| **PostgreSQL** | CloudNativePG (2 instance) | Baza podatkov (78 users, 294 rezervacij) |
| **MetalLB** | Oba noda | LoadBalancer IP 193.2.171.200 |
| **Nginx** | Oba noda | Reverse proxy + SSL |
| **Cloudflare** | Zunanji | DNS, proxy, SSL (ostc-app.org) |
| **Longhorn** | Oba noda | Repliciran distributed storage |

---

## ☸️ **Kubernetes cluster (k3s)**

Dva simetrična noda (oba control-plane + etcd).

```bash
kubectl get nodes -o wide

# NAME    STATUS   ROLES                INTERNAL-IP     OS-IMAGE
# k3s-1   Ready    control-plane,etcd   193.2.171.250   Ubuntu 24.04
# k3s-2   Ready    control-plane,etcd   193.2.171.249   Ubuntu 24.04
```

### **Namespaca**

| Namespace | Vsebina |
|---|---|
| `sola-app` | Deployment (2 poda), Service (LoadBalancer), Secret, ConfigMap, CronJobs |
| `sola` | CloudNativePG cluster, Longhorn PVC, servisi |
| `longhorn-system` | Longhorn distributed storage |

---

## 🐍 **Aplikacija (sola-app)**

FastAPI aplikacija za:
- **Rezervacije prostorov:** tablice, računalnica, ladja, gospodinjska-ucilnica
- **Napoved ocenjevanj:** pisna ocenjevanja z omejitvami (max 3/teden)
- **Zasedeni datumi:** označevanje zasedenih dni za posamezne razrede
- **Avtentikacija:** email + geslo, ponastavitev prek emaila

```bash
kubectl get pods -n sola-app -o wide

# NAME                        READY   STATUS    IP            NODE
# sola-app-xxxxx-xxxxx        1/1     Running   10.42.0.x     k3s-1
# sola-app-xxxxx-xxxxx        1/1     Running   10.42.1.x     k3s-2
```

---

## 🗄️ **PostgreSQL baza (CloudNativePG)**

```bash
kubectl get pods -n sola -o wide

# NAME                    READY   STATUS    IP            NODE
# sola-db-1 (primary)     1/1     Running   10.42.0.x     k3s-1
# sola-db-2 (replica)     1/1     Running   10.42.1.x     k3s-2
```

**Servisi:** `sola-db-rw` (vedno na primary), `sola-db-ro` (read-only)  
**Auto-failover:** 30 sekund (vgrajen v CNP)  
**Storage:** Longhorn (repliciran)

[→ Podrobnosti v HA dokumentu](ha.md)

---

## 🌐 **Dostop**

| URL | Opis |
|---|---|
| `https://ostc-app.org` | Produkcija (Cloudflare → nginx → LB) |
| `http://193.2.171.200:8002` | LoadBalancer IP (direct) |
| SSH k3s-1: `ssh admin_os@193.2.171.250` | Direct access to node |

---

## 📚 **Celotna dokumentacija po mapah**

```
documentation/
├── main.md                ← STE S TU (glavni meni)
├── ha.md                  # HA arhitektura
├── admin_devops.md        # Admin/devops navodila
├── navodila.md            # Splošna admin navodila
├── domena.md              # Domena, Cloudflare, nginx
├── k3s_setup.md           # K3S namestitev
├── lokalni_zagon.md       # Lokalni zagon (uvicorn)
├── poletna_pavza.md       # Poletna pavza
├── ucitelji_report.md     # Navodila za učitelje
└── vodstvo_report.md      # Navodila za vodstvo (UI)
```

---

## 🔧 **Hitri ukazi**

```bash
# Stanje appa
kubectl get pods -n sola-app -o wide
kubectl logs -n sola-app deployment/sola-app --tail=50

# Stanje baze
kubectl get pods -n sola -o wide
kubectl get cluster -n sola sola-db

# Restart appa po spremembi
kubectl rollout restart -n sola-app deployment/sola-app

# Build in deploy
cd /home/admin_os/reservation_app
docker build -t mato12345/sola-app:latest -f k8s/Dockerfile .
docker push mato12345/sola-app:latest
kubectl rollout restart -n sola-app deployment/sola-app

# Git
cd /home/admin_os/reservation_app
git add -A && git commit -m "sprememba" && git push origin main

# Nginx
sudo nginx -t && sudo systemctl reload nginx
```
