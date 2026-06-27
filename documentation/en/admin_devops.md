[🇸🇮 Slovenščina](../admin_devops.md) | [🇬🇧 English](admin_devops.md)

---

# 🏫 **Admin/DevOps Guide — ostc-app**
## **OŠ Toneta Čufarja**

> Complete admin instructions for maintaining and managing the application.
> For detailed installation instructions, see the [ostc-app_deli repository](https://github.com/os-tc-jesenice/ostc-app_deli).

---

## Contents

1. [What the app does](#what-the-app-does)
2. [Requirements](#requirements)
3. [Kubernetes (k3s) mode](#kubernetes-k3s-mode--high-availability)
4. [Maintenance & automation (cron jobs)](#maintenance--automation-cron-jobs)
5. [Adding a new node to the cluster](#adding-a-new-node-to-the-k3s-cluster)
6. [Repository structure](#repository-structure)

---

## What the app does

- **Room reservations:**
  - **Tablets** – 28 units available, can be shared by multiple teachers in the same hour
  - **Computer lab** – one reservation per time slot
  - **Wellbeing boat** – one reservation per time slot
- **Exam scheduling** – written exams with limits (max 3/week, max 2 regular)
- **Blocked dates** – Management/Admin can mark busy days (sports day, field trip...)
- **Admin panel** – user management
- **Forgot password** – password reset via email

---

## Requirements

The app is built with **FastAPI** (Python) and works in three modes:

| Mode | Difficulty | Best for |
|---|---|---|
| **Local (uvicorn)** | ⭐ Easy | Single computer in the staff room |
| **mDNS** | ⭐⭐ Medium | Multiple computers on the school network |
| **Kubernetes (k3s)** | ⭐⭐⭐ Advanced | High availability, 2+ computers |

**Recommended OS:** Ubuntu Server 24.04 LTS

---

## Kubernetes (k3s) mode – High Availability

> **Current state:** 2 nodes (k3s-1, k3s-2), both control-plane + etcd.
> CloudNativePG for HA database, MetalLB for LoadBalancer, Longhorn for storage.

### What are Kubernetes and k3s?

**Kubernetes (k8s)** is a container orchestration system that keeps the application running even if one computer fails. **k3s** is a lightweight version of Kubernetes, suitable for smaller servers and older hardware.

### Node Preparation

#### Static IP setup

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

Example for k3s-1 (193.2.171.250):
```yaml
network:
  ethernets:
    eth0:
      addresses:
        - 193.2.171.250/24
      routes:
        - to: default
          via: 193.2.171.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 1.1.1.1
  version: 2
```

```bash
sudo netplan apply
```

#### Laptop as server (lid close behavior)

```bash
sudo nano /etc/systemd/logind.conf
# Uncomment #HandleLidSwitch=ignore
sudo systemctl restart systemd-logind
```

#### SSH – remote access

```bash
sudo apt install -y openssh-server
sudo systemctl enable --now ssh

# From another computer:
ssh admin_os@193.2.171.250   # k3s-1
ssh admin_os@193.2.171.249   # k3s-2
```

### Installing k3s (first master)

```bash
# On first node (k3s-1)
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=servicelb --disable=traefik" sh -

# Verify
sudo kubectl get nodes
sudo cat /var/lib/rancher/k3s/server/node-token  # save this token
```

Set up kubeconfig for regular user:
```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
```

### Adding a second master

```bash
# On k3s-2 (replace TOKEN and IP)
curl -sfL https://get.k3s.io | \
  K3S_URL=https://193.2.171.250:6443 \
  K3S_TOKEN=*** \
  sh -
```

### Installing MetalLB (LoadBalancer)

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml

# Wait for metallb pods to be Running
kubectl wait --namespace metallb-system --for=condition=ready pod --selector=app=metallb --timeout=120s

# Configure IP pool
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 193.2.171.200-193.2.171.200
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-advertisement
  namespace: metallb-system
EOF
```

### Installing Longhorn (distributed storage)

```bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.7.1/deploy/longhorn.yaml

# Dashboard (port-forward):
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# Open: http://localhost:8080
```

#### Enabling replica-auto-balance

```bash
kubectl edit settings -n longhorn-system replica-auto-balance
# Set to "least-effort"
```

### Installing the application

The app resides in the `ostc-app_deli` repository. K8s manifests are in the `k8s/` folder:

```bash
cd /home/admin_os/ostc-app_deli

# Namespace
kubectl create namespace sola-app

# ConfigMap
kubectl create configmap sola-config -n sola-app \
  --from-literal=APP_PORT=8002 \
  --from-literal=BASE_URL=https://ostc-app.org \
  --from-literal=PROSTORI=tablice,racunalnica,ladja,gospodinjska-ucilnica \
  ...

# Secret (customize values)
kubectl create secret generic sola-secrets -n sola-app \
  --from-literal=DATABASE_URL="postgresql://sola:***@sola-db-rw.sola:5432/sola" \
  --from-literal=MAIL_USERNAME=oscuf \
  --from-literal=MAIL_FROM=os-toneta.cufarja-jesenice@guest.arnes.si \
  ...

# Deployment
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

---

## Maintenance & Automation (cron jobs)

### Daily database backup (sola-db-backup)

Kubernetes CronJob that creates a database dump daily at 02:00 and emails it.

```bash
# Check latest backup
kubectl logs -n sola-app -l job-name=sola-db-backup --tail=20
```

### Daily cluster report (sola-daily-report)

CronJob at 04:00 Europe/Ljubljana that sends a reservation summary and system status.

```bash
kubectl logs -n sola-app -l job-name=sola-daily-report --tail=20
```

### Importing teachers at the start of the year

A script in the `ostc-app_deli` repository reads the staff list from the school website:

```bash
cd /home/admin_os/ostc-app_deli

# Dry-run
python3 scripts/import_teachers.py --dry-run

# Actual import
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Include admin/technical staff
python3 scripts/import_teachers.py --base-url https://ostc-app.org --include-all
```

---

## Adding a new node to the k3s cluster

### Preparation

1. Install Ubuntu Server 24.04 (see [local setup](lokalni_zagon.md))
2. Configure static IP
3. Enable SSH

### Get the token from an existing master

```bash
sudo cat /var/lib/rancher/k3s/server/token
```

### Join as an additional master

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://193.2.171.250:6443 \
  K3S_TOKEN=*** \
  sh -
```

### Verify it was added

```bash
kubectl get nodes
```

---

## Repository structure

```
ostc-app_deli/
├── app/                    # Python application (FastAPI)
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── routers/            # API endpoints
│   ├── templates/          # Jinja2 HTML
│   └── static/             # CSS, JS
├── k8s/                    # Kubernetes manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── Dockerfile
│   └── cronjob.yaml
├── scripts/                # Helper scripts
│   ├── import_teachers.py
│   └── db_backup.py
└── documentation/          # Documentation
```

---

## AI Agents

**Hermes Agent** runs on the k3s nodes via Discord. It can:
- Manage the app using natural language
- Fix configuration issues
- Execute commands on the nodes
- Generate daily reports

More: https://hermes-agent.nousresearch.com/docs
