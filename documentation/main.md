🌐 **Jezik / Language:** [🇸🇮 Slovenščina](main.md) | [🇬🇧 English](en/main.md)

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
┌──────────────────────────────────────────────────────────────────────────┐
│                         K3S KUBERNETES CLUSTER (2 noda)                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────┐    ┌──────────────────────────┐            │
│  │    k3s-1                  │    │    k3s-2                  │            │
│  │    HP ProBook 455 G5     │    │    HP ProBook 450 G5     │            │
│  │    IP: 193.2.171.250     │    │    IP: 193.2.171.249     │            │
│  │    control-plane,etcd    │    │    control-plane,etcd    │            │
│  │                          │    │                          │            │
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ sola-app Pod 1    │   │    │  │ sola-app Pod 2    │   │            │
│  │  │ (app.ostc-app.org)│   │    │  │ (app.ostc-app.org)│   │            │
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
│  │        nginx Reverse Proxy (k3s-2, port 8080)              │           │
│  │        proxy_pass http://193.2.171.200:8002                │           │
│  └───────────────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────────────┘
                              │
                              │
                    ┌─────────▼─────────┐
                    │  Cloudflare DNS    │
                    │  ostc-app.org      │
                    │  → 104.21.81.50    │  📡 Cloudflare proxy IP-ja
                    │  → 172.67.156.249  │
                    └───────────────────┘
                              │
                              │  Internet
                              ▼
                    🌐 Uporabniki (učitelji, vodstvo)
```

> **Opomba:** Oba noda sta `control-plane,etcd` — ni ločenih worker nodov. k3s podpava poganjanje uporabniških podov tudi na control-plane nodih.

### **Prometni tok**

```
🌐 Uporabnik
  → Cloudflare (SSL, proxy, ostc-app.org)
    → Cloudflare IP 104.21.81.50 / 172.67.156.249
      → Cloudflare tunnel/forward na 193.2.171.249:8080 (k3s-2)
        → nginx proxy_pass 193.2.171.200:8002
          → Service LoadBalancer (MetalLB)
            → sola-app Pod (k3s-1 ali k3s-2)
```

Cloudflare proxy omogoča:
- **SSL termination** — HTTPS od uporabnika do Cloudflare
- **DDoS zaščita**
- **Caching** — statične vsebine
- **Skrit javni IP** — resnični strežniki niso direktno izpostavljeni

### **Pregled komponent**

| Komponenta | Lokacija | Namen |
|---|---|---|
| **k3s-1** | HP ProBook 455 G5 (193.2.171.250) | Control-plane, app pod, PG primary, nginx |
| **k3s-2** | HP ProBook 450 G5 (193.2.171.249) | Control-plane, app pod, PG replica, nginx |
| **Sola App (FastAPI)** | 2 poda (oba noda) | Rezervacije, ocenjevanje, prijava |
| **CloudNativePG** | 2 instanci (oba noda) | PostgreSQL baza z avtomatskim failoverjem |
| **Longhorn** | Oba noda | Distribuirano shranjevanje (PVC-ji) |
| **MetalLB** | Oba noda | LoadBalancer IP (193.2.171.200) |
| **nginx** | Oba noda (k3s-2 primaren) | Reverse proxy (port 8080 → LoadBalancer) |
| **Cloudflare** | Zunanji | DNS, SSL, proxy |

---

## 💻 **Strojna oprema in omrežje**

### **Specifikacije**

| Node | Model | CPU | RAM | Disk | Vloga |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Control-plane,etcd, app, PG primary, nginx |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Control-plane,etcd, app, PG replica, nginx |

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

### **Dostop**

```bash
# SSH v oba noda
ssh admin_os@193.2.171.250    # k3s-1
ssh admin_os@193.2.171.249    # k3s-2

# sudo geslo je enako na obeh nodih
```

---

## ☸️ **Kubernetes (k3s) Cluster**

### **Namestitev k3s (en ukaz)**

```bash
# Na k3s-1 (prvi control-plane)
curl -sfL https://get.k3s.io | sh -s - --disable=servicelb

# Na k3s-2 (drugi control-plane)
curl -sfL https://get.k3s.io | K3S_URL=https://193.2.171.250:6443 \
  K3S_TOKEN=$(sudo cat /var/lib/rancher/k3s/server/node-token) sh -
