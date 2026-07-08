🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../migracija_oblak.md) | [🇬🇧 English](migracija_oblak.md)

---

# ☁️ Cloud Migration — Options

> Discussion document. Nothing is decided until we say otherwise.

Currently the app **runs at home** on 2 HP laptops with k3s. This means: hardware will eventually fail, someone has to handle k3s upgrades, Longhorn, CNPG, backups, MetalLB, networking, power outages, etc. Below are possible alternatives to offload maintenance responsibility.

---

## 1. 🏆 PaaS — "Push-to-deploy" (Railway / Fly.io / Render)

**How it works:** Connect your GitHub repo, they automatically detect Python/FastAPI, build and deploy on every `git push`.
For the database, just add their managed PostgreSQL — no configuration needed.

### Railway.app — best fit

| Pros | Cons |
|------|------|
| + Auto-deploy on `git push` | – App is in a foreign cloud (US/EU) |
| + Managed Postgres (backups, PITR) | – If Railway goes bust, you need to migrate |
| + HTTPS/SSL automatic | – Limited free tier (€5 to start) |
| + Database only — app doesn't store files/images | – No "physical access" |
| + Price: ~€5–20/month | |
| + 0 infrastructure maintenance | |

**Pricing (Railway):**
| Service | Price |
|---------|-------|
| App (FastAPI) — 1 CPU, 1GB RAM | €5/month |
| PostgreSQL — 1GB storage | €5/month |
| Domain | Not required — you get `app.railway.app`. Can buy your own (~€10/year) |
| **Total** | **~€10–15/month** |

### Fly.io

| Pros | Cons |
|------|------|
| + Very fast deploys | – Slightly more complex CLI than Railway |
| + Managed Postgres with backups | – Slightly higher price |
| + Regional: can choose EU region | |
| + Good free tier for small projects | |

**Pricing (Fly.io):**
| Service | Price |
|---------|-------|
| App — shared CPU, 256MB RAM | Free |
| App — 1 CPU, 1GB RAM | ~€12/month |
| PostgreSQL — 1GB | ~€8/month |
| Domain | Not required — you get `app.fly.dev`. Can buy your own (~€10/year) |
| **Total** | **~€15–20/month** |

### Render

| Pros | Cons |
|------|------|
| + Very simple UI | – Slower deploys |
| + Managed Postgres | – Less capable free tier |
| + Blueprint (Infrastructure as Code) | |

**Pricing (Render):**
| Service | Price |
|---------|-------|
| App (starter) | €7/month |
| PostgreSQL — 1GB | €7/month |
| Domain | Not required — you get `app.onrender.com`. Can buy your own (~€10/year) |
| **Total** | **~€14/month** |

**What you don't need to maintain:** OS, Docker, Kubernetes, database, backups, SSL, domain names (DNS set once).

---

## 2. 🐧 VPS + Coolify (self-hosted PaaS)

