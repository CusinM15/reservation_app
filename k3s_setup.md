# k3s Setup – Šolski App

Navodila za postavitev k3s Kubernetes clusterja z Longhorn storage za Šolski App.

---

## Arhitektura

```
┌─────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│   Master node       │     │   Worker node 1      │     │   Worker node 2      │
│   ostonecufar       │     │   worker1            │     │   worker2            │
│   (ta računalnik)   │     │                      │     │                      │
│                     │     │  replike: 2-4        │     │  replike: 2-4        │
│  ┌───────────────┐  │     │  ┌────────────────┐  │     │  ┌────────────────┐  │
│  │   PostgreSQL  │  │     │  │ sola-app pod   │  │     │  │ sola-app pod   │  │
│  └───────────────┘  │     │  └────────────────┘  │     │  └────────────────┘  │
│                     │     │                      │     │                      │
│  ┌───────────────┐  │     │                      │     │                      │
│  │   Longhorn    │  │     │                      │     │                      │
│  │   (storage)   │  │     │                      │     │                      │
│  └───────────────┘  │     │                      │     │                      │
└─────────────────────┘     └──────────────────────┘     └──────────────────────┘
```

---

## 1. Namestitev master node (ostonecufar)

### 1.1 Namesti k3s server

```bash
# Prijavi se na master mašino in poženi:
curl -sfL https://get.k3s.io | sudo sh -s - server \
  --disable=traefik \
  --disable=servicelb \
  --write-kubeconfig-mode=644 \
  --cluster-cidr=10.42.0.0/16 \
  --service-cidr=10.43.0.0/16
```

Parametri:
- `--disable=traefik` – onemogoči vgrajeni ingress (uporabili bomo svoj reverse proxy)
- `--disable=servicelb` – onemogoči vgrajeni load balancer
- `--write-kubeconfig-mode=644` – omogoči branje kubeconfig vsem uporabnikom

### 1.2 Preveri, da k3s deluje

```bash
# Preveri node
kubectl get nodes

# Preveri, da so vsi podi running
kubectl get pods -A
```

### 1.3 Pridobi token za join workerjev

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
# Izpiše nekaj takega: K10...::server:...
```

Shrani ta token — potrebovali ga bomo za vsak worker.

### 1.4 Pridobi IP masterja

```bash
ip a show | grep inet | grep -v 127.0.0.1
# Npr. 193.2.171.250
```

---

## 2. Join worker node 1 (worker1)

### 2.1 Namesti k3s agent

```bash
# Na worker1 mašini:
curl -sfL https://get.k3s.io | sudo K3S_URL=https://<MASTER_IP>:6443 K3S_TOKEN=<TOKEN> sh -
```

Zamenjaj `<MASTER_IP>` z IP-jem masterja in `<TOKEN>` s tokenom iz 1.3.

### 2.2 Preveri, da je worker dodan

```bash
# Na masterju:
kubectl get nodes
# Prikazati mora master + worker1
```

---

## 3. Join worker node 2 (worker2)

Ponovi korak 2 na drugi mašini:

```bash
curl -sfL https://get.k3s.io | sudo K3S_URL=https://<MASTER_IP>:6443 K3S_TOKEN=<TOKEN> sh -
```

---

## 4. Namestitev Longhorn (storage)

### 4.1 Namesti Longhorn preko Helm

```bash
# Na masterju:
kubectl create namespace longhorn-system

helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --version 1.9.0 \
  --set defaultSettings.defaultReplicaCount=2
```

### 4.2 Preveri Longhorn

```bash
kubectl -n longhorn-system get pods
# Vsi podi morajo biti v statusu Running

kubectl get storageclass
# longhorn (default) bi moral biti viden
```

### 4.3 Dostop do Longhorn UI (opcijsko)

```bash
kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80
# Odpri http://localhost:8080 v brskalniku
```

---

## 5. Namestitev PostgreSQL

### 5.1 Namesti PostgreSQL preko Helm

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

kubectl create namespace sola

helm install sola-postgresql bitnami/postgresql \
  --namespace sola \
  --set auth.database=sola \
  --set auth.username=sola \
  --set auth.password=<VARNOSTNO_GESLO> \
  --set persistence.storageClass=longhorn \
  --set persistence.size=10Gi \
  --set primary.persistence.storageClass=longhorn \
  --set primary.persistence.size=10Gi
```

### 5.2 Preveri PostgreSQL

```bash
kubectl -n sola get pods
kubectl -n sola get pvc
```

---

## 6. Namestitev Šolski App

### 6.1 Ustvari namespace

```bash
kubectl create namespace sola-app
```

### 6.2 Ustvari Secret za nastavitve

```bash
kubectl create secret generic sola-secrets \
  --namespace sola-app \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=MAIL_USERNAME=oscuf \
  --from-literal=MAIL_PASSWORD=wzdmccdt \
  --from-literal=MAIL_SERVER=mail.arnes.si \
  --from-literal=MAIL_PORT=587 \
  --from-literal=MAIL_FROM=os-toneta.cufarja-jesenice@guest.arnes.si
```

### 6.3 Ustvari ConfigMap za nastavitve

