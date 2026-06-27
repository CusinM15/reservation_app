[🇸🇮 Slovenščina](admin_devops.md) | [🇬🇧 English](en/admin_devops.md)

---

# 🏫 **Admin/DevOps navodila — ostc-app**
## **OŠ Toneta Čufarja**

> Celotna admin navodila za vzdrževanje in upravljanje aplikacije.
> Podrobnejša navodila za namestitev so v [ostc-app_deli repozitoriju](https://github.com/os-tc-jesenice/ostc-app_deli).

---

## 📋 Vsebina

1. [Kaj aplikacija omogoča](#kaj-aplikacija-omogoča)
2. [Zahteve za zagon](#zahteve-za-zagon)
3. [Kubernetes (k3s) način](#3-način-kubernetes-k3s--visoka-razpoložljivost)
4. [Vzdrževanje in avtomatizacija (cron jobi)](#vzdrževanje-in-avtomatizacija-cron-jobi)
5. [Dodajanje novega računalnika v cluster](#dodajanje-novega-računalnika-v-k3s-cluster)
6. [Struktura repozitorija](#struktura-repozitorija)

---

## Kaj aplikacija omogoča

- **Rezervacije** prostorov:
  - **Tablice** – didaktične tablice (kapaciteta: 28 kosov, lahko si jih deli več učiteljev v isti uri)
  - **Računalnica** – ena rezervacija na uro
  - **Ladja** – ena rezervacija na uro
- **Ocenjevanja** – napovedovanje pisnih ocenjevanj z omejitvami (max 3/teden, max 2 običajni)
- **Zasedeni datumi** – Vodstvo/admin lahko označi dneve kot zasedene (športni dan, ekskurzija...)
- **Admin panel** – upravljanje uporabnikov
- **Pozabljeno geslo** – ponastavitev preko emaila

---

## Zahteve za zagon

Aplikacija je narejena v Pythonu s **FastAPI** in deluje na treh načinih:

| Način | Zahtevnost | Za kaj je primeren |
|---|---|---|
| **Lokalno (uvicorn)** | ⭐ Enostavno | En računalnik v zbornici |
| **mDNS** | ⭐⭐ Srednje | Več računalnikov znotraj šolskega omrežja |
| **Kubernetes (k3s)** | ⭐⭐⭐ Zahtevno | Visoka razpoložljivost, 2+ računalnikov |

**Priporočen OS:** Ubuntu Server 24.04 LTS

---

## 3. način: Kubernetes (k3s) – visoka razpoložljivost

> **Trenutno stanje:** 2 noda (k3s-1, k3s-2), oba control-plane + etcd.
> CloudNativePG za HA bazo, MetalLB za LoadBalancer, Longhorn za storage.

### Kaj sta Kubernetes in k3s?

**Kubernetes (k8s)** je sistem za upravljanje zabojnikov (containerjev), ki poskrbi, da aplikacija teče tudi ob izpadu enega računalnika. **k3s** je lažja različica Kubernetes, primerna za manjše strežnike in star računalnik.

### 3.1 Priprava računalnika

#### Nastavitev statičnega IP

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

Primer za k3s-1 (193.2.171.250):
```yaml
network:
  ethernets:
    eth0:
      addresses:
        - 193.2.171.250/24
      routes:
        - to: default
          via: 193.2.171.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 1.1.1.1
  version: 2
```

```bash
sudo netplan apply
```

#### Nastavitev laptopa kot server

```bash
sudo nano /etc/systemd/logind.conf
# Odstrani # pred HandleLidSwitch=ignore
sudo systemctl restart systemd-logind
```

#### SSH – oddaljen dostop

```bash
sudo apt install -y openssh-server
sudo systemctl enable --now ssh

# Z drugega računalnika:
ssh admin_os@193.2.171.250   # k3s-1
ssh admin_os@193.2.171.249   # k3s-2
```

### 3.2 Namestitev k3s (prvi master)

```bash
# Na prvem nodu (k3s-1)
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=servicelb --disable=traefik" sh -

# Preveri
sudo kubectl get nodes
sudo cat /var/lib/rancher/k3s/server/node-token  # shrani token
```

Nastavi kubeconfig za običajnega uporabnika:
```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
```

### 3.3 Dodajanje drugega master

```bash
# Na k3s-2 (zamenjaj TOKEN in IP)
curl -sfL https://get.k3s.io | \
  K3S_URL=https://193.2.171.250:6443 \
  K3S_TOKEN=<TOKEN> \
  sh -
```

### 3.5 Namestitev MetalLB (LoadBalancer)

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml

# Počakaj, da so metallb podi Running
kubectl wait --namespace metallb-system --for=condition=ready pod --selector=app=metallb --timeout=120s

# Konfiguracija IP pool
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 193.2.171.200-193.2.171.200
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-advertisement
  namespace: metallb-system
EOF
```

### 3.6 Namestitev Longhorn (distribuiran storage)

```bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.7.1/deploy/longhorn.yaml

# Portal (port-forward):
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# Odpri: http://localhost:8080
```

#### 3.6.1 Dodajanje diskov na vse node

Longhorn zazna diske na vsakem nodu samodejno. Za dodaten disk (npr. `/dev/sdb`):
1. Odpri Longhorn UI → **Node** → izberi node → **Edit disks**
2. Dodaj nov disk (npr. `/mnt/longhorn-extra`)

#### 3.6.2 Omogočanje replica-auto-balance

```bash
kubectl edit settings -n longhorn-system replica-auto-balance
# Nastavi na "least-effort"
```

### 3.7 Namestitev aplikacije

Aplikacija se nahaja v `ostc-app_deli` repozitoriju. K8s manifesti so v `k8s/` mapi:

```bash
cd /home/admin_os/ostc-app_deli

# Namespace
kubectl create namespace sola-app

# ConfigMap
kubectl create configmap sola-config -n sola-app \
  --from-literal=APP_PORT=8002 \
  --from-literal=BASE_URL=https://ostc-app.org \
  --from-literal=PROSTORI=tablice,racunalnica,ladja,gospodinjska-ucilnica \
  ...

# Secret (prilagodi vrednosti)
kubectl create secret generic sola-secrets -n sola-app \
  --from-literal=DATABASE_URL="postgresql://sola:***@sola-db-rw.sola:5432/sola" \
  --from-literal=MAIL_USERNAME=oscuf \
  --from-literal=MAIL_FROM=os-toneta.cufarja-jesenice@guest.arnes.si \
  ...

# Deployment
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

---

## Vzdrževanje in avtomatizacija (cron jobi)

### Dnevna varnostna kopija baze (sola-db-backup)

CronJob v Kubernetes, ki vsak dan ob 02:00 naredi dump baze in ga pošlje email.

```bash
# Preveri zadnji backup
kubectl logs -n sola-app -l job-name=sola-db-backup --tail=20
```

### Dnevno poročilo o stanju (sola-daily-report)

CronJob ob 04:00 Europe/Ljubljana, ki pošlje povzetek rezervacij in stanje.

```bash
kubectl logs -n sola-app -l job-name=sola-daily-report --tail=20
```

### Import učiteljev na začetku leta

Skripta v `ostc-app_deli` repozitoriju prebere seznam s šolske spletne strani:

```bash
cd /home/admin_os/ostc-app_deli

# Dry-run
python3 scripts/import_teachers.py --dry-run

# Dejanski uvoz
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Z vključitvijo admin/tehničnega osebja
python3 scripts/import_teachers.py --base-url https://ostc-app.org --include-all
```

---

## Dodajanje novega računalnika v k3s cluster

### Priprava

1. Namesti Ubuntu Server 24.04 (glej [lokalni_zagon.md](lokalni_zagon.md))
2. Nastavi statični IP
3. Omogoči SSH

### Pridobitev tokena z obstoječega masterja

```bash
sudo cat /var/lib/rancher/k3s/server/token
```

### Priključitev kot dodatni master

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://193.2.171.250:6443 \
  K3S_TOKEN=<TOKEN> \
  sh -
```

### Preverite, da je dodan

```bash
kubectl get nodes
```

---

## Struktura repozitorija

```
ostc-app_deli/
├── app/                    # Python aplikacija (FastAPI)
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── routers/            # API endpointi
│   ├── templates/          # Jinja2 HTML
│   └── static/             # CSS, JS
├── k8s/                    # Kubernetes manifesti
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── Dockerfile
│   └── cronjob.yaml
├── scripts/                # Pomožne skripte
│   ├── import_teachers.py
│   └── db_backup.py
└── documentation/          # Dokumentacija
```

---

## AI agenti za pomoč

Na k3s nodih teče **Hermes Agent** prek Discord-a. Omogoča:

- Upravljanje aplikacije prek naravnega jezika
- Popravilo nastavitev
- Izvajanje ukazov na nodih
- Dnevna poročila

Več: https://hermes-agent.nousresearch.com/docs
