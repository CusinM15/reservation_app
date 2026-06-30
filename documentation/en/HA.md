🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../HA.md) | [🇬🇧 English](HA.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# HA Architecture — ostc-app (sola-app)

## Overview

The ostc-app runs in a **k3s** Kubernetes cluster on two nodes:
- **k3s-1** ({{K3S_1_IP}}) — HP ProBook 455 G5
- **k3s-2** ({{K3S_2_IP}}) — HP ProBook 450 G5

Goal: if either node fails, the application remains accessible within a few minutes without manual intervention.

## High Availability

### 1. Application (sola-app)

- **2 pods** — one on each node
- **Deployment** with `replicas: 2`
- Pods are scheduled via the standard k3s scheduler
- If a node goes down, k3s automatically reschedules the pod onto the surviving node
- **Health check** — `/health` endpoint, 200 OK ⇒ pod is ready

```
Kubernetes Deployment sola-app
├── Pod k3s-1 (10.42.0.x)
└── Pod k3s-2 (10.42.1.x)
```

### 2. Access (network)

```
Internet → {{DOMAIN}} (Cloudflare)
                │
                ▼
   Service LoadBalancer {{LB_IP}}:8002 (MetalLB)
                │
        ┌───────┴───────┐
        ▼               ▼
   app pod (k3s-1)  app pod (k3s-2)
```

- **Cloudflare** proxies to LoadBalancer IP `{{LB_IP}}` (MetalLB, port 80)
- **Service type LoadBalancer** (MetalLB) — fixed IP, layer2 failover
- If one node fails, MetalLB takes over traffic on the other node

### 3. PostgreSQL Database — CloudNativePG (CNPG)

The most important part of HA. We use the **CloudNativePG** operator.

```
CNPG Cluster "sola-db"
├── sola-db-1 (primary)  → k3s-1
│   └── Storage: Longhorn PVC (1Gi)
├── sola-db-2 (replica)  → k3s-2
│   └── Storage: Longhorn PVC (1Gi)

Services:
├── sola-db-rw → always on primary (write + read)
├── sola-db-ro → on all ready instances (read only)
└── sola-db-r  → on all instances
```

**How they work:**

| Service | Target | Purpose | Usage in app |
|---|---|---|---|
| `sola-db-rw` | **Primary only** (e.g. `sola-db-1`) | Write + read — the only service that accepts `INSERT`/`UPDATE`/`DELETE`. Always points to the current primary, even after failover. | `DATABASE_URL` — main connection for all operations |
| `sola-db-ro` | **All ready instances** (primary + replica) | **Read only** — Kubernetes Service distributes read queries (`SELECT`) across primary and replica. Useful for read-heavy workloads. | `DATABASE_URL_RO` — rarely used, mostly for reports |
| `sola-db-r` | **All instances** (including those not yet ready) | **Read only** — similar to `ro`, but includes instances not yet marked as ready. Less relevant for daily use. | — |

Key distinction: `sola-db-rw` is the **only** one that accepts writes. `sola-db-ro` and `sola-db-r` are read-only — they can offload read queries from the primary. In practice, the app uses exclusively `sola-db-rw` via `DATABASE_URL`.

#### Auto-failover (built-in)

- **`failoverDelay: 30`** — if the primary pod goes down, CNPG waits 30s then promotes a replica to primary (actual detection takes ~1 minute due to Kubernetes health checks)
- **`enablePDB: true`** — PodDisruptionBudget prevents both pods from going down simultaneously
- **Replication** — streaming replication, asynchronous (OK for this application)
- **Storage** — Longhorn, each instance has its own PVC
- **Node anti-affinity** — `podAntiAffinityType: preferred` on `kubernetes.io/hostname`

#### Failover process

1. K3s-1 crashes → primary pod `sola-db-1` becomes unreachable
2. CNPG operator detects the outage (~1 minute)
3. CNPG promotes `sola-db-2` (on k3s-2) to primary (~2 minutes)
4. Service `sola-db-rw` automatically redirects to `sola-db-2`
5. App on k3s-1: pod is dead → k3s reschedules it onto k3s-2
6. App on k3s-2: connects to `sola-db-rw` (which points to `sola-db-2`) → continues working

**Total downtime:** ~3 minutes (~1 min detection + ~2 min promotion + time for k3s to detect the dead node and reschedule the app pod)

#### Recovery after node repair

When k3s-1 comes back up:
1. CNPG automatically notices a new node is available
2. `sola-db-1` automatically joins as a **replica** (no manual intervention needed!)
3. CNPG manages the entire process — no manual `cnpg` command required

### 4. Configuration

**App connection to database:**
```
DATABASE_URL=postgresql://sola:***@sola-db-rw.sola:5432/sola
```
Uses the `sola-db-rw` Service, which always points to the current primary.

**Application secret:**
- Namespace: `sola-app`
- Secret: `sola-secrets`
- Contains: `DATABASE_URL`, `MAIL_*`, `BACKUP_EMAIL`

**CNPG Cluster:**
- Namespace: `sola`
- Name: `sola-db`
- 2 instances, each on its own node
- Longhorn storage (1Gi)
- Auto-failover: 30s

**Operator:**
- Namespace: `cnpg-system`
- Name: `cnpg/cloudnative-pg`
- Version: helm chart, latest stable

### 5. Testing HA

To simulate an outage:
```bash
# Shut down one node (e.g. k3s-1)
ssh k3s-1 "sudo poweroff"

# Check that the app remains accessible
curl -I https://{{DOMAIN}}

# After ~2 min check the status
kubectl get pods -n sola -o wide      # sola-db-2 should be primary
kubectl get pods -n sola-app -o wide  # sola-app pod on k3s-2

# When the node is back up, check the status
kubectl get cluster -n sola sola-db    # CNPG should have 2 ready instances
```

### 6. Important Notes

- **Cloudflare** points to LoadBalancer IP `{{LB_IP}}` — if this IP changes, Cloudflare DNS must be updated
- **Longhorn** takes care of PVCs — data is safe even if one node is lost
- **No custom failover scripts** — everything is managed by the CNPG operator
- **Failover is fully automatic** — no manual intervention required
- **Old Bitnami PostgreSQL** was removed after the migration to CNPG