**How it works:** Rent a VPS (€4–8/month), install [Coolify](https://coolify.io) (open source).
Coolify is like Railway, but on your own server. Connect your GitHub repo, it deploys automatically.

| Pros | Cons |
|------|------|
| + Full control — your server | – You still need to maintain the OS on the VPS |
| + Data stays in EU/SLO (depends on VPS) | – Database backups need manual setup |
| + Cheaper than PaaS | – If the VPS crashes, manual recovery needed |
| + No vendor lock-in (open source) | – More initial setup work |
| + Can host multiple apps on the same VPS | |

**Pricing:**
| Service | Price |
|---------|-------|
| VPS (Hetzner CX22 — 2 CPU, 4GB RAM) | €3.99/month |
| Coolify (free, open-source) | €0 |
| PostgreSQL (Docker on same VPS) | €0 (included) |
| Backups (Hetzner Storage Box) | ~€3/month |
| Domain | **Required** (~€10/year). Without a domain, access is IP-only with no HTTPS. |
| **Total** | **~€7–8/month** |

Alternatives: **Dokploy** (lighter than Coolify) or **Dokku** (even simpler).

**What you don't need to maintain:** Kubernetes, Longhorn, MetalLB, networking, physical laptops.
**What you still need:** OS upgrades on VPS (occasional `apt update && apt upgrade`), backup configuration.

---

## 3. 🐳 VPS + Docker Compose (simplest — no PaaS)

**How it works:** Rent a VPS. Install Docker + Docker Compose.
Push to GitHub, then on the VPS run `git pull && docker compose up -d --build`.

| Pros | Cons |
|------|------|
| + Cheapest option | – Every deploy is manual (or set up a GitHub Action + SSH) |
| + Full control | – No automatic rebuild on failures |
| + Very simple to understand | – If you're on vacation and it breaks, nobody redeploys |
| + No extra tools needed | |

**Pricing:**
| Service | Price |
|---------|-------|
| VPS (Hetzner CX22 — 2 CPU, 4GB RAM) | €3.99/month |
| Docker — free | €0 |
| Backups (Hetzner Storage Box) | ~€3/month |
| Domain | **Required** (~€10/year). Without a domain, access is IP-only with no HTTPS. |
| **Total** | **~€7/month** |

**What you don't need to maintain:** Kubernetes, Longhorn, MetalLB, physical laptops.
**What you still need:** OS upgrades, Docker upgrades, manual deploys, backup scripts.

---

## 4. ☸️ Managed Kubernetes (EKS / AKS / GKE)

**How it works:** Rent the Kubernetes control plane in the cloud (AWS, Azure, Google).
Your existing YAML files work as-is — you just don't need to manage etcd, API server, scheduler.

| Pros | Cons |
|------|------|
| + Same YAMLs as now — nothing changes | – **Expensive** |
| + Managed control plane (auto upgrades) | – You still need k8s knowledge |
| + Auto-scaling | – You still need to handle storage, monitoring |
| | – Longhorn doesn't work in the cloud (need EBS/disks) |
| | – Most work of all options |

**Pricing:**
| Service | Price |
|---------|-------|
| AKS/EKS/GKE control plane | ~€70/month (EKS) – €0 (AKS/GKE, workers only) |
| Worker nodes (2x 2CPU, 4GB) | ~€30/month |
| Managed PostgreSQL (Azure DB/Cloud SQL) | ~€15/month |
| Disk storage | ~€5/month |
| Domain | **Recommended** (~€10/year). You get a LB IP, but need a domain for HTTPS/SSL. |
| **Total** | **~€50–100/month** |

**Why it doesn't make sense:** You pay more than all other options, have more work, and for one school application it's overkill.

---

## 5. ☁️ Serverless (AWS Lambda / Cloud Run)

**How it works:** The app runs only when someone calls the API. You don't pay for "idle" time.

| Pros | Cons |
|------|------|
| + Pay only for actual usage | – FastAPI isn't the best fit for Lambda (needs adapter) |
| + Auto-scales down to 0 | – WebSockets / long connections don't work |
| + 0 maintenance | – "Cold start" delay on first call |
| | – Harder to debug |
| | – App wasn't written for serverless (cold start) |

**Pricing (Cloud Run + Cloud SQL):**
| Service | Price |
|---------|-------|
| Cloud Run — 2M calls/month | ~€5/month |
| Cloud SQL (PostgreSQL mini) | ~€10/month |
| Domain | Not required — you get `app.run.app`. Can buy your own (~€10/year) |
| **Total** | **~€15/month** |

**Why it's not ideal:** The app wasn't written for a serverless architecture — cold starts on first call, harder debugging. Possible (FastAPI + Mangum adapter), but more work than Railway.

---

## 📊 Comparison of all options

| Option | Price/month | Maintenance | Work compared to now |
|--------|------------|-------------|----------------------|
| **Now (k3s at home)** | €15–25 (electricity + HW) | ⚠️ High | 100 % |
| **Railway / PaaS** | ~€10–15 | 🟢 None | 5 % |
| **Coolify on VPS** | ~€7–8 | 🟢 Very little | 10 % |
| **Docker Compose on VPS** | ~€7 | 🟡 Little | 15 % |
| **Managed K8s** | ~€50–100 | 🔶 Moderate | 60 % |
| Domain (all options) | ~€10/**year** (if you buy one) | – | – |
| **Serverless** | ~€15 | 🟢 Little | 25 % |

---

## 🎯 Recommendation (for discussion)

**1. Railway.app** — if you want the least work. €10–15/month, nothing to maintain, push-to-deploy.
**2. Hetzner VPS + Coolify** — if you want cheaper and more control. ~€7/month, a bit more initial setup.
**3. Docker Compose on VPS** — if you don't want extra tools and occasional manual deploys are fine. ~€7/month.

---

> **All prices are approximate, as of July 2026. These assume micro services (1 CPU, 1GB RAM, 1GB database), which is sufficient for a school application with ~100–200 users.**
