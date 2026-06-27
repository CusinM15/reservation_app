🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../POLETNA_PAVZA.md) | [🇬🇧 English](POLETNA_PAVZA.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# 🌞 Summer Shutdown — k3s Cluster

This document contains instructions for safely shutting down the application and the k3s cluster over the summer (July/August) when the application is not needed. The goal is to reduce wear on old computers and preserve data.

> ⚠️ **This document has been updated for the CNPG architecture.** If you are using the old Bitnami PostgreSQL, refer to the older version.

---

## 📋 Summary

```text
1. Check cluster status
2. Backup database
3. Stop application (scale down)
4. Stop database (scale down CNPG)
5. Stop k3s on nodes
6. Poweroff
--- in autumn ---
7. Power on nodes in reverse order
8. Wait for Longhorn to be healthy
9. Start database (scale up CNPG)
10. Start application (scale up)
11. Verify everything
```

---

## 1. Current status (before shutdown)

| Node | IP | Role | Status |
|---|---|---|---|
| k3s-1 | 192.168.1.1 | control-plane,etcd | Ready |
| k3s-2 | 192.168.1.2 | control-plane,etcd | Ready |

Current pods:

```bash
kubectl get pods -A -o wide
```

Longhorn volumes:

```bash
kubectl get volumes -n longhorn-system -o wide
# Expected: both sola-db volumes "attached", "healthy"
```

---

## 2. Before shutdown — verification

### 2.1 Check cluster status

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl get volumes.longhorn.io -n longhorn-system -o wide
kubectl get pvc,pv -A -o wide
kubectl get cluster -n sola sola-db
```

Verify:
- Both nodes are `Ready`
- Longhorn volumes are `healthy`
- CNPG cluster has 2 ready instances
- No Longhorn rebuilds in progress

### 2.2 Backup database

Before shutting down, take a fresh backup:

```bash
# Backup via CNPG (recommended)
kubectl exec -n sola -it sola-db-1 -- pg_dump -U postgres -d sola --clean > /tmp/sola_backup_pred_pavzo.sql

# Check size
ls -lh /tmp/sola_backup_pred_pavzo.sql

# Also save outside the cluster (e.g. on a USB stick)
```

---

## 3. Stopping the application and database

### 3.1 Stop app

```bash
kubectl -n sola-app scale deployment sola-app --replicas=0
kubectl -n sola-app rollout status deployment/sola-app
# Wait until there are no more Running pods
```

### 3.2 Stop database (CNPG)

CNPG does not use StatefulSet. The cluster is stopped with:

```bash
# Patch cluster to 0 instances (stops without deleting PVCs)
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":0}}'

# Wait for pods to disappear
kubectl get pods -n sola -w

# Verify that PVCs are still present
kubectl get pvc -n sola
# Expected: sola-db-1 and sola-db-2 (Bound)
```

> ✅ PVCs remain — data is safe in Longhorn.

### 3.3 Wait for Longhorn volumes to detach

```bash
kubectl get volumes -n longhorn-system -o wide
# Wait for sola-db volumes to become "detached"
```

---

## 4. Shutting down nodes

### 4.1 Stop k3s and power off

First `k3s-1`, then `k3s-2`:

```bash
# On k3s-1:
sudo systemctl stop k3s
sudo poweroff

# Wait for k3s-1 to shut down

# On k3s-2:
sudo systemctl stop k3s
sudo poweroff
```

> **Order is not critical** (both are control-plane), but I recommend k3s-1 → k3s-2 for consistency.

---

## 5. Powering on in autumn

### 5.1 Power on both nodes

Physically turn on the computers. Once the systems have booted:

### 5.2 Start k3s

```bash
# On k3s-2 (any order):
sudo systemctl start k3s

# Wait for the node to be Ready
kubectl get nodes

# On k3s-1:
sudo systemctl start k3s

# Wait for both to be Ready
kubectl get nodes
```

### 5.3 Verify Longhorn

```bash
kubectl get volumes -n longhorn-system -o wide
# Wait for volumes to be "healthy" (may take a few minutes)
# If any volume is "detached", Longhorn will automatically reattach it
```

### 5.4 Start database (CNPG)

```bash
# Restore CNPG cluster to 2 instances
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":2}}'

# Wait for both pods to be Running
kubectl get pods -n sola -w

# Check cluster status
kubectl get cluster -n sola sola-db
# Expected: 2 ready instances, healthy
```

### 5.5 Start application

```bash
kubectl -n sola-app scale deployment sola-app --replicas=2
kubectl -n sola-app rollout status deployment/sola-app
```

### 5.6 Verify application

```bash
# Health check
curl -s http://192.168.1.10:8002/health
# {"status":"ok","version":"0.1.0"}

# Website
curl -sI https://ostc-app.org
# HTTP/2 307 → redirect to /auth/login

# Check data in database
kubectl exec -n sola sola-db-1 -- psql -U postgres -d sola -c \
  "SELECT count(*) FROM users; SELECT count(*) FROM reservations;"
```

---

## 6. Important warnings

1. **Longhorn is not a backup** — Longhorn protects against disk/node failure, not human error. Always have an external database backup.

2. **Do not power off during a Longhorn rebuild** — if Longhorn is repairing a replica, wait until the volume is `healthy` again.

3. **Do not just flip the power switch** — always graceful shutdown: scale down app → scale down database → stop k3s → poweroff.

4. **The domain will be unreachable during the shutdown** — Cloudflare proxy points to k3s-2, which will be powered off.

5. **Check cronjobs after powering on** — backup and report will start automatically per schedule.

6. **CNPG automatically establishes replication** — no manual command needed.
