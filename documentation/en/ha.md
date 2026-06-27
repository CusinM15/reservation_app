[🇸🇮 Slovenščina](../ha.md) | [🇬🇧 English](ha.md)

---

# 🚀 **HA Architecture — ostc-app (sola-app)**

## Overview

The ostc-app runs on a **k3s** Kubernetes cluster with two nodes:
- **k3s-1** (193.2.171.250) — HP ProBook 455 G5
- **k3s-2** (193.2.171.249) — HP ProBook 450 G5

Goal: if either node fails, the application remains accessible within a few minutes without manual intervention.

## High Availability

### 1. Application (sola-app)

- **2 pods** — one on each node
- **Deployment** with `replicas: 2`
- Pods are distributed by the standard k3s scheduler
- If a node fails, k3s automatically reschedules the pod to the surviving node (~5 min, depends on `pod-eviction-timeout`)
- **Health check** — `/health` endpoint, 200 OK ⇒ pod is ready

```
Kubernetes Deployment sola-app
├── Pod k3s-1 (10.42.0.x)
└── Pod k3s-2 (10.42.1.x)
```

### 2. Network Access

```
Internet → ostc-app.org (Cloudflare)
  ├── k3s-1:443 (nginx, SSL)  → Service LoadBalancer 193.2.171.200:8002 → app pod
  └── k3s-2:8080 (nginx)      → Service LoadBalancer 193.2.171.200:8002 → app pod
```

- **Cloudflare** points to LoadBalancer IP `193.2.171.200` (MetalLB)
- **Nginx** on both nodes proxies to `193.2.171.200:8002`
- **Service type LoadBalancer** (MetalLB) — fixed IP, layer2 failover
- If one node fails, MetalLB takes over traffic on the other node

### 3. PostgreSQL Database — CloudNativePG (CNP)

The most critical HA component. Uses the **CloudNativePG** operator.

```
CNP Cluster "sola-db"
├── sola-db-1 (primary)  → k3s-1  → ha/active=true
│   └── Storage: Longhorn PVC (1Gi, replicated)
└── sola-db-2 (replica)  → k3s-2
    └── Storage: Longhorn PVC (1Gi, replicated)

Services:
├── sola-db-rw → always on primary (writes + reads)
├── sola-db-ro → on all ready instances (read-only)
└── sola-db-r  → on all instances
```

#### Auto-failover (built-in)

- **`failoverDelay: 30`** — if the primary pod goes down, CNP waits 30s then promotes the replica to primary
- **`enablePDB: true`** — PodDisruptionBudget prevents both pods from going down simultaneously
- **Replication** — streaming replication (asynchronous, fine for this app)
- **Storage** — Longhorn (replicated volume, each pod has its own PVC)

#### Failover Process

1. k3s-1 fails → primary pod `sola-db-1` becomes unavailable
2. CNP operator detects the failure (30s `failoverDelay`)
3. CNP promotes `sola-db-2` (on k3s-2) to primary
4. Service `sola-db-rw` automatically redirects to `sola-db-2`
5. App on k3s-2 connects to `sola-db-rw` (now pointing to `sola-db-2`) → continues working

**Total downtime:** ~1–2 minutes (30s failover delay + ~30s promotion + time for k3s to detect failed node)

#### Recovery After Node Repair

When k3s-1 comes back up:
1. CNP automatically detects the available node
2. Manual `cnpg` command or CNP self-heals (depending on configuration)
3. Alternative: delete old `sola-db-1` PVC, CNP will recreate it as a replica

### 4. Configuration

**App database connection:**
```
DATABASE_URL=postgresql://sola:password@sola-db-rw.sola:5432/sola
```
Uses the `sola-db-rw` Service, which always points to the current primary.

**Application secret:**
- Namespace: `sola-app`
- Secret: `sola-secrets`
- Contains: `DATABASE_URL`, `MAIL_*`, `BACKUP_EMAIL`

**CNP Cluster:**
- Namespace: `sola`
- Name: `sola-db`
- 2 instances, each on its own node
- Longhorn storage (1Gi)
- Auto-failover: 30s

### 5. Testing HA

To simulate a failure:
```bash
# Shut down one node (e.g. k3s-1)
ssh k3s-1 "sudo poweroff"

# Verify the app is still accessible
curl -I https://ostc-app.org

# After ~2 min check status
kubectl get pods -n sola -o wide      # sola-db-2 should be primary
kubectl get pods -n sola-app -o wide  # sola-app pod on k3s-2

# When the node is back up
kubectl get cluster -n sola sola-db    # CNP should have 2 ready instances
```

### 6. Important Notes

- **Cloudflare** points to LoadBalancer IP `193.2.171.200` — if this IP changes, update Cloudflare DNS
- **Nginx** on both nodes proxies to the LoadBalancer IP — if the IP changes, update `/etc/nginx/sites-available/default`
- **Longhorn** replicates PVCs — data is safe even if one node is lost
- **No custom failover scripts** — everything is managed by the CNP operator
