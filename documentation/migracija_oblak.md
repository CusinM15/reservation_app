# ☁️ Migracija v oblak — opcije

> Dokument za debato. Nič ni odločeno, dokler ne rečemo drugače.

Trenutno app **teče doma** na 2 HP prenosnikih s k3s. To pomeni: strojna oprema bo slej ko prej crknila, nekdo mora skrbeti za k3s upgrade, Longhorn, CNPG, backup, MetalLB, omrežje, izpade elektrike itd. Spodaj so možne alternative, kako se znebiti odgovornosti vzdrževanja.

---

## 1. 🏆 PaaS — "Push-to-deploy" (Railway / Fly.io / Render)

**Kako deluje:** Povežeš GitHub repo, oni sami zaznajo Python/FastAPI, buildajo in deployajo ob vsakem `git push`. 
Za bazo samo dodaš njihov managed PostgreSQL — ne rabiš nič konfigurirati.

### Railway.app — najboljši fit

| Plus | Minus |
|------|-------|
| + Samodejni deploy ob `git push` | – App je v tujem cloudu (ZDA/EU) |
| + Managed Postgres (backupi, PITR) | – Če gre Railway bankrot, je treba seliti |
| + HTTPS/SSL avtomatsko | – Omejen free tier (€5 za začetek) |
| + Storage volumes za file shrambo | – Ni "fizičnega dostopa" |
| + Cena: ~€5–20/mesec | |
| + 0 vzdrževanja infrastrukture | |

**Cena (Railway):**
| Storitev | Cena |
|----------|------|
| App (FastAPI) — 1 CPU, 1GB RAM | €5/mesec |
| PostgreSQL — 1GB storage | €5/mesec |
| Dodaten storage (če app rabi) | ~€2/mesec |
| **Skupaj** | **~€10–15/mesec** |

### Fly.io

| Plus | Minus |
|------|-------|
| + Zelo hitri deployi | – Malo bolj zapleten CLI kot Railway |
| + Managed Postgres z backupi | – Cena malo višja |
| + Regionalno: lahko izbereš EU regijo | |
| + Dober free tier za male stvari | |

**Cena (Fly.io):**
| Storitev | Cena |
|----------|------|
| App — shared CPU, 256MB RAM | Free |
| App — 1 CPU, 1GB RAM | ~€12/mesec |
| PostgreSQL — 1GB | ~€8/mesec |
| **Skupaj** | **~€15–20/mesec** |

### Render

| Plus | Minus |
|------|-------|
| + Zelo preprost UI | – Počasnejši deployi |
| + Managed Postgres | – Manj zmogljiv free tier |
| + Blueprint (Infrastructure as Code) | |

**Cena (Render):**
| Storitev | Cena |
|----------|------|
| App (starter) | €7/mesec |
| PostgreSQL — 1GB | €7/mesec |
| **Skupaj** | **~€14/mesec** |

**Kaj ni treba vzdrževati:** OS, Docker, Kubernetes, baza, backupi, SSL, domenska imena (DNS nastaviš enkrat).

---

## 2. 🐧 VPS + Coolify (self-hosted PaaS)