```

> ⚠️ `--disable=servicelb` onemogoči vgrajeni k3s load balancer, ker uporabljamo MetalLB.

### **Trenutno stanje**

```bash
kubectl get nodes
# NAME    STATUS   ROLES                AGE   VERSION
# k3s-1   Ready    control-plane,etcd   19d   v1.35.5+k3s1
# k3s-2   Ready    control-plane,etcd   22d   v1.35.5+k3s1

kubectl get pods -A
kubectl get svc -A
```

### **Namespaces na clusterju**

| Namespace | Namen |
|---|---|
| `sola-app` | Aplikacija (deployment, configmap, secret, cronjob) |
| `sola` | PostgreSQL cluster (CNPG instance, servisi) |
| `cnpg-system` | CloudNativePG operator |
| `longhorn-system` | Longhorn distributed storage |
| `metallb-system` | MetalLB load balancer |
| `kube-system` | Kubernetes sistemski podi |

---

## 🐍 **Aplikacija Sola App**

### **Opis**

Sola App je **FastAPI** spletna aplikacija za:
- **Rezervacije** — tablice, računalnica, ladja, gospodinjska učilnica
- **Ocenjevanje** — napovedovanje pisnih ocenjevanj
- **Blokirani datumi** — zaprtje terminov za posamezne prostore
- **Prijava** — avtentikacija, vloge: admin, vodstvo, teacher

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
│   │   ├── auth.py          # Prijava, gesla, admin panel
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
├── documentation/           # 📚 Dokumentacija (ta mapa)
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
        image: mato12345/sola-app:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8002
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

### **ConfigMap (sola-config) — dejanske vrednosti**

```yaml
BASE_URL: "https://ostc-app.org"
APP_HOST: "0.0.0.0"
APP_PORT: "8002"
TABLICE_MAX: "28"
PROSTORI: "tablice,racunalnica,ladja,gospodinjska-ucilnica"
SCHEDULE: '{"0":"07:30-08:15","1":"08:20-09:05","2":"09:15-10:00","3":"10:20-11:05","4":"11:10-12:55","5":"12:00-12:45","6":"12:50-13:35","7":"14:00-14:45"}'
RAZREDI: "IP/NIP/ID,1.a,1.b,1.c,1.č,2.a,2.b,2.c,2.č,3.a,3.b,3.c,3.č,4.a,4.b,4.c,4.č,5.a,5.b,5.c,5.č,6.a,6.b,6.c,6.č,7.a,7.b,7.c,8.a,8.b,8.c,8.č,8.1,8.2,8.3,8.4,8.5,8.6,9.a,9.b,9.c,9.1,9.2,9.3,9.4,9.5"
```

> ⚠️ **Opomba:** `SCHEDULE` indeks 4 (`"11:10-12:55"`) je podaljšana ura (predzadnja ura traja 1h45m). Preverite, če to ustreza dejanskemu urniku.

### **Secret (sola-secrets)**

Podatki v Secretu (base64 kodirani):
- `DATABASE_URL` — `postgresql://sola:***@sola-db-rw.sola:5432/sola`
- `MAIL_USERNAME` — `oscuf`
- `MAIL_PASSWORD` — (geslo za SMTP)
- `MAIL_SERVER` — `mail.arnes.si`
- `MAIL_PORT` — `587`
- `MAIL_FROM` — `os-toneta.cufarja-jesenice@guest.arnes.si`
- `BACKUP_EMAIL` — `matej.cusin2@guest.arnes.si`

> ⚠️ `DATABASE_URL` uporablja **CNPG service** `sola-db-rw.sola:5432` — vedno kaže na trenutni primary, tudi po failoverju.

---

## 🗄️ **PostgreSQL HA — CloudNativePG**

> **Podrobnosti:** [HA.md](HA.md) — celoten opis arhitekture, failover potek, testiranje.

### **Zakaj CloudNativePG?**

| Lastnost | Bitnami Helm (prej) | CloudNativePG (zdaj) |
|---|---|---|
| Avtomatski failover | ❌ | ✅ ~30-60s |
| Node anti-affinity | Ročno | ✅ Vgrajeno |
| Storage management | Ročno | ✅ Vgrajeno |
| Built-in backup | ❌ | ✅ Barman/WAL |
| Kubernetes native | ❌ (klasičen Helm) | ✅ CRD operator |

### **Kratka konfiguracija**

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

### **Trenutno stanje**

