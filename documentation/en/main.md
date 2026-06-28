🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../main.md) | [🇬🇧 English](main.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses and other sensitive data in this
> documentation have been replaced with examples. For actual values, check Kubernetes
> Secrets or contact the administrator.

---

> 🛠️ **Customize documentation with your IPs**
>
> All documentation uses a central `.env.ip` file where
> all IP addresses, ports, and domains are defined. Want documentation with your own data?
>
> ```bash
> cd documentation
> nano .env.ip                          # enter your own IPs
> ./replace-ips.sh                      # documentation adapts to your setup
> ```
>
> The script replaces all IPs in `.md` files. After running it, you can directly copy
> and paste commands into the terminal — they will work without modification.
>
> > 💡 **Note:** Placeholders ({{LB_IP}}, {{K3S_1_IP}}, etc.) remain in `.drawio` diagrams as well — the `replace-ips.sh` script leaves them untouched since they are part of the images.

---

# 🚀 **ostc-app — Reservation System**
## **OŠ Toneta Čufarja — Documentation**

---

## 📚 **Documentation Index**

This file is the **main entry document** — like the reception desk at school, telling you where to find what. Below are links to specialized sub-documents:

| Document | Description |
|---|---|
| [🏗️ **HA Architecture**](HA.md) | CloudNativePG, automatic failover, procedure when a node goes down |
| [🌞 **Summer Break**](POLETNA_PAVZA.md) | Safe shutdown of the k3s cluster over summer and restart in autumn |
| [☁️ **Domain and DNS**](domena.md) | Domain setup, Cloudflare, DNS records |
| [🐍 **Run the app locally**](postavi-lokalni-app.md) | Installation on a single machine (without Kubernetes) |
| [☸️ **K3s setup**](k3s-setup.md) | Installing the k3s cluster from scratch |
| [⚙️ **Admin/devops instructions**](admin-devops-navodila.md) | Maintenance, updates, troubleshooting |
| [👩‍🏫 **Instructions for teachers**](navodila-ucitelji.md) | Using the application — reservations and assessments |
| [👑 **Instructions for management**](navodila-vodstvo.md) | Browser-based management (series, blocked dates) |
| [📱 **Application description**](aplikacija-rezervacije.md) | What the application offers, purpose, features |
| [📖 **User instructions**](navodila-uporabnika.md) | Login, passwords, daily use |

---

## 📑 **Table of Contents** (this document)

1. [System Architecture](#system-architecture)
2. [Hardware and Network](#hardware-and-network)
3. [Kubernetes (k3s) Cluster](#kubernetes-k3s-cluster)
4. [Sola App Application](#sola-app-application)
5. [PostgreSQL HA — CloudNativePG](#postgresql-ha-cloudnativepg)
6. [MetalLB LoadBalancer](#metallb-loadbalancer)
7. [Cloudflare DNS](#cloudflare-dns)
8. [Longhorn Storage](#longhorn-storage)
9. [Daily Backup and Reports](#daily-backup-and-reports)
10. [Maintenance and Failures](#maintenance-and-failures)
11. [Complete Command Reference](#complete-command-reference)
12. [📖 Glossary](#glossary)

---

## 🏗️ **System Architecture**

> **In one sentence:** Two laptops (HP ProBook) work as a team — if one fails, the other seamlessly takes over everything the first was doing.

### **How to picture the entire system? (for non-technical readers)**

Imagine your school has two **reception desks**. At each desk sits an employee (this is a **Pod** — a container with the application) who welcomes visitors (users who want to book a time slot). Both employees do the same job — if one is absent, the other keeps working. Behind them are **file cabinets with student records (the database)**, in two copies — if one catches fire, you have a backup. The entire show is conducted by a **conductor (Kubernetes)**, making sure all containers work in harmony.

Below is the technical diagram, followed by an explanation.

> **Simple explanation of the diagram below:**
> - Two computers (k3s-1 and k3s-2) are connected in a cluster — like two desks in the same office.
> - Each computer runs **one copy of the application (sola-app Pod)** and **one copy of the database (sola-db)**.
> - The database has one **boss (PRIMARY)** and one **assistant (REPLICA)**, who constantly copies everything the boss does.
> - All data is stored in **Longhorn** — a system that ensures you have 2 copies on 2 different computers, so even if one computer fails, data is not lost.
> - When a user opens a browser, traffic goes through **Cloudflare** (security filter + SSL) to **MetalLB LoadBalancer** (the reception desk), which sends it to one of the two application copies.

### **Hardware and Network Diagram**

![Full k3s architecture — 2 nodes, app pods, database, LoadBalancer, Cloudflare](diagrams/arhitektura-clustra.png)


> **Note:** Both nodes are `control-plane, etcd` — there are no separate worker nodes. k3s runs user pods on control-plane nodes too. This is perfectly fine for a smaller cluster — with 100+ nodes you would separate them, but for a school system with two HP ProBooks this is perfectly okay (plus HA is much easier this way).

> **From experience:** Both HP ProBooks have the `control-plane` role because k3s allows this without any issues. In large companies (Google, Amazon) they have separate control-plane nodes, but that's for thousands of nodes. For a school cluster this is perfectly fine — you save on hardware and simplify the setup.

### **Traffic Flow**

> **Simple explanation:** When a teacher types `https://ostc-app.org` into their browser, here's what happens: the browser first asks Cloudflare (the internet's phone book) where this site is. Cloudflare looks up its directory, sees IP {{LB_IP}}, and sends the user there. There, **MetalLB** (the reception desk) greets them and redirects them to one of the two application copies — whichever is currently available.

![Traffic flow: user → Cloudflare → LoadBalancer → app pod](diagrams/prometni-tok.png)


> **Cloudflare proxy** points directly to **LoadBalancer (`{{LB_IP}}`, port 80)** — traffic goes directly to MetalLB, HA works automatically — if one node fails, MetalLB moves the IP to the other.

> **Pro Tip:** Always use Cloudflare proxy (orange cloud) — not just DNS-only (gray cloud). Proxy gives you free SSL, DDoS protection, and hides your real IP from hackers. If you use DNS-only, your IP {{LB_IP}} is publicly exposed and anyone can attack it directly.

### **Component Overview**

|  | Component | Location | Purpose |
|---|---|---|---|
| | **k3s-1** | HP ProBook 455 G5 ({{K3S_1_IP}}) | Control-plane, app pod, PG primary (main computer) |
| | **k3s-2** | HP ProBook 450 G5 ({{K3S_2_IP}}) | Control-plane, app pod, PG replica (backup computer) |
| | **Sola App (FastAPI)** | 2 pods (both nodes) | Reservations, assessments, login |
| | **Longhorn** | Both nodes | Distributed storage (PVCs) — data in 2 copies |
| | **MetalLB** | Both nodes | LoadBalancer IP ({{LB_IP}}) — the front door |
| | **Cloudflare** | External | DNS, SSL, proxy — internet security |

---

## 💻 **Hardware and Network**

> **In one sentence:** Two ordinary HP ProBook laptops, each with a 256 GB disk, connected to the school's Arnes network — that's all you need for the entire system.

### **Specifications**

> **ELI5:** Imagine you have two office computers. The first one (k3s-1) has 16 GB RAM — it's like a bigger desk where you can put more papers. The second one (k3s-2) has 8 GB RAM — a smaller desk, but still enough for routine work.

| Node | Model | CPU | RAM | Disk | Role |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Control-plane, etcd, app, PG primary (main) |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Control-plane, etcd, app, PG replica (backup) |

> **From experience:** k3s-1 has 16 GB of RAM, while k3s-2 has 8 GB of RAM. This is not a mistake — the primary database (PG primary) on k3s-1 needs more RAM for cache and WAL buffers. When k3s-2 becomes primary (during failover), it will run a bit slower, but the system will still work. If the budget ever allows, add another 8 GB of RAM to k3s-2.

### **Network Settings**

> **ELI5:** Each computer on the network has its own house address (IP). k3s-1 is at address {{K3S_1_IP}}, and k3s-2 is at {{K3S_2_IP}}. Together with other devices at the school they form a neighborhood (/24 means up to 254 devices can be in the same neighborhood). The Gateway ({{GATEWAY_IP}}) is the school's main door through which all traffic goes to the internet.

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

> **Common mistake:** The Pod CIDR (10.42.0.0/16) and Service CIDR (10.43.0.0/16) must NOT overlap with the local network ({{K3S_1_IP}}/24). If they do, Kubernetes won't be able to route traffic properly. Always check with `ip route` on the nodes before setting up k3s.

### **Access**

```bash
# SSH into both nodes
ssh {{SSH_USER}}@{{K3S_1_IP}}    # k3s-1
ssh {{SSH_USER}}@{{K3S_2_IP}}    # k3s-2

# Kubernetes (k3s) — kubeconfig is on both nodes
kubectl get nodes -o wide
kubectl get pods -A -o wide

# Application in browser
https://ostc-app.org          # via Cloudflare + LoadBalancer (recommended)
http://{{LB_IP}}:{{LB_PORT}}     # directly (internal network only, no SSL)
```

---

## ☸️ **Kubernetes (k3s) Cluster**

> **In one sentence:** k3s is a lightweight version of Kubernetes (the conductor for applications) that runs on both HP ProBooks and ensures the application always works — even if one computer fails.

> **ELI5 — Kubernetes/k3s:** Imagine an orchestra. Each musician is one application (Pod). **Kubernetes** is the **conductor** — he decides who plays what, when to play, and what to do if someone is late or sick. **k3s** is the same thing, but lighter — like having a smaller orchestra that doesn't need a huge concert hall. On an HP ProBook laptop, k3s works great, while full Kubernetes (k8s) would be too heavy.

### **Node Status**

> **ELI5:** `kubectl get nodes` is like taking attendance in class — it shows which computers are in the cluster and whether they're ready to work.

```bash
kubectl get nodes -o wide

# NAME    STATUS   ROLES                       AGE   VERSION        INTERNAL-IP      EXTERNAL-IP
# k3s-1   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_1_IP}}    <none>
# k3s-2   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_2_IP}}    <none>
```

### **Installing k3s**

> **Simple explanation:** On the first computer (k3s-1) you start k3s with `--cluster-init` — this means "create a new cluster." On the second (k3s-2) you join the existing cluster with `--server https://{{K3S_1_IP}}:6443` — this is like saying "please connect me to the boss at this address."

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

Token can be obtained with: `sudo cat /var/lib/rancher/k3s/server/node-token` (on k3s-1).

> **Note:** `--disable=traefik` disables the built-in ingress because we use MetalLB LoadBalancer. If we left Traefik enabled, we'd have two systems competing for the same port — confusion we avoided.

> **Pro Tip:** Always add `--flannel-iface=eth0`. Why? Because a laptop often has multiple network interfaces — one for WiFi (e.g. `wlan0`) and one for the ethernet cable (`eth0`). Flannel (Kubernetes' networking system) doesn't know which one to use. If it chooses WiFi, which is slow or unstable, the cluster won't work. With `--flannel-iface=eth0` you tell it: "use the ethernet cable, not WiFi." Check what your network interfaces are called with the `ip a` command on each computer.

---

## 🚀 **Sola App Application**

> **In one sentence:** A web application (FastAPI + HTML) running in two copies on both computers — if one fails, the other seamlessly takes over.

> **ELI5:** Imagine a **paper list** on a bulletin board where teachers sign up for gym or classroom reservations. With paper, what you write stays. If you make a mistake, you can only cross it out (messy and hard to read) or take a new sheet. The application is like **the same list, but digital** — you can add a reservation, **change it anytime** or **delete it** with one click, everything stays clean and organized. No crossing out, no new sheets, no smudging.
> And because it's digital, you can run it in **two copies (Pods)** on two computers. Like having two identical bulletin boards in the hallway — if someone damages or removes one, the other is still there and teachers can reserve normally. Teachers (users) don't even notice — they just open the app and keep working.

### **Deployment**

Namespace: `sola-app`

```bash
kubectl get deployments -n sola-app
kubectl get pods -n sola-app -o wide
kubectl get services -n sola-app
```

The application runs in **1-3 pods**, depending on load. **HorizontalPodAutoscaler (HPA)** automatically adjusts the count:

| Load | Replicas | When |
|-------------|--------|------|
| 🟢 Low (afternoon, weekend, holidays) | **1** — one node works, the other rests |
| 🟡 Normal (school time, reservations) | **2** — one copy on each node |
| 🔴 High (assessments, start of year) | **3** — both nodes together handle 3 copies |

> **ELI5 — HPA:** Like a coffee machine at school — when there are few people, one works. When lunch break comes, a second and third automatically turn on. When the crowd thins out, the extras turn off. HPA does the same for the application.

```bash
kubectl get hpa -n sola-app
# NAME            REFERENCE              TARGETS              MIN   MAX   REPLICAS
# sola-app-hpa    Deployment/sola-app    45%/60% CPU           1     3     2
#                                        60%/70% MEM
#
```
```bash
kubectl get pods -n sola-app -o wide

# NAME                        READY   STATUS    RESTARTS   AGE   IP           NODE
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.0.x    k3s-1
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.1.x    k3s-2
```

### **Docker Image**

> **ELI5 — Docker Image:** It's like a **recipe for a cake**. You use the same recipe to bake two cakes (two Pods) in two different places. Each cake is identical — the same program, the same settings, the same code. The Dockerfile contains this recipe.

- **Image:** `sola-app:latest`
- **Dockerfile:** `reservation_app/k8s/Dockerfile`
- **Deployment YAML:** `reservation_app/k8s/sola-app.yaml`

### **Updating the Application**

> **ELI5 — rollout restart:** When you want to update the application, you don't need to shut down the server. Kubernetes does it **without interruption (zero-downtime)** — it first starts a new Pod, waits for it to be ready, and only then shuts down the old one. Like changing tires on a moving car — you replace them one by one, the car keeps driving the whole time.

```bash
cd reservation_app
git pull
# Wait for the CI build to finish (GitHub Actions)
# or manually:
kubectl rollout restart deployment -n sola-app sola-app
kubectl rollout status deployment -n sola-app sola-app
```

> **Pro Tip:** Never delete old Pods manually. Use `rollout restart`. Kubernetes itself ensures at least one Pod is always active. If you delete both at once, you get downtime. `rollout status` tells you when the update is complete — don't guess, wait for the "rollout successfully rolled out" message.

---

## 🗄️ **PostgreSQL HA — CloudNativePG**

> **In one sentence:** The database (PostgreSQL) runs in a high-availability configuration — one primary on k3s-1 and one replica on k3s-2, with CloudNativePG automatically handling the switchover if the primary fails.

> **ELI5 — PostgreSQL:** The database is like a **school folder with all reservations and assessments**. Its purpose is to store data.
>
> **ELI5 — HA (High Availability):** High availability means you have **two folders** — one original (primary) and one photocopy (replica). Every time you write something in the original, the photocopy gets it immediately. If the original burns (fails), you take the photocopy and continue where you left off.
>
> **ELI5 — CloudNativePG (CNPG):** This is a **smart assistant** that watches over both folders. If it notices the original has failed, it automatically says "photocopy, you're the boss now!" and redirects all users to the photocopy. All without human intervention.

### **Status**

```bash
kubectl get pods -n sola-app -o wide | grep db

# NAME                    READY   STATUS    IP            NODE
# sola-db-1 (primary)     1/1     Running   10.42.0.x     k3s-1
# sola-db-2 (replica)     1/1     Running   10.42.1.x     k3s-2
```

Built with the **CloudNativePG** operator. Primary always on k3s-1, replica on k3s-2.

### **Failover**

> **ELI5 — Failover:** Failover is an **automatic guard change**. Imagine two guards. The first one (primary) stands at the door. The second (replica) sits in the office and constantly watches what the first one does (copying the logbook). If the first one faints, the second immediately jumps to the door and continues as if nothing happened — visitors (users) don't even notice.

When k3s-1 goes down:

1. **Primary pod `sola-db-1` becomes unreachable** — the computer has failed.
2. **CNPG operator detects the failure** (30s `failoverDelay`) — the assistant notices the guard is not responding.
3. **CNPG promotes `sola-db-2` (on k3s-2) to primary** — the assistant takes over.
4. **Service `sola-db-rw` automatically redirects to `sola-db-2`** — all doors are redirected to the new guard.
5. **App pod on k3s-1 is dead → k3s reschedules it to k3s-2** — Kubernetes realizes the first computer is dead and moves the application to the other.
6. **App on k3s-2 connects to `sola-db-rw` (which now points to `sola-db-2`) → keeps working** — the system continues running.

**Total downtime:** ~1–2 minutes (30s failover delay + ~30s for promotion + time for k3s to detect the dead node)

> **From experience:** 1-2 minutes of downtime sounds like a lot, but in practice it's perfectly acceptable for a school system. A teacher who refreshes the page after 2 minutes will be working normally again — no data is lost because Longhorn handled replication. Compared to the old system (downtime for a whole day until IT arrives), this is a huge improvement.

### **Access**

```bash
# Primary database (rw) — where writes go
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL

# Replica (read-only) — only for reading (reports, analytics)
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL_RO
```

### **Service Endpoints (CNPG)**

> **ELI5:** CNPG creates three directories:
> - **sola-db-rw** = "main entrance" — anyone who wants to write or read goes through this entrance. Always points to primary.
> - **sola-db-ro** = "side entrance" — read-only. Points to the replica (backup database), which offloads the primary.
> - **sola-db-r** = "any entrance" — you can go to primary or replica, whoever is available first.

CNPG automatically creates three Kubernetes Services for database access:

| Service | Role |
|---|---|
| `sola-db-rw.sola:5432` | **Read-Write** — always on primary (used by the app) |
| `sola-db-ro.sola:5432` | Read-Only — replica only (for reports, analytics) |
| `sola-db-r.sola:5432` | Read — any instance (primary or replica) |

`DATABASE_URL` in the application points to `sola-db-rw` — on failover it automatically redirects to the new primary, the app doesn't know about the change.

---

## 🌐 **MetalLB LoadBalancer**

> **In one sentence:** MetalLB is the **reception desk** for your Kubernetes cluster — it assigns a public IP ({{LB_IP}}) and routes visitors to the right application, even if the application moves between computers.

> **ELI5 — LoadBalancer:** In a large company, there's a reception desk that directs visitors to the right office. A **LoadBalancer** is the same thing for applications. When a user arrives at IP {{LB_IP}}, the LoadBalancer checks which copy of the application (Pod) is free and sends them there. If one copy is busy or down, it sends them to the other.
>
> **ELI5 — MetalLB:** MetalLB is one type of LoadBalancer, specialized for places where you don't have a cloud server (AWS, Google Cloud), but have your own computers (on-premise). Unlike an AWS Load Balancer, which you rent from Amazon, MetalLB runs right on your HP ProBooks.

MetalLB is installed in the `metallb-system` namespace. It assigns the external IP {{LB_IP}} to the `sola-app` Service in the `sola-app` namespace.

**Why MetalLB and not Traefik/Ingress?**

k3s has a built-in Traefik ingress controller, but we disabled it (`--disable=traefik`). Reason: Traefik is excellent for HTTP traffic, but for a very small cluster with 2 nodes, MetalLB + Service LoadBalancer is simpler — fewer moving parts, fewer chances for errors. If the system ever grows to 5+ nodes with multiple applications, then consider an Ingress controller.

---

## ☁️ **Cloudflare DNS**

> **In one sentence:** Cloudflare is the **internet's phone book** — when someone types `ostc-app.org` into their browser, Cloudflare tells them where (on which IP) to find the application, and handles the secure connection (SSL).

> **ELI5 — DNS:** DNS (Domain Name System) is like a phone book for the internet. You type in a name (`ostc-app.org`), DNS returns a number (IP address). Instead of remembering the number {{LB_IP}}, you remember the name `ostc-app.org`. Much easier, right?
>
> **ELI5 — Cloudflare proxy:** When you enable Cloudflare proxy (orange cloud), Cloudflare doesn't just act as a directory — it also **stands in front of your server as a security guard**. All connections go through Cloudflare, which:
> - Encrypts traffic (SSL) — nobody can eavesdrop.
> - Hides your real IP — hackers don't know exactly where your server is.
> - Blocks DDoS attacks — if someone sends a million requests per second, Cloudflare stops them.

### **DNS Records**

| Type | Name | Value | Proxy |
|---|---|---|---|
| A | `@` (ostc-app.org) | {{LB_IP}} | ✅ Cloudflare proxy (LoadBalancer) |
| A | `www` | {{LB_IP}} | ✅ Cloudflare proxy |

### **SSL/TLS**

Cloudflare handles:

- **Edge certificate** — between the user and Cloudflare (HTTPS). That's the green lock in the browser.
- **Flexible SSL** — Cloudflare → {{LB_IP}} (port 80) via HTTP (no certificate on the origin). This means you have HTTPS on the outside, but inside the school network traffic goes unencrypted — which is fine in the school network since it's physically protected.

Settings in the Cloudflare dashboard:

- **SSL/TLS encryption mode:** `Flexible`
- **Always Use HTTPS:** ON
- **Minimum TLS Version:** 1.2

> **Pro Tip:** Flexible SSL is fine for a school environment, but if you ever add data requiring PCI-DSS or HIPAA compliance, you would need to use Full (strict) SSL with a Let's Encrypt certificate on the origin server. For booking time slots and assessments at an elementary school, Flexible SSL is perfectly sufficient.

> **Common mistake:** If you set SSL/TLS to "Full" without a certificate on the origin, Cloudflare won't be able to establish a connection and users will get a 502 error. Start with "Flexible" (easiest) and upgrade when you add a certificate to the origin.

---

## 💾 **Longhorn Storage**

> **In one sentence:** Longhorn is a storage system that ensures every piece of data has 2 copies on 2 different computers — if one disk fails, data is not lost.

> **ELI5 — Longhorn:** Imagine you have an important school logbook. Longhorn is like a **photocopier that photocopies every page immediately after you write it, onto another desk**. If one desk (computer) catches fire, you have the photocopy on the other desk. Without Longhorn, your logbook would only be in one place — if that disk fails, the data is lost forever.
>
> **ELI5 — PVC (PersistentVolumeClaim):** A PVC is a **virtual hard drive** in Kubernetes. The application says "I need 5 GB of storage space" and Kubernetes + Longhorn provide it — even if the application moves to another computer, the data stays. It's like having a portable drive that you can plug into any computer.

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

**Explanation of PVCs for non-technical readers:**

| PVC | What it stores | Why it's important |
|---|---|---|
| `sola-postgresql` (5Gi) | **PG database data** — all tables, indexes, users, reservations, assessments. This is the "main" PVC. | Without it, there is no database. 5Gi is enough for the entire school year. |
| `sola-postgresql-wal` (2Gi) | **Write-Ahead Logs (WAL)** — a log of every change before it is written to the data files. | Without WAL, the replica cannot keep up with the primary. Used for crash recovery, streaming replication, and point-in-time recovery. |

> **ELI5 — WAL (Write-Ahead Log):** Imagine you're writing a test. First, you write the answer on a **scratch pad (WAL)**, and only then do you copy it into the **clean folder (main data)**. If you get interrupted while writing, you still have the scratch pad from which you can recover what you wanted to write. WAL is that scratch pad — a log of changes before they get written to the main database.

**Why two separate PVCs?** PostgreSQL first writes every change to the WAL, then to the main data files. Separate PVCs allow for different I/O profiles — WAL is sequential writes (fast), data is random read-write access. It also enables separate backup strategies: WAL is archived continuously, data is snapshotted periodically.

**Longhorn replication** (2 copies) ensures that even if one node is lost, data remains. Both PVCs have two replicas — each on a different k3s node.

> **From experience:** 5 Gi for data and 2 Gi for WAL sounds small, but for a school system with a few hundred users and reservations, it's more than enough. PostgreSQL is surprisingly efficient with space — the entire database for a year of work will likely be under 1 GB. If you ever get close to the limit, monitor with `kubectl get pvc` and increase the size — Longhorn supports online resize without downtime.

---

## 📅 **Daily Backup and Reports**

> **In one sentence:** Every night at 4:00 AM, the system automatically sends a summary to Discord — the number of reservations, logged-in users, and any errors.

> **ELI5:** Imagine you have a **night guard** who checks the entire school at 4:00 AM every morning and writes a report: "Today there are 150 students in the school, 45 reservations, everything is working." He sends this report to Discord (the school chat). This way, you know the system is working before you even come to work.

### **Daily App Report**

```bash
# Cron: 04:00 every day (Europe/Ljubljana)
# Sends a summary to Discord — number of reservations, logged-in users, etc.
kubectl logs -n sola-app job/sola-report
```

It updates **automatically** via a Hermes cron job. The report includes:

- Number of active reservations
- Number of logged-in users
- Assessment status
- Any errors

> **Pro Tip:** A Discord webhook is great for alerting in a school environment — free, simple, everyone has it on their phone. But don't trust it 100%. Once a week, also check `kubectl get events -n sola-app --sort-by='.lastTimestamp'` — there you'll see things that the Discord report might not show (OOMKilled, CrashLoopBackOff, failed volume mounts).

---

## 🔧 **Maintenance and Failures**

> **In one sentence:** Most problems can be solved with a single `kubectl get ...` command — see what's not working, and the system handles the rest.

### **Daily Operations**

> **ELI5:** These are your **morning checks**, like before driving a car — check the oil, tire pressure, lights. Here you check whether all computers in the cluster are alive, whether applications are running, whether disks are full.

```bash
# Check node status — are all computers alive?
kubectl get nodes -o wide

# Check pods in sola-app — are the applications running?
kubectl get pods -n sola-app -o wide

# Check Longhorn status — are the disks okay?
kubectl get volumes.longhorn.io -n longhorn-system

# Check CloudNativePG — is the database working?
kubectl get cluster -n sola-app
```

### **When a Node Fails**

> **ELI5:** If one of the computers fails, an **automatic guard change** happens. Don't panic — the system is designed to survive the failure of one computer. Wait a minute, check, fix the failed computer when you have time.

1. **The remaining node takes over** — the app pod migrates, PG failover happens automatically
2. **Wait a minute** — CNPG failover (30s delay + promotion) and Longhorn reconfigure
3. **Check** — `kubectl get pods -n sola-app -o wide`
4. **Fix** the failed node as needed (replace disk, fix power, reinstall k3s)

### **Full Shutdown (Summer Break)**

See [🌞 Summer Break](POLETNA_PAVZA.md).

> **From experience:** Summer break is often overlooked, but it's crucial for the long life of the hardware. HP ProBooks in a cabinet without cooling can easily reach 50°C while idle during summer. Shutting down for 2 months extends the life of disks and batteries. Before shutting down, **mandatorily** take a snapshot of Longhorn volumes and dump the database — "better to have it and not need it, than to need it and not have it."

---

## 📋 **Complete Command Reference**

```bash
# === Status ===
kubectl get nodes -o wide                           # Which computers are in the cluster?
kubectl get pods -n sola-app -o wide                # Which applications are running and where?
kubectl get services -n sola-app                    # Which services are available?
kubectl get pvc -n sola-app                         # How much disk space is used?
kubectl get cluster -n sola-app                     # How's the database?
kubectl get events -n sola-app --sort-by='.lastTimestamp'  # What happened recently?

# === Application Management ===
kubectl rollout restart deployment -n sola-app sola-app          # Restart without downtime
kubectl rollout status deployment -n sola-app sola-app           # Monitor update progress
kubectl logs -n sola-app deployment/sola-app --tail=50           # Last 50 log lines
kubectl logs -n sola-app deployment/sola-app --previous          # Logs of the previous (failed) Pod

# === Database Management ===
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL                    # Connect to the database
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
*💡 **ELI5** = *Explain Like I'm 5* — means the explanation is written as simply as possible, without technical jargon.*

| Term | Explanation |
|---|---|
| **Arnes** | **Academic and Research Network of Slovenia** — Slovenian educational internet. The school is connected to the internet via Arnes. |
| **Cloudflare** | **Security guard in front of your server** — encrypts traffic (SSL), hides your IP, blocks attacks, speeds up loading. |
| **CloudNativePG (CNPG)** | **Smart assistant for PostgreSQL database** — automatically manages replication, failover, backup, and recovery. |
| **Cluster** | **A group of computers working as one** — two HP ProBooks connected into the same Kubernetes cluster. Kubernetes ensures applications run on whichever computer is available. |
| **ConfigMap / Secret** | **Kubernetes objects for storing settings** — ConfigMap for public settings (e.g., BASE_URL), Secret for sensitive data (passwords, keys). Secret is encoded, ConfigMap is readable. |
| **Control-plane** | **The "brain" of the cluster** — the control part that makes all decisions. We have control-plane on both HP ProBooks, meaning we have two "brains" — if one fails, the other takes over. |
| **Discord webhook** | **Automatic message sending to Discord** — our application sends a nightly report to the school Discord channel. |
| **DNS** | **The internet's phone book** — converts the name `ostc-app.org` into an IP address {{LB_IP}} (for example). |
| **Docker Image** | **Recipe for an application** — contains the program, libraries, settings. From one recipe you can make several identical containers (Pods). |
| **ELI5** | *Explain Like I'm 5* — a way of explaining that avoids technical terms and uses everyday analogies. E.g., Kubernetes isn't "a container orchestration system," but "a conductor for applications." |
| **etcd** | **The cluster's memory book** — stores all data about what runs where, what the settings are, who is alive and who is dead. It's the brain of Kubernetes. |
| **Failover** | **Automatic guard change** — when the primary system fails, the backup automatically takes over its role. In our case, CNPG promotes the replica to primary. |
| **FastAPI** | **A framework for web applications in Python** — sola-app is written in it. Fast, modern, supports automatic documentation. |
| **Git** | **A system for tracking code changes** — like "Track Changes" in Word, but for program code. |
| **GitHub Actions** | **Automatic testing and building on every change** — when someone uploads new code to GitHub, a new Docker Image is automatically built. |
| **Helm** | **"App Store" for Kubernetes** — a tool for installing ready-made packages (e.g., Longhorn, CNPG) into Kubernetes. Instead of manually writing YAML, you just say "install Longhorn." |
| **HPA (HorizontalPodAutoscaler)** | **Automatic adjustment of application replicas** — monitors CPU/RAM usage and adds or removes replicas (1-3) based on load. Like a coffee machine at school — when it's busy, another one turns on. |
| **HTTPS** | **Secure web connection** — HTTP + SSL. The green lock in the browser means the connection is secure. |
| **k3s** | **A lightweight version of Kubernetes** — specifically made for smaller computers and IoT devices. We use it on HP ProBooks because full Kubernetes is too heavy for laptops. The same `kubectl` commands work for both. |
| **Kubernetes (k8s)** | **The conductor for applications** — a system that automatically manages where and how your applications run. If one fails, it automatically starts it elsewhere. |
| **LoadBalancer** | **The reception desk in a building** — directs visitors (users) to the right application. In our case, MetalLB at IP {{LB_IP}}. |
| **Longhorn** | **A system that ensures you have 2 copies of data on 2 different computers** — distributed storage for Kubernetes, built for smaller clusters. |
| **MetalLB** | **A LoadBalancer for on-premise environments** — an alternative to cloud LoadBalancers (AWS, Google). Runs right on your own computers. |
| **Node** | **A physical computer in the cluster** — in our case k3s-1 (HP ProBook 455 G5) and k3s-2 (HP ProBook 450 G5). |
| **Pod** | **A container with an application** — the smallest unit in Kubernetes. It runs one copy of an application (e.g., sola-app or sola-db). Each Pod has its own private IP address. |
| **Primary (database)** | **The main database** — the only one that can be written to. All changes go through it. |
| **PVC (PersistentVolumeClaim)** | **A virtual hard drive** — a request for disk space in Kubernetes. Data stays even if the application moves to another computer. |
| **Replica** | **A copy that vigilantly watches the original** — a second database that constantly copies all changes from the primary. Ready to take over if the original fails. |
| **Replica (database)** | **Backup database** — read-only. Constantly copies changes from the primary. If the primary fails, it becomes the new primary. |
| **SSH** | **Secure access to a remote computer via command line** — like sitting in front of that computer, even though you're in another room. |
| **SSL/TLS** | **Encrypted connection (the lock in the browser)** — ensures nobody can eavesdrop on the communication between the user and the server. |
| **Uvicorn** | **The server that runs the FastAPI application** — reads Python code and serves it as a web page. Like a waiter bringing food (responses) to customers. |
| **WAL (Write-Ahead Log)** | **A log of changes before they are written** — PostgreSQL first writes every change to the WAL, then to the main data files. This enables crash recovery and replication. |
| **YAML** | **A human-readable format for writing configuration** — similar to JSON, but more readable. In Kubernetes, all settings are written in YAML format. |
| **Zero-downtime (rollout)** | **An update without service interruption** — Kubernetes first starts the new version, waits for it to work, then shuts down the old one. Users don't notice a thing. |

---

*Documentation for ostc-app — OŠ Toneta Čufarja Jesenice*
*Last updated: June 27, 2026*
