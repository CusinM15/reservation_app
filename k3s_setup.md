# k3s Setup – Šolski App

Celotna navodila za postavitev k3s Kubernetes clusterja: en master, dva workerja, MetalLB load balancer, Longhorn storage na vseh nodih, PostgreSQL baza, containerizirana FastAPI aplikacija in avtomatski backupi na email.

---

## Arhitektura

```
Internet
    │
    ▼
ostc.si (Cloudflare / DNS)
    │
    ▼
┌──────────────────────────────────────────────────┐
│  Reverse Proxy (nginx na masterju, :80/:443)     │
│  → proxy_pass k3s MetalLB IP                     │
└────────────────────────┬─────────────────────────┘
                         │
                    ┌────┴────┐
                    │ MetalLB │  (LoadBalancer IP :8002)
                    └────┬────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────┴─────┐  ┌────┴─────┐  ┌────┴─────┐
    │  Master   │  │ Worker 1 │  │ Worker 2 │
    │k3s-master   │  │          │  │          │
    │             │  │ ┌──────┐ │  │ ┌──────┐ │
    │PostgreSQL │  │ │sola  │ │  │ │sola  │ │
    │Longhorn   │  │ │pod   │ │  │ │pod   │ │
    │           │  │ └──────┘ │  │ └──────┘ │
    │           │  │Longhorn  │  │Longhorn  │
    └───────────┘  └──────────┘  └──────────┘
```

---

## 📋 Predpogoji

- 3 fizične ali virtualne mašine z **Ubuntu 24.04**
- Vsaka mašina: min **2 CPU**, **4GB RAM**, **20GB disk**
- **root** ali `sudo` dostop na vseh mašinah
- Mašine naj bodo v istem omrežju (medsebojna komunikacija)
- Domena `ostc.si` (za reverse proxy)
- Docker nameščen na masterju (za build slike):
  ```bash
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER
  # Odjavi/prijavi se ponovno
  ```

---

## 1. NAMESTITEV MASTER NODE

Prijavi se na master mašino (`k3s-master`).

### 1.1 Namesti k3s server

```bash
curl -sfL https://get.k3s.io | sudo sh -s - server \
  --disable=traefik \
  --disable=servicelb \
  --write-kubeconfig-mode=644 \
  --cluster-cidr=10.42.0.0/16 \
  --service-cidr=10.43.0.0/16
```

| Parameter | Opis |
|---|---|
| `--disable=traefik` | Ne potrebujemo vgrajenega ingressa, uporabili bomo nginx |
| `--disable=servicelb` | Ne potrebujemo vgrajenega LB, uporabili bomo MetalLB |
| `--write-kubeconfig-mode=644` | Omogoči branje kubeconfig vsem uporabnikom |

### 1.2 Preveri, da k3s deluje

```bash
kubectl get nodes
# Izhod: master (Ready)

kubectl get pods -A
# Vsi naj bodo Running
```

### 1.3 Pridobi token za workerje

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```
Shrani ta token. Izgleda: `K10e8a2...::server:...`

### 1.4 Pridobi IP masterja

```bash
ip a show | grep "inet " | grep -v 127.0.0.1
# Npr. 192.168.1.100
```

---

## 2. NAMESTITEV WORKER NODE 1

Prijavi se na **worker1**.

```bash
export K3S_URL="https://<MASTER_IP>:6443"
export K3S_TOKEN="<TOKEN_IZ_1.3>"
curl -sfL https://get.k3s.io | sudo K3S_URL=$K3S_URL K3S_TOKEN=$K3S_TOKEN sh -
```

Zamenjaj `<MASTER_IP>` in `<TOKEN_IZ_1.3>`.

Na masterju preveri:
```bash
kubectl get nodes
# Prikaz: master + worker1
```

---

## 3. NAMESTITEV WORKER NODE 2

Na **worker2** ponovi:

```bash
export K3S_URL="https://<MASTER_IP>:6443"
export K3S_TOKEN="<TOKEN_IZ_1.3>"
curl -sfL https://get.k3s.io | sudo K3S_URL=$K3S_URL K3S_TOKEN=$K3S_TOKEN sh -
```

Preveri:
```bash
kubectl get nodes
# Prikaz: master, worker1, worker2 (vsi Ready)
```

---

## 4. NAMESTITEV METALLB (LOAD BALANCER)

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml
kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=120s
```

MetalLB IP pool je zdaj shranjen v repozitoriju kot `k8s/cluster/metallb-config.yaml`. Pred uporabo preveri IP range glede na tvoje omrežje (`ip a | grep "inet "`) in ga po potrebi popravi v tej datoteki.

```bash
kubectl apply -f k8s/cluster/metallb-config.yaml
```

---

