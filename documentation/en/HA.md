🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../HA.md) | [🇬🇧 English](HA.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# HA Architecture — ostc-app (sola-app)

## What does "high availability" even mean?

In plain English: **if one computer dies, another takes over instantly, and users don't even notice.**

The application and database run on two physical nodes (HP ProBook 455 G5 and 450 G5). If one crashes, goes to service, or loses power — the other node picks everything up without anyone having to manually switch anything over.

---

## 1. Application (sola-app) — "two run, one falls, the other carries"

The application runs in **two copies (pods)**, one on each node. This isn't luxury, it's the bare minimum for HA.

**One replica per node** — that's the rule. With 2 nodes (k3s-1 and k3s-2), we always have 2 replicas, each on its own machine.

When it gets busy (start of school year...), the **HorizontalPodAutoscaler (HPA)** automatically adds a third replica. When load drops, it scales back to 2.

```bash
kubectl get hpa -n sola-app
# NAME            REFERENCE              TARGETS          MIN   MAX   REPLICAS
# sola-app-hpa    Deployment/sola-app    45%/60% (CPU)    2     4     2
```

> **ELI5:** Like two coffee machines in the school kitchen — each has its own water and coffee. During break when 100 teachers want coffee at once, a third and fourth machine automatically kick in. When the rush ends, it's back to "just" two. Teachers (users) just get their coffee — they don't care how many machines are behind the curtain.

> Note: Health check at /health endpoint — if it returns 200 OK, the pod is alive. If not, Kubernetes kills it and starts a new one.

---

## 2. Network Access — "traffic always finds a way"

![HA network flow: Internet to Cloudflare to LoadBalancer to app pods](diagrams/ha-network.png)

- **Cloudflare** points to the static IP LB_IP — this is the public entry point
- **MetalLB** (Layer2 mode) advertises this IP on one of the nodes
- If that node goes down, **the IP automatically moves to the other**, like porting a phone number to a different exchange — callers (users) don't know and don't care where the phone physically is

> ELI5: Imagine a house with a mailbox on the front door. If the door jams, the mailman (Cloudflare) tosses the letter (traffic) through the window. The letter always gets in, even if the door is locked.

---

## 3. PostgreSQL Database — CNPG (CloudNativePG)

**This is the most critical part.** The app can survive losing one pod, but not the database. That's why PostgreSQL runs in HA configuration via **CloudNativePG (CNPG) operator**.

![CNPG PostgreSQL cluster — primary, replica, service endpoints](diagrams/cnpg-cluster.png)

### How streaming replication works

The replica watches the primary and **mirrors every move**. Every INSERT, UPDATE, DELETE on the primary is streamed to the replica in real-time. If the primary fails, the replica already has all the data — it's just missing "permission" to start writing.

### Database Services

| Service | Target | Purpose |
|---------|--------|---------|
| sola-db-rw | Current primary only | **Write + read.** Accepts INSERT/UPDATE/DELETE. After failover, automatically points to the new primary. Used by the app via DATABASE_URL. |
| sola-db-ro | All ready instances | **Read-only.** Kubernetes round-robins read requests (SELECT) between primary and replica. For reports and heavy read loads. |
| sola-db-r | All instances (including unready) | **Read-only.** Rarely used. |

In practice, the app exclusively uses sola-db-rw via DATABASE_URL.

---

### Failover — "guardian watching the database"

The CNPG operator is like a **guardian watching over the database**. It constantly checks whether the primary is alive. If the primary goes down, it immediately promotes the standby.

```yaml
failoverDelay: 30      # waits 30 seconds to be sure the primary really isn't coming back
enablePDB: true        # prevents both pods from going down simultaneously
podAntiAffinityType: preferred  # prefers pods on different nodes
```

#### Failover process (step by step)

1. **k3s-1 goes down** — primary pod sola-db-1 disappears
2. **CNPG detects the outage** — 30s failover delay to avoid false alarms
3. **Promotion** — sola-db-2 (on k3s-2) becomes the new primary and starts accepting writes (~2 minutes)
4. **Service sola-db-rw** — automatically redirects to sola-db-2
5. **App on k3s-1** — pod is dead, k3s reschedules it to k3s-2
6. **App on k3s-2** — connects to sola-db-rw (now pointing to sola-db-2) — business as usual

**Total downtime:** ~1-2 minutes. In IT, that's pretty solid for HA without a formal downtime.

> ELI5: Like a plane with two engines. One fails — the pilot (CNPG) just increases power on the other. Passengers (users) feel a slight shudder (a couple minutes of inaccessibility), then the plane flies on like nothing happened.

#### Recovery (when the failed node comes back)

When k3s-1 comes back online, this happens without any manual intervention:

1. CNPG notices the node is available again
2. sola-db-1 automatically rejoins as a **replica** — it doesn't become primary, it starts mirroring the current primary
3. All you have to say is "nice, it works"

---

## 4. etcd Consensus — "majority decides"

K3s uses **embedded etcd** to store the entire cluster state (which pods are where, what services exist, etc.).

Etcd works on a **quorum** principle. For 2 nodes this means:

- **2 nodes = quorum of 2** — both must confirm a change
- **If one node goes down** — the other can still read and write because 1 out of 2 is technically a majority... wait, **that's not entirely accurate**

> Technical note: A classic 2-node etcd cluster is technically in a risk zone, because losing one node means losing quorum for writes. In practice, k3s with 2 nodes works fine for our use-case (2 ProBooks) because k3s tolerates losing 1 node for reads, while writes still need confirmation. But for production with strict requirements, go with more nodes if you have "a lot" of Windows 10 computers.

**The takeaway:** 2 nodes can work normally even if one fails, as long as the surviving node takes over all operations.

> ELI5: etcd is like a club with rules. Every decision (change in the cluster) needs a majority vote. With two members and one goes down — the other can still decide alone. But if both go down, the club is closed until someone comes back.

---

## 5. Quick Config Reference

**App connection to database:**
```
DATABASE_URL=postgresql://sola:***@sola-db-rw.sola:5432/sola
```
The sola-db-rw service always points to the current primary. The app never needs to care which node is primary.

**Application secrets:**
- Namespace: `sola-app`
- Secret: `sola-secrets`
- Contains: DATABASE_URL, MAIL_*, BACKUP_EMAIL

**CNPG Cluster:**
- Namespace: `sola`
- Name: `sola-db`
- 2 instances, each on its own node
- Longhorn storage (1Gi) each
- Auto-failover: 30s

**Operator:**
- Namespace: `cnpg-system`
- Name: cnpg/cloudnative-pg
- Version: helm chart, latest stable

---

## 6. HA Testing — "hit it and see what happens"

If you want to simulate an outage:

```bash
# Shut down one node (e.g. k3s-1)
ssh k3s-1 "sudo poweroff"

# Verify the app stays accessible in few minutes it should be active again
curl -I https://{{DOMAIN}}

# After ~2 min, check the state
kubectl get pods -n sola -o wide      # sola-db-2 should be primary
kubectl get pods -n sola-app -o wide  # sola-app pod on k3s-2

# When the node is back up, verify state
kubectl get cluster -n sola sola-db    # CNPG should have 2 ready instances
```

---

## 7. Important Notes

- **Cloudflare** points to LoadBalancer IP LB_IP — if this IP changes, Cloudflare DNS needs to be updated
- **Longhorn** takes care of PVCs — data is safe even if one node is lost
- **No custom failover scripts** — everything is managed by the CNPG operator (leave it alone, it does what it needs to)
- **Failover is fully automatic** — no manual intervention required

---

## Q&A

### What if both nodes fail?

Then you're out of luck. The app is dead, the database is dead, users see "site unreachable". When the nodes come back, k3s etcd needs recovery, Longhorn PVCs need to reattach, and CNPG will try to restart the database. Data is safe (Longhorn replication), but **as long as both nodes are down, nothing works.** If this happens often, you need a 3rd node or a cloud solution.

### How do I know which node has the primary database?

```bash
kubectl get cluster -n sola sola-db -o json | jq '.status.currentPrimary'
```
or
```bash
kubectl exec -n sola -it deploy/sola-app -- psql $DATABASE_URL -c "SELECT pg_is_in_recovery();"
```
`pg_is_in_recovery()` returns `f` (false) = primary, `t` (true) = replica.

### Do I lose data if a node fails?

**No, if only one node fails.** Longhorn handles data replication. Even if the node hosting the primary database goes down, the replica on the other node has all the data (a slight delay due to async streaming replication — max a few seconds, in practice usually under 1s). This is called **RPO (Recovery Point Objective)** — in the worst case you lose the last few seconds of transactions. For this app, that's acceptable.

### Why run the app locally?

As of October 2025, Windows 10 is officially dead — no more updates, no more security patches. But that doesn't mean these computers need to be thrown away. They're still perfectly usable. Let's look at the options.

**1. Linux instead of Windows**
You can install **Zorin OS 18.01** or **Linux Mint** on these machines. Both are fast, secure, and user-friendly — Zorin is even designed for people switching from Windows. The catch? Schools have Microsoft contracts and most staff use Office. Switching OS isn't always practical when teachers rely on Outlook, Word, and Excel.

**2. Local server from obsolete computers**
Even if a computer isn't suitable for daily work with Windows 11 anymore, it still makes an excellent server. Install Linux on it and host this app (and other things). This means more work for the admin — setup, maintenance — but:
- The computer stays in full use until the end of its life
- Nothing goes to waste
- The app stays fully under your control
- No monthly cloud costs

**3. Windows 10? Not an option**
Without security updates, it's a ticking time bomb. Especially for an app that handles data.

**Bottom line:** These computers are still good — just not for Windows 10 anymore. The options are: Linux (for users), local server (for infrastructure), or newer Windows. This app solves the problem because you don't need a powerful machine — even an old laptop as a server is enough.

---


> **Author:** Matej Čušin  
