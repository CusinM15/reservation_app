🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../main.md) | [🇬🇧 English](main.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

> 🛠️ **Customize the documentation to your IPs**
>
> All documentation uses a central `.env.ip` file that defines every IP address,
> port, and domain. Want documentation with your own values?
>
> ```bash
> cd documentation
> nano .env.ip                          # enter your IPs
> ./replace-ips.sh                      # docs are updated
> ```
>
> The script replaces all IPs in `.md` files. After running it, you can
> copy-paste commands directly into your terminal — they'll work as-is.

---

## 📚 Documentation Index

| Document | Description |
|---|---|
| [🏗️ **HA Architecture**](HA.md) | CloudNativePG, automatic failover, node failure procedure |
| [🌞 **Summer Shutdown**](POLETNA_PAVZA.md) | Safe k3s cluster shutdown for summer and restart in fall |
| [☁️ **Domain & DNS**](domena.md) | Domain setup, Cloudflare, DNS records |
| [🐍 **Local App Setup**](postavi-lokalni-app.md) | Single-machine installation (no Kubernetes) |
| [☸️ **K3s Setup**](k3s-setup.md) | k3s cluster installation from scratch |
| [⚙️ **Admin/DevOps Guide**](admin-devops-navodila.md) | Maintenance, updates, troubleshooting |
| [👩‍🏫 **Teachers Guide**](navodila-ucitelji.md) | Using the app — reservations and assessments |
| [👑 **Management Guide**](navodila-vodstvo.md) | Browser-based administration (series, blocked dates) |
| [📱 **App Description**](aplikacija-rezervacije.md) | What the app does, purpose, features |
| [📖 **User Manual**](navodila-uporabnika.md) | Login, passwords, daily use |

---

# 🚀 **ostc-app — Reservation System**
## OŠ Toneta Čufarja — Documentation

---


## 📑 **Table of Contents** (this document)
1. [System Architecture](#system-architecture)
2. [Hardware and Network](#hardware-and-network)
3. [Kubernetes (k3s) Cluster](#kubernetes-k3s-cluster)
4. [Sola App Application](#sola-app-application)
5. [PostgreSQL HA — CloudNativePG](#postgresql-ha--cloudnativepg)
6. [MetalLB LoadBalancer](#metallb-loadbalancer)
7. [Nginx Reverse Proxy](#nginx-reverse-proxy)
8. [Cloudflare DNS](#cloudflare-dns)
9. [Longhorn Storage](#longhorn-storage)
10. [Daily Backup and Reports](#daily-backup-and-reports)
11. [Maintenance and Failures](#maintenance-and-failures)
12. [Complete Command Reference](#complete-command-reference)

---

## 🏗️ **System Architecture**

### **Hardware and Network Diagram**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         K3S KUBERNETES CLUSTER (2 nodes)                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────┐    ┌──────────────────────────┐            │
│  │    k3s-1                  │    │    k3s-2                  │            │
│  │    HP ProBook 455 G5     │    │    HP ProBook 450 G5     │            │
│  │    IP: {{LB_IP}}     │    │    IP: {{K3S_1_IP}}1     │            │
│  │    control-plane,etcd    │    │    control-plane,etcd    │            │
│  │                          │    │                          │            │
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ sola-app Pod 1    │   │    │  │ sola-app Pod 2    │   │            │
│  │  │ (app.{{DOMAIN}})│   │    │  │ (app.{{DOMAIN}})│   │            │
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
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ MetalLB Speaker   │   │    │  │ MetalLB Speaker   │   │            │
│  │  └───────────────────┘   │    │  └───────────────────┘   │            │
│  └──────────────────────────┘    └───────────┬───────────────┘            │
│                                               │                           │
│              ┌────────────────────────────────┘                           │
│              │                                                           │
│  ┌───────────▼───────────────────────────────────────────────┐           │
│  │        nginx Reverse Proxy (k3s-2, port {{NGINX_PORT}})              │           │
│  │        proxy_pass http://{{LB_IP}}:{{LB_PORT}}                │           │
│  └───────────────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────────────┘
                              │
                              │
                    ┌─────────▼─────────┐
                    │  Cloudflare DNS    │
                    │  {{DOMAIN}}      │
                    │  → 203.0.113.1    │  📡 Cloudflare proxy IPs
                    │  → 203.0.113.2  │
                    └───────────────────┘
                              │
                              │  Internet
                              ▼
                    🌐 Users (teachers, management)
```

> **Note:** Both nodes are `control-plane,etcd` — there are no separate worker nodes. k3s supports running user pods on control-plane nodes as well.

### **Traffic Flow**

```
🌐 User
  → Cloudflare (SSL, proxy, {{DOMAIN}})
    → Service LoadBalancer (MetalLB, {{LB_IP}}:{{LB_PORT}})
      → sola-app Pod (k3s-1 or k3s-2)

Alternative path (internal network):
  → http://{{K3S_1_IP}}:{{NGINX_PORT}} → nginx on k3s-1 → proxy_pass {{LB_IP}}:{{LB_PORT}}
  → http://{{K3S_2_IP}}:{{NGINX_PORT}} → nginx on k3s-2 → proxy_pass {{LB_IP}}:{{LB_PORT}}
  → http://{{LB_IP}}:{{LB_PORT}} → direct to LoadBalancer
```

Cloudflare proxy provides:
- **SSL termination** — HTTPS from user to Cloudflare
- **DDoS protection**
- **Caching** — for static content
- **Hidden public IP** — real servers are not directly exposed

### **Component Overview**

| Component | Location | Purpose |
|---|---|---|
| **k3s-1** | HP ProBook 455 G5 ({{K3S_1_IP}}) | Control-plane, app pod, PG primary, nginx |
| **k3s-2** | HP ProBook 450 G5 ({{K3S_2_IP}}) | Control-plane, app pod, PG replica, nginx |
| **Sola App (FastAPI)** | 2 pods (both nodes) | Reservations, assessments, login |
| **CloudNativePG** | 2 instances (both nodes) | PostgreSQL database with automatic failover |
| **Longhorn** | Both nodes | Distributed storage (PVCs) |
| **MetalLB** | Both nodes | LoadBalancer IP ({{LB_IP}}) |
| **nginx** | Both nodes (port {{NGINX_PORT}}) | Reverse proxy → LoadBalancer. For internal network (backup if Cloudflare/LB is unavailable) |
| **Cloudflare** | External | DNS, SSL, proxy |

---

## 💻 **Hardware and Network**

### **Specifications**

| Node | Model | CPU | RAM | Disk | Role |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Control-plane,etcd, app, PG primary, nginx |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Control-plane,etcd, app, PG replica, nginx |

### **Network Settings**

```bash
# Local network (Arnes)
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

### **Access**

```bash
# SSH to both nodes
ssh admin@{{K3S_1_IP}}    # k3s-1
ssh admin@{{K3S_2_IP}}    # k3s-2

# sudo password is the same on both nodes
```

---

## ☸️ **Kubernetes (k3s) Cluster**

### **k3s Installation (single command)**

```bash
# On k3s-1 (first control-plane)
curl -sfL https://get.k3s.io | sh -s - --disable=servicelb

# On k3s-2 (second control-plane)
curl -sfL https://get.k3s.io | K3S_URL=https://{{K3S_1_IP}}:6443 \\
  K3S_TOKEN=$(sudo cat /var/lib/rancher/k3s/server/node-token) sh -
```

> ⚠️ `--disable=servicelb` disables the built-in k3s load balancer because we use MetalLB.

### **Current Status**

```bash
kubectl get nodes
# NAME    STATUS   ROLES                AGE   VERSION
# k3s-1   Ready    control-plane,etcd   19d   v1.35.5+k3s1
# k3s-2   Ready    control-plane,etcd   22d   v1.35.5+k3s1

kubectl get pods -A
kubectl get svc -A
```

### **Namespaces on the Cluster**

| Namespace | Purpose |
|---|---|
| `sola-app` | Application (deployment, configmap, secret, cronjob) |
| `sola` | PostgreSQL cluster (CNPG instance, services) |
| `cnpg-system` | CloudNativePG operator |
| `longhorn-system` | Longhorn distributed storage |
| `metallb-system` | MetalLB load balancer |
| `kube-system` | Kubernetes system pods |

---

## 🐍 **Sola App Application**

### **Description**

Sola App is a **FastAPI** web application for:
- **Reservations** — tablets, computer room, ship, home economics classroom
- **Assessments** — scheduling written assessments
- **Blocked dates** — closing time slots for individual rooms
- **Login** — authentication, roles: admin, management, teacher

### **Code Structure**

```
reservation_app/
├── app/
│   ├── main.py              # FastAPI app, middleware, startup
│   ├── config.py            # Settings (from env/ConfigMap)
│   ├── database.py          # SQLAlchemy engine, session
│   ├── models.py            # DB models (User, Reservation, Assessment, BlockedDate)
│   ├── schemas.py           # Pydantic schemas
│   ├── race.py              # Helper for time slots
│   ├── routers/
│   │   ├── auth.py          # Login, passwords, admin panel
│   │   ├── rezervacije.py   # CRUD for reservations
│   │   ├── ocenjevanja.py   # CRUD for assessments
│   │   └── blocked_dates.py # Blocked dates
│   └── templates/           # Jinja2 HTML templates
├── k8s/                     # Kubernetes deploy configuration
│   ├── app/base/            # Base kustomize
│   ├── app/overlays/        # Overlays (ingress, production-lb)
│   └── cluster/             # MetalLB configuration
├── Dockerfile               # Container build
├── documentation/           # 📚 Documentation (this folder)
└── requirements.txt         # Python dependencies
```

### **FastAPI Endpoints**

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check (200 = OK) |
| `/auth/login` | GET, POST | User login |
| `/auth/logout` | GET | Logout |
| `/auth/forgot-password` | GET, POST | Forgot password |
| `/auth/reset-password` | GET, POST | Reset password |
| `/rezervacije` | GET, POST | List / new reservation |
| `/rezervacije/{id}` | DELETE | Cancel reservation |
| `/api/razredi` | GET | List of classes |
| `/api/prostori` | GET | List of rooms |
| `/api/schedule` | GET | Time slots schedule |
| `/ocenjevanja` | GET, POST | List / new assessment |
| `/blocked-dates` | GET, POST, DELETE | Blocked dates |

### **DB Models**

```python
class User(Base):
    # id, username, email, first_name, last_name,
    # password_hash, role (admin/vodstvo/teacher),
    # is_active, reset_token

class Reservation(Base):
    # id, teacher_id, room (tablice/racunalnica/ladja/
    #   gospodinjska-ucilnica),
    # date, time_slot, purpose, notes

class Assessment(Base):
    # id, teacher_id, class_name, subject, type (oral/written),
    # date, description

class BlockedDate(Base):
    # id, room, date, reason
```

### **Kubernetes Deployment**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sola-app
  namespace: sola-app
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0    # Zero-downtime deploy
  selector:
    matchLabels:
      app: sola-app
  template:
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              matchExpressions:
              - key: app
                operator: In
                values: [sola-app]
              topologyKey: kubernetes.io/hostname
      containers:
      - name: app
        image: sola-app:latest
        imagePullPolicy: Always
        ports:
        - containerPort: {{LB_PORT}}
        envFrom:
        - configMapRef:
            name: sola-config
        - secretRef:
            name: sola-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        readinessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 8
        livenessProbe:
          httpGet:
            path: /health
            port: 8002
          failureThreshold: 5
```

### **ConfigMap (sola-config) — actual values**

```yaml
BASE_URL: "https://{{DOMAIN}}"
APP_HOST: "0.0.0.0"
APP_PORT: "8002"
TABLICE_MAX: "28"
PROSTORI: "tablice,racunalnica,ladja,gospodinjska-ucilnica"
SCHEDULE: '{"0":"07:30-08:15","1":"08:20-09:05","2":"09:15-10:00","3":"10:20-11:05","4":"11:10-12:55","5":"12:00-12:45","6":"12:50-13:35","7":"14:00-14:45"}'
RAZREDI: "IP/NIP/ID,1.a,1.b,1.c,1.č,2.a,2.b,2.c,2.č,3.a,3.b,3.c,3.č,4.a,4.b,4.c,4.č,5.a,5.b,5.c,5.č,6.a,6.b,6.c,6.č,7.a,7.b,7.c,8.a,8.b,8.c,8.č,8.1,8.2,8.3,8.4,8.5,8.6,9.a,9.b,9.c,9.1,9.2,9.3,9.4,9.5"
```

> ⚠️ **Note:** `SCHEDULE` index 4 (`"11:10-12:55"`) is an extended period (the second-to-last period lasts 1h45m). Verify if this matches the actual schedule.

### **Secret (sola-secrets)**

Data in the Secret (base64 encoded):
- `DATABASE_URL` — `postgresql://sola:***@sola-db-rw.sola:{{K8S_DB_PORT}}/sola`
- `MAIL_USERNAME` — `oscuf`
- `MAIL_PASSWORD` — (password for SMTP)
- `MAIL_SERVER` — `mail.arnes.si`
- `MAIL_PORT` — `587`
- `MAIL_FROM` — `sola@example.com`
- `BACKUP_EMAIL` — `admin@example.com`

> ⚠️ `DATABASE_URL` uses the **CNPG service** `sola-db-rw.sola:{{K8S_DB_PORT}}` — it always points to the current primary, even after failover.

---

## 🗄️ **PostgreSQL HA — CloudNativePG**

> **Details:** [HA.md](HA.md) — full architecture description, failover procedure, testing.

### **Why CloudNativePG?**

| Feature | Bitnami Helm (before) | CloudNativePG (now) |
|---|---|---|
| Automatic failover | ❌ | ✅ ~30-60s |
| Node anti-affinity | Manual | ✅ Built-in |
| Storage management | Manual | ✅ Built-in |
| Built-in backup | ❌ | ✅ Barman/WAL |
| Kubernetes native | ❌ (classic Helm) | ✅ CRD operator |

### **Short Configuration**

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: sola-db
  namespace: sola
spec:
  instances: 2
  storage:
    size: 1Gi
    storageClass: longhorn
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
  enablePDB: true
  failoverDelay: 30
```

### **Current Status**

```bash
kubectl get cluster -n sola sola-db
# NAME      AGE   INSTANCES   READY   STATUS                     PRIMARY
# sola-db   2h    2           2       Cluster in healthy state   sola-db-1

kubectl get pods -n sola -o wide
# NAME        READY   STATUS    IP            NODE
# sola-db-1   1/1     Running   10.42.0.10    k3s-1   ← PRIMARY
# sola-db-2   1/1     Running   10.42.1.20   k3s-2   ← REPLICA
```

### **Connection Services**

| Service | Role |
|---|---|
| `sola-db-rw.sola:{{K8S_DB_PORT}}` | **Read-Write** — always on primary (used by app) |
| `sola-db-ro.sola:{{K8S_DB_PORT}}` | Read-Only — replica only |
| `sola-db-r.sola:{{K8S_DB_PORT}}` | Read — any instance |

### **Automatic Failover Procedure**

```ascii
┌─ K3s-1 goes down ────────────────────────────────────┐
│                                                       │
│  1. sola-db-1 (primary) becomes unreachable           │
│  2. CNPG operator detects the failure                 │
│  3. Waits 30s (failoverDelay)                         │
│  4. Promotes sola-db-2 (k3s-2) to new primary         │
│  5. Service sola-db-rw redirects to sola-db-2         │
│  6. App on k3s-2 connects to new primary              │
│                                                       │
│  Total downtime: ~1-2 minutes                         │
└───────────────────────────────────────────────────────┘

┌─ K3s-1 comes back ───────────────────────────────────┐
│                                                       │
│  1. CNPG detects the new node                         │
│  2. sola-db-1 automatically joins as REPLICA          │
│  3. No manual intervention needed                     │
└───────────────────────────────────────────────────────┘
```

### **Key Points**

- **No manual intervention** during failover
- **Database password** is in `sola-db-creds` (namespace `sola`) — CNPG creates it automatically
- **App uses** `sola-db-rw` — always on the current primary
- **Old Bitnami PostgreSQL** was removed after migration

---

## 🌐 **MetalLB LoadBalancer**

### **Configuration**

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - {{METALLB_RANGE_START}} - {{METALLB_RANGE_END}}
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-advertisement
  namespace: metallb-system
```

### **LoadBalancer Service**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: sola-app
  namespace: sola-app
spec:
  type: LoadBalancer
  selector:
    app: sola-app
  ports:
  - port: 8002
    targetPort: {{LB_PORT}}
    name: http
```

```bash
kubectl get svc -n sola-app sola-app
# NAME      TYPE           CLUSTER-IP      EXTERNAL-IP      PORT(S)
# sola-app  LoadBalancer   10.43.0.10   {{LB_IP}}   {{LB_PORT}}:32364/TCP
```

---

## 🔄 **Nginx Reverse Proxy**

### **Location**

Nginx runs on **both nodes** with an identical configuration (only port {{NGINX_PORT}}):

| Node | Port | Role |
|---|---|---|
| **k3s-1** | {{NGINX_PORT}} | Reverse proxy → LoadBalancer (backup) |
| **k3s-2** | {{NGINX_PORT}} | Reverse proxy → LoadBalancer (nginx backend) |

### **Configuration (both nodes identical)**

File: `/etc/nginx/sites-enabled/default`

```nginx
server {
    listen {{NGINX_PORT}};

    location / {
        proxy_pass http://{{LB_IP}}:{{LB_PORT}};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

> **Cloudflare** uses **Flexible SSL** — HTTPS to the user, HTTP to LoadBalancer IP (`{{LB_IP}}`, port 80).
> **HA is provided by MetalLB** — layer2 failover: if the node currently holding the LB IP goes down, the other node automatically takes over the IP within seconds. Cloudflare keeps sending to the same IP — nothing needs to be changed.

> **Note:** Cloudflare handles SSL (HTTPS). Nginx listens on port {{NGINX_PORT}} (not 80/443) and forwards to the MetalLB IP.

---

## ☁️ **Cloudflare DNS**

### **DNS Settings**

| Type | Name | Value | Proxy |
|---|---|---|---|
| A | `{{DOMAIN}}` | `{{LB_IP}}` | ✅ Proxied (orange cloud) |

Cloudflare proxy means:
- `{{DOMAIN}}` resolves to Cloudflare IPs
- Cloudflare forwards traffic to `{{LB_IP}}` (LoadBalancer, port 80, Flexible SSL)
- SSL certificate is managed by Cloudflare (Flexible — HTTPS to user, HTTP to origin)

> **Details:** [domena.md](domena.md) — complete domain change history.

---

## 💾 **Longhorn Storage**

### **Installation**

```bash
kubectl create namespace longhorn-system
helm repo add longhorn https://charts.longhorn.io
helm install longhorn longhorn/longhorn --namespace longhorn-system \
  --set defaultSettings.defaultReplicaCount=2 \
  --set persistence.defaultClassReplicaCount=2
```

### **StorageClass**

```bash
kubectl get sc
# NAME             PROVISIONER            RECLAIMPOLICY   VOLUMEBINDINGMODE
# longhorn (default) driver.longhorn.io   Delete          Immediate
# local-path       rancher.io/local-path  Delete          WaitForFirstConsumer
```

### **PVCs in Use**

```bash
kubectl get pvc -n sola-app
```

| PVC | Size | Access Mode | Usage |
|---|---|---|---|
| `sola-postgresql` | 5Gi | RWO | PG data |
| `sola-postgresql-wal` | 2Gi | RWO | WAL logs |

**PVC Explanation:**

| PVC | What it stores | Why it matters |
|---|---|---|
| `sola-postgresql` (5Gi) | **PG database data** — all tables, indexes, users, reservations, grades. The "main" PVC. If this is lost, all data is gone. | The database itself. 5Gi is enough for a full school year (users, reservations, assessments). |
| `sola-postgresql-wal` (2Gi) | **Write-Ahead Logs (WAL)** — a journal of every change made to the database, written before the data files themselves. Used for: crash recovery (if PG crashes mid-write), replica replication (the replica reads WAL and replays changes), point-in-time recovery (restore to an exact moment). | Smaller PVC (2Gi) because WALs are recycled. Without WALs the replica cannot keep up with the primary. |

**Longhorn replication** (2 copies) ensures data survives the loss of one node. Both PVCs have two replicas — one on each k3s node.

### **Longhorn UI**

```bash
# Access Longhorn dashboard
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# Open: http://localhost:8080
```

### **Checking Disks**

```bash
kubectl get lhn -n longhorn-system -o json | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for n in data['items']:
    name = n['metadata']['name']
    for disk_id, disk in n['status']['diskStatus'].items():
        avail = int(disk.get('storageAvailable',0)) / 1024**3
        max_s = int(disk.get('storageMaximum',0)) / 1024**3
        print(f'{name}: {avail:.0f} GiB free / {max_s:.0f} GiB total')
"
```

---

## 📊 **Daily Backup and Reports**

### **Backup CronJob** (`sola-db-backup`)

- **Schedule:** `0 4 * * *` (every day at 4:00)
- **Time zone:** Europe/Ljubljana
- **Active:** ✅ (last executed 10h ago)

Backs up the entire database (pg_dump) and sends to `BACKUP_EMAIL`.

### **Daily Report CronJob** (`sola-daily-report`)

- **Schedule:** `0 4 * * *` (every day at 4:00)
- **Time zone:** Europe/Ljubljana
- **Active:** ✅ (last executed 10h ago)

Sends a daily status overview of the k3s cluster (nodes, Longhorn, replicas) via Hermes agent.

---

## 🛠️ **Maintenance and Failures**

### **Common Diagnostic Commands**

```bash
# Check node status
kubectl get nodes -o wide

# Check all important pods
kubectl get pods -n sola-app -o wide
kubectl get pods -n sola -o wide
kubectl get pods -n longhorn-system | grep -E "instance-manager|longhorn-manager"

# Check CNPG cluster status
kubectl get cluster -n sola sola-db
kubectl describe cluster -n sola sola-db

# Check app logs
kubectl logs -n sola-app -l app=sola-app --tail=50

# Test health endpoint
curl -s http://{{LB_IP}}:{{LB_PORT}}/health
curl -sI https://{{DOMAIN}}
```

### **Failure Simulation — Node Failure**

```bash
# Power off k3s-1
ssh k3s-1 "sudo poweroff"

# Wait 2 minutes, then verify
kubectl get pods -n sola -o wide
# sola-db-2 should be primary

kubectl get pods -n sola-app -o wide
# Both sola-app pods should be on k3s-2
# (k3s reschedules them to the surviving node)

curl -I https://{{DOMAIN}}
# Still accessible!

# When k3s-1 comes back:
# CNPG automatically adds sola-db-1 as a replica
kubectl get cluster -n sola sola-db
# 2 ready instances
```

### **Failure Simulation — Pod Failure**

```bash
# Delete one app pod — Deployment recreates it immediately
kubectl delete pod -n sola-app -l app=sola-app
kubectl rollout status -n sola-app deployment/sola-app
```

### **Fixing nginx**

```bash
# If LoadBalancer IP changes
ssh k3s-2
sudo sed -i 's/{{LB_IP}}/NEW_IP/' /etc/nginx/sites-available/default
sudo systemctl restart nginx
sudo nginx -t
```

---

## 📝 **Complete Command Reference**

### **App Management**

```bash
# Deploy production
kubectl apply -k k8s/app/overlays/production-lb/

# Restart
kubectl rollout restart -n sola-app deployment/sola-app

# Logs (real-time)
kubectl logs -n sola-app -f deployment/sola-app

# Scale
kubectl scale deployment -n sola-app sola-app --replicas=3
```

### **Database**

```bash
# Connect to primary database
kubectl exec -n sola -it sola-db-1 -- psql -U postgres -d sola

# Count records
kubectl exec -n sola sola-db-1 -- psql -U postgres -d sola -c \
  "SELECT count(*) FROM users; SELECT count(*) FROM reservations;"

# CNPG cluster status
kubectl get cluster -n sola sola-db -o yaml

# Check replication
kubectl exec -n sola sola-db-1 -- psql -U postgres -c \
  "SELECT application_name, state, sync_state FROM pg_stat_replication;"
```

### **Storage**

```bash
# PVCs
kubectl get pvc -n sola
kubectl get pv | grep sola

# Longhorn volume
kubectl get volumes -n longhorn-system
```

### **Networking**

```bash
# Services
kubectl get svc -n sola-app
kubectl get svc -n sola

# Endpoints (who is the current primary)
kubectl get endpoints -n sola sola-db-rw
```

### **Logs**

```bash
# App
kubectl logs -n sola-app -l app=sola-app --tail=100

# CNPG
kubectl logs -n sola sola-db-1 --tail=50

# Nginx
ssh k3s-2 "sudo tail -f /var/log/nginx/access.log"

# MetalLB
kubectl logs -n metallb-system -l app=metallb --tail=50
```

### **Application Update**

```bash
cd /home/admin/reservation_app
git pull
docker build -t sola-app:latest .
docker push sola-app:latest
kubectl rollout restart -n sola-app deployment/sola-app
kubectl rollout status -n sola-app deployment/sola-app
```

---

## ✅ **Checklist — Current System Status**

- [x] k3s-1 Ready (control-plane,etcd)
- [x] k3s-2 Ready (control-plane,etcd)
- [x] sola-app Pod 1 Running (k3s-1)
- [x] sola-app Pod 2 Running (k3s-2)
- [x] sola-db-1 Primary (k3s-1)
- [x] sola-db-2 Replica (k3s-2)
- [x] CNPG cluster healthy (2/2 ready)
- [x] MetalLB LoadBalancer ({{LB_IP}})
- [x] nginx proxy (k3s-2:8080 → {{LB_IP}}:{{LB_PORT}})
- [x] Cloudflare DNS ({{DOMAIN}}, proxied)
- [x] Longhorn storage (both nodes)
- [x] Daily backup (4:00) ✅
- [x] Daily report (4:00) ✅
- [x] Health check (200 OK)

---

## 📌 **Important Notes**

- **Failover is completely automatic** — no manual intervention needed
- **Both nodes are control-plane** — no separate worker nodes
- **Cloudflare origin** → LoadBalancer IP (`{{LB_IP}}`, port 80)
- **Nginx on both nodes** (port {{NGINX_PORT}}) — proxy_pass to LoadBalancer IP `{{LB_IP}}:{{LB_PORT}}`
- **App uses** `sola-db-rw.sola:{{K8S_DB_PORT}}` — always on the current primary
- **Old Bitnami PostgreSQL was removed** — we use CNPG
- **Longhorn replication** — 2 replicas, data safe even with one node loss
- **If LoadBalancer IP changes** — update: Cloudflare, nginx, and this document