```bash
kubectl create configmap sola-config \
  --namespace sola-app \
  --from-literal=APP_HOST=0.0.0.0 \
  --from-literal=APP_PORT=8002 \
  --from-literal=BASE_URL=https://ostonecufar.local \
  --from-literal=DATABASE_URL=postgresql://sola:<VARNOSTNO_GESLO>@sola-postgresql.sola:5432/sola \
  --from-literal=TABLICE_MAX=28 \
  --from-literal=SCHEDULE='{"0":"07:30-08:15","1":"08:20-09:05","2":"09:15-10:00","3":"10:20-11:05","4":"11:10-11:55","5":"12:00-12:45","6":"12:50-13:35","7":"14:00-14:45"}' \
  --from-literal=RAZREDI='IP/NIP/ID,1.a,1.b,1.c,1.č,2.a,2.b,2.c,2.č,3.a,3.b,3.c,3.č,4.a,4.b,4.c,4.č,5.a,5.b,5.c,5.č,6.a,6.b,6.c,6.č,7.a,7.b,7.c,8.a,8.b,8.c,8.č,8.1,8.2,8.3,8.4,8.5,8.6,9.a,9.b,9.c,9.1,9.2,9.3,9.4,9.5' \
  --from-literal=PROSTORI='tablice,racunalnica,ladja'
```

### 6.4 Deployment manifest

Ustvari datoteko `sola-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sola-app
  namespace: sola-app
spec:
  replicas: 3
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
                  values:
                  - sola-app
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
        readinessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8002
          initialDelaySeconds: 15
          periodSeconds: 20
---
apiVersion: v1
kind: Service
metadata:
  name: sola-app
  namespace: sola-app
spec:
  type: ClusterIP
  ports:
  - port: 8002
    targetPort: 8002
  selector:
    app: sola-app
```

> **Opomba:** `image: sola-app:latest` — to sliko morate zgraditi iz Dockerfile-a v repozitoriju in jo pushati v register (npr. Docker Hub, GitHub Container Registry, ali local registry).

### 6.5 Deployaj aplikacijo

```bash
kubectl apply -f sola-deployment.yaml

# Preveri deployment
kubectl -n sola-app get pods -o wide
# Preveri, da podi tečejo na različnih workerjih
```

---

## 7. Ingress (dostop iz zunanjosti)

### 7.1 Namesti nginx ingress controller

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/baremetal/deploy.yaml
```

### 7.2 Ustvari Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sola-app
  namespace: sola-app
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
  - host: ostonecufar.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: sola-app
            port:
              number: 8002
```

```bash
kubectl apply -f sola-ingress.yaml
```

---

## 8. Skaliranje (dodajanje replik)

Prilagodi število replik:

```bash
# Za 4 replike (2 na vsakem workerju):
kubectl -n sola-app scale deployment sola-app --replicas=4

# Za 6 replik (3 na vsakem workerju):
kubectl -n sola-app scale deployment sola-app --replicas=6

# Preveri, da so podi enakomerno razporejeni:
kubectl -n sola-app get pods -o wide
```

> **Opomba:** `podAntiAffinity` v deployment manifestu poskrbi, da podi niso vsi na istem workerju, ampak se enakomerno porazdelijo.

---

## 9. Vzdrževanje

### 9.1 Posodobitev aplikacije

```bash
# 1. Zgradi novo Docker sliko
docker build -t sola-app:latest .

# 2. Pushaj v register
docker tag sola-app:latest <registry>/sola-app:latest
docker push <registry>/sola-app:latest

# 3. Rolling update
kubectl -n sola-app set image deployment/sola-app app=<registry>/sola-app:latest
kubectl -n sola-app rollout status deployment/sola-app
```

### 9.2 Dump baze

```bash
kubectl exec deploy/sola-postgresql --namespace sola -- pg_dump -U sola sola > ./sola-backup.sql
```

### 9.3 Obnovitev baze

```bash
cat ./sola-backup.sql | kubectl exec -i deploy/sola-postgresql --namespace sola -- psql -U sola sola
```

### 9.4 Zamenjava master node

Če master crkne:

```bash
# 1. Popravi master ali ga zamenjaj
# 2. Na workerjih uredi /etc/rancher/k3s/k3s.yaml z novim IP-jem masterja
# 3. Restartaj k3s agent na workerjih:
sudo systemctl restart k3s-agent
# 4. Preveri stanje:
kubectl get nodes
```

---

## 10. Prilagoditev števila replik na worker

Deployment ima nastavljen `replicas: 3` in `podAntiAffinity`, ki razporeja pode med workerje. Če imamo 2 workerja:

| Replike | Na worker 1 | Na worker 2 |
|---------|------------|------------|
| 2       | 1          | 1          |
| 3       | 2          | 1 (ali 2/1)|
| 4       | 2          | 2          |
| 6       | 3          | 3          |

Prilagodi po potrebi:

```bash
kubectl -n sola-app scale deployment sola-app --replicas=4
```

---

## 11. Opombe

- **Longhorn** replicira podatke na 2 nodih (`defaultReplicaCount=2`), kar pomeni, da lahko preživi okvaro enega noda brez izgube podatkov.
- **PostgreSQL** ima persistent volume na Longhorn, zato podatki preživijo restart poda ali noda.
- **Uporabniki** se uvozijo preko `scripts/import_users.py` po prvem deployu.
- **Password policy** se uveljavlja v aplikaciji (min 5 znakov, mala/velika črka, številka).
- **Pozabljeno geslo** uporablja `BASE_URL` iz configMap za povezave v emailih. Nastavi ga na dejanski URL aplikacije.