```bash
kubectl get cluster -n sola sola-db
# NAME      AGE   INSTANCES   READY   STATUS                     PRIMARY
# sola-db   2h    2           2       Cluster in healthy state   sola-db-1

kubectl get pods -n sola -o wide
# NAME        READY   STATUS    IP            NODE
# sola-db-1   1/1     Running   10.42.0.85    k3s-1   ← PRIMARY
# sola-db-2   1/1     Running   10.42.1.106   k3s-2   ← REPLICA
```

### **Servisi za povezavo**

| Service | Vloga |
|---|---|
| `sola-db-rw.sola:5432` | **Read-Write** — vedno na primary (uporablja app) |
| `sola-db-ro.sola:5432` | Read-Only — samo replica |
| `sola-db-r.sola:5432` | Read — katerakoli instance |

### **Potek avtomatskega failoverja**

```ascii
┌─ K3s-1 crkne ─────────────────────────────────────┐
│                                                     │
│  1. sola-db-1 (primary) postane nedosegljiv         │
│  2. CNPG operator zazna izpad                       │
│  3. Počaka 30s (failoverDelay)                      │
│  4. Promovira sola-db-2 (k3s-2) v novo primary      │
│  5. Service sola-db-rw preusmeri na sola-db-2       │
│  6. App na k3s-2 se poveže na nova primary          │
│                                                     │
│  Skupni izpad: ~1-2 minuti                          │
└─────────────────────────────────────────────────────┘

┌─ K3s-1 nazaj ──────────────────────────────────────┐
│                                                     │
│  1. CNPG opazi nov node                             │
│  2. sola-db-1 se samodejno pridruži kot REPLICA     │
│  3. Brez ročnega posega                             │
└─────────────────────────────────────────────────────┘
```

### **Ključne točke**

- **Brez ročnega posredovanja** pri failoverju
- **Geslo baze** je v `sola-db-creds` (namespace `sola`) — CNPG ga avtomatsko ustvari
- **App uporablja** `sola-db-rw` — vedno na trenutnem primary
- **Stara Bitnami PostgreSQL** je bila odstranjena po migraciji

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
    name: http
