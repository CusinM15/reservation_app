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

Ustvari `metallb-config.yaml`:

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.1.200-192.168.1.210
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-advertisement
  namespace: metallb-system
```

> Prilagodi IP range glede na tvoje omrežje. Preveri: `ip a | grep "inet "`.

```bash
kubectl apply -f metallb-config.yaml
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

### 7.4 Ustvari ConfigMap

```bash
kubectl create configmap sola-config \
  --namespace sola-app \
  --from-literal=APP_HOST=0.0.0.0 \
  --from-literal=APP_PORT=8002 \
  --from-literal=BASE_URL=https://ostc.si \
  --from-literal=DATABASE_URL='postgresql://sola:<VARNOSTNO_GESLO>@sola-postgresql.sola:5432/sola' \
  --from-literal=TABLICE_MAX=28 \
  --from-literal=SCHEDULE='{"0":"07:30-08:15","1":"08:20-09:05","2":"09:15-10:00","3":"10:20-11:05","4":"11:10-11:55","5":"12:00-12:45","6":"12:50-13:35","7":"14:00-14:45"}' \
  --from-literal=RAZREDI='IP/NIP/ID,1.a,1.b,1.c,1.č,2.a,2.b,2.c,2.č,3.a,3.b,3.c,3.č,4.a,4.b,4.c,4.č,5.a,5.b,5.c,5.č,6.a,6.b,6.c,6.č,7.a,7.b,7.c,8.a,8.b,8.c,8.č,8.1,8.2,8.3,8.4,8.5,8.6,9.a,9.b,9.c,9.1,9.2,9.3,9.4,9.5' \
  --from-literal=PROSTORI='tablice,racunalnica,ladja'
```

> Zamenjaj `<VARNOSTNO_GESLO>` z istim geslom kot v koraku 6.

### 7.5 Deployment manifest

Ustvari `sola-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sola-app
  namespace: sola-app
spec:
  replicas: 4
  selector:
    matchLabels:
      app: sola-app
  template:
    metadata:
      labels:
        app: sola-app
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values: [sola-app]
              topologyKey: kubernetes.io/hostname

      containers:
      - name: app
        image: sola-app:latest
        imagePullPolicy: IfNotPresent
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

        # /tmp na disku (ne na RAM tmpfs!) – pomembno za FastAPI
        volumeMounts:
        - name: tmp-volume
          mountPath: /tmp

        readinessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 8
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 20
          periodSeconds: 30
          failureThreshold: 5

      volumes:
      - name: tmp-volume
        emptyDir:
          sizeLimit: 2Gi
---
apiVersion: v1
kind: Service
metadata:
  name: sola-app
  namespace: sola-app
spec:
  type: LoadBalancer
  ports:
  - port: 8002
    targetPort: 8002
  selector:
    app: sola-app
```

### 7.6 Deployaj

```bash
kubectl apply -f sola-deployment.yaml

# Preveri
kubectl -n sola-app get pods -o wide
kubectl -n sola-app get svc sola-app
# EXTERNAL-IP naj bo iz MetalLB pool-a (npr. 192.168.1.200)
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
kubectl -n sola-app set env configmap/sola-config BASE_URL=https://ostc.si
kubectl -n sola-app rollout restart deployment/sola-app
```

---

## 9. AVTOMATSKI BACKUP NA EMAIL

### 9.1 CronJob manifest

Ustvari `sola-backup-cronjob.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: sola-db-backup
  namespace: sola-app
spec:
  schedule: "0 3 * * *"  # Vsak dan ob 3:00
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: sola-app:latest
            imagePullPolicy: IfNotPresent
            command:
            - python
            - -m
            - scripts.db_backup
            env:
            - name: DATABASE_URL
              valueFrom:
                configMapKeyRef:
                  name: sola-config
                  key: DATABASE_URL
            - name: MAIL_USERNAME
              valueFrom:
                secretKeyRef:
                  name: sola-secrets
                  key: MAIL_USERNAME
            - name: MAIL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: sola-secrets
                  key: MAIL_PASSWORD
            - name: MAIL_SERVER
              valueFrom:
                secretKeyRef:
                  name: sola-secrets
                  key: MAIL_SERVER
            - name: MAIL_PORT
              valueFrom:
                secretKeyRef:
                  name: sola-secrets
                  key: MAIL_PORT
            - name: MAIL_FROM
              valueFrom:
                secretKeyRef:
                  name: sola-secrets
                  key: MAIL_FROM
            - name: BACKUP_EMAIL
              valueFrom:
                secretKeyRef:
                  name: sola-secrets
                  key: BACKUP_EMAIL
          restartPolicy: OnFailure
```

```bash
kubectl apply -f sola-backup-cronjob.yaml
```

### 9.2 Testiraj backup

```bash
kubectl -n sola-app create job --from=cronjob/sola-db-backup manual-backup-test
kubectl -n sola-app logs -l job-name=manual-backup-test --tail=50 -f
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