## 5. NAMESTITEV LONGHORN STORAGE

Longhorn bo zagotovil distributed persistent storage na **vseh nodih**.

### 5.1 Namesti predpogoje na vsak node

```bash
# Poženi na master, worker1 in worker2:
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

### 5.2 Namesti Longhorn

```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | sudo bash

helm repo add longhorn https://charts.longhorn.io
helm repo update
kubectl create namespace longhorn-system

helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --version 1.9.0 \
  --set defaultSettings.defaultReplicaCount=3 \
  --set persistence.defaultClassReplicaCount=3 \
  --set defaultSettings.replicaSoftAntiAffinity=true \
  --set persistence.defaultClass=true
```

### 5.3 Preveri

```bash
kubectl -n longhorn-system get pods -w
kubectl get storageclass          # longhorn (default)
kubectl -n longhorn-system get nodes  # vsi 3 nodi
```

---

## 6. NAMESTITEV POSTGRESQL

```bash
kubectl create namespace sola

helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install sola-postgresql bitnami/postgresql \
  --namespace sola \
  --set auth.database=sola \
  --set auth.username=sola \
  --set auth.password=<VARNOSTNO_GESLO> \
  --set persistence.storageClass=longhorn \
  --set persistence.size=10Gi \
  --set primary.persistence.storageClass=longhorn \
  --set primary.persistence.size=10Gi \
  --set global.storageClass=longhorn
```

Preveri:
```bash
kubectl -n sola get pods
kubectl -n sola get pvc   # Bound na longhorn
```

---

## 7. CONTAINERIZACIJA IN NAMESTITEV ŠOLSKI APP

### 7.1 Dockerfile

V korenu projekta (`/home/admin_os/reservation_app/Dockerfile`):

```dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

# Sistemske odvisnosti za build (psycopg2 potrebuje libpq-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -u 1000 appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY . .

RUN chown -R appuser:appuser /app
USER appuser

# /tmp kot volumen (rešuje tmpfs polnjenje)
VOLUME /tmp

EXPOSE 8002

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "2"]
```

### 7.2 Zgradi sliko

```bash
cd /home/admin_os/reservation_app

docker build -t sola-app:latest .

# Uvozi v k3s (brez registra)
docker save sola-app:latest | sudo k3s ctr images import -
```

### 7.3 Ustvari namespace in Secret

```bash
kubectl create namespace sola-app

kubectl create secret generic sola-secrets \
  --namespace sola-app \
  --from-literal=MAIL_USERNAME=oscuf \
  --from-literal=MAIL_PASSWORD=wzdmccdt \
  --from-literal=MAIL_SERVER=mail.arnes.si \
  --from-literal=MAIL_PORT=587 \
  --from-literal=MAIL_FROM=os-toneta.cufarja-jesenice@guest.arnes.si \
  --from-literal=BACKUP_EMAIL=matej.cusin2@guest.arnes.si
```

### 7.4 ConfigMap in Deployment

Namesto ročnega ustvarjanja ConfigMapa in Deploymenta uporabi Kustomize overlaye v mapi `k8s/`.

Manifesti so organizirani takole:

- `k8s/app/base/` — Namespace, ConfigMap, Deployment, Service (`ClusterIP`) in CronJob.
- `k8s/app/overlays/production-lb/` — ista osnova, Service pa spremeni v MetalLB `LoadBalancer`.
- `k8s/app/overlays/ingress/` — ista osnova, dodan Ingress in Service ostane `ClusterIP`.
- `k8s/app/overlays/frp/` — ista osnova za FRP/tunel varianto, Service ostane `ClusterIP`.

Občutljive vrednosti ostanejo v Secretu `sola-secrets`; `DATABASE_URL` ni več v ConfigMapu.

Deploy z LoadBalancer servisom:

```bash
kubectl apply -k k8s/app/overlays/production-lb

