🌐 **Language:** [🇸🇮 Slovenščina](../k3s-setup.md) | [🇬🇧 English](k3s-setup.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses and other sensitive data in
> this documentation have been replaced with examples. For actual values, check Kubernetes
> Secrets or contact your administrator.

---

# ☸️ K3s Setup — School App

> **I'll walk you through setting up k3s in about 20 minutes. But first, let's understand what you're doing and why.**

---

## 🧠 What is Kubernetes (and k3s)?

### Kubernetes / k3s — the hotel receptionist for your apps
Imagine you have an application (web app, database, API). You hand it to Kubernetes and it handles:
- If the app crashes → it restarts it somewhere else.
- If traffic spikes → it automatically adds another copy.
- If you need to update → it slowly replaces old copies with new ones, with zero downtime.

**k3s** is just a lighter, smaller version of Kubernetes — like a SmartCar instead of a truck. It's designed for smaller setups and edge devices. But the logic is exactly the same.

### Control-plane — the brain of the cluster
This is the "management" of your cluster. It decides: where each pod goes, what happens if something crashes, who's currently in charge. If the control-plane goes down, the cluster still works (apps keep running), but you can't change anything — like a company without a director.

### etcd — the cluster's memory
etcd is a small database that stores everything: "which pod is running where", "what's the configuration", "who's the leader node". If etcd disappears, the cluster doesn't know who it is or what it's doing. That's why we have etcd on both nodes (replicated).

### Pod — the container with your app
The smallest unit in Kubernetes. It contains one or more Docker containers with everything the app needs — code, libraries, settings. Each pod gets its own IP.

### Node — the physical computer
This is the actual computer on your network. In our case: 2 HP ProBook laptops. Each node has k3s installed and can run pods.

### MetalLB — gives fixed IPs to apps in the cluster
When you tell Kubernetes "this app should be accessible on an external address", you need a **LoadBalancer**. But Kubernetes itself can't hand out IPs from your network. MetalLB does that — like saying "give this app the fixed IP 192.168.1.50".

### Longhorn — distributed hard drive
Instead of each pod using the local disk (which disappears if the pod moves to another node), Longhorn ensures every piece of data has **2 copies on 2 different computers**. If one node crashes, the data still exists on the other.

---

## 📋 Architecture (current)

![K3s architecture: Internet → Cloudflare → MetalLB → 2 nodes](../diagrams/k3s-setup-arhitektura.png)


---

## 📋 Prerequisites

- 2 physical machines running **Ubuntu 24.04 LTS** (your HP ProBook laptops)
- Each machine: min **2 CPU**, **4GB RAM**, **20GB disk**
- **sudo** access on both machines
- Machines on the same network (they can ping each other without issues)
- Docker installed (for building images):
  ```bash
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER
  ```
  This installs Docker and adds your user to the `docker` group, so you don't have to type `sudo docker` every time.

---

## 1. Installing k3s (both nodes as control-plane)

**Why both nodes as control-plane?** In a classic Kubernetes setup, you have one "master" node (control-plane) and several "workers". But with only 2 nodes, it's a waste to have one just "deciding" and the other just "working". So we set both up as control-plane — both can run apps and both can take over leadership if one crashes.

### 1.1 Install k3s on the first node (k3s-1)

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --disable=traefik \         # Disable the built-in traffic router (Traefik). We don't need it because we'll use MetalLB for assigning IPs.
  --disable=servicelb \       # Disable k3s's own LoadBalancer — we don't need it either, MetalLB does it better.
  --write-kubeconfig-mode=644 \  # Allow regular users to read the kubeconfig file (no need for sudo every time).
  --cluster-cidr=10.42.0.0/16 \ # IP range for pods (internal cluster network).
  --service-cidr=10.43.0.0/16 \ # IP range for services (another internal network).
  --node-ip={{K3S_1_IP}}        # Which IP this node should use. Enter the internal IP of the first laptop (type `ip a` in terminal and pick the one from the wired/wifi interface, e.g. 192.168.1.10).
```

**What happens now?** curl downloads the script from get.k3s.io, and the script installs k3s in `server` mode (as control-plane). All the `--disable` flags turn off things we don't need. `--node-ip` tells k3s "your IP is this", which is important if the machine has multiple network interfaces.

### 1.2 Get the token (key for the second node to join)

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```
This is like a **password to enter the cluster**. The second node needs it to join the first one. Copy it somewhere — you'll need it in the next step.

### 1.3 Install k3s on the second node (k3s-2)

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://{{K3S_1_IP}}:6443 \  # Connect to the first node (k3s-1) on port 6443 — the default Kubernetes API port.
  --token <TOKEN> \                     # Token from the previous step — proof that you're allowed into the cluster.
  --disable=traefik \                   # Same reason as on the first node — we don't need Traefik.
  --disable=servicelb \                 # Also don't need ServiceLB.
  --write-kubeconfig-mode=644 \
  --node-ip={{K3S_2_IP}}               # IP of the second laptop.
```

**Important:** `--server https://{{K3S_1_IP}}:6443` means "don't start a new cluster, join an existing one". Without this, the second node would try to become its own cluster — and you'd have 2 separate clusters instead of one.

### 1.4 Verify

```bash
kubectl get nodes
# NAME    STATUS   ROLES                AGE
# k3s-1   Ready    control-plane,etcd   1m
# k3s-2   Ready    control-plane,etcd   30s
```

**If you see both as `Ready` — congratulations, the cluster is up! 🎉** If either is `NotReady`, wait a minute and try again — sometimes etcd needs a few seconds to sync.

---

## 2. Installing MetalLB (LoadBalancer)

**Why MetalLB?** Kubernetes itself has no idea about your physical network. When you say "give this app an external IP", MetalLB looks at the IP range you gave it and says "this IP is free, I'll assign it to this app". Without MetalLB, the app would only get an internal IP, unreachable from outside.

```bash
# 1. Install MetalLB in the cluster
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml

# 2. Wait for all MetalLB pods to be ready (--all means "all pods in the namespace")
kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=120s

# 3. Apply the configuration — tell MetalLB which IPs are available
kubectl apply -f k8s/cluster/metallb-config.yaml
```

**Don't skip the `wait --for=condition=ready pod --all`** — this blocks until all MetalLB pods are actually ready. If you move on without it, the MetalLB config will fail because the service doesn't exist yet, and you'll be stuck waiting indefinitely.

---

## 3. Installing Longhorn (distributed disk)

**Why Longhorn?** If you have an app that stores data (database, images, documents), and that pod crashes and restarts on another node — where are the data now? On the first node, which is dead. **Longhorn solves this by keeping every piece of data in 2 copies on 2 different computers.** If one crashes, the other still works.

### 3.1 Prerequisites on each node

```bash
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

- **open-iscsi** — a tool that allows Longhorn to connect to remote disks via the iSCSI protocol (like saying "mount a remote disk over the network").
- **nfs-common** — support for NFS (Network File System), which Longhorn uses for some operations.

**Install this on BOTH nodes.** Longhorn uses the local disk on each node, but it needs these tools for replication.

### 3.2 Install Helm, then Longhorn

**Helm is like the app store for Kubernetes.** Instead of manually writing YAML files for every component, you just say "give me Longhorn" and Helm handles everything.

```bash
# Install Helm (if you don't have it yet)
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | sudo bash

# Add the Longhorn repository to Helm
helm repo add longhorn https://charts.longhorn.io
helm repo update

# Create a namespace for Longhorn
kubectl create namespace longhorn-system

# Install Longhorn with the Helm chart
helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --version 1.9.0 \
  --set defaultSettings.defaultReplicaCount=2 \      # Default: each piece of data in 2 copies
  --set persistence.defaultClassReplicaCount=2 \      # Same for persistent volumes
  --set defaultSettings.replicaSoftAntiAffinity=true \ # "Prefer" putting replicas on different nodes (if possible)
  --set persistence.defaultClass=true                 # Make Longhorn the default StorageClass
```

**Why replicaCount=2?** Because we have 2 nodes. 1 copy = no protection. 2 copies = if one node crashes, data is on the other. 3 copies would be even better, but with 2 nodes it's physically impossible — where would the third copy go?

### 3.3 Enable replica-auto-balance

```bash
kubectl patch settings.longhorn -n longhorn-system replica-auto-balance \
  --type='merge' -p '{"value":"least-effort"}'
```

**What does this do?** Longhorn's "smarts" for distributing copies. If one of the nodes gets full, Longhorn automatically moves some copies to the other. `least-effort` = "do what's easiest, don't reshuffle unnecessarily".

---

## 4. CloudNativePG (PostgreSQL database)

### 4.1 Install the CNPG operator

CNPG (CloudNativePG) is a Kubernetes operator for PostgreSQL. An **operator** is like a "robot-maintainer" — it automatically takes care of the database: backups, replication, failover (when one database crashes, another takes over).

```bash
# Add the CNPG repository to Helm
helm repo add cnpg https://cloudnative-pg.github.io/charts

# Install the CNPG operator in its own namespace
helm install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system \
  --create-namespace   # Create the namespace if it doesn't exist yet
```

### 4.2 Create a CNPG cluster

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
  instances: 2                    # Two copies of the database (one primary, one standby)
  storage:
    size: 1Gi                    # Each gets 1GB of disk (on Longhorn = duplicated)
    storageClass: longhorn        # Store on Longhorn (not locally!)
  bootstrap:
    initdb:
      database: sola             # Database name on first startup
      owner: sola                # Database owner
  affinity:
    enablePodAntiAffinity: true   # "Don't put both databases on the same computer"
    podAntiAffinityType: preferred # "Preferably not, but if there's no other option, it's okay"
    topologyKey: kubernetes.io/hostname  # Based on the physical computer
  enablePDB: true                # PodDisruptionBudget — ensures at least one database is always running
  failoverDelay: 30              # ⏱ 30 seconds of waiting before CNPG declares the primary
                                  # node dead and promotes the standby.
                                  # This prevents false alarms during brief outages.
```

**Why `failoverDelay: 30`?** Imagine the primary database freezes for a moment (network glitch, high CPU load). CNPG waits 30 seconds before deciding "is this node really dead or just struggling?". If it recovers within 30 seconds — great, no unnecessary switchover. If not — only then does the failover happen. This prevents **false alarms** and unnecessary switching.

---

## 5. Installing the application

### 5.1 Build the image

```bash
cd /home/admin/reservation_app
docker build -t sola-app:latest .   # Build a Docker image from the Dockerfile in the current directory
docker push sola-app:latest         # Push the image to a registry so Kubernetes can pull it
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

**`--from-literal`** — writes the data directly on the command line. In production, you'd use `--from-file` or pull from Azure Key Vault / HashiCorp Vault, but for a school app this is sufficient.

**`DATABASE_URL`** — tells the app where the database is. `sola-db-rw` is the service pointing to the **currently primary** database (rw = read-write). `sola.sola` = service name in the `sola` namespace.

### 5.3 Deploy using overlays

```bash
kubectl apply -k k8s/app/overlays/production-lb
```

**`-k` = Kustomize.** This isn't a regular `apply` — Kustomize lets you have a base configuration and then an "overlay" for each environment (dev, staging, production). Here we're using the `production-lb` overlay, which adds a MetalLB LoadBalancer.

---

## 6. Maintenance

### Updating the application

```bash
cd /home/admin/reservation_app
git pull                          # Pull the latest code
docker build -t sola-app:latest . # Build a new image
docker push sola-app:latest       # Push to registry
kubectl rollout restart -n sola-app deployment/sola-app  # Slowly replace old pods with new ones
kubectl rollout status -n sola-app deployment/sola-app   # Monitor until all new pods are running
```

**`rollout restart`** — Kubernetes doesn't kill all pods at once. It replaces them one by one (rolling update), so the app is never completely unavailable.

### Adding a new node

```bash
# On the master (any node in our setup) get the token
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

**Don't forget:** When you add a third node, consider increasing the Longhorn replicaCount to 3 — then you'll have data on all three nodes.

---

## 7. Common issues

| Issue | Solution |
|-------|----------|
| Pod won't start | `kubectl logs -n sola-app <pod>` — check the logs to see what happens at startup |
| DB won't connect | Check the `sola-db-rw` endpoint: `kubectl get endpoints -n sola sola-db-rw` — does the service exist? |
| MetalLB won't assign IP | `kubectl -n metallb-system get ipaddresspool` — check if you've defined the IP range |
| Longhorn volume stuck | Check in Longhorn UI: `kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80` — open `localhost:8080` in browser |

---

## 🚨 Common installation mistakes

### ❌ 1. Forgetting `--disable=servicelb`
If you don't disable k3s's built-in ServiceLB, MetalLB and k3s will fight over the same services. MetalLB won't get an IP because k3s ServiceLB will grab it first. **Solution:** always use both: `--disable=traefik --disable=servicelb`.

### ❌ 2. Mixed up node IPs
`--node-ip={{K3S_1_IP}}` on the first node and `--node-ip={{K3S_2_IP}}` on the second — swapping them means k3s will think the first node is on the second's address. Pods won't be able to connect. **Solution:** run `ip a` on each machine before installation and write down the exact IP.

### ❌ 3. Impatience — not waiting for pods to be `Ready`
MetalLB, Longhorn, and CNPG take time to start up. If you move on without `kubectl wait --for=condition=ready pod --all`, the next command will fail because the service doesn't exist yet. **Solution:** after each installation, run `kubectl get pods -n <namespace>` and wait for `Running`/`Ready`.

### ❌ 4. Longhorn installed on only one node
open-iscsi and nfs-common must be installed on **every** node. If you forget the second one, Longhorn won't be able to attach disks on that node. **Solution:** run `sudo apt-get install -y open-iscsi nfs-common` on both.

### ❌ 5. Wrong `DATABASE_URL` in Secret
If you write the wrong hostname in `DATABASE_URL` (e.g. `sola-db` instead of `sola-db-rw`), the app won't be able to connect to the database. **Solution:** always check the service name: `kubectl get svc -n sola` shows you the exact names.

---

## 📖 Glossary

| Term | Meaning (ELI5) |
|------|----------------|
| **Kubernetes (k8s)** | Hotel receptionist for apps — manages where and how they run |
| **k3s** | Lighter version of Kubernetes — like a compact car instead of a truck |
| **Control-plane** | The brain of the cluster — decides where things go |
| **etcd** | The cluster's memory — if it's gone, the cluster doesn't know who it is |
| **Pod** | Container with the app and everything it needs |
| **Node** | Physical computer in the cluster |
| **Cluster** | Group of computers (nodes) working as one |
| **MetalLB** | Gives fixed IPs to apps in the cluster — like a receptionist assigning rooms to guests |
| **Longhorn** | Distributed hard drive — every piece of data in 2 copies on 2 different computers |
| **LoadBalancer** | Service that gives the app an external IP |
| **Namespace** | Folder in Kubernetes — separates different projects from each other |
| **Helm** | App store for Kubernetes — you say which package you want and Helm installs it |
| **Operator** | Robot-maintainer — automatically manages complex services (databases, monitoring) |
| **Secret** | Kubernetes storage for passwords and keys — not stored in plain text |
| **Replica** | Copy — more copies = better reliability |
| **Failover** | When one component crashes, another automatically takes over |
| **Rolling update** | Slowly replacing old pods with new ones — zero downtime |
| **StorageClass** | Disk type in Kubernetes (e.g. "fast SSD" or "slow HDD" or "Longhorn") |
| **ClusterCIDR** | IP range for pods — internal cluster network |
| **ServiceCIDR** | IP range for services — another internal network |
| **Kubeconfig** | Configuration file for accessing the cluster — like an ID card |
| **Token** | Password for joining the cluster — without it you can't get in |

---

> **Author:** Matej Čušin

