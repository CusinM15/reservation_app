🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../k3s-setup.md) | [🇬🇧 English](k3s-setup.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# ☸️ K3s Setup — School App

Instructions for setting up a k3s Kubernetes cluster on **two nodes** (both control-plane), with MetalLB, Longhorn, CloudNativePG (PostgreSQL) and a FastAPI application.

> ⚠️ **Current configuration uses 2 nodes, both as control-plane,etcd.** This is a lighter configuration than the classic 3-node setup (no separate worker nodes).

---

## 📋 Architecture (current)

```
Internet → Cloudflare → {{DOMAIN}}
                            │
                            ▼
                    MetalLB LoadBalancer
                    ({{LB_IP}}:8002)
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

## 📋 Prerequisites

- 2 physical machines with **Ubuntu 24.04 LTS**
- Each machine: min **2 CPU**, **4GB RAM**, **20GB disk**
- **sudo** access on both
- Machines on the same network
- Docker installed (for building the image):
  ```bash
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER
  ```

---

## 1. Installing k3s (both nodes as control-plane)

### 1.1 Install k3s on the first node (k3s-1)

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --disable=traefik `# using MetalLB LoadBalancer instead of Traefik` \
  --disable=servicelb \
  --write-kubeconfig-mode=644 \
  --cluster-cidr=10.42.0.0/16 \
  --service-cidr=10.43.0.0/16 \
  --node-ip={{K3S_1_IP}}
```

### 1.2 Get the token

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

### 1.3 Install k3s on the second node (k3s-2)

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://{{K3S_1_IP}}:6443 \
  --token <TOKEN> \
  --disable=traefik `# using MetalLB LoadBalancer instead of Traefik` \
  --disable=servicelb \
  --write-kubeconfig-mode=644 \
  --node-ip={{K3S_2_IP}}
```

### 1.4 Verify

```bash
kubectl get nodes
# NAME    STATUS   ROLES                AGE
# k3s-1   Ready    control-plane,etcd   1m
# k3s-2   Ready    control-plane,etcd   30s
```

---

## 2. Installing MetalLB (LoadBalancer)

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml
kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=120s

# Apply configuration from the repository (adjust IP range beforehand)
kubectl apply -f k8s/cluster/metallb-config.yaml
```

---

## 3. Installing Longhorn

### 3.1 Prerequisites on each node

```bash
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

### 3.2 Install Longhorn

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

### 3.3 Enable replica-auto-balance

```bash
kubectl patch settings.longhorn -n longhorn-system replica-auto-balance \
  --type='merge' -p '{"value":"least-effort"}'
```

---

## 4. CloudNativePG

### 4.1 Install CNPG operator

```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system \
  --create-namespace
```

### 4.2 Create CNPG cluster

```bash
kubectl apply -f sola-cnpg-cluster.yaml
```

Example `sola-cnpg-cluster.yaml`:

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

## 5. Installing the application

### 5.1 Build the image

```bash
cd /home/admin/reservation_app
docker build -t sola-app:latest .
docker push sola-app:latest
```

### 5.2 Create namespace and Secret

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

### 5.3 Deploy with overlays

```bash
kubectl apply -k k8s/app/overlays/production-lb
```

---

## 6. Maintenance

### Updating the application

```bash
cd /home/admin/reservation_app
git pull
docker build -t sola-app:latest .
docker push sola-app:latest
kubectl rollout restart -n sola-app deployment/sola-app
kubectl rollout status -n sola-app deployment/sola-app
```

### Adding a new node

```bash
# On the master, get the token
sudo cat /var/lib/rancher/k3s/server/node-token

# On the new node:
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://<MASTER_IP>:6443 \
  --token <TOKEN> \
  --node-ip <NEW_IP> \
  --disable traefik --disable=servicelb

# Install Longhorn prerequisites
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

---

## 7. Common issues

| Issue | Solution |
|---|---|
| Pod won't start | `kubectl logs -n sola-app <pod>` |
| DB won't connect | Check `sola-db-rw` endpoint: `kubectl get endpoints -n sola sola-db-rw` |
| MetalLB won't assign IP | `kubectl -n metallb-system get ipaddresspool` |
| Longhorn volume stuck | Check in Longhorn UI: `kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80` |

---

> **Author:** Matej Čušin  
