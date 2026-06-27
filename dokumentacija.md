# 🚀 **Sola App — Rezervacijski Sistem OŠ Toneta Čufarja**
## **Celovit vodič za postavitev, upravljanje in visoko razpoložljivost**

---

## 📑 **Kazalo vsebine**
1. [Arhitektura sistema](#arhitektura-sistema)
2. [Strojna oprema in omrežje](#strojna-oprema-in-omrežje)
3. [Kubernetes (k3s) Cluster](#kubernetes-k3s-cluster)
4. [Aplikacija Sola App](#aplikacija-sola-app)
5. [PostgreSQL HA — CloudNativePG](#postgresql-ha--cloudnativepg)
6. [MetalLB LoadBalancer](#metallb-loadbalancer)
7. [Nginx Reverse Proxy](#nginx-reverse-proxy)
8. [Cloudflare DNS](#cloudflare-dns)
9. [Longhorn Storage](#longhorn-storage)
10. [Dnevni backup in reporti](#dnevni-backup-in-reporti)
11. [Vzdrževanje in okvare](#vzdrževanje-in-okvare)
12. [Celoten sklic ukazov](#celoten-sklic-ukazov)

---

## 🏗️ **Arhitektura sistema**

### **Strojna in omrežna shema**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         K3S KUBERNETES CLUSTER                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────┐    ┌─────────────────────────┐            │
│  │    k3s-1 (MASTER)       │    │    k3s-2 (WORKER)       │            │
│  │    HP ProBook 455 G5    │    │    HP ProBook 450 G5    │            │
│  │    IP: 193.2.171.250    │    │    IP: 193.2.171.249    │            │
│  │                         │    │                         │            │
│  │  ┌──────────────────┐   │    │  ┌──────────────────┐   │            │
│  │  │ sola-app Pod 1   │   │    │  │ sola-app Pod 2   │   │            │
│  │  │ (app.ostc.org)   │   │    │  │ (app.ostc.org)   │   │            │
│  │  └──────────────────┘   │    │  └──────────────────┘   │            │
│  │  ┌──────────────────┐   │    │  ┌──────────────────┐   │            │
│  │  │ sola-db-1        │   │    │  │ sola-db-2        │   │            │
│  │  │ (PG PRIMARY)     │◄──┼────┼──┤ (PG REPLICA)     │   │            │
│  │  │ CNPG Instance    │   │    │  │ CNPG Instance    │   │            │
│  │  └──────────────────┘   │    │  └──────────────────┘   │            │
│  │                         │    │                         │            │
│  │  ┌──────────────────┐   │    │  ┌──────────────────┐   │            │
│  │  │ Longhorn         │   │    │  │ Longhorn         │   │            │
│  │  │ Instance Manager │   │    │  │ Instance Manager │   │            │
│  │  └──────────────────┘   │    │  └──────────────────┘   │            │
│  │                         │    │                         │            │
│  │  ┌──────────────────┐   │    │  ┌──────────────────┐   │            │
│  │  │ MetalLB Speaker  │   │    │  │ MetalLB Speaker  │   │            │
│  │  └──────────────────┘   │    │  └──────────────────┘   │            │
│  └─────────────────────────┘    └───────────┬─────────────┘            │
│                                              │                          │
│              ┌───────────────────────────────┘                          │
│              │                                                          │
│  ┌───────────▼──────────────────────────────────────────────┐           │
│  │        nginx Reverse Proxy (k3s-2, port 8080)            │           │
│  │        proxy_pass http://193.2.171.200:8002              │           │
│  └──────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              │
                    ┌─────────▼─────────┐
                    │  Cloudflare DNS    │
                    │  ostc-app.org      │
                    │  → 193.2.171.200   │
                    └───────────────────┘
                              │
                              │  Internet
                              ▼
                    🌐 Uporabniki (učitelji, vodstvo)
```

### **Pregled komponent**

| Komponenta | Lokacija | Namen |
|---|---|---|
| **k3s-1** | HP ProBook 455 G5 (193.2.171.250) | Control-plane, app pod, PG primary |
| **k3s-2** | HP ProBook 450 G5 (193.2.171.249) | Worker, app pod, PG replica, nginx |
| **Sola App (FastAPI)** | 2 poda (oba noda) | Rezervacije, ocenjevanje, prijava |
| **CloudNativePG** | 2 instanci (oba noda) | PostgreSQL baza z avtomatskim failoverjem |
| **Longhorn** | Oba noda | Distribuirano shranjevanje (PVC-ji) |
| **MetalLB** | Oba noda | LoadBalancer IP (193.2.171.200) |
| **nginx** | k3s-2 | Reverse proxy (port 8080 → LoadBalancer) |
| **Cloudflare** | Zunanji | DNS, SSL, proxy |

---

## 💻 **Strojna oprema in omrežje**

### **Specifikacije**

| Node | Model | CPU | RAM | Disk | Vloga |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Control-plane, app, PG primary |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Worker, app, PG replica, nginx |

### **Omrežne nastavitve**

```bash
# Lokalno omrežje (Arnes)
k3s-1: 193.2.171.250/24
k3s-2: 193.2.171.249/24
Gateway: 193.2.171.1
DNS: 193.2.171.10

# Kubernetes Pod CIDR
10.42.0.0/16

# Kubernetes Service CIDR
10.43.0.0/16

# LoadBalancer IP pool (MetalLB)
193.2.171.200 - 193.2.171.210
```

### **Namizni dostop**

```bash
# SSH v oba noda
ssh admin_os@193.2.171.250    # k3s-1
ssh admin_os@193.2.171.249    # k3s-2

# Sudo geslo je enako na obeh
sudo -i  # password: 7c6b1234?
```

---

## ☸️ **Kubernetes (k3s) Cluster**

### **Namestitev k3s (en ukaz)**

```bash
# Na k3s-1 (control-plane)
curl -sfL https://get.k3s.io | sh -s - --disable=servicelb

# Na k3s-2 (worker)
curl -sfL https://get.k3s.io | K3S_URL=https://193.2.171.250:6443 \
  K3S_TOKEN=$(sudo cat /var/lib/rancher/k3s/server/node-token) sh -
```

> ⚠️ `--disable=servicelb` onemogoči vgrajeni k3s load balancer, ker uporabljamo MetalLB.

### **Preverjanje stanja**

```bash
kubectl get nodes
# NAME    STATUS   ROLES                  AGE   VERSION
# k3s-1   Ready    control-plane,etcd     19d   v1.35.5+k3s1
# k3s-2   Ready    control-plane,etcd     22d   v1.35.5+k3s1

kubectl get pods -A
kubectl get svc -A
```

### **Namespaces na clusterju**

| Namespace | Namen |
|---|---|
| `sola-app` | Aplikacija (deployment, configmap, secret) |
| `sola` | PostgreSQL cluster (CNPG instance, servisi) |
| `cnpg-system` | CloudNativePG operator |
| `longhorn-system` | Longhorn distributed storage |
| `metallb-system` | MetalLB load balancer |
| `kube-system` | Kubernetes sistemski podi |

---

## 🐍 **Aplikacija Sola App**

### **Opis**

Sola App je **FastAPI** spletna aplikacija za:
- **Rezervacije** — tablice, računalnica, ladja (pomivalni čoln), gospodinjska učilnica
- **Ocenjevanje** — beleženje ocen, ustnih in pisnih preizkusov
- **Blokirani datumi** — zaprtje terminov za posamezne prostore
- **Prijava** — avtentikacija preko šolskega Nextcloud računa, vloge: admin, vodstvo, teacher

### **Struktura kode**

```
reservation_app/
├── app/
│   ├── main.py              # FastAPI app, middleware, startup
│   ├── config.py            # Nastavitve (iz env/ConfigMap)
│   ├── database.py          # SQLAlchemy engine, session
│   ├── models.py            # DB modeli (User, Reservation, Assessment, BlockedDate)
│   ├── schemas.py           # Pydantic sheme
│   ├── race.py              # Helper za časovne termine
│   ├── routers/
│   │   ├── auth.py          # Prijava, gesla
│   │   ├── rezervacije.py   # CRUD rezervacij
│   │   ├── ocenjevanja.py   # CRUD ocenjevanj
│   │   └── blocked_dates.py # Blokirani datumi
│   └── templates/           # Jinja2 HTML predloge
├── k8s/                     # Kubernetes deploy konfiguracija
│   ├── app/base/            # Base kustomize
│   ├── app/overlays/        # Overlayi (ingress, production-lb, frp)
│   └── cluster/             # MetalLB konfiguracija
├── deploy/                  # FRP tunel konfiguracija
├── Dockerfile               # Container build
└── requirements.txt         # Python odvisnosti
```

### **FastAPI endpointi**

| Endpoint | Metoda | Opis |
|---|---|---|
| `/health` | GET | Health check (200 = OK) |
| `/auth/login` | GET, POST | Prijava uporabnika |
| `/auth/logout` | GET | Odjava |
| `/auth/forgot-password` | GET, POST | Pozabljeno geslo |
| `/auth/reset-password` | GET, POST | Ponastavitev gesla |
| `/rezervacije` | GET, POST | Seznam / nova rezervacija |
| `/rezervacije/{id}` | DELETE | Preklic rezervacije |
| `/api/razredi` | GET | Seznam razredov |
| `/api/prostori` | GET | Seznam prostorov |
| `/api/schedule` | GET | Urnik terminov |
| `/ocenjevanja` | GET, POST | Seznam / novo ocenjevanje |
| `/blocked-dates` | GET, POST, DELETE | Blokirani datumi |

### **DB modeli**

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
              topologyKey: kubernetes.io/hostname
      containers:
      - name: app
        image: mato12345/sola-app:latest
        ports:
        - containerPort: 8002
        envFrom:
        - configMapRef:
            name: sola-config
        - secretRef:
            name: sola-secrets
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

### **Dockerfile (multi-stage)**

```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq5 postgresql-client-18 curl
COPY --from=builder /root/.local /home/appuser/.local
COPY . .
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "2"]
```

### **ConfigMap (sola-config)**

```yaml
BASE_URL: "https://ostc-app.org"
APP_HOST: "0.0.0.0"
APP_PORT: "8002"
TABLICE_MAX: "28"
PROSTORI: "tablice,racunalnica,ladja,gospodinjska-ucilnica"
SCHEDULE: '{"0":"07:30-08:15","1":"08:20-09:05","2":"09:15-10:00",...}'
RAZREDI: "IP/NIP/ID,1.a,1.b,...,9.5"
```

### **Secret (sola-secrets)**

```yaml
DATABASE_URL: "postgresql://sola:***@sola-db-rw.sola:5432/sola"
MAIL_SERVER: "mail.arnes.si"
MAIL_PORT: "587"
MAIL_USERNAME: "oscuf"
MAIL_PASSWORD: "***"
MAIL_FROM: "os-toneta-cufarja-jesenice@guest.arnes.si"
BACKUP_EMAIL: "matej.cusin2@guest.arnes.si"
```

---

## 🗄️ **PostgreSQL HA — CloudNativePG**

### **Zakaj CloudNativePG?**

| Lastnost | Bitnami Helm | CloudNativePG |
|---|---|---|
| Avtomatski failover | ❌ | ✅ ~30-60s |
| Node anti-affinity | Ročno | ✅ Vgrajeno |
| Storage management | Ročno | ✅ Vgrajeno |
| Velikost | 1GB+ | ~50MB operator |
| Built-in backup | ❌ | ✅ Barman/WAL |
| Kubernetes native | ❌ (klasičen Helm) | ✅ CRD operator |

### **Namestitev CNPG operatorja**

```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system \
  --create-namespace
```

### **CNPG Cluster konfiguracija**

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
  affinity:
    enablePodAntiAffinity: true
    podAntiAffinityType: preferred
    topologyKey: kubernetes.io/hostname
  enablePDB: true
  failoverDelay: 30
```

### **Stanje clustra**

```bash
kubectl get cluster -n sola sola-db
# NAME      AGE   INSTANCES   READY   STATUS                     PRIMARY
# sola-db   30m   2           2       Cluster in healthy state   sola-db-1

kubectl get pods -n sola -o wide
# NAME        READY   STATUS    IP            NODE
# sola-db-1   1/1     Running   10.42.0.85    k3s-1   ← PRIMARY
# sola-db-2   1/1     Running   10.42.1.106   k3s-2   ← REPLICA
```

### **Servisi za povezavo**

| Service | Namespace | Vloga |
|---|---|---|
| `sola-db-rw.sola:5432` | sola | Read-Write — **vedno na primary** (uporablja app) |
| `sola-db-ro.sola:5432` | sola | Read-Only — load-balanced čez vse instance |
| `sola-db-r.sola:5432` | sola | Read — katerakoli instance |

### **Potek avtomatskega failoverja**

```ascii
┌─ K3s-1 crkne ─────────────────────────────────────┐
│                                                    │
│  1. sola-db-1 (primary) postane nedosegljiv        │
│  2. CNPG operator zazna izpad                      │
│  3. Počaka 30s (failoverDelay)                     │
│  4. Promovira sola-db-2 (k3s-2) v novo primary     │
│  5. Service sola-db-rw preusmeri na sola-db-2      │
│  6. App na k3s-2 se poveže na nova primary         │
│                                                    │
│  Skupni izpad: ~1-2 minuti                         │
└────────────────────────────────────────────────────┘

┌─ K3s-1 nazaj ─────────────────────────────────────┐
│                                                    │
│  1. CNPG opazi nov node                            │
│  2. sola-db-1 se samodejno pridruži kot REPLICA    │
│  3. Brez ročnega posega                            │
└────────────────────────────────────────────────────┘
```

### **Migracija iz Bitnami PostgreSQL**

```bash
# 1. Backup obstoječe baze
kubectl exec -n sola sola-postgresql-primary-0 -- \
  pg_dump -U sola sola > /tmp/backup.sql

# 2. Ustvari CNPG cluster
kubectl apply -f sola-cnpg-cluster.yaml

# 3. Restore v novo bazo
sed '/^\\\\restrict /d' /tmp/backup.sql | \
  kubectl exec -n sola -i sola-db-1 -- psql -U postgres -d sola

# 4. Posodobi DATABASE_URL v secretu
# (geslo mora ostati enako)

# 5. Poženi app
kubectl scale deployment -n sola-app sola-app --replicas=2

# 6. Počisti staro Bitnami bazo
kubectl delete sts -n sola sola-postgresql-primary sola-postgresql-read
kubectl delete svc -n sola sola-postgresql-primary sola-postgresql-read
kubectl delete pod -n sola sola-postgresql-primary-0 sola-postgresql-read-0
```

---

## 🌐 **MetalLB LoadBalancer**

### **Konfiguracija**

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 193.2.171.200-193.2.171.210
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-advertisement
  namespace: metallb-system
```

### **Service tipa LoadBalancer**

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
    targetPort: 8002
```

```bash
kubectl get svc -n sola-app sola-app
# NAME      TYPE           CLUSTER-IP     EXTERNAL-IP      PORT(S)
# sola-app  LoadBalancer   10.43.216.34   193.2.171.200   8002:31927/TCP
```

---

## 🔄 **Nginx Reverse Proxy**

### **Lokacija**

Nginx teče **samo na k3s-2** (ni ga na k3s-1).

```bash
ssh k3s-2
cat /etc/nginx/sites-available/default
```

### **Konfiguracija**

```nginx
server {
    listen 8080 default_server;
    listen [::]:8080 default_server;
    
    server_name ostc-app.org;
    
    location / {
        proxy_pass http://193.2.171.200:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### **Prometni tok**

```
Uporabnik → Cloudflare (SSL, ostc-app.org)
    → nginx:8080 na k3s-2
        → proxy_pass 193.2.171.200:8002
            → Service LoadBalancer
                → sola-app Pod (k3s-1 ali k3s-2)
```

---

## ☁️ **Cloudflare DNS**

### **DNS nastavitve**

| Tip | Ime | Vrednost | Proxy |
|---|---|---|---|
| A | `ostc-app.org` | `193.2.171.200` | ✅ Proxied (SSL) |

### **Zakaj LoadBalancer IP in ne ClusterIP?**

- **ClusterIP** (10.43.x.x) je dostopen samo znotraj Kubernetes omrežja
- **LoadBalancer IP** (193.2.171.200) je fiksen IP v lokalnem omrežju, dosegljiv nginxu in FRP tunelu
- Cloudflare proxy omogoča SSL termination, DDoS zaščito in caching

---

## 💾 **Longhorn Storage**

### **Namestitev**

```bash
kubectl create namespace longhorn-system
helm repo add longhorn https://charts.longhorn.io
helm install longhorn longhorn/longhorn --namespace longhorn-system
```

### **StorageClass**

```bash
kubectl get sc
# NAME             PROVISIONER          RECLAIMPOLICY   VOLUMEBINDINGMODE
# longhorn         driver.longhorn.io   Delete          Immediate
# local-path       rancher.io/local-path Delete          WaitForFirstConsumer
```

### **PVC-ji v uporabi**

| PVC | Namespace | Velikost | Uporaba |
|---|---|---|---|
| `sola-db-1` | sola | 1Gi | CNPG primary (k3s-1) |
| `sola-db-2` | sola | 1Gi | CNPG replica (k3s-2) |

### **Longhorn UI**

```bash
# Dostop do Longhorn dashboarda
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# Odpri: http://localhost:8080
```

---

## 📊 **Dnevni backup in reporti**

### **Backup CronJob**

Backupira celotno bazo in pošlje na email.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: sola-db-backup
  namespace: sola-app
spec:
  schedule: "0 3 * * *"    # Vsak dan ob 3:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:18-alpine
            command:
            - sh
            - -c
            - |
              PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | gzip > /tmp/backup.sql.gz
              echo "Backup: $(date)" | mail -s "DB Backup" -a /tmp/backup.sql.gz $BACKUP_EMAIL
```

### **Daily Report CronJob**

Pošlje dnevni pregled rezervacij in ocenjevanj.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: sola-daily-report
  namespace: sola-app
spec:
  schedule: "0 6 * * *"    # Vsak dan ob 6:00
```

---

## 🛠️ **Vzdrževanje in okvare**

### **Pogosti ukazi za diagnostiko**

```bash
# Preveri stanje nodov
kubectl get nodes -o wide

# Preveri vse pomebne pod-e
kubectl get pods -n sola-app -o wide
kubectl get pods -n sola -o wide
kubectl get pods -n longhorn-system | grep -E "instance-manager|longhorn-manager"

# Preveri stanje CNPG clustra
kubectl get cluster -n sola sola-db
kubectl describe cluster -n sola sola-db

# Preveri log-e app-a
kubectl logs -n sola-app -l app=sola-app --tail=50

# Testiraj health endpoint
curl -s http://193.2.171.200:8002/health
curl -sI https://ostc-app.org
```

### **Simulacija okvare — padec k3s-1**

```bash
# Ugasni k3s-1
ssh k3s-1 "sudo poweroff"

# Počakaj 2 minuti, nato preveri
kubectl get pods -n sola -o wide
# sola-db-2 naj bo primarna

kubectl get pods -n sola-app -o wide
# Oba sola-app poda naj bosta na k3s-2
# (k3s jih reschedule-a na preživeli node)

curl -I https://ostc-app.org
# Še vedno dostopno!

# Ko k3s-1 nazaj
# CNPG samodejno doda sola-db-1 kot repliko
kubectl get cluster -n sola sola-db
# 2 ready instance
```

### **Simulacija okvare — padec aplikacijskega poda**

```bash
# Izbriši en app pod
kubectl delete pod -n sola-app -l app=sola-app --field-selector status.phase=Running
# Deployment ga takoj recreira
```

### **Obnova gesla za bazo**

```bash
# Preveri geslo v secretu
kubectl get secret -n sola sola-db-creds -o jsonpath='{.data.password}' | base64 -d

# Popravi DATABASE_URL v app secretu
NEW_URL="postgresql://sola:PASSWORD@sola-db-rw.sola:5432/sola"
kubectl patch secret -n sola-app sola-secrets \
  --type='json' \
  -p="[{\"op\":\"replace\",\"path\":\"/data/DATABASE_URL\",\"value\":\"$(echo -n $NEW_URL | base64)\"}]"

# Restartaj app
kubectl rollout restart -n sola-app deployment/sola-app
```

### **Poprava nginx-a**

```bash
# Če se LoadBalancer IP spremeni
ssh k3s-2
sudo sed -i 's/193.2.171.200/NEW_IP/' /etc/nginx/sites-available/default
sudo systemctl restart nginx

# Preveri konfiguracijo
sudo nginx -t
```

---

## 📝 **Celoten sklic ukazov**

### **App management**

```bash
# Deploy
kubectl apply -k k8s/app/overlays/production-lb/

# Restart
kubectl rollout restart -n sola-app deployment/sola-app

# Logs
kubectl logs -n sola-app -f deployment/sola-app

# Scale
kubectl scale deployment -n sola-app sola-app --replicas=3
```

### **Database**

```bash
# Poveži se na primary bazo
kubectl exec -n sola -it sola-db-1 -- psql -U postgres -d sola

# Preštej uporabnike
kubectl exec -n sola sola-db-1 -- psql -U postgres -d sola -c \
  "SELECT count(*) FROM users; SELECT count(*) FROM reservations;"

# Status clustra
kubectl get cluster -n sola sola-db -o yaml

# Preveri replikacijo
kubectl exec -n sola sola-db-1 -- psql -U postgres -c \
  "SELECT application_name, state, sync_state FROM pg_stat_replication;"
```

### **Storage**

```bash
# PVC-ji
kubectl get pvc -n sola
kubectl get pv | grep sola

# Longhorn
kubectl get volumes -n longhorn-system
```

### **Networking**

```bash
# Servisi
kubectl get svc -n sola-app
kubectl get svc -n sola

# Endpointi
kubectl get endpoints -n sola-app sola-app
```

### **Dnevniki**

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

---

## ✅ **Kontrolni seznam — stanje sistema**

- [x] k3s-1 Running (control-plane)
- [x] k3s-2 Running (worker)
- [x] sola-app Pod 1 Running (k3s-1)
- [x] sola-app Pod 2 Running (k3s-2)
- [x] sola-db-1 Primary (k3s-1)
- [x] sola-db-2 Replica (k3s-2)
- [x] CNPG cluster healthy
- [x] MetalLB LoadBalancer (193.2.171.200)
- [x] nginx proxy (k3s-2:8080)
- [x] Cloudflare DNS (ostc-app.org)
- [x] Longhorn storage (oba noda)
- [x] Dnevni backup (3:00)
- [x] Dnevni report (6:00)
- [x] Health check (200 OK)

---

## 📌 **Pomembne opombe**

- **Failover je popolnoma avtomatski** — ni potrebno ročno posredovanje
- **Geslo za sudo na nodih:** `7c6b1234?` (isto na obeh)
- **Cloudflare kaže na LoadBalancer IP** `193.2.171.200` — ne na ClusterIP
- **Nginx samo na k3s-2** — proxy_pass na LoadBalancer IP (ne na ClusterIP)
- **Stara Bitnami PostgreSQL je odstranjena** po migraciji na CNPG
- **Longhorn replikacija** — podatki so varni tudi ob izgubi enega noda
- **Če se LoadBalancer IP spremeni**, posodobi: Cloudflare, nginx in ta dokument
