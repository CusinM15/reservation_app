[🇸🇮 Slovenščina](../poletna_pavza.md) | [🇬🇧 English](poletna_pavza.md)

---

# ☀️ **Summer Shutdown — ostc-app**
## **OŠ Toneta Čufarja**

This document covers the annual summer shutdown procedure (July–August) when the app is not needed.

**Purpose:** Reduce wear on the older laptop hardware and preserve data for the next school year.

**Goal:** 60 days of rest for both nodes.

---

## Procedure

### 1. Before Shutdown (last working day)

#### Backup database

```bash
# Manual backup (in addition to automatic CronJob)
kubectl exec -n sola sola-db-1 -- bash -c "PGPASSWORD=*** pg_dump -U sola -d sola" > /tmp/sola-full-backup-$(date +%Y%m%d).sql
```

#### Scale down app

```bash
kubectl scale deploy -n sola-app sola-app --replicas=0
```

#### Stop both nodes

```bash
# k3s-2 first (replica)
ssh admin_os@193.2.171.249 "sudo poweroff"

# Wait 1 minute, then k3s-1
ssh admin_os@193.2.171.250 "sudo poweroff"
```

### 2. During Shutdown

- Both nodes are powered off
- No power consumption, no fan wear, no disk activity
- Longhorn data is replicated and safe on both disks
- Make sure the room is dry and at reasonable temperature

### 3. Startup (September)

#### Power on k3s-1 first

If Wake-on-LAN is configured:
```bash
# From Windows admin machine (193.2.171.244)
wakeonlan -i 193.2.171.255 <MAC_ADDRESS_k3s-1>
```

Or manually press the power button on k3s-1.

Wait for k3s-1 to boot and verify:
```bash
ssh admin_os@193.2.171.250
sudo systemctl status k3s
kubectl get nodes
```

#### Power on k3s-2

```bash
# From k3s-1, wake k3s-2 via WoL
# Or manually press power button on k3s-2
```

#### Verify cluster

```bash
kubectl get nodes    # Both should be Ready
kubectl get pods -n sola -o wide  # Both DB pods running
```

#### Scale up the app

```bash
kubectl scale deploy -n sola-app sola-app --replicas=2
kubectl rollout status -n sola-app deployment/sola-app
```

#### Verify everything works

```bash
curl -I https://ostc-app.org   # Should return 307
kubectl get pods -A            # All pods healthy
```

## Expected lifetime benefit

| Node | Before | After 60-day rest |
|---|---|---|
| k3s-1 | 120–180 days | 180–240 days |
| k3s-2 | 60–120 days | 120–180 days |

The summer break can extend the usable lifetime by approximately **2 months**.
