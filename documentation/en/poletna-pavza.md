🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../poletna-pavza.md) | [🇬🇧 English](poletna-pavza.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# 🌞 Summer Break — k3s Cluster

This document contains **step-by-step instructions** for safely shutting down and later powering up the entire school server system — the so-called **"holiday shutdown"**. It's written for people who aren't in Kubernetes every day, so every command is also **explained in plain language**.

The system we're shutting down:

| Component                                   | Description                                                                                                               |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **2 nodes** (laptops): `k3s-1` and `k3s-2` | Both serve as control-planes and store data (etcd). Physically: old laptops.                                               |
| **CloudNativePG (CNPG)**                    | The database (PostgreSQL). Runs in 2 instances (replicas) for safety.                                                     |
| **Longhorn**                                | Disk storage — like a "filing cabinet for data." Ensures data isn't lost, even if one disk fails.                          |
| **MetalLB**                                 | Assigns external IP addresses to applications (e.g. {{LB_IP}} for web access).                                            |
| **Application**                             | The school web application itself (namespace: sola-app).                                                                  |

---

## 📋 Summary — what happens start to finish

```
1.  Check cluster status — make sure everything is OK
2.  Backup the database — save a copy just in case
3.  Stop the application (scale down) — tell the system "sleep, not death"
4.  Stop the database (scale down CNPG) — the database goes dormant, data stays
5.  Wait for Longhorn disks to detach — volumes become "detached"
6.  Stop Kubernetes and power off the laptops
7.  Unplug from power (optional)
   --- SUMMER BREAK ---
8.  Power on the laptops
9.  Start Kubernetes on both
10. Wait for Longhorn to be healthy — disks must be "healthy"
11. Start the database (scale up CNPG)
12. Start the application (scale up)
13. Verify everything works
```

---

## 🤔 Why shut down at all?

Because these are **old laptops**. Nobody uses the application during the summer break (July, August), so:

- **Less runtime = less wear = longer lifespan.** Old fans, old disks, old chips — every hour of operation counts. Two months saved is huge.
- **Less electricity usage** — every kilowatt matters, especially in a school.
- **Less risk** — during summer storms and power outages, there's nobody around to check if the system is OK.

**Important:** we're not deleting anything. We're just stopping. Think of it as **hibernation** for the computer — when it wakes up, it returns exactly where it was.

---

## 1. 📊 Current State (Before the Break)

Before we do anything, let's see what the system looks like right now.

| Node  | IP           | Role                | Status |
| ----- | ------------ | ------------------- | ------ |
| k3s-1 | {{K3S_1_IP}} | control-plane, etcd | Ready  |
| k3s-2 | {{K3S_2_IP}} | control-plane, etcd | Ready  |

See what's running:

```bash
kubectl get pods -A -o wide
```

Longhorn disk (storage) status:

```bash
kubectl get volumes -n longhorn-system -o wide
# Expected: both sola-db volumes "attached" and "healthy"
```

> **Why are we checking this?** If something is already wrong (e.g. a volume is "faulted" or a node isn't "Ready"), we don't want to make it worse by shutting down. Fix any issues first, then proceed with the shutdown.

---

## 2. ✅ Before Shutdown — Verification and Backup

### 2.1 Check the Entire Cluster

Run these commands. They're not "magic words" — each one checks a different part of the system:

```bash
# Check that both laptops are alive, reachable, and ready
kubectl get nodes -o wide

# Check what's running (pods = programs)
kubectl get pods -A

# Check Longhorn disks — are they "healthy"?
kubectl get volumes.longhorn.io -n longhorn-system -o wide

# Check that disk claims (PVCs) are properly connected
kubectl get pvc,pv -A -o wide

# Check the database (CNPG) — does it have 2 working instances?
kubectl get cluster -n sola sola-db
```

**What you should see (checklist):**

- [ ] Both nodes: `Ready`
- [ ] Longhorn volumes: `healthy`
- [ ] CNPG cluster: 2 ready instances
- [ ] No Longhorn rebuilds in progress (no "rebuilding" in the STATE column)

### 2.2 Database Backup — Safety Copy

**This is the most important step.** If anything goes wrong, you'll have a backup on a USB drive.

```bash
# Dump the entire database to a file
kubectl exec -n sola -it sola-db-1 -- pg_dump -U postgres -d sola --clean > /tmp/sola_backup_pred_pavzo.sql

# Verify the file exists and isn't empty (~1 MB or more)
ls -lh /tmp/sola_backup_pred_pavzo.sql

# COPY TO A USB STICK or another safe disk!
cp /tmp/sola_backup_pred_pavzo.sql /media/usb/
```

> **Why USB?** Longhorn is great, but if both laptops die over the summer (lightning, humidity, anything), the USB backup is the only solution. Longhorn protects against one disk failing, not against a fire in the school.

---

## 3. ⬇️ Stopping the Application and Database — "Let's Put the System to Sleep"

**The order is important!** We stop in this order:
```
Application → Database (CNPG) → Wait for Longhorn → Power off nodes
```

Why? Think of a **restaurant kitchen**:
1. First, tell the cooks to stop cooking (stop the application)
2. Then close the pantry (stop the database) — nobody will grab ingredients anymore
3. Then clean up and close the kitchen (Longhorn detaches disks)
4. Finally, turn off the lights (power off the laptops)
   If you turned off the lights while cooks were still chopping vegetables, there'd be a mess.

---

### 3.1 First: Stop the Application

The application is the web program people use in their browser. We tell it to "go to sleep":

```bash
# Scale down = tell the system "put the pods to sleep, don't delete them"
# --replicas=0 means: 0 copies = nothing is running
kubectl -n sola-app scale deployment sola-app --replicas=0

# Wait for the system to confirm all pods are stopped
kubectl -n sola-app rollout status deployment/sola-app
```

**Important:** pods (programs) disappear, **but the data stays**. Disks, settings, everything remains. When you say `--replicas=2` in autumn, they come back exactly as they were.

Verify the application is gone:

```bash
kubectl get pods -n sola-app
# Expected: no pod is "Running"
```

### 3.2 Next: Stop the Database (CNPG)

The database is the heart of the system. All the data is here (grades, reservations, users). CNPG manages the database in two copies (replicas), so stopping works a bit differently than a regular application — **we don't delete, we just patch to 0**.

```bash
# "Patch cluster to instances=0" = tell the database "stop yourself, but don't delete the disks"
# This is NOT deletion! Instance=0 means "temporarily stop" — like putting the kitchen in standby,
# not demolishing it. Disks (PVCs) remain attached and preserved.
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":0}}'

# Wait for the database pods to disappear (watch live)
kubectl get pods -n sola -w
# Press Ctrl+C when you see no more Running pods

# Verify that disks (PVCs) are STILL present!
kubectl get pvc -n sola
# Expected: sola-db-1 and sola-db-2 — both "Bound" (attached, though without active pods)
```

> ✅ PVCs (disks) remain. This means **your data is safe in Longhorn**. When you start the database again, it attaches to the same disks with the same data.

### 3.3 Wait for Longhorn Disks to Detach

Once the database is no longer running, Longhorn will **automatically detach the disks** after a few minutes. This is normal and expected.

```bash
kubectl get volumes -n longhorn-system -o wide
```

In the `STATE` column you'll see:

- **Before:** `attached` (disks are attached to database pods — normal during operation)
- **Later:** `detached` (disks are detached — **this is OK**, meaning they're safe in storage and nobody is writing to them)

**Why is "detached" OK?** Think of a book in a library. When someone is reading it, it's "attached" (to the reader). When they return it to the shelf, it's "detached" (on the shelf, safe, nobody can damage it). The data is still there. When we need the database again in autumn, Longhorn automatically reattaches the disks.

> ⚠️ **Don't continue until all volumes are "detached"!** If you power off a laptop while Longhorn is still writing something to disk, you could lose data.

---

## 4. 🔌 Shutting Down Nodes

### 4.1 Stop Kubernetes and Power Off

Now that all programs are stopped and disks are safe, we can power off the laptops.

**Order: k3s-1 first, then k3s-2.** Why? Both are control-planes, so the order isn't critically important, but it's good practice to always follow the same order — fewer chances for mistakes.

```bash
# ON k3s-1 (physically or via SSH):
# 1. Stop the Kubernetes service
sudo systemctl stop k3s
# 2. Power off the laptop
sudo poweroff

# Wait for k3s-1 to be completely off (no longer pings)

# ON k3s-2:
sudo systemctl stop k3s
sudo poweroff
```

> **Tip:** If you have SSH access, check that the laptop really powered off (try connecting again via SSH — a refused connection means the computer is off).

### 4.2 Optional: Unplug from Power

If summer storms are frequent, you can also **physically unplug the laptops from power**. Laptops have internal batteries that will protect the system in case of a sudden power event.

---

## 5. ⬆️ Powering On in Autumn — "Waking from Hibernation"

**The power-on order is the reverse of the shutdown:**
```
Power on nodes → Start Kubernetes → Wait for Longhorn → Start database → Start application
```

Why this order? Think of unlocking a store:
1. First, unlock the door (power on laptops)
2. Then turn on the lights (start Kubernetes)
3. Then check that the fridge is plugged in and working (check Longhorn)
4. Then open the warehouse (start the database)
5. Then turn on the cash register and open the doors for customers (start the application)

---

### 5.1 Physically Power On Laptops

Go to the laptops and turn them on (power button — usually on the side or keyboard). Wait for both systems to boot (about 1–2 minutes).

### 5.2 Start Kubernetes

Start on one, then the other:

```bash
# ON k3s-2 (order isn't critical, but let's start with the second one):
sudo systemctl start k3s

# Wait for the node to be visible and "Ready"
kubectl get nodes
# k3s-2 should be "Ready"

# ON k3s-1:
sudo systemctl start k3s

# Wait for both to be "Ready"
kubectl get nodes
# Expected: both nodes "Ready"
```

> **Why not start both at the same time?** Because we want to see if either one causes problems. If you start both at once and one dies, you won't know which one is at fault.

### 5.3 Check Longhorn — Disks Must Be Healthy

Longhorn is the most sensitive part of the system. When Kubernetes starts, Longhorn automatically **reattaches disks** (they transition from "detached" to "attached" and then to "healthy").

```bash
kubectl get volumes -n longhorn-system -o wide
```

**What you'll see:**
1. First: volumes are "detached" — this is OK, Longhorn hasn't attached them yet
2. After ~30 seconds to 5 minutes: they become "attached" — reattached
3. Then: "healthy" — all data has been read and verified

**Wait for ALL volumes to be "healthy."** This is the signal that storage is ready.

> **Why does this take time?** Longhorn needs to read data from disk, check that all parts (replicas) are consistent, and fix minor discrepancies if needed. It's like restoring a backup onto a disk — it takes a while.

**If any volume is "faulted" (broken):**
This is rare but possible. Go to the "If Something Goes Wrong" section below.

### 5.4 Start the Database (CNPG)

Once Longhorn is healthy, you can start the database. This is the reverse of step 3.2 — instead of `instances:0`, we set `instances:2`:

```bash
# Restore CNPG cluster to 2 instances (two database copies)
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":2}}'

# Watch database pods start up (wait for both to be Running)
kubectl get pods -n sola -w
# Press Ctrl+C when you see sola-db-1 and sola-db-2 in Running state

# Verify the CNPG cluster is healthy
kubectl get cluster -n sola sola-db
# Expected: 2 ready instances, status "healthy"
```

> **Good news:** CNPG (CloudNativePG) automatically establishes replication between both instances. No manual command is needed. This means data syncs automatically between the first and second database copies.

### 5.5 Start the Application

Once the database is running, we can start the application:

```bash
# Scale up = tell the system "wake up the pods"
# --replicas=2: two copies of the application (for better reliability)
kubectl -n sola-app scale deployment sola-app --replicas=2

# Wait for all pods to be Running and the application to be ready
kubectl -n sola-app rollout status deployment/sola-app
# Expected: "deployment sola-app successfully rolled out"
```

### 5.6 Verify Everything Works

Now it's time for the final check:

```bash
# 1. Application health check — ask the system "are you alive?"
curl -s http://{{LB_IP}}:8002/health
# Response: {"status":"ok","version":"0.1.0"}

# 2. Check that the domain works (website)
curl -sI https://{{DOMAIN}}
# Response: HTTP/2 307 → redirect to /auth/login (normal!)

# 3. Check the data in the database — are all users and reservations still there?
kubectl exec -n sola sola-db-1 -- psql -U postgres -d sola -c \
  "SELECT count(*) FROM users; SELECT count(*) FROM reservations;"
# Expected: numbers that aren't 0 (same number of users and reservations as before the break)
```

---

## 6. ⚠️ Important Warnings

1. **Longhorn is NOT a backup.** Longhorn protects against a single disk failure (if one laptop dies, data remains on the other). **It does NOT protect against:**
   - Human error (someone accidentally deletes the database)
   - Software bugs (a bug in the application deletes data)
   - Physical theft or fire
   → Therefore, always keep an **external backup** (as we did in step 2.2)

2. **Don't shut down during a Longhorn rebuild.** If Longhorn is currently repairing a replica (you see "rebuilding" in the STATE column), **wait!** Shutting down during a rebuild can corrupt data. Wait until the volume is `healthy` again.

3. **Don't just flip the power switch!** Always do a **graceful shutdown**:
   ```
   Scale down app → scale down database → wait for Longhorn to detach → stop k3s → poweroff
   ```
   Think of it like: don't throw a book out the window — close it and place it neatly on the shelf.

4. **The domain will be unreachable during the break.** The Cloudflare proxy points to the LoadBalancer ({{LB_IP}}), which will be off during the break. When the application starts in autumn, the LoadBalancer automatically starts with it. The domain will work again within a few minutes of powering on.

5. **Check cronjobs after powering on.** The system has scheduled tasks (database backups, daily reports). Verify they've started:
   ```bash
   kubectl get cronjobs -A
   kubectl get jobs -A
   ```

6. **CNPG automatically establishes replication.** No manual `pg_basebackup` or similar command is needed. CloudNativePG handles everything itself.

---

## 7. 🆘 If Something Goes Wrong — Troubleshooting

Here are the most common issues and how to resolve them.

### Issue: Longhorn volume stays "detached" even after 15 minutes

**Cause:** Longhorn is waiting for the disk to attach, but something is blocking it.
**Solution:** Try manually attaching the volume:
```bash
# Find the volume name
kubectl get volumes -n longhorn-system

# Manually attach
kubectl annotate volume -n longhorn-system <volume-name> longhorn.io/volume-scheduling-error-

# If that doesn't help, check the Longhorn UI:
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# Open in browser: http://localhost:8080
# Go to "Volume" and check what's listed under "Conditions"
```

### Issue: Longhorn volume is "faulted" (broken)

**Cause:** One of the disks has physically failed or the data is corrupted.
**Solution:**
1. Check which replica is faulty
2. If one replica is working, you can restore from it:
```bash
kubectl get volumes -n longhorn-system -o yaml | grep -A 5 "robustness"
# See which replica is "healthy"
```
3. In the Longhorn UI (see above), select "Detach" and then "Attach" — this often fixes itself
4. If there's no fix, **restore the database from the USB backup** (step 2.2)

### Issue: CNPG won't start (pods stay "Pending" or "CrashLoopBackOff")

**Cause:** PVCs are corrupted or Longhorn isn't ready yet.
**Solution:**
```bash
# Check what's wrong
kubectl describe pod -n sola sola-db-1

# Check PVC status
kubectl get pvc -n sola

# If PVC isn't "Bound", check Longhorn
kubectl get volumes -n longhorn-system -o wide

# Wait for Longhorn volumes to become "healthy", then try again:
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":0}}'
# Wait 30 seconds
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":2}}'
```

### Issue: Application starts but throws "database connection refused"

**Cause:** The database isn't ready yet when the application tries to connect.
**Solution:** Wait a few more minutes and try again. If that doesn't help:
```bash
# Check if the database is reachable
kubectl exec -n sola-app deploy/sola-app -- nc -zv sola-db-rw.sola 5432
# If "Connection refused", the database isn't ready yet

# Check database status
kubectl get cluster -n sola sola-db
```

### Issue: Node won't wake up (no response on SSH)

**Cause:** There might be a network issue or the laptop wasn't properly powered on.
**Solution:**
1. Physically check the laptop — are there lights? Can you hear the fan?
2. Try holding the power button for 30 seconds (hard reset), then turn it on again
3. Consider the possibility that the battery completely drained over the summer — plug in the charger and wait 10 minutes

### Issue: Data is missing from the database after powering on

**Cause:** Very rare — disk corruption or a Longhorn replication error may have occurred.
**Solution:** Restore from the USB backup:
```bash
# Copy the backup into the database pod
kubectl cp /media/usb/sola_backup_pred_pavzo.sql sola/sola-db-1:/tmp/

# Restore the database
kubectl exec -n sola -it sola-db-1 -- psql -U postgres -d sola -f /tmp/sola_backup_pred_pavzo.sql
```

---

## 8. 📝 Quick Checklist

### Before Shutdown (July)
- [ ] Both nodes `Ready`
- [ ] Longhorn volumes `healthy`
- [ ] Database backup created and saved to USB
- [ ] App scaled down to 0
- [ ] Database scaled down to 0 (instances: 0)
- [ ] Longhorn volumes `detached`
- [ ] k3s stopped on both nodes
- [ ] Laptops powered off

### After Powering On (August)
- [ ] Both laptops powered on
- [ ] k3s running on both nodes
- [ ] Both nodes `Ready`
- [ ] Longhorn volumes `healthy`
- [ ] Database scaled up to 2
- [ ] App scaled up to 2
- [ ] Health check OK (`curl /health`)
- [ ] Website reachable
- [ ] Cronjobs running

---

> **Author:** Matej Čušin  