**Kako deluje:** Najameš VPS (€4–8/mesec), nanj namestiš [Coolify](https://coolify.io) (odprta koda).
Coolify je kot Railway, ampak na tvojem strežniku. Povežeš GitHub repo, on sam deploya.

| Plus | Minus |
|------|-------|
| + Full kontrola — strežnik je tvoj | – Še vedno moraš vzdrževati OS na VPS |
| + Podatki ostanejo v EU/SLO (odvisno od VPS) | – Backup baze moraš sam nastaviti |
| + Ceneje od PaaS | – Če VPS crkne, je treba ročno obnovit |
| + Ni vendor lock-in (odprta koda) | – Malo več začetnega nastavljanja |
| + Lahko dodaš več appov na isti strežnik | |

**Cena:**
| Storitev | Cena |
|----------|------|
| VPS (Hetzner CX22 — 2 CPU, 4GB RAM) | €3.99/mesec |
| Coolify (brezplačen, open-source) | €0 |
| PostgreSQL (v Docker na istem VPS) | €0 (všteto) |
| Backups (Hetzner Storage Box) | ~€3/mesec |
| **Skupaj** | **~€7–8/mesec** |

Alternative: **Dokploy** (lažji od Coolify) ali **Dokku** (še bolj simpl).

**Kaj ni treba vzdrževati:** Kubernetes, Longhorn, MetalLB, omrežje, fizični prenosniki.
**Kaj še vedno rabiš:** OS upgrade na VPS (občasno `apt update && apt upgrade`), backup nastavitev.

---

## 3. 🐳 VPS + Docker Compose (najbolj simpl — brez PaaS)

**Kako deluje:** Najameš VPS. Gor namestiš Docker + Docker Compose.
Na GitHub pushaš, na VPS greš `git pull && docker compose up -d --build`.

| Plus | Minus |
|------|-------|
| + Najceneje | – Vsak deploy = ročen (ali pa narediš GitHub Action + SSH) |
| + Popolna kontrola | – Ni avtomatskega rebuildanja ob napakah |
| + Zelo preprosto razumeti | – Če si na dopustu in crkne, nihče ne redeploya |
| + Brez dodatnih orodij | |

**Cena:**
| Storitev | Cena |
|----------|------|
| VPS (Hetzner CX22 — 2 CPU, 4GB RAM) | €3.99/mesec |
| Docker — brezplačen | €0 |
| Backups (Hetzner Storage Box) | ~€3/mesec |
| **Skupaj** | **~€7/mesec** |

**Kaj ni treba vzdrževati:** Kubernetes, Longhorn, MetalLB, fizični prenosniki.
**Kaj še vedno rabiš:** OS upgrade, Docker upgrade, ročni deployi, backup skripte.

---

## 4. ☸️ Managed Kubernetes (EKS / AKS / GKE)

**Kako deluje:** Najameš Kubernetes kontrolno ravnino v cloudu (AWS, Azure, Google).
Tvoje YAMLe daš gor enake kot zdaj — samo ne rabiš skrbeti za etcd, API server, scheduler.

| Plus | Minus |
|------|-------|
| + Isti YAMLi kot zdaj — nič ne spreminjaš | – **Drago** |
| + Managed kontrolna ravnina (upgradei avtomatski) | – Še vedno rabiš znanje k8s |
| + Avtomatsko skaliranje | – Še vedno rabiš skrbeti za storage, monitoring |
| | – Longhorn ne dela v cloudu (rabiš EBS/disk) |
| | – Največ dela od vseh opcij |

**Cena:**
| Storitev | Cena |
|----------|------|
| AKS/EKS/GKE kontrolna ravnina | ~€70/mesec (EKS) – €0 (AKS/GKE, samo worker nodi) |
| Worker nodi (2x 2CPU, 4GB) | ~€30/mesec |
| Managed PostgreSQL (Azure DB/Cloud SQL) | ~€15/mesec |
| Disk storage | ~€5/mesec |
| **Skupaj** | **~€50–100/mesec** |

**Zakaj ni smiselno:** Plačaš več kot vse druge opcije, imaš več dela, in za eno šolsko aplikacijo je to topovska cev na muho.

---

## 5. ☁️ Serverless (AWS Lambda / Cloud Run)

**Kako deluje:** App teče samo ko nekdo kliče API. Ne plačuješ za "idle" čas.

| Plus | Minus |
|------|-------|
| + Plačaš samo za dejansko uporabo | – FastAPI ni najbolj fit za Lambda (rabiš adapter) |
| + Skalira se avtomatsko do 0 | – WebSocket/i dolge povezave ne delajo |
| + 0 vzdrževanja | – "Cold start" zakasnitev ob prvem klicu |
| | – Težje debugiranje |
| | – Storage (file uploadi) je zapleten |

**Cena (Cloud Run + Cloud SQL):**
| Storitev | Cena |
|----------|------|
| Cloud Run — 2M klicev/mesec | ~€5/mesec |
| Cloud SQL (PostgreSQL mini) | ~€10/mesec |
| Cloud Storage (slike/datoteke) | ~€1/mesec |
| **Skupaj** | **~€15/mesec** |

**Zakaj ni idealno:** Šolska aplikacija rabi file upload (slike, dokumenti) in verjetno kakšen daljši proces — serverless je za to neroden. Možno, ampak več dela kot Railway.

---

## 📊 Primerjava vseh opcij

| Opcija | Cena/mesec | Vzdrževanje | Delež "dela" v primerjavi z zdaj |
|--------|-----------|-------------|----------------------------------|
| **Zdaj (k3s doma)** | €15–25 (elektrika + HW) | ⚠️ Visoko | 100 % |
| **Railway / PaaS** | ~€10–15 | 🟢 Nič | 5 % |
| **Coolify na VPS** | ~€7–8 | 🟢 Zelo malo | 10 % |
| **Docker Compose na VPS** | ~€7 | 🟡 Malo | 15 % |
| **Managed K8s** | ~€50–100 | 🔶 Srednje | 60 % |
| **Serverless** | ~€15 | 🟢 Malo | 25 % |

---

## 🎯 Priporočilo (za debato)

**1. Railway.app** — če hočeš najmanj dela. €10–15/mesec, nič ne vzdržuješ, push-to-deploy.
**2. Hetzner VPS + Coolify** — če hočeš ceneje in več kontrole. ~€7/mesec, malo več začetnega dela.
**3. Docker Compose na VPS** — če nočeš dodatnih orodij in ti ustreza občasen ročen deploy. ~€7/mesec.

---

> **Vse cene so okvirne, stanje julij 2026. Načeloma gre za mikrostoritve (1 CPU, 1GB RAM, 1GB baza), kar za šolsko aplikacijo s ~100–200 uporabniki povsem zadostuje.**
