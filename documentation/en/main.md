[🇸🇮 Slovenščina](../main.md) | [🇬🇧 English](main.md)

---

# 🚀 **ostc-app — Reservation System**
## **OŠ Toneta Čufarja — Documentation**

---

> **This is the main document of the entire documentation.**  
> From here you can navigate to all areas — architecture, HA, admin instructions, teacher guides, maintenance, and more.

---

## 📑 **Documentation Index**

### ⚙️ Architecture & Setup

| Document | Description |
|---|---|
| [**HA Architecture**](ha.md) | High availability — CloudNativePG, MetalLB, failover |
| [**K3S Cluster Setup**](k3s_setup.md) | Installing and configuring k3s on both nodes |
| [**Domain & Network**](domena.md) | DNS, Cloudflare, nginx, SSL |
| [**Local Setup**](lokalni_zagon.md) | Running the app locally (uvicorn) or via mDNS |
| [**Admin/DevOps Guide**](admin_devops.md) | Complete admin instructions for maintenance |

### 🧑‍🏫 User Instructions

| Document | Description |
|---|---|
| [**Teacher Guide**](ucitelji_report.md) | Login, reservations, exam scheduling |
| [**Management/Admin Guide**](vodstvo_report.md) | UI-based management — series, blocked dates, admin panel |

### 🔧 Maintenance

| Document | Description |
|---|---|
| [**Summer Shutdown**](poletna_pavza.md) | Shutting down and restarting during summer break |
| [**Admin Instructions**](navodila.md) | General admin instructions (troubleshooting, recovery) |

---

## 🏗️ **System Architecture**

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

### **Component Overview**

| Component | Location | Purpose |
|---|---|---|
| **k3s-1** (193.2.171.250) | physical HP ProBook 455 G5 | Control plane, primary DB, app pod |
| **k3s-2** (193.2.171.249) | physical HP ProBook 450 G5 | Control plane, read replica, app pod |
| **sola-app** | Both nodes (2 pods) | FastAPI + Jinja2 template app |
| **PostgreSQL** | CloudNativePG (2 instances) | Database (78 users, 294 reservations) |
| **MetalLB** | Both nodes | LoadBalancer IP 193.2.171.200 |
| **Nginx** | Both nodes | Reverse proxy + SSL |
| **Cloudflare** | External | DNS, proxy, SSL (ostc-app.org) |
| **Longhorn** | Both nodes | Replicated distributed storage |

---

## ☸️ **Kubernetes cluster (k3s)**

Two symmetric nodes (both control-plane + etcd).

```bash
kubectl get nodes -o wide

# NAME    STATUS   ROLES                INTERNAL-IP     OS-IMAGE
# k3s-1   Ready    control-plane,etcd   193.2.171.250   Ubuntu 24.04
# k3s-2   Ready    control-plane,etcd   193.2.171.249   Ubuntu 24.04
```

### **Namespaces**

| Namespace | Contents |
|---|---|
| `sola-app` | Deployment (2 pods), Service (LoadBalancer), Secret, ConfigMap, CronJobs |
| `sola` | CloudNativePG cluster, Longhorn PVC, services |
| `longhorn-system` | Longhorn distributed storage |

---

## 🐍 **Application (sola-app)**

FastAPI application for:
- **Room reservations:** tablets, computer lab, boat, home economics classroom
- **Exam scheduling:** written exams with limits (max 3/week)
- **Blocked dates:** marking busy days for specific classes
- **Authentication:** email + password, password reset via email

```bash
kubectl get pods -n sola-app -o wide

# NAME                        READY   STATUS    IP            NODE
# sola-app-xxxxx-xxxxx        1/1     Running   10.42.0.x     k3s-1
# sola-app-xxxxx-xxxxx        1/1     Running   10.42.1.x     k3s-2
```

---

## 🗄️ **PostgreSQL Database (CloudNativePG)**

```bash
kubectl get pods -n sola -o wide

# NAME                    READY   STATUS    IP            NODE
# sola-db-1 (primary)     1/1     Running   10.42.0.x     k3s-1
# sola-db-2 (replica)     1/1     Running   10.42.1.x     k3s-2
```

**Services:** `sola-db-rw` (always on primary), `sola-db-ro` (read-only)  
**Auto-failover:** 30 seconds (built into CNP)  
**Storage:** Longhorn (replicated)

[→ Details in HA document](ha.md)

---

## 🌐 **Access**

| URL | Description |
|---|---|
| `https://ostc-app.org` | Production (Cloudflare → nginx → LB) |
| `http://193.2.171.200:8002` | LoadBalancer IP (direct) |
| SSH k3s-1: `ssh admin_os@193.2.171.250` | Direct node access |

---

## 📚 **Documentation Structure**

```
documentation/
├── main.md                ← YOU ARE HERE (main menu)
├── ha.md                  # HA architecture
├── admin_devops.md        # Admin/devops guide
├── navodila.md            # General admin instructions
├── domena.md              # Domain, Cloudflare, nginx
├── k3s_setup.md           # K3S installation
├── lokalni_zagon.md       # Local setup (uvicorn)
├── poletna_pavza.md       # Summer shutdown
├── ucitelji_report.md     # Teacher guide
├── vodstvo_report.md      # Management UI guide
└── en/                    # English version
    └── main.md            ← ENGLISH INDEX
```

---

## 🔧 **Quick Commands**

```bash
# App status
kubectl get pods -n sola-app -o wide
kubectl logs -n sola-app deployment/sola-app --tail=50

# Database status
kubectl get pods -n sola -o wide
kubectl get cluster -n sola sola-db

# Restart app after config change
kubectl rollout restart -n sola-app deployment/sola-app

# Build & deploy
cd /home/admin_os/reservation_app
docker build -t mato12345/sola-app:latest -f k8s/Dockerfile .
docker push mato12345/sola-app:latest
kubectl rollout restart -n sola-app deployment/sola-app

# Git
cd /home/admin_os/reservation_app
git add -A && git commit -m "change" && git push origin main

# Nginx
sudo nginx -t && sudo systemctl reload nginx
```