# Preveri
kubectl -n sola-app get pods -o wide
kubectl -n sola-app get svc sola-app
# EXTERNAL-IP naj bo iz MetalLB pool-a
```

Deploy z Ingressom:

```bash
kubectl apply -k k8s/app/overlays/ingress
```

Deploy za FRP/tunel:

```bash
kubectl apply -k k8s/app/overlays/frp
```

Za pregled generiranih manifestov brez spreminjanja klasterja:

```bash
kubectl kustomize k8s/app/overlays/production-lb
kubectl kustomize k8s/app/overlays/ingress
kubectl kustomize k8s/app/overlays/frp
```

### 7.7 Uvozi uporabnike

```bash
POD=$(kubectl -n sola-app get pods -l app=sola-app -o jsonpath='{.items[0].metadata.name}')
kubectl -n sola-app cp ./uporabniki.csv $POD:/app/uporabniki.csv
kubectl -n sola-app exec $POD -- python -m scripts.import_users
```

---

## 8. REVERSE PROXY (ostc.si)

### 8.1 Namesti nginx na master

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 8.2 Konfiguriraj nginx

Ustvari `/etc/nginx/sites-available/sola-app`:

```nginx
server {
    listen 80;
    server_name ostc.si;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ostc.si;

    ssl_certificate /etc/letsencrypt/live/ostc.si/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ostc.si/privkey.pem;

    location / {
        proxy_pass http://192.168.1.200:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> `192.168.1.200` je MetalLB IP. Prilagodi.

### 8.3 Omogoči in SSL

```bash
sudo ln -s /etc/nginx/sites-available/sola-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo certbot --nginx -d ostc.si
curl -I https://ostc.si
```

### 8.4 Posodobi BASE_URL

```bash
kubectl -n sola-app patch configmap/sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://ostc.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
kubectl -n sola-app rollout status deployment/sola-app
```

---

## 9. AVTOMATSKI BACKUP NA EMAIL

### 9.1 CronJob manifest

CronJob je zdaj del `k8s/app/base/sola-backup-cronjob.yaml`. Ker `DATABASE_URL` ni več v ConfigMapu, ga CronJob bere iz Secreta `sola-secrets`.

Če uporabljaš Kustomize overlay, se CronJob deploya skupaj z aplikacijo:

```bash
kubectl apply -k k8s/app/overlays/production-lb
# ali
kubectl apply -k k8s/app/overlays/ingress
# ali
kubectl apply -k k8s/app/overlays/frp
```

Če želiš aplicirati samo osnovo:

```bash
kubectl apply -k k8s/app/base
```

### 9.2 Testiraj backup

```bash
kubectl -n sola-app create job --from=cronjob/sola-db-backup manual-backup-test
kubectl -n sola-app logs -l job-name=manual-backup-test --tail=50 -f
```

### 9.3 Dnevni k3s/Longhorn health report

CronJob `sola-daily-report` teče ob **04:00 Europe/Ljubljana** in pošlje read-only report:

- k3s agent: nodi, podi, workloadi, cronjobi, warning eventi
- Longhorn agent: volumi, replike, degradacije, rebuildi, disk usage
- node health / lifetime estimate agent: heuristic ocena tveganja po nodu

RBAC je omejen na `get/list/watch` za potrebne resurse.

```bash
kubectl -n sola-app get cronjob sola-daily-report
kubectl -n sola-app describe cronjob sola-daily-report
kubectl -n sola-app logs -l job-name=<report-job> --tail=100
```

---

## 10. SKALIRANJE

```bash
# 4 replike (2 na worker):
kubectl -n sola-app scale deployment sola-app --replicas=4

# 6 replik (3 na worker):
kubectl -n sola-app scale deployment sola-app --replicas=6
```

| Replike | Master | Worker1 | Worker2 |
|---------|--------|---------|---------|
| 2 | 0 | 1 | 1 |
| 4 | 0 | 2 | 2 |
| 6 | 0 | 3 | 3 |

---

## 11. VZDRŽEVANJE

### 11.1 Posodobitev aplikacije

```bash
cd /home/admin_os/reservation_app
git pull
docker build -t sola-app:latest .
docker save sola-app:latest | sudo k3s ctr images import -
kubectl -n sola-app rollout restart deployment/sola-app
kubectl -n sola-app rollout status deployment/sola-app
```

### 11.2 Dump in obnovitev baze

```bash
# Dump
kubectl -n sola exec deploy/sola-postgresql -- pg_dump -U sola sola > ./sola-backup.sql

# Obnovi
cat ./sola-backup.sql | kubectl -n sola exec -i deploy/sola-postgresql -- psql -U sola sola
```

### 11.3 Zamenjava master node

```bash
# 1. Na novi mašini namesti k3s server
curl -sfL https://get.k3s.io | sudo sh -s - server \
  --disable=traefik --disable=servicelb --write-kubeconfig-mode=644

# 2. Če Longhorn volume še obstajajo na workerjih:
sudo systemctl restart k3s-agent  # na workerjih

# 3. Preveri
kubectl get nodes
```

### 11.4 Dodajanje novega worker node

```bash
sudo cat /var/lib/rancher/k3s/server/node-token  # na masterju
curl -sfL https://get.k3s.io | sudo K3S_URL=https://<MASTER_IP>:6443 K3S_TOKEN=<TOKEN> sh -
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

---

## 12. UPORABNA POVEZAVE

| Storitev | URL / ukaz |
|---|---|
| Aplikacija | https://ostc.si |
| Longhorn UI | `kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80` → http://localhost:8080 |

---

## 13. ODPRAVLJANJE TEŽAV

### Pod se ne zažene
```bash
kubectl -n sola-app logs <pod-name>
kubectl -n sola-app describe pod <pod-name>
```

### PostgreSQL se ne poveže
```bash
kubectl -n sola get pods
kubectl -n sola-app exec <sola-pod> -- python3 -c "
from app.config import settings; from app.database import engine
engine.connect(); print('DB OK')
"
```

### MetalLB ne dodeli IP
```bash
kubectl -n metallb-system get ipaddresspool
kubectl -n sola-app describe svc sola-app
```

### Longhorn volume stuck
```bash
kubectl -n longhorn-system get volumes
kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80
# Odpri http://localhost:8080
```


---

## 2. 🌐 Nastavitev reverse proxy na `ostc.si/solski-app`

Ker želiš, da aplikacija deluje na poti `/solski-app`, moramo nginx konfigurirati tako, da:

- Sprejema zahteve na `ostc.si/solski-app`
- Jih posreduje na `http://192.168.1.10:8002` **brez** poti `/solski-app` (če app pričakuje koren) ali **s potjo** (odvisno od app-a).

Tvoja aplikacija je verjetno napisana za koren (`/`), zato bomo v nginx-u odstranili prefiks `/solski-app` s pravilom `rewrite` ali `proxy_pass` z `location /solski-app/`.

### Predpogoji

- `ostc.si` DNS naj kaže na javni IP tvojega master vozlišča (kjer bo tekel nginx).
- MetalLB naslov `192.168.1.10` je dosegljiv iz masterja (ker sta v istem omrežju).

### Namestitev nginx na master (OS)

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
```

### Konfiguracija nginx (z upoštevanjem podpoti)

Ustvari `/etc/nginx/sites-available/sola-app`:

```nginx
server {
    listen 80;
    server_name ostc.si;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ostc.si;

    ssl_certificate /etc/letsencrypt/live/ostc.si/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ostc.si/privkey.pem;

    # Glavna lokacija za aplikacijo pod /solski-app
    location /solski-app/ {
        proxy_pass http://192.168.1.10:8002/;   # končna poševnica odstrani /solski-app
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Prefix /solski-app;
    }

    # Če želiš, da tudi koren (ostc.si) kamorkoli preusmeri, lahko dodaš:
    location / {
        return 302 https://ostc.si/solski-app/;
    }
}
```

> **Pomembno**: `proxy_pass http://192.168.1.10:8002/;` s končno poševnico **odstrani** prefiks `/solski-app` iz zahteve. Tako app dobi zahtevo na `/` (koren). Če pa tvoj app pričakuje, da bo gostoval pod `/solski-app` (ima npr. `root_path="/solski-app"`), potem pusti `proxy_pass http://192.168.1.10:8002;` (brez končne poševnice) in dodaš `proxy_set_header X-Forwarded-Prefix /solski-app;` (že zgoraj).

### Omogoči in pridobi SSL

```bash
sudo ln -s /etc/nginx/sites-available/sola-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo certbot --nginx -d ostc.si
```

Po pridobitvi SSL bo nginx samodejno uporabljal HTTPS.

---

## 3. ⚙️ Posodobi `BASE_URL` v ConfigMap

Aplikacija bo zdaj dostopna na `https://ostc.si/solski-app/`, zato mora `BASE_URL` kazati tja:

```bash
kubectl -n sola-app patch configmap/sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://ostc.si/solski-app"}}'
kubectl -n sola-app rollout restart deployment/sola-app
kubectl -n sola-app rollout status deployment/sola-app
```

---

## 4. 🧪 Testiranje

Ko je nginx nastavljen in app podi stabilni, odpri brskalnik na `https://ostc.si/solski-app/`. Če app nima posebnega usmerjanja, bi morala biti prikazana (npr. loginska stran).

Če še vedno dobivaš `502 Bad Gateway`, preveri, da nginx dosega MetalLB naslov:

```bash
curl -I http://192.168.1.10:8002/health
```

Če to deluje, potem je težava v nginx konfiguraciji.

---

## 5. 🧹 Glede backupa

Backup (CronJob) bo deloval, ko bo aplikacija stabilna in ko bo `pg_dump` prisoten v sliki (kot sva že popravila Dockerfile). Worker node ni potreben za backup, saj se job izvaja na kateremkoli nodu (verjetno master). Ker si že posodobil Dockerfile in ponovno buildal ter pushal sliko, bo novi pod uporabil pravilno sliko. Toda najprej rešiva, da app sploh teče.

---

Počakam na izpis logov (iz koraka 1), da vidiva, zakaj se podi restartajo. Brez tega ne bova mogla stabilno postaviti app-a.