```

```bash
kubectl get svc -n sola-app sola-app
# NAME      TYPE           CLUSTER-IP      EXTERNAL-IP      PORT(S)
# sola-app  LoadBalancer   10.43.122.112   193.2.171.200   8002:32364/TCP
```

---

## 🔄 **Nginx Reverse Proxy**

### **Lokacija**

Nginx teče na **obeh nodih**, vendar Cloudflare kaže na k3s-2 (port 8080). Na k3s-1 je nginx nameščen z ostanki stare konfiguracije, ki ni aktivno v uporabi.

```bash
ssh k3s-2
sudo cat /etc/nginx/sites-available/default
```

### **Konfiguracija (dejanska)**

```nginx
server {
    listen 8080;

    location / {
        proxy_pass http://193.2.171.200:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

> **Opomba:** Cloudflare skrbi za SSL (HTTPS). Nginx posluša na portu 8080 (ne 80/443) in posreduje na MetalLB IP.

---

## ☁️ **Cloudflare DNS**

### **DNS nastavitve**

| Tip | Ime | Vrednost | Proxy |
|---|---|---|---|
| A | `ostc-app.org` | `193.2.171.200` | ✅ Proxied (oranžni oblak) |

Cloudflare proxy pomeni, da:
- `ostc-app.org` resolve-a na Cloudflare IP-je (`104.21.81.50`, `172.67.156.249`)
- Cloudflare posreduje promet na `193.2.171.200:8080` (nginx na k3s-2)
- SSL certifikat ureja Cloudflare (Auto SSL)

> **Podrobnosti:** [domena.md](domena.md) — celotna zgodovina sprememb domene.

---

## 💾 **Longhorn Storage**

### **Namestitev**

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

### **PVC-ji v uporabi**

| PVC | Namespace | Velikost | Uporaba | Node |
|---|---|---|---|---|
| `sola-db-1` | sola | 1Gi | CNPG primary (k3s-1) |
| `sola-db-2` | sola | 1Gi | CNPG replica (k3s-2) |

### **Longhorn UI**

```bash
# Dostop do Longhorn dashboarda
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# Odpri: http://localhost:8080
```

### **Preverjanje diskov**

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

## 📊 **Dnevni backup in reporti**

### **Backup CronJob** (`sola-db-backup`)

- **Schedule:** `0 4 * * *` (vsak dan ob 4:00)
- **Časovna cona:** Europe/Ljubljana
- **Aktivni:** ✅ (nazadnje izveden pred 10h)

Backupira celotno bazo (pg_dump) in pošlje na `BACKUP_EMAIL`.

### **Daily Report CronJob** (`sola-daily-report`)

- **Schedule:** `0 4 * * *` (vsak dan ob 4:00)
- **Časovna cona:** Europe/Ljubljana
- **Aktivni:** ✅ (nazadnje izveden pred 10h)

Pošlje dnevni pregled stanja k3s clustra (nodi, Longhorn, replike) prek Hermes agenta.

---

## 🛠️ **Vzdrževanje in okvare**

### **Pogosti ukazi za diagnostiko**

```bash
# Preveri stanje nodov
kubectl get nodes -o wide

# Preveri vse pomembne pod-e
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

### **Simulacija okvare — padec noda**

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

# Ko k3s-1 nazaj:
# CNPG samodejno doda sola-db-1 kot repliko
kubectl get cluster -n sola sola-db
# 2 ready instance
```

### **Simulacija okvare — padec poda**

```bash
# Izbriši en app pod — Deployment ga takoj recreira
kubectl delete pod -n sola-app -l app=sola-app
kubectl rollout status -n sola-app deployment/sola-app
```

### **Poprava nginx-a**

```bash
# Če se LoadBalancer IP spremeni
ssh k3s-2
sudo sed -i 's/193.2.171.200/NOVI_IP/' /etc/nginx/sites-available/default
sudo systemctl restart nginx
sudo nginx -t
```

---

## 📝 **Celoten sklic ukazov**

### **App management**

```bash
# Deploy produkcija
kubectl apply -k k8s/app/overlays/production-lb/

# Restart
kubectl rollout restart -n sola-app deployment/sola-app

# Logs (v realnem času)
kubectl logs -n sola-app -f deployment/sola-app

# Scale
kubectl scale deployment -n sola-app sola-app --replicas=3
```

### **Database**

```bash
# Poveži se na primary bazo
kubectl exec -n sola -it sola-db-1 -- psql -U postgres -d sola

# Preštej podatke
kubectl exec -n sola sola-db-1 -- psql -U postgres -d sola -c \
  "SELECT count(*) FROM users; SELECT count(*) FROM reservations;"

# Status CNPG clustra
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

# Longhorn volume
kubectl get volumes -n longhorn-system
```

### **Networking**

```bash
# Servisi
kubectl get svc -n sola-app
kubectl get svc -n sola

# Endpointi (kdo je trenutni primary)
kubectl get endpoints -n sola sola-db-rw
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

### **Posodobitev aplikacije**

```bash
cd /home/admin_os/reservation_app
git pull
docker build -t mato12345/sola-app:latest .
docker push mato12345/sola-app:latest
kubectl rollout restart -n sola-app deployment/sola-app
kubectl rollout status -n sola-app deployment/sola-app
```

---

## ✅ **Kontrolni seznam — trenutno stanje sistema**

- [x] k3s-1 Ready (control-plane,etcd)
- [x] k3s-2 Ready (control-plane,etcd)
- [x] sola-app Pod 1 Running (k3s-1)
- [x] sola-app Pod 2 Running (k3s-2)
- [x] sola-db-1 Primary (k3s-1)
- [x] sola-db-2 Replica (k3s-2)
- [x] CNPG cluster healthy (2/2 ready)
- [x] MetalLB LoadBalancer (193.2.171.200)
- [x] nginx proxy (k3s-2:8080 → 193.2.171.200:8002)
- [x] Cloudflare DNS (ostc-app.org, proxied)
- [x] Longhorn storage (oba noda)
- [x] Dnevni backup (4:00) ✅
- [x] Dnevni report (4:00) ✅
- [x] Health check (200 OK)

---

## 📌 **Pomembne opombe**

- **Failover je popolnoma avtomatski** — ni potrebno ročno posredovanje
- **Oba noda sta control-plane** — ni ločenih worker nodov
- **Cloudflare kaže na LoadBalancer IP** `193.2.171.200` — posreduje prek proxy-ja
- **Nginx na obeh nodih** — Cloudflare kaže na k3s-2:8080, na k3s-1 je nginx z ostanki stare konfiguracije
- **App uporablja** `sola-db-rw.sola:5432` — vedno na trenutnem primary
- **Stara Bitnami PostgreSQL je odstranjena** — uporabljamo CNPG
- **Longhorn replikacija** — 2 repliki, podatki varni tudi ob izgubi enega noda
- **Če se LoadBalancer IP spremeni** — posodobi: Cloudflare, nginx in ta dokument
