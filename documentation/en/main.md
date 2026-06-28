🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../main.md) | [🇬🇧 English](main.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

> 🛠️ **Customize the documentation to your IPs**
>
> All documentation uses a central `.env.ip` file that defines every IP address,
> port, and domain. Want documentation with your own values?
>
> ```bash
> cd documentation
> nano .env.ip                          # enter your IPs
> ./replace-ips.sh                      # docs are updated
> ```
>
> The script replaces all IPs in `.md` files. After running it, you can
> copy-paste commands directly into your terminal — they'll work as-is.
>
> > 💡 **Note:** Placeholders ({{LB_IP}}, {{K3S_1_IP}}, etc.) remain in `.drawio` diagrams — the `replace-ips.sh` script leaves them untouched as they are part of images.

---

# 🚀 **ostc-app — Reservation System**
## **OŠ Toneta Čufarja — Documentation**

---

## 📚 **Documentation Index**

This file is the **main entry point** — like a school reception desk that tells you where to find things. Below are links to specialized subdocuments:

| Document | Description |
|---|---|
| [🏗️ **HA Architecture**](../HA.md) | CloudNativePG, automatic failover, node failure procedure |
| [🌞 **Summer Shutdown**](../POLETNA_PAVZA.md) | Safe k3s cluster shutdown for summer and restart in fall |
| [☁️ **Domain & DNS**](../domena.md) | Domain setup, Cloudflare, DNS records |
| [🐍 **Local App Setup**](../postavi-lokalni-app.md) | Single-machine installation (no Kubernetes) |
| [☸️ **K3s Setup**](../k3s-setup.md) | k3s cluster installation from scratch |
| [⚙️ **Admin/DevOps Guide**](../admin-devops-navodila.md) | Maintenance, updates, troubleshooting |
| [👩‍🏫 **Teachers Guide**](../navodila-ucitelji.md) | Using the app — reservations and assessments |
| [👑 **Management Guide**](../navodila-vodstvo.md) | Browser-based administration (series, blocked dates) |
| [📱 **App Description**](../aplikacija-rezervacije.md) | What the app does, purpose, features |
| [📖 **User Manual**](../navodila-uporabnika.md) | Login, passwords, daily use |

---

## 📑 **Table of Contents** (this document)

1. [System Architecture](#system-architecture)
2. [Hardware and Network](#hardware-and-network)
3. [Kubernetes (k3s) Cluster](#kubernetes-k3s-cluster)
4. [Sola App Application](#sola-app-application)
5. [PostgreSQL HA — CloudNativePG](#postgresql-ha--cloudnativepg)
6. [MetalLB LoadBalancer](#metallb-loadbalancer)
7. [Cloudflare DNS](#cloudflare-dns)
8. [Longhorn Storage](#longhorn-storage)
9. [Daily Backup and Reports](#daily-backup-and-reports)
10. [Maintenance and Failures](#maintenance-and-failures)
11. [Complete Command Reference](#complete-command-reference)
12. [📖 Glossary](#glossary)

---

## 🏗️ **System Architecture**

> **In a nutshell:** Two laptops (HP ProBook) work as a team — if one crashes, the other seamlessly takes over everything the first was doing.

### **How to imagine the whole system? (for non-technical readers)**

Imagine you have two **reception desks** at school. At each desk sits an employee (this is a **Pod** — a container with the application) who receives visitors (users who want to book a slot). Both employees do the same thing — if one is absent, the other keeps working. Behind them are **containers with student records (the database)**, kept in two copies — if one goes up in flames, you have a backup copy. The whole operation is conducted by an **orchestra conductor (Kubernetes)** who makes sure all containers work in harmony.

Below is the technical diagram. Above it is the explanation.

> **Simple explanation of the diagram below:**
> - Two computers (k3s-1 and k3s-2) are connected in a cluster — like two desks in the same office.
> - On each computer runs **one copy of the application (sola-app Pod)** and **one copy of the database (sola-db)**.
> - The database has one **primary (PRIMARY)** and one **replica (REPLICA)**, which constantly copies everything the primary does.
> - All data is stored in **Longhorn** — a system that ensures you have 2 copies on 2 different computers, so even if one computer crashes, no data is lost.
> - When a user opens a browser, traffic goes through **Cloudflare** (security filter + SSL) to **MetalLB LoadBalancer** (reception desk), which sends it to one of the two application copies.

### **Hardware and Network Diagram**

![Complete k3s architecture — 2 nodes, app pods, database, LoadBalancer, Cloudflare](../diagrams/arhitektura-clustra.png)

> **Note:** Both nodes are `control-plane, etcd` — there are no separate worker nodes. k3s runs user pods on control-plane nodes as well. This is perfectly fine for a smaller cluster — with 100+ nodes you would separate them, but for a school system with two HP ProBooks this is totally OK (plus HA becomes much simpler).

> **Btw:** Both HP ProBooks have the `control-plane` role because k3s allows this without issues. In large companies (Google, Amazon) they have separate control-plane nodes, but there we're talking thousands of nodes. For a school cluster this is perfectly OK — you save hardware and simplify setup.

### **Traffic Flow**

> **Simple explanation:** When a teacher enters `https://{{DOMAIN}}` in a browser, this happens: the browser first asks Cloudflare (the internet's phonebook) where this page is. Cloudflare checks its directory, sees IP {{LB_IP}}, and sends the user there. There they are greeted by **MetalLB** (reception desk), which redirects them to one of the two application copies — whichever is currently free.

> **Cloudflare proxy** points directly to the **LoadBalancer (`{{LB_IP}}`, port 80)** — traffic goes directly to MetalLB, HA works automatically — if one node crashes, MetalLB moves the IP to the other.

![Traffic flow: user → Cloudflare → LoadBalancer → app pod](../diagrams/prometni-tok.png)

> **Tip:** Always use Cloudflare proxy (orange cloud) — not just DNS-only (gray cloud). Proxy gives you free SSL, DDoS protection, and hides your real IP from hackers. If you use only DNS, you publicly expose your IP {{LB_IP}} and anyone can attack it directly.

### **Component Overview**

|  | Component | Location | Purpose |
|---|---|---|---|
| | **k3s-1** | HP ProBook 455 G5 ({{K3S_1_IP}}) | Control-plane, app pod, PG primary (main computer) |
| | **k3s-2** | HP ProBook 450 G5 ({{K3S_2_IP}}) | Control-plane, app pod, PG replica (backup computer) |
| | **Sola App (FastAPI)** | 2 pods (both nodes) | Reservations, assessments, login |
| | **Longhorn** | Both nodes | Distributed storage (PVCs) — data in 2 copies |
| | **MetalLB** | Both nodes | LoadBalancer IP ({{LB_IP}}) — entry gate |
| | **Cloudflare** | External | DNS, SSL, proxy — security on the internet |

---

## 💻 **Hardware and Network**

> **In a nutshell:** Two ordinary HP ProBook laptops, each with 256GB disk, connected to the school's Arnes network — that's all you need for the entire system.

### **Specifications**

> **ELI5:** Imagine you have two office computers. The first one (k3s-1) has 16GB RAM — that's like a bigger desk where you can put more papers. The second (k3s-2) has 8GB RAM — a smaller desk, but still enough for routine work.

| Node | Model | CPU | RAM | Disk | Role |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Control-plane, etcd, app, PG primary (main) |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Control-plane, etcd, app, PG replica (backup) |

> **Btw:** k3s-1 has 16GB RAM, k3s-2 has 8GB. This is not a mistake — the primary database (PG primary) on k3s-1 needs more RAM for cache and WAL buffers. When k3s-2 becomes primary (during failover), it will run a bit slower, but the system will still work.

### **Network Settings**

> **ELI5:** Every computer on the network has its own house address (IP). k3s-1 is at address {{K3S_1_IP}}, k3s-2 is at {{K3S_2_IP}}. Together with other devices in the school they form a neighborhood (/24 means up to 254 devices in the same neighborhood). The gateway ({{GATEWAY_IP}}) is the main door of the school, through which all traffic goes to the internet.

```bash
# Local network (Arnes)
k3s-1: {{K3S_1_IP}}/24
k3s-2: {{K3S_2_IP}}/24
Gateway: {{GATEWAY_IP}}
DNS: {{DNS_IP}}

# Kubernetes Pod CIDR — private addresses within the cluster
# (applications in Kubernetes get these addresses, not visible from outside)
10.42.0.0/16

# Kubernetes Service CIDR — internal addresses for services
10.43.0.0/16

# LoadBalancer IP pool (MetalLB) — public addresses visible on the network
{{METALLB_RANGE_START}} - {{METALLB_RANGE_END}}
```

> **Common mistake:** Pod CIDR (10.42.0.0/16) and Service CIDR (10.43.0.0/16) must not overlap with the local network ({{K3S_1_IP}}/24). If they do, Kubernetes won't be able to route traffic correctly. Always check with `ip route` on the nodes before setting up k3s.

### **Access**

```bash
# SSH to both nodes
ssh {{SSH_USER}}@{{K3S_1_IP}}    # k3s-1
ssh {{SSH_USER}}@{{K3S_2_IP}}    # k3s-2

# Kubernetes (k3s) — kubeconfig is on both nodes
kubectl get nodes -o wide
kubectl get pods -A -o wide

# Application in browser
https://{{DOMAIN}}          # via Cloudflare + LoadBalancer (recommended)
http://{{LB_IP}}:{{LB_PORT}}     # directly (internal network only, no SSL)
```

---

## ☸️ **Kubernetes (k3s) Cluster**

> **In a nutshell:** k3s is a lightweight version of Kubernetes (orchestra conductor for applications) that runs on both HP ProBooks and ensures the application always works — even if one computer fails.

> **ELI5 — Kubernetes/k3s:** Imagine an orchestra. Each musician is one application (Pod). **Kubernetes** is the **conductor** — he decides who plays what, when to play, and what to do if someone is late or falls ill. **k3s** is the same thing but lighter — like having a smaller orchestra that doesn't need a huge concert hall. On an HP ProBook laptop, k3s works great, while full Kubernetes (k8s) would be too heavy.

### **Node Status**

> **ELI5:** `kubectl get nodes` is like taking attendance in class — it shows which computers are in the cluster and whether they are ready for work.

```bash
kubectl get nodes -o wide

# NAME    STATUS   ROLES                       AGE   VERSION        INTERNAL-IP      EXTERNAL-IP
# k3s-1   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_1_IP}}    <none>
# k3s-2   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_2_IP}}    <none>
```

### **k3s Installation**

> **Simple explanation:** On the first computer (k3s-1) you run k3s with `--cluster-init` — that means "create a new cluster". On the second (k3s-2) you join an existing cluster with `--server https://{{K3S_1_IP}}:6443` — that's like "please connect me to the boss at this address".

```bash
# On k3s-1 (first node — create a new cluster)
curl -sfL https://get.k3s.io | sh -s - server \
  --cluster-init \
  --disable=traefik \
  --node-ip={{K3S_1_IP}} \
  --flannel-iface=eth0

# On k3s-2 (second node — join existing cluster)
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://{{K3S_1_IP}}:6443 \
  --disable=traefik \
  --node-ip={{K3S_2_IP}} \
  --flannel-iface=eth0 \
  --token <NODE_TOKEN>
```

Get the token with: `sudo cat /var/lib/rancher/k3s/server/node-token` (on k3s-1).

> **Note:** `--disable=traefik` disables the built-in ingress because we use MetalLB LoadBalancer. If we left Traefik enabled, we'd have two systems competing for the same port — confusion we've avoided.

> **ELI5:** Each computer has one or more **network interfaces** — like doors in a house. One interface is for the **Ethernet cable** (physical wire), another for **WiFi** (wireless). **Flannel** is the internal network cabling in Kubernetes — it connects all containers (Pods) with each other, even if they are on different computers. `--flannel-iface=eth0` tells it: "use the Ethernet cable, not WiFi." If you don't specify this, Flannel might pick WiFi (which is slower and less reliable) and the whole cluster won't work correctly.

> **Tip:** Always add `--flannel-iface=eth0`. Why? Because a laptop often has multiple network cards — one for WiFi (e.g. `wlan0`) and one for the Ethernet cable (`eth0`). Flannel (the networking system in Kubernetes) doesn't know which one to use. If it picks WiFi, which is slow or unstable, the cluster won't work. With `--flannel-iface=eth0` you tell it: "use the Ethernet cable, not WiFi." Check what your network cards are called with the `ip a` command on each computer.

---

## 🚀 **Sola App Application**

> **In a nutshell:** A web application (FastAPI + HTML) running in two copies on both computers — if one crashes, the other seamlessly takes over.

> **ELI5:** Imagine a **paper list** on a bulletin board where teachers sign up for computer room or classroom reservations. With paper, what you write stays. If you make a mistake, you can only cross it out (which is messy and hard to read) or get a new sheet. The application is like **the same list, but digital** — you can add a reservation, **change it anytime** or **delete it** with one click, and everything stays clean and organized. No crossing out, no new sheets, no smudging.
> And because it's digital, you can run it in **two copies (Pods)** on two computers. Like having two identical bulletin boards in the hallway — if someone damages or removes one, the other still hangs there and teachers can book normally. Teachers (users) don't even notice — they just open the app and continue working.

### **Deployment**

Namespace: `sola-app`

```bash
kubectl get deployments -n sola-app
kubectl get pods -n sola-app -o wide
kubectl get services -n sola-app
```

The application runs in **1-3 pods**, depending on load. **HorizontalPodAutoscaler (HPA)** automatically adjusts the count:

| **Load** | **Replicas** | **When** |
|---|---|---|
| 🟢 Low (afternoon, weekend, holidays) | **1** | one node works, other rests |
| 🟡 Normal (school hours, reservations) | **2** | one copy on each node |
| 🔴 High (assessments, start of year) | **3** | 2 on one, 1 on the other — Kubernetes decides |

> **ELI5 — HPA:** Like a coffee machine at school — when there are few people, one works. When lunch break comes, a second and third automatically turn on. When the crowd thins out, the extras turn off. HPA does the same for the application.

```bash
kubectl get hpa -n sola-app
# NAME            REFERENCE              TARGETS              MIN   MAX   REPLICAS
# sola-app-hpa    Deployment/sola-app    45%/60% CPU           1     3     2
#                                        60%/70% MEM
```

```bash
kubectl get pods -n sola-app -o wide

# NAME                        READY   STATUS    RESTARTS   AGE   IP           NODE
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.0.x    k3s-1
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.1.x    k3s-2
```

### **Docker Image**

> **ELI5 — Docker Image:** This is like a **recipe for a cake**. You use the same recipe to bake two cakes (two Pods) in two different places. Each cake is identical — the same program, the same settings, the same code. The Dockerfile contains this recipe.

- **Image:** `sola-app:latest`
- **Dockerfile:** `reservation_app/k8s/Dockerfile`
- **Deployment YAML:** `reservation_app/k8s/sola-app.yaml`

### **Application Update**

> **ELI5 — rollout restart:** When you want to update the application, you don't need to shut down the server. Kubernetes does it **with zero-downtime** — it first starts a new Pod, waits until it's ready, only then shuts down the old one. Like changing tires on a car while driving — you swap them one by one, the car keeps moving.

```bash
cd reservation_app
git pull
# Wait for the CI build to finish (GitHub Actions)
# or manually:
kubectl rollout restart deployment -n sola-app sola-app
kubectl rollout status deployment -n sola-app sola-app
```

> **Tip:** Never delete old pods manually. Use `rollout restart`. Kubernetes itself ensures at least one Pod is always active. If you delete both at the same time, you'll have an outage. `rollout status` tells you when the update is complete — don't guess, wait for the "rollout successfully rolled out" message.

---

## 🗄️ **PostgreSQL HA — CloudNativePG**

> **In a nutshell:** The database (PostgreSQL) runs in a high-availability configuration — one primary on k3s-1 and one replica on k3s-2, with CloudNativePG automatically handling the switchover if the primary fails.

> **ELI5 — PostgreSQL:** The database is like a **school folder with all reservations and grades**. It is meant for storing data.
>
> **ELI5 — HA (High Availability):** High availability means you have **two folders** — one original (primary) and one photocopy (replica). Every time you write something in the original, the photocopy gets it immediately. If the original burns (crashes), you take the photocopy and continue where you left off.
>
> **ELI5 — CloudNativePG (CNPG):** This is a **smart assistant** that watches over both folders. If it notices the original has crashed, it automatically says "photocopy, now you're the boss!" and redirects all users to the photocopy. All of this without human intervention.

### **Status**

```bash
kubectl get pods -n sola-app -o wide | grep db

# NAME                    READY   STATUS    IP            NODE
# sola-db-1 (primary)     1/1     Running   10.42.0.x     k3s-1
# sola-db-2 (replica)     1/1     Running   10.42.1.x     k3s-2
```

Built with the **CloudNativePG** operator. Primary always on k3s-1, replica on k3s-2.

### **Failover**

> **ELI5 — Failover:** Failover is an **automatic guard change**. Imagine two guards. The first one (primary) stands at the door. The second (replica) sits in the office and constantly monitors what the first is doing (copying the log). If the first faints, the second immediately jumps to the door and continues as if nothing happened — visitors (users) don't even notice.

During k3s-1 failure:

1. **Primary pod `sola-db-1` becomes unreachable** — the computer has crashed.
2. **CNPG operator detects the failure** (30s `failoverDelay`) — the assistant notices the guard isn't responding.
3. **CNPG promotes `sola-db-2` (on k3s-2) to primary** — the assistant takes over.
4. **Service `sola-db-rw` automatically redirects to `sola-db-2`** — all doors point to the new guard.
5. **App pod on k3s-1 is dead → k3s reschedules it to k3s-2** — Kubernetes determines the first computer is dead and moves the application to the other.
6. **App on k3s-2 connects to `sola-db-rw` (pointing to `sola-db-2`) → continues working** — the system keeps running.

**Total downtime:** ~1–2 minutes (30s failover delay + ~30s for promotion + time for k3s to detect the dead node)

> **Btw:** 1-2 minutes of downtime sounds like a lot, but in practice this is perfectly acceptable for a school system. A teacher who refreshes the page after 2 minutes will be working normally again — no data is lost because Longhorn handled the replication. Compared to the old system (outage for an entire day until IT arrives), this is a huge improvement.

### **Access**

```bash
# Primary database (rw) — where writes go
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL

# Replica (read-only) — for reading only (reports, analytics)
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL_RO
```

### **Service Endpoints (CNPG)**

> **ELI5:** CNPG creates three directories:
> - **sola-db-rw** = "main entrance" — everyone who wants to write or read goes through this entrance. Always points to the primary.
> - **sola-db-ro** = "side entrance" — read-only. Points to the replica (backup database), which offloads the primary.
> - **sola-db-r** = "any entrance" — you can go to primary or replica, whoever is first in line.

CNPG automatically creates three Kubernetes Services for database access:

| Service | Role |
|---|---|
| `sola-db-rw.sola:5432` | **Read-Write** — always on primary (used by the app) |
| `sola-db-ro.sola:5432` | Read-Only — replica only (for reports, analytics) |
| `sola-db-r.sola:5432` | Read — any instance (primary or replica) |

`DATABASE_URL` in the application points to `sola-db-rw` — during failover it automatically redirects to the new primary, the app doesn't know about the change.

---

## 🌐 **MetalLB LoadBalancer**

> **In a nutshell:** MetalLB is the **reception desk** for your Kubernetes cluster — it assigns a public IP ({{LB_IP}}) and directs visitors to the right application, even if the application moves between computers.

> **ELI5 — LoadBalancer:** In a large company you have a reception desk that directs visitors to the right office. **LoadBalancer** is the same thing for applications. When a user arrives at IP {{LB_IP}}, the LoadBalancer checks which copy of the application (Pod) is free and sends them there. If one copy is busy or has crashed, it sends them to the other.
>
> **ELI5 — MetalLB:** MetalLB is one type of LoadBalancer, specialized for places where you don't have a cloud server (AWS, Google Cloud), but have your own computers (on-premise). Unlike an AWS Load Balancer, which you rent from Amazon, MetalLB runs right on your HP ProBooks.

MetalLB is installed in the `metallb-system` namespace. It assigns the external IP {{LB_IP}} to the `sola-app` Service in the `sola-app` namespace.

**Why MetalLB and not Traefik/Ingress?**

k3s has a built-in Traefik ingress controller, but we disabled it (`--disable=traefik`). Reason: Traefik is great for HTTP traffic, but for a very small cluster with 2 nodes, MetalLB + Service LoadBalancer is simpler — fewer moving parts, fewer chances for errors. If the system ever grows to 5+ nodes with multiple applications, then consider an Ingress controller.

---

## ☁️ **Cloudflare DNS**

> **In a nutshell:** Cloudflare is the **internet's phonebook** — when someone enters `{{DOMAIN}}` in a browser, Cloudflare tells them where (at which IP) to find this application, and handles the secure connection (SSL).

> **ELI5 — DNS:** DNS (Domain Name System) is like a phonebook for the internet. You type in a name (`{{DOMAIN}}`), DNS returns a number (IP address). Instead of remembering the number {{LB_IP}}, you remember the name `{{DOMAIN}}`. Much easier, right?
>
> **ELI5 — Cloudflare proxy:** When you enable Cloudflare proxy (orange cloud), Cloudflare doesn't just work as a directory — it also **stands in front of your server as a security guard**. All connections go through Cloudflare, which:
> - Encrypts traffic (SSL) — nobody can eavesdrop.
> - Hides your real IP — hackers don't know exactly where your server is.
> - Blocks DDoS attacks — if someone sends a million requests per second, Cloudflare stops them.

### **DNS Records**

| Type | Name | Value | Proxy |
|---|---|---|---|
| A | `@` ({{DOMAIN}}) | {{LB_IP}} | ✅ Cloudflare proxy (LoadBalancer) |
| A | `www` | {{LB_IP}} | ✅ Cloudflare proxy |

### **SSL/TLS**

Cloudflare handles:

- **Edge certificate** — between the user and Cloudflare (HTTPS). This is the green lock in the browser.
- **Flexible SSL** — Cloudflare → {{LB_IP}} (port 80) via HTTP (no certificate on the origin). This means you have HTTPS on the outside, but within the school network traffic is unencrypted — which is fine in a school network because it is physically protected.

Settings in Cloudflare dashboard:

- **SSL/TLS encryption mode:** `Flexible`
- **Always Use HTTPS:** ON
- **Minimum TLS Version:** 1.2

> **Tip:** Flexible SSL is fine for a school environment, but if you ever add data that requires PCI-DSS or HIPAA compliance, you would need to use Full (strict) SSL with a Let's Encrypt certificate on the origin server. For scheduling reservations and grades at an elementary school, Flexible SSL is perfectly sufficient.

> **Common mistake:** If you set SSL/TLS to "Full" without a certificate on the origin, Cloudflare won't be able to establish a connection and users will get a 502 error. Start with "Flexible" (easiest) and upgrade when you add a certificate to the origin.

---

## 💾 **Longhorn Storage**

> **In a nutshell:** Longhorn is a storage system that ensures every piece of data has 2 copies on 2 different computers — if one disk crashes, no data is lost.

> **ELI5 — Longhorn:** Imagine you have an important school logbook. Longhorn is like a **photocopier that photocopies every page immediately to another desk**. If one desk (computer) goes up in flames, you have the photocopy on the other desk. Without Longhorn, your logbook would only be in one place — if that disk crashes, the data is lost forever.
>
> **ELI5 — PVC (PersistentVolumeClaim):** A PVC is a **virtual hard drive** in Kubernetes. The application says "I need 5GB of storage" and Kubernetes + Longhorn provide it — even if the application moves to another computer, the data stays. It's like having a portable disk that you can plug into any computer.

### **Status**

```bash
kubectl get pvc -n sola-app
kubectl get volumes.longhorn.io -n longhorn-system
```

### **PVCs**

| PVC | Size | Access Mode | Usage |
|---|---|---|---|
| `sola-postgresql` | 5Gi | RWO | PG data |
| `sola-postgresql-wal` | 2Gi | RWO | WAL logs |

**PVC explanation for non-technical readers:**

| PVC | What it stores | Why it matters |
|---|---|---|
| `sola-postgresql` (5Gi) | **PG database data** — all tables, indexes, users, reservations, assessments. This is the "main" PVC. | Without this, there is no database. 5Gi is enough for an entire school year. |
| `sola-postgresql-wal` (2Gi) | **Write-Ahead Logs (WAL)** — a journal of every change, written before it is saved to the data files. | Without WAL, the replica cannot keep up with the primary. Used for crash recovery, streaming replication, and point-in-time recovery. |

> **ELI5 — PV (PersistentVolume):** In Kubernetes there are two concepts:
> - **PV** = **actual physical disk** — real storage space on one of the computers.
> - **PVC** = **request** for that disk — the application says "I need 5GB".
>
> In a course you probably created PVs manually (`hostPath` or `nfs`) to have somewhere to store data.
> Here, you **don't create PVs manually** — **Longhorn does it for you**.
> When you create a PVC (e.g. `sola-postgresql`), Longhorn behind the scenes:
> 1. Creates a PV on one node's disk
> 2. Creates a replica on the other node
> 3. Binds the PVC to that PV
>
> You can check with `kubectl get pv` — you'll see PVs with names like `pvc-...`, all created by Longhorn.

> **ELI5 — WAL (Write-Ahead Log):** Imagine you are writing a test. First you write the answer on a **scratch sheet (WAL)**

**Why two separate PVCs?** PostgreSQL first writes every change to WAL, then to the main data files. Separate PVCs allow different I/O profiles — WAL is sequential writing (fast), data is random read-write access. It also enables separate backup strategies: WAL is archived continuously, data is snapshotted periodically.

**Longhorn replication** (2 copies) ensures data survives the loss of one node. Both PVCs have two replicas — one on each k3s node.

> **Btw:** 5Gi for data and 2Gi for WAL sounds small, but for a school system with a few hundred users and reservations, it's more than enough. PostgreSQL is surprisingly efficient with space — the entire database for a year of work will likely be under 1GB. If you ever get close to the limit, monitor with `kubectl get pvc` and increase the size — Longhorn supports online resize without downtime.

---

## 📅 **Daily Backup and Reports**

> **In a nutshell:** Every night at 4:00 AM, the system automatically sends a database backup to `BACKUP_EMAIL` and a daily status report to `STANJE_MAIL` (both variables in the Kubernetes Secret, currently both set to the same address). Nothing is sent to Discord automatically — Discord is only used when you explicitly ask Hermes Agent for something.

> **ELI5:** Imagine you have a **night guard** who every morning at 4:00:
> 1. **Photocopies the entire school register** and puts it in your mailbox (email).
> 2. **Checks if all computers are running** and sends a report to your email.
>
> He leaves the Discord (school chat) alone, unless you call him: "Hey, what's up with the server?" — then he answers right in the chat. Think of him as a **silent assistant who doesn't disturb until you call**.

### **Daily database backup (`sola-db-backup`)**

```bash
# Cron: 04:00 every day (Europe/Ljubljana)
# Sends a full pg_dump of the database to BACKUP_EMAIL
kubectl get cronjob -n sola-app sola-db-backup
```

Creates a complete snapshot of the database (all tables, users, reservations, assessments) and emails it. If data gets lost (disk failure, accidental deletion), you have the backup from last night in your email.

### **Daily status report (`sola-daily-report`)**

```bash
# Cron: 04:00 every day (Europe/Ljubljana)
# Sends a report on node status, Longhorn replicas, and application health to STANJE_MAIL
kubectl get cronjob -n sola-app sola-daily-report
```

The report includes:

- 📊 **Node status** — whether both servers are alive
- 💾 **Longhorn replica status** — whether data is properly replicated
- 🟢 **Application health** — whether everything is running
- ⚠️ **Errors** — any issues found

> **Tip:** Email backup is **reliable and simple** — no extra tools needed, everyone knows how to open email. But email can end up in spam. So once a week also check `kubectl get events -n sola-app --sort-by='.lastTimestamp'` — there you'll see things the email report might not show (OOMKilled, CrashLoopBackOff, failed volume mounts).
>
> **What do these errors mean?**
>
> | Error | Meaning | In practice |
> |-------|---------|-------------|
> | **OOMKilled** | Out Of Memory — the app **ran out of RAM**, Kubernetes killed it | The app is using more memory than allocated (e.g., 128 MB instead of 256 MB). Fix by increasing the `memory` limit in the Deployment YAML. |
> | **CrashLoopBackOff** | The app **keeps crashing and restarting** — it fails quickly every time, Kubernetes keeps trying to restart it | Like a computer that shuts down right after you turn it on. The cause is almost always a code error or wrong config. Check logs: `kubectl logs -n sola-app <pod-name>` |
> | **Failed volume mounts** | The app can't **attach its disk** — Longhorn didn't find the disk or it's broken | Like trying to open a folder on a drive that's unplugged. Check with `kubectl get pv,pvc -n sola-app` and `kubectl get volumes.longhorn.io -n longhorn-system`. |

---

## 🔧 **Maintenance and Failures**

> **In a nutshell:** Most issues can be solved with a single `kubectl get ...` command — see what's not working, and the system handles the rest.

### **Daily Operations**

> **ELI5:** These are your **morning checks**, like before driving a car — check the oil, tire pressure, lights. Here you check whether all computers in the cluster are alive, whether applications are running, whether disks aren't full.

```bash
# Check node status — are all computers alive?
kubectl get nodes -o wide

# Check pods in sola-app — are applications running?
kubectl get pods -n sola-app -o wide

# Check Longhorn status — are disks OK?
kubectl get volumes.longhorn.io -n longhorn-system

# Check CloudNativePG — is the database working?
kubectl get cluster -n sola-app
```

### **When a Node Fails**

> **ELI5:** If one of the computers crashes, an **automatic guard change** happens. Don't panic — the system is designed to survive the failure of one computer. Wait a minute, check, fix the failed computer when you have time.

1. **The remaining node takes over** — the app pod moves, PG failover happens automatically
2. **Wait a minute** — CNPG failover (30s delay + promotion) and Longhorn reconfigure
3. **Check** — `kubectl get pods -n sola-app -o wide`
4. **Fix** the failed node as needed (replace disk, fix power, reinstall k3s)

### **Full Shutdown (Summer Break)**

See [🌞 Summer Shutdown](../POLETNA_PAVZA.md).

> **Btw:** The summer shutdown is often overlooked, but it is crucial for the longevity of the hardware. HP ProBooks in a cabinet without cooling can easily reach 50°C at idle during summer. Shutting down for 2 months extends the life of disks and batteries. Before shutdown, **mandatorily** take a snapshot of Longhorn volumes and dump the database — "better to have it and not need it, than need it and not have it."

---

## 📋 **Complete Command Reference**

```bash
# === Status ===
kubectl get nodes -o wide                           # Which computers are in the cluster?
kubectl get pods -n sola-app -o wide                # Which applications are running and where?
kubectl get services -n sola-app                    # Which services are available?
kubectl get pvc -n sola-app                         # How much disk space is used?
kubectl get cluster -n sola-app                     # How is the database doing?
kubectl get events -n sola-app --sort-by='.lastTimestamp'  # What happened recently?

# === App Management ===
kubectl rollout restart deployment -n sola-app sola-app          # Zero-downtime restart
kubectl rollout status deployment -n sola-app sola-app           # Monitor update
kubectl logs -n sola-app deployment/sola-app --tail=50           # Last 50 log lines
kubectl logs -n sola-app deployment/sola-app --previous          # Log of the previous (failed) Pod
kubectl exec -it -n sola-app deploy/sola-app -- /bin/sh          # Connect to container terminal (shell)

# === Database Management ===
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL                    # Connect to database
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL -c "SELECT * FROM users;"  # Run a query

# === Longhorn ===
kubectl get volumes.longhorn.io -n longhorn-system               # Disk status
kubectl get engineimages.longhorn.io -n longhorn-system           # Longhorn engine version
kubectl get nodes.longhorn.io -n longhorn-system                  # Longhorn status on each node

# === Git (on k3s-2) ===
cd /home/admin/reservation_app
git pull                                    # Pull the latest code
```

---

## 📖 **Glossary**

*Explanation of technical terms for non-technical readers — if something in the documentation isn't clear, look here.*
*💡 **ELI5** = *Explain Like I'm 5* — means the explanation is written as simply as possible, without professional jargon.*

| Term | Explanation |
|---|---|
| **Arnes** | **Academic Research Network Infrastructure of Slovenia** — Slovenian educational internet. The school is connected to the internet via Arnes. |
| **Cloudflare** | **Security guard in front of your server** — encrypts traffic (SSL), hides your IP, blocks attacks, speeds up loading. |
| **CloudNativePG (CNPG)** | **Smart assistant for PostgreSQL database** — automatically manages replication, failover, backup, and recovery. |
| **Cluster** | **A group of computers working as one** — two HP ProBooks connected into the same Kubernetes cluster. Kubernetes ensures applications run on whichever computer is available. |
| **ConfigMap / Secret** | **Kubernetes objects for storing settings** — ConfigMap for public settings (e.g. BASE_URL), Secret for sensitive data (passwords, keys). Secret is encoded, ConfigMap is readable. |
| **Control-plane** | **The "brain" of the cluster** — the control part that makes all decisions. Both HP ProBooks have control-plane, meaning we have two "brains" — if one crashes, the other takes over. |
| **Discord webhook** | **Automatic message sending to Discord** — used for communication with Hermes Agent: you say something, Hermes replies. No automatic notifications (nightly report, backup) — everything goes via email. |
| **DNS** | **Internet phonebook** — converts the name `{{DOMAIN}}` into an IP address {{LB_IP}} (for example). |
| **Docker Image** | **Recipe for an application** — contains the program, libraries, settings. From one recipe you can make multiple identical containers (Pods). |
| **ELI5** | *Explain Like I'm 5* — an explanation style where you avoid technical terms and use everyday analogies. E.g. Kubernetes is not "a container orchestration system" but "an orchestra conductor for applications." |
| **etcd** | **The cluster's memory book** — stores all data about what runs where, what the settings are, who is alive and who is dead. It is the brain of Kubernetes. |
| **Failover** | **Automatic guard change** — when the primary system crashes, the backup automatically takes over its role. In our case, CNPG promotes the replica to primary. |
| **FastAPI** | **Framework for web applications in Python** — sola-app is written in it. Fast, modern, supports automatic documentation. |
| **Git** | **System for tracking code changes** — like "Track Changes" in Word, but for program code. |
| **GitHub Actions** | **Automatic testing and building with every change** — when someone uploads new code to GitHub, a new Docker Image is automatically built. |
| **Helm** | **"App Store" for Kubernetes** — a tool for installing ready-made packages (e.g. Longhorn, CNPG) into Kubernetes. Instead of manually writing YAML, you just say "install Longhorn." |
| **HPA (HorizontalPodAutoscaler)** | **Automatic scaling of application copies** — monitors CPU/RAM usage and adds or removes replicas (1-3) based on load. Like a coffee machine at school — when it's busy, another one turns on. |
| **HTTPS** | **Secure web connection** — HTTP + SSL. A green lock in the browser means the connection is secure. |
| **k3s** | **Lightweight version of Kubernetes** — specifically made for smaller computers and IoT devices. We use it on HP ProBooks because full Kubernetes is too heavy for laptops. The same `kubectl` commands work for both. |
| **Kubernetes (k8s)** | **Orchestra conductor for applications** — a system that automatically manages where and how your applications run. If one crashes, it automatically starts it elsewhere. |
| **LoadBalancer** | **Reception desk in a building** — directs visitors (users) to the right application. In our case, MetalLB at IP {{LB_IP}}. |
| **Longhorn** | **A system that ensures you have 2 copies of data on 2 different computers** — distributed storage for Kubernetes, made for smaller clusters. |
| **MetalLB** | **LoadBalancer for on-premise environments** — an alternative to cloud LoadBalancers (AWS, Google). Runs right on your computers. |
| **Node** | **Physical computer in the cluster** — in our case k3s-1 (HP ProBook 455 G5) and k3s-2 (HP ProBook 450 G5). |
| **Pod** | **Container with an application** — the smallest unit in Kubernetes. Each pod runs separately: one for the app itself (`sola-app`), another for the database (`sola-db`). Each pod has its own private IP address. |
| **Primary (database)** | **Main database** — the only one that can be written to. All changes go through it. |
| **PVC (PersistentVolumeClaim)** | **Virtual hard drive** — a request for disk space in Kubernetes. Data persists even if the application moves to another computer. |
| **Replica** | **A copy that vigilantly watches the original** — a second database that constantly copies all changes from the primary. Ready to take over if the original crashes. |
| **Replica (database)** | **Backup database** — read-only. Constantly copies changes from the primary. If the primary crashes, it becomes the new primary. |
| **SSH** | **Secure access to a remote computer via command line** — like sitting in front of that computer, even though you're in a different room. |
| **SSL/TLS** | **Encrypted connection (lock in the browser)** — ensures nobody can eavesdrop on the communication between the user and the server. |
| **Uvicorn** | **Server that runs the FastAPI application** — reads Python code and serves it as a web page. Like a waiter who carries food (responses) to customers. |
| **WAL (Write-Ahead Log)** | **Journal of changes before they are written** — PostgreSQL writes every change first to WAL, then to the main data files. This enables crash recovery and replication. |
| **YAML** | **Human-readable format for writing configuration** — similar to JSON, but more readable. In Kubernetes, all settings are written in YAML format. |
| **Zero-downtime (rollout)** | **Update without service interruption** — Kubernetes first starts the new version, waits for it to work, only then shuts down the old one. Users don't notice anything. |

---

*Documentation for ostc-app — OŠ Toneta Čufarja Jesenice*
*Last updated: 27 June 2026*
