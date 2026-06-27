🌐 **Jezik / Language:** [🇸🇮 Slovenščina](k3s-setup.md) | [🇬🇧 English](en/k3s-setup.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# ☸️ K3s Setup — Šolski App

Navodila za postavitev k3s Kubernetes clusterja na **dveh nodih** (oba control-plane), z MetalLB, Longhorn, CloudNativePG (PostgreSQL) in FastAPI aplikacijo.

> ⚠️ **Trenutna konfiguracija uporablja 2 noda, oba kot control-plane,etcd.** To je lažja konfiguracija kot klasični 3-node setup (ni ločenih worker nodov).

---

## 📋 Arhitektura (trenutna)

```
Internet → Cloudflare → ostc-app.org
                            │
                            ▼
                    k3s-2:8080 (nginx)
                    proxy_pass 192.168.1.50:8002
                            │
                    MetalLB LoadBalancer
                            │
               ┌────────────┴────────────┐
               │                         │
         k3s-1 (cp,etcd)          k3s-2 (cp,etcd)
         ┌────────────┐          ┌────────────┐
         │ sola-app   │          │ sola-app   │
         │ sola-db-1  │◄────────►│ sola-db-2  │
         │ (PRIMARY)  │  stream  │ (REPLICA)  │
         │ Longhorn   │  repl.   │ Longhorn   │
         │ MetalLB    │          │ MetalLB    │
         └────────────┘          └────────────┘
```

---

## 📋 Predpogoji

- 2 fizični mašini z **Ubuntu 24.04 LTS**
- Vsaka mašina: min **2 CPU**, **4GB RAM**, **20GB disk**
- **sudo** dostop na obeh
- Mašini v istem omrežju
- Docker nameščen (za build slike):
  ```bash
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER
  ```

---

## 1. Namestitev k3s (oba noda kot control-plane)

### 1.1 Namesti k3s na prvem nodu (k3s-1)

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --disable=traefik \
  --disable=servicelb \
  --write-kubeconfig-mode=644 \
  --cluster-cidr=10.42.0.0/16 \
  --service-cidr=10.43.0.0/16 \
  --node-ip=192.168.1.10
```

### 1.2 Pridobi token

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

### 1.3 Namesti k3s na drugem nodu (k3s-2)

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://192.168.1.10:6443 \
  --token <TOKEN> \
  --disable=traefik \
  --disable=servicelb \
  --write-kubeconfig-mode=644 \
  --node-ip=192.168.1.11
```

### 1.4 Preveri

```bash
kubectl get nodes
# NAME    STATUS   ROLES                AGE
# k3s-1   Ready    control-plane,etcd   1m
# k3s-2   Ready    control-plane,etcd   30s
```

---

## 2. Namestitev MetalLB (LoadBalancer)

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml
kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=120s

# Uporabi konfiguracijo iz repozitorija (predhodno prilagodi IP range)
kubectl apply -f k8s/cluster/metallb-config.yaml
```

---

## 3. Namestitev Longhorn

### 3.1 Predpogoji na vsakem nodu

```bash
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

### 3.2 Namesti Longhorn

```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | sudo bash

helm repo add longhorn https://charts.longhorn.io
helm repo update
kubectl create namespace longhorn-system

helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --version 1.9.0 \
  --set defaultSettings.defaultReplicaCount=2 \
  --set persistence.defaultClassReplicaCount=2 \
  --set defaultSettings.replicaSoftAntiAffinity=true \
  --set persistence.defaultClass=true
```

### 3.3 Omogoči replica-auto-balance

```bash
kubectl patch settings.longhorn -n longhorn-system replica-auto-balance \
  --type='merge' -p '{"value":"least-effort"}'
```

---

## 4. CloudNativePG

### 4.1 Namesti CNPG operator

```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system \
  --create-namespace
```

### 4.2 Ustvari CNPG cluster

```bash
kubectl apply -f sola-cnpg-cluster.yaml
```

Primer `sola-cnpg-cluster.yaml`:

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

---

## 5. Namestitev aplikacije

### 5.1 Build slike

```bash
cd /home/admin/reservation_app
docker build -t sola-app:latest .
docker push sola-app:latest
```

### 5.2 Ustvari namespace in Secret

```bash
kubectl create namespace sola-app

kubectl create secret generic sola-secrets \
  --namespace sola-app \
  --from-literal=MAIL_USERNAME=oscuf \
  --from-literal=MAIL_PASSWORD=*** \
  --from-literal=MAIL_SERVER=mail.arnes.si \
  --from-literal=MAIL_PORT=587 \
  --from-literal=MAIL_FROM=sola@example.com \
  --from-literal=BACKUP_EMAIL=admin@sola.si \
  --from-literal=DATABASE_URL=postgresql://sola:***@sola-db-rw.sola:5432/sola
```

### 5.3 Deploy z overlay-i

```bash
kubectl apply -k k8s/app/overlays/production-lb
```

---

## 6. Nginx reverse proxy

Na k3s-2:

```bash
sudo apt install -y nginx
```

Ustvari `/etc/nginx/sites-available/default`:

```nginx
server {
    listen 8080;
    location / {
        proxy_pass http://192.168.1.50:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo nginx -t && sudo systemctl restart nginx
```

---

## 7. Vzdrževanje

### Posodobitev aplikacije

```bash
cd /home/admin/reservation_app
git pull
docker build -t sola-app:latest .
docker push sola-app:latest
kubectl rollout restart -n sola-app deployment/sola-app
kubectl rollout status -n sola-app deployment/sola-app
```

### Dodajanje novega noda

```bash
# Na masterju pridobi token
sudo cat /var/lib/rancher/k3s/server/node-token

# Na novem nodu:
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://<MASTER_IP>:6443 \
  --token <TOKEN> \
  --node-ip <NOVI_IP> \
  --disable traefik --disable=servicelb

# Namesti Longhorn predpogoje
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

---

## 8. Pogoste težave

| Težava | Rešitev |
|---|---|
| Pod se ne zažene | `kubectl logs -n sola-app <pod>` |
| DB se ne poveže | Preveri `sola-db-rw` endpoint: `kubectl get endpoints -n sola sola-db-rw` |
| MetalLB ne dodeli IP | `kubectl -n metallb-system get ipaddresspool` |
| Longhorn volume stuck | Preveri v Longhorn UI: `kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80` |
