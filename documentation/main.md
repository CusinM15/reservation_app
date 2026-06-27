🌐 **Jezik / Language:** [🇸🇮 Slovenščina](main.md) | [🇬🇧 English](en/main.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 🚀 **ostc-app — Rezervacijski sistem**
## **OŠ Toneta Čufarja — Dokumentacija**

---

## 📚 **Kazalo dokumentacije**

Ta datoteka je **glavni vstopni dokument**. Spodaj so povezave na specializirane poddokumente:

| Dokument | Opis |
|---|---|
| [🏗️ **HA arhitektura**](HA.md) | CloudNativePG, avtomatski failover, potek ob izpadu noda |
| [🌞 **Poletna pavza**](POLETNA_PAVZA.md) | Varen izklop k3s clustra čez poletje in ponoven vklop jeseni |
| [☁️ **Domena in DNS**](domena.md) | Nastavitev domene, Cloudflare, DNS zapisi |
| [🐍 **Postavi lokalni app**](postavi-lokalni-app.md) | Namestitev na enem računalniku (brez Kubernetes) |
| [☸️ **K3s setup**](k3s-setup.md) | Namestitev k3s clustra iz nič |
| [⚙️ **Admin/devops navodila**](admin-devops-navodila.md) | Vzdrževanje, posodabljanje, odpravljanje težav |
| [👩‍🏫 **Navodila za učitelje**](navodila-ucitelji.md) | Uporaba aplikacije — rezervacije in ocenjevanja |
| [👑 **Navodila za vodstvo**](navodila-vodstvo.md) | Upravljanje prek brskalnika (serije, zasedeni datumi) |
| [📱 **Opis aplikacije**](aplikacija-rezervacije.md) | Kaj aplikacija omogoča, namen, funkcionalnosti |
| [📖 **Navodila za uporabnika**](navodila-uporabnika.md) | Prijava, gesla, dnevna uporaba |

---

## 📑 **Kazalo vsebine** (ta dokument)
1. [Arhitektura sistema](#arhitektura-sistema)
2. [Strojna oprema in omrežje](#strojna-oprema-in-omrežje)
3. [Kubernetes (k3s) Cluster](#kubernetes-k3s-cluster)
4. [Aplikacija Sola App](#aplikacija-sola-app)
5. [PostgreSQL HA — CloudNativePG](#postgresql-ha--cloudnativepg)
6. [MetalLB LoadBalancer](#metallb-loadbalancer)
7. [Nginx Reverse Proxy](#nginx-reverse-proxy)
8. [Cloudflare DNS](#cloudflare-dns)
9. [Longhorn Storage](#longhorn-storage)
10. [Dnevni backup in reporti](#dnevni-backup-in-reporti)
11. [Vzdrževanje in okvare](#vzdrževanje-in-okvare)
12. [Celoten sklic ukazov](#celoten-sklic-ukazov)

---

## 🏗️ **Arhitektura sistema**

### **Strojna in omrežna shema**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         K3S KUBERNETES CLUSTER (2 noda)                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────┐    ┌──────────────────────────┐            │
│  │    k3s-1                  │    │    k3s-2                  │            │
│  │    HP ProBook 455 G5     │    │    HP ProBook 450 G5     │            │
│  │    IP: 192.168.1.10      │    │    IP: 192.168.1.11      │            │
│  │    control-plane,etcd    │    │    control-plane,etcd    │            │
│  │                          │    │                          │            │
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ sola-app Pod 1    │   │    │  │ sola-app Pod 2    │   │            │
│  │  │ (app.ostc-app.org)│   │    │  │ (app.ostc-app.org)│   │            │
│  │  └───────────────────┘   │    │  └───────────────────┘   │            │
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ sola-db-1         │   │    │  │ sola-db-2         │   │            │
│  │  │ (PG PRIMARY)      │◄──┼────┼──┤ (PG REPLICA)      │   │            │
│  │  │ CNPG Instance     │   │    │  │ CNPG Instance     │   │            │
│  │  └───────────────────┘   │    │  └───────────────────┘   │            │
│  │                          │    │                          │            │
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ Longhorn          │   │    │  │ Longhorn          │   │            │
│  │  │ Instance Manager  │   │    │  │ Instance Manager  │   │            │
│  │  └───────────────────┘   │    │  └───────────────────┘   │            │
│  │                          │    │                          │            │
│  │  ┌───────────────────┐   │    │  ┌───────────────────┐   │            │
│  │  │ nginx (old conf)  │   │    │  │ nginx (ACTIVE)    │   │            │
│  │  │ (80/443, stale)   │   │    │  │ (port 8080)       │   │            │
│  │  └───────────────────┘   │    │  └───────────┬───────┘   │            │
│  └──────────────────────────┘    └───────────────┼───────────┘            │
│                                                  │                          │
│                                        proxy_pass│192.168.1.50:8002        │
│                                                  │                          │
│                    ┌─────────────────────────────┘                          │
│                    │                                                       │
│  ┌─────────────────▼──────────────────────────────────────────┐           │
│  │        Service LoadBalancer (MetalLB, 192.168.1.50:8002)    │           │
│  │        → sola-app Pod 1 ali Pod 2                            │           │
│  └─────────────────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Cloudflare DNS    │
                    │  ostc-app.org      │
                    │  → 192.168.1.11:8080│  📡 Cloudflare proxy
                    │    (k3s-2 nginx)   │
                    └───────────────────┘
                              │
                              │  Internet
                              ▼
                    🌐 Uporabniki (učitelji, vodstvo)```
                    🌐 Uporabniki (učitelji, vodstvo)
```

> **Opomba:** Oba noda sta `control-plane,etcd` — ni ločenih worker nodov. k3s podpava poganjanje uporabniških podov tudi na control-plane nodih.

### **Prometni tok**

```
🌐 Uporabnik
  → Cloudflare (SSL, proxy, ostc-app.org)
    → Cloudflare proxy → k3s-2:8080
      → nginx na k3s-2
        → proxy_pass http://192.168.1.50:8002
          → Service LoadBalancer (MetalLB)
            → sola-app Pod (k3s-1 ali k3s-2)

Alternativna pot (interno omrežje):
  → http://192.168.1.50:8002 (direkten dostop do LB)
```

> **Opomba:** Cloudflare proxy kaže na **k3s-2 (port 8080)** — nginx na k3s-2 posreduje promet na LoadBalancer IP. Na k3s-1 je nginx nameščen z ostanki stare konfiguracije (porta 80/443), ki ni aktivno v uporabi.

### **Pregled komponent**

| Komponenta | Lokacija | Namen |
|---|---|---|
| **k3s-1** | HP ProBook 455 G5 (192.168.1.10) | Control-plane, app pod, PG primary, nginx |
| **k3s-2** | HP ProBook 450 G5 (192.168.1.11) | Control-plane, app pod, PG replica, nginx |
| **Sola App (FastAPI)** | 2 poda (oba noda) | Rezervacije, ocenjevanje, prijava |
| **Longhorn** | Oba noda | Distribuirano shranjevanje (PVC-ji) |
| **MetalLB** | Oba noda | LoadBalancer IP (192.168.1.50) |
| **nginx** | k3s-1 (80/443), k3s-2 (8080) | Reverse proxy (k3s-1: SSL termination, k3s-2: port 8080 → LoadBalancer) |
| **Cloudflare** | Zunanji | DNS, SSL, proxy |

---

## 💻 **Strojna oprema in omrežje**

### **Specifikacije**

| Node | Model | CPU | RAM | Disk | Vloga |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Control-plane,etcd, app, PG primary, nginx |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Control-plane,etcd, app, PG replica, nginx |

### **Omrežne nastavitve**

```bash
# Lokalno omrežje (Arnes)
k3s-1: 192.168.1.10/24
k3s-2: 192.168.1.11/24
Gateway: 192.168.1.1
DNS: 192.168.1.10

# Kubernetes Pod CIDR
10.42.0.0/16

# Kubernetes Service CIDR
10.43.0.0/16

# LoadBalancer IP pool (MetalLB)
192.168.1.50 - 192.168.1.55
```

### **Dostop**

```bash
# SSH v oba noda
ssh admin@192.168.1.10    # k3s-1
ssh admin@192.168.1.11    # k3s-2

# Kubernetes (k3s) — kubeconfig je na obeh nodih
kubectl get nodes -o wide
kubectl get pods -A -o wide

# Aplikacija v brskalniku
https://ostc-app.org          # prek Cloudflare + nginx
http://192.168.1.50:8002     # direkt (samo interno omrežje)
```

---

## ☸️ **Kubernetes (k3s) Cluster**

### **Stanje nodov**

```bash
kubectl get nodes -o wide

# NAME    STATUS   ROLES                       AGE   VERSION        INTERNAL-IP      EXTERNAL-IP
# k3s-1   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   192.168.1.10    <none>
# k3s-2   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   192.168.1.11    <none>
```

### **Namestitev k3s**

```bash
# Na k3s-1 (prvi node)
curl -sfL https://get.k3s.io | sh -s - server \
  --cluster-init \
  --disable=traefik \
  --node-ip=192.168.1.10 \
  --flannel-iface=eth0

# Na k3s-2 (drugi node)
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://192.168.1.10:6443 \
  --disable=traefik \
  --node-ip=192.168.1.11 \
  --flannel-iface=eth0 \
  --token <NODE_TOKEN>
```

Token dobite z: `sudo cat /var/lib/rancher/k3s/server/node-token` (na k3s-1).

> **Opomba:** `--disable=traefik` izklopi vgrajeni ingress, ker uporabljamo lastni nginx reverse proxy.

---

## 🚀 **Aplikacija Sola App**

### **Deployment**

Namespace: `sola-app`

```bash
kubectl get deployments -n sola-app
kubectl get pods -n sola-app -o wide
kubectl get services -n sola-app
```

Aplikacija teče v **dveh podih** (ena na vsakem nodu):

```bash
kubectl get pods -n sola-app -o wide

# NAME                        READY   STATUS    RESTARTS   AGE   IP           NODE
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.0.x    k3s-1
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.1.x    k3s-2
```

### **Docker Image**

- **Image:** `sola-app:latest`
- **Dockerfile:** `reservation_app/k8s/Dockerfile`
- **Deployment YAML:** `reservation_app/k8s/sola-app.yaml`

### **Posodobitev aplikacije**

```bash
cd reservation_app
git pull
# Počakaj, da se CI build konča (GitHub Actions)
# al pa ročno:
kubectl rollout restart deployment -n sola-app sola-app
kubectl rollout status deployment -n sola-app sola-app
```

---

## 🗄️ **PostgreSQL HA — CloudNativePG**

### **Stanje**

```bash
kubectl get pods -n sola-app -o wide | grep db

# NAME                    READY   STATUS    IP            NODE
# sola-db-1 (primary)     1/1     Running   10.42.0.x     k3s-1
# sola-db-2 (replica)     1/1     Running   10.42.1.x     k3s-2
```

Zgrajena z **CloudNativePG** operatorjem. Primary vedno na k3s-1, replica na k3s-2.

### **Failover**

Ob izpadu k3s-1:
1. CloudNativePG zazna izpad v ~10 sekundah
2. Replica na k3s-2 se promovira v primary (~20 sekund)
3. Service `sola-db-rw` se preusmeri na nov primary
4. Aplikacija izve za novo lokacijo prek Kubernetes DNS → brez izpada

### **Dostop**

```bash
# Primarna baza (rw)
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL

# Replica (read-only)
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL_RO
```

---

## 🌐 **Nginx Reverse Proxy**

### **Arhitektura**

Nginx teče na **obeh nodih**:

| Node | Porti | Vloga |
|---|---|---|
| **k3s-1** | 80, 443 | SSL termination (Cloudflare → k3s-1:443) |
| **k3s-2** | 8080 | Reverse proxy za interni promet |

### **Konfiguracija**

```nginx
# k3s-1 — /etc/nginx/conf.d/ostc-app.org.conf
server {
    listen 80;
    server_name ostc-app.org www.ostc-app.org;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name ostc-app.org www.ostc-app.org;

    ssl_certificate     /etc/nginx/ssl/ostc-app.org.pem;
    ssl_certificate_key /etc/nginx/ssl/ostc-app.org.key;

    location / {
        proxy_pass http://192.168.1.50:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# k3s-2 — /etc/nginx/conf.d/ostc-app.conf
server {
    listen 8080;
    server_name ostc-app.org www.ostc-app.org;

    location / {
        proxy_pass http://192.168.1.50:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## ☁️ **Cloudflare DNS**

### **DNS zapisi**

| Tip | Ime | Vrednost | Proxy |
|---|---|---|---|
| A | `@` (ostc-app.org) | 192.168.1.10 | ✅ Cloudflare proxy |
| A | `www` | 192.168.1.10 | ✅ Cloudflare proxy |

### **SSL/TLS**

Cloudflare skrbi za:
- **Edge certifikat** — med uporabnikom in Cloudflare (HTTPS)
- **Origin CA certifikat** — med Cloudflare in k3s-1 nginx (HTTPS)

Nastavitve v Cloudflare dashboard:
- **SSL/TLS encryption mode:** `Full (strict)`
- **Always Use HTTPS:** ON
- **Minimum TLS Version:** 1.2

---

## 💾 **Longhorn Storage**

### **Stanje**

```bash
kubectl get pvc -n sola-app
kubectl get volumes.longhorn.io -n longhorn-system
```

### **PVC-ji**

| PVC | Name | Size | Access Mode | Uporaba |
|---|---|---|---|---|
| `sola-postgresql` | 5Gi | RWO | PG data |
| `sola-postgresql-wal` | 2Gi | RWO | WAL logi |

Longhorn replikacija (2 kopiji) zagotavlja, da tudi ob izgubi enega noda podatki ostanejo.

---

## 📅 **Dnevni backup in reporti**

### **Dnevni app report**

```bash
# Cron: 04:00 vsak dan (Europe/Ljubljana)
# Pošlje summary na Discord — število rezervacij, prijavljenih, itd.
kubectl logs -n sola-app job/sola-report
```

Posodobi se **samodejno** preko Hermes cron joba. Poročilo vključuje:
- Število aktivnih rezervacij
- Število prijavljenih uporabnikov
- Stanje ocenjevanj
- Morebitne napake

---

## 🔧 **Vzdrževanje in okvare**

### **Dnevne operacije**

```bash
# Preveri stanje nodov
kubectl get nodes -o wide

# Preveri pode v sola-app
kubectl get pods -n sola-app -o wide

# Preveri stanje Longhorn
kubectl get volumes.longhorn.io -n longhorn-system

# Preveri CloudNativePG
kubectl get cluster -n sola-app

# Preveri nginx
sudo systemctl status nginx
```

### **Ob izpadu noda**

1. **Ostali node prevzame** — app pod se preseli, PG failover
2. **Počakaj 30s** — CNP failover in Longhorn se rekonfigurirata
3. **Preveri** — `kubectl get pods -n sola-app -o wide`
4. **Popravi** izpadli node po potrebi

### **Popolna zaustavitev (poletna pavza)**

Glej [🌞 Poletna pavza](POLETNA_PAVZA.md).

---

## 📋 **Celoten sklic ukazov**

```bash
# === Stanje ===
kubectl get nodes -o wide
kubectl get pods -n sola-app -o wide
kubectl get services -n sola-app
kubectl get pvc -n sola-app
kubectl get cluster -n sola-app
kubectl get events -n sola-app --sort-by='.lastTimestamp'

# === Upravljanje aplikacije ===
kubectl rollout restart deployment -n sola-app sola-app
kubectl rollout status deployment -n sola-app sola-app
kubectl logs -n sola-app deployment/sola-app --tail=50
kubectl logs -n sola-app deployment/sola-app --previous

# === Upravljanje baze ===
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL -c "SELECT * FROM users;"

# === Longhorn ===
kubectl get volumes.longhorn.io -n longhorn-system
kubectl get engineimages.longhorn.io -n longhorn-system
kubectl get nodes.longhorn.io -n longhorn-system

# === Nginx ===
sudo systemctl status nginx
sudo systemctl restart nginx
sudo nginx -t
sudo journalctl -u nginx --no-pager -n 30

# === Git (na k3s-2) ===
cd /home/admin/reservation_app
git pull
```

---

*Dokumentacija za ostc-app — OŠ Toneta Čufarja Jesenice*
*Zadnja posodobitev: 27. junij 2026*
