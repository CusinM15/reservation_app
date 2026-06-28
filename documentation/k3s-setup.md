🌐 **Jezik / Language:** [🇸🇮 Slovenščina](k3s-setup.md) | [🇬🇧 English](en/k3s-setup.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# ☸️ K3s Setup — Šolski Rezervacijski Sistem (ostc-app)

> **Kaj sploh je Kubernetes in zakaj ga rabimo?**
>
> Kubernetes (krajše K8s) je **orodje za vodenje zbirke programov** — kot bi imeli pametnega hišnika,
> ki pazi, da vsi programi na strežnikih tečejo, se samodejno zaženejo, če padejo, in porazdelijo
> obiskovalce med več strežnikov. Če en strežnik crkne, Kubernetes poskrbi, da program še vedno
> deluje na drugem. Brez njega bi morali vse to delati ročno — in ob 3h zjutraj, ko pade baza, to
> ni zabavno.
>
> **Kaj je k3s?**
>
> k3s je **lažja verzija Kubernetes** — kot Fiat Punto namesto BMW-ja, ampak za šolo čisto dovolj.
> Originalni Kubernetes (»vanilla K8s«) je ogromen, težek in požre veliko spomina. k3s je zmanjšan
> na eno samo izvršljivo datoteko, porabi manj kot polovico RAM-a, pa vseeno naredi čisto vse,
> kar rabimo. Odlično za manjše strežnike, kot sta naša HP ProBook laptopa.

## 📋 Arhitektura (trenutna)

Naš sistem teče na **dveh HP ProBook laptopih** — oba igrata vlogo krmilnika (control-plane) in
hkrati nosita podatke (etcd). Nimamo ločenih delavskih nodov (worker nodes). To je lažja
konfiguracija, ki za šolski sistem povsem zadostuje.

> 📐 **Diagram:** diagrams/k3s-setup-arhitektura.drawio

### Razlaga arhitekture v preprosti slovenščini:

| Sestavina | Vloga | Enostavna razlaga |
|-----------|-------|-------------------|
| **Cloudflare** | Vhodna vrata (DNS + zaščita) | Ko nekdo vnese `ostc-app.org`, Cloudflare pove, na katerem IP-ju aplikacija živi. Ščiti nas tudi pred napadi. |
| **MetalLB** | Razdeljevalec prometa | Dodeli javni IP in usmerja obiskovalce na enega od dveh strežnikov. |
| **k3s-1 in k3s-2** | Strežnika (HP ProBook laptopa) | Dejanski računalniki, ki poganjajo aplikacijo. Oba sta enakovredna — če eden crkne, drugi prevzame. |
| **sola-app** | Sama aplikacija (FastAPI) | Program, prek katerega učitelji rezervirajo prostore in opremo. |
| **sola-db-1 / sola-db-2** | Podatkovna baza (PostgreSQL) | Hrani vse rezervacije, uporabnike in nastavitve. Baza se samodejno podvaja (replicira) med oba strežnika. |
| **Longhorn** | Shramba (disk) | Poskrbi, da se datoteke in podatki shranjujejo na obeh laptopih, tako da jih ne izgubimo, če eden odpove. |

---

## 📋 Predpogoji — Kaj moramo imeti pripravljeno, preden začnemo?

Preden sploh začnemo z nameščanjem, moramo imeti:

- **2 fizični mašini z Ubuntu 24.04 LTS** — v našem primeru dva HP ProBook laptopa
- Vsaka mašina: vsaj **2 CPU jedri**, **4 GB RAM**, **20 GB diska** (več je vedno bolje)
- **sudo dostop** na obeh — to pomeni, da imamo skrbniške pravice (lahko nameščamo programe)
- Mašini morata biti v **istem omrežju** — da se lahko med seboj pogovarjata
- **Docker** nameščen (potrebujemo ga za gradnjo slik aplikacije):

```bash
# Docker namestimo z uradnim skriptom — požene se in vse uredi samodejno
curl -fsSL https://get.docker.com | sudo sh
# Dodamo svojega uporabnika v skupino 'docker', da nam ni treba ves čas pisati 'sudo'
sudo usermod -aG docker $USER
```

> ⚠️ Po `usermod` se **odjavite in ponovno prijavite**, da začne veljati.

---

## 1. Namestitev k3s (oba noda kot control-plane)

### 1.1 Namesti k3s na prvem nodu (k3s-1)

To je trenutek, ko prvi laptop postane **gospodar (master)** k8s gruče.

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --disable=traefik \
  --disable=servicelb \
  --write-kubeconfig-mode=644 \
  --cluster-cidr=10.42.0.0/16 \
  --service-cidr=10.43.0.0/16 \
  --node-ip={{K3S_1_IP}}
```

#### 🔍 Kaj se dogaja?

Ukaz naredi naslednje:

1. **`curl -sfL https://get.k3s.io`** — z uradne k3s spletne strani prenese namestitveni skript
2. **`| sh -s - server`** — požene skript in mu reče, naj namesti **strežniško** (server) različico. Če bi napisali `agent` namesto `server`, bi namestili le delavca (worker), ki ne more sam sprejemati odločitev.
3. **`--disable=traefik`** — **IZKLOPIMO** vgrajeni Traefik (spletni vratar / reverse proxy). Zakaj? Ker bomo namesto njega uporabili **MetalLB**, ki je boljši za naše potrebe. Če tega ne izklopimo, bi imeli dva vratarja, ki bi se prepirala, kdo upravlja promet.
4. **`--disable=servicelb`** — **IZKLOPIMO** vgrajeni Service Load Balancer. Spet — uporabili bomo kakovostnejši MetalLB namesto osnovne k3s rešitve.
5. **`--write-kubeconfig-mode=644`** — omogoči, da lahko naš uporabnik (ne samo root) uporablja `kubectl` ukaze. Brez tega bi morali vsakemu ukazu dodati `sudo`.
6. **`--cluster-cidr=10.42.0.0/16`** — določi **naslovni prostor za zbirke (pode)**. Vsak programski zabojnik (pod) dobi svoj IP znotraj tega območja.
7. **`--service-cidr=10.43.0.0/16`** — določi **naslovni prostor za storitve (services)**. Storitve so javna vrata do programov.
8. **`--node-ip={{K3S_1_IP}}`** — pove k3s, kateri IP naj uporabi za ta računalnik. To je **notranji omrežni IP** (npr. 192.168.1.10), ne javni.

#### ⚠️ Kaj se zgodi, če izpustimo `--disable=traefik`?

Na vsakem nodu bi se zagnal Traefik, ki bi poskušal odpreti vrata 80 in 443. Potem bi namestili še MetalLB in oba bi se borila za ista vrata. Aplikacija ne bi delovala, logi bi bili polni napak »port already in use«. **Zato Traefik in ServiceLB vedno izklopimo.**

#### ⚠️ Kaj se zgodi, če izpustimo `--write-kubeconfig-mode=644`?

Vsak `kubectl` ukaz bi zahteval `sudo`. Ker bomo `kubectl` uporabljali ves čas, bi bilo to zelo nepraktično. To je nastavitev za udobje, ne nujnost.

---

### 1.2 Pridobi token — »vstopnica« za nove člane gruče

Token je **kot geslo za zabavo**, ki novemu računalniku dovoli vstop v gručo (cluster).
Brez njega se drugi strežnik ne more povezati s prvim.

```bash
# Preberemo token iz datoteke, ki jo je k3s ustvaril med namestitvijo
sudo cat /var/lib/rancher/k3s/server/node-token
```

#### 🔍 Kaj se dogaja?

K3s je med namestitvijo ustvaril skrivno datoteko `/var/lib/rancher/k3s/server/node-token`. V njej je niz znakov, podoben temu:

```
K107f8a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0::server:node:1234567890abcdef
```

Ta niz bomo uporabili v naslednjem koraku, ko bomo drugi laptop dodajali v gručo.

---

### 1.3 Namesti k3s na drugem nodu (k3s-2)

Zdaj drugi laptop povežemo v gručo. Vidite, kako uporabimo token?

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://{{K3S_1_IP}}:6443 \
  --token <TOKEN> \
  --disable=traefik \
  --disable=servicelb \
  --write-kubeconfig-mode=644 \
  --node-ip={{K3S_2_IP}}
```

#### 🔍 Kaj se dogaja?

Razlika od prve namestitve:

1. **`--server https://{{K3S_1_IP}}:6443`** — to pove drugemu laptopu: »Poveži se s prvim laptopom na vratih 6443 (to so privzeta k3s vrata za pogovarjanje med strežniki).« Brez tega bi drugi laptop poskušal ustvariti **novo, ločeno gručo** — in ne bi pridružil obstoječi.
2. **`--token <TOKEN>`** — »vstopnica«, ki smo jo pridobili v prejšnjem koraku. Brez pravilnega tokena prvi strežnik zavrne povezavo.

Vse ostalo (`--disable=traefik`, `--disable=servicelb`, ...) je enako kot na prvem.

---

### 1.4 Preveri, da oba laptopa delujeta skupaj

```bash
kubectl get nodes
# NAME    STATUS   ROLES                AGE
# k3s-1   Ready    control-plane,etcd   1m
# k3s-2   Ready    control-plane,etcd   30s
```

#### 🔍 Kaj se dogaja?

`kubectl get nodes` vpraša gručo: »Kdo si ti in kdo so tvoji prijatelji?«

Če vidimo oba noda s STATUS `Ready`, pomeni, da se drugi laptop uspešno pridružil prvemu in oba delujeta. Izpis `ROLES: control-plane,etcd` pomeni, da oba laptopa:
- **control-plane** — sprejemata odločitve (kaj naj se zgodi, če nekaj pade)
- **etcd** — hranita podatke o stanju gruče (kaj je nameščeno, kje teče)

#### ⚠️ Če node ni `Ready`?

Pogledamo log-e:
```bash
sudo journalctl -u k3s --no-pager | tail -50
```
Najpogostejši vzroki:
- Napačen token
- Napačen `--node-ip`
- Ogenj (firewall) blokira vrata 6443
- Laptopa nista v istem omrežju

---

## 2. Namestitev MetalLB — »prometni policist« za našo gručo

MetalLB je **orodje, ki programom v Kubernetes dodeli prave omrežne naslove (IP)**.
Predstavljajte si ga kot prometnega policista, ki obiskovalce usmerja na pravi strežnik.

Brez MetalLB-ja bi vsi programi dobili samo notranje IP-je (znotraj gruče) in ne bi bili
dostopni od zunaj. Z MetalLB-jem dobijo svoj pravi IP v našem omrežju.

```bash
# 1. Namestimo MetalLB v gručo (prenese in zažene vse potrebno)
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml

# 2. Počakamo, da so vsi MetalLB delčki (pods) pripravljeni
kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=120s

# 3. Uporabimo našo konfiguracijo (IP range, ki ga lahko MetalLB deli)
kubectl apply -f k8s/cluster/metallb-config.yaml
```

#### 🔍 Kaj se dogaja?

1. **`kubectl apply -f https://...`** — prenesemo in namestimo MetalLB iz uradnega vira.
2. **`kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=120s`** — počakamo do 2 minuti, da se MetalLB zažene. Brez tega bi naslednji ukaz morda sprožil napako, ker MetalLB še ne bi bil pripravljen.
3. **`kubectl apply -f k8s/cluster/metallb-config.yaml`** — uporabimo konfiguracijsko datoteko, ki MetalLB-ju pove: »Kateri IP naslovi so na voljo za razdeljevanje?«

Datoteka `k8s/cluster/metallb-config.yaml` mora vsebovati IP range, npr.:

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: primary
  namespace: metallb-system
spec:
  addresses:
  - {{LB_IP}}-{{LB_IP}}  # npr. 192.168.1.200-192.168.1.200
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: l2-advert
  namespace: metallb-system
spec:
  ipAddressPools:
  - primary
```

---

## 3. Namestitev Longhorn — pametna shramba, ki ne izgubi podatkov

Longhorn je **sistem za shranjevanje podatkov v Kubernetes**. Omogoča, da se podatki
samodejno podvajajo (replicirajo) med oba laptopa. Če eden crkne, podatki ostanejo
na drugem.

### 3.1 Predpogoji na vsakem nodu — orodja, ki jih Longhorn potrebuje

```bash
# open-iscsi: orodje, ki Linuxu omogoča povezovanje z oddaljenimi diski
# (iSCSI je protokol za dostop do diskov prek omrežja)
sudo apt-get install -y open-iscsi

# nfs-common: orodje za dostop do datotek prek omrežja
# (NFS je protokol za souporabo map in datotek po omrežju)
sudo apt-get install -y nfs-common

# Zaženemo iscsid (strežnik za iSCSI povezave) in mu rečemo,
# naj se samodejno zažene ob vsakem zagonu računalnika
sudo systemctl enable --now iscsid
```

#### 🔍 Kaj se dogaja?

- **open-iscsi** — Longhorn uporablja iSCSI protokol za komunikacijo z diski prek omrežja. Brez tega programa Longhorn ne more dostopati do prostora na disku.
- **nfs-common** — dodatno orodje za deljenje datotek prek omrežja. Nekatere starejše Longhorn funkcije ga uporabljajo.
- **systemctl enable --now iscsid** — `enable` pomeni, da se bo iscsid zagnal ob vsakem vklopu računalnika. `--now` pomeni, da ga zaženemo takoj, brez ponovnega zagona.

#### ⚠️ Kaj se zgodi, če tega ne namestimo?

Longhorn se bo namestil, vendar ne bo mogel ustvariti nobenega diska (volume). Podatkov ne bo kam shraniti. Vse, kar potrebuje prostor na disku, bo ostalo v stanju »Pending«.

---

### 3.2 Namesti Helm (upravitelj paketov za Kubernetes) in Longhorn

Helm je kot »trgovina z aplikacijami« za Kubernetes. Namesto da ročno nameščamo vsako
datoteko posebej, s Helmovimi grafi (charts) namestimo vse naenkrat.

```bash
# Namestitev Helma (upravitelja paketov)
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | sudo bash

# Dodamo Longhorn trgovino (repo)
helm repo add longhorn https://charts.longhorn.io

# Osvežimo seznam razpoložljivih paketov
helm repo update

# Ustvarimo mapo (namespace) za Longhorn
kubectl create namespace longhorn-system

# Namestimo Longhorn s posebnimi nastavitvami
helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --version 1.9.0 \
  --set defaultSettings.defaultReplicaCount=2 \
  --set persistence.defaultClassReplicaCount=2 \
  --set defaultSettings.replicaSoftAntiAffinity=true \
  --set persistence.defaultClass=true
```

#### 🔍 Kaj pomenijo te nastavitve?

| Nastavitev | Pomen | Enostavna razlaga |
|------------|-------|-------------------|
| `defaultReplicaCount=2` | Vsak kos podatkov naj bo shranjen v **2 izvodih** | Če en laptop crkne, drugi še vedno ima podatke |
| `defaultClassReplicaCount=2` | Enako, ampak za privzeti razred shranjevanja | Dvojna varnost |
| `replicaSoftAntiAffinity=true` | Podvode (replike) naj bodo na različnih laptopih | Če sta oba izvoda na istem laptopu in ta crkne, so podatki izgubljeni. Ta nastavitev jih poskuša razporediti na različne nod-e. |
| `defaultClass=true` | Longhorn naj bo **privzeti način shranjevanja** v celotni gruči | Vsi programi bodo samodejno uporabljali Longhorn, razen če izrecno zahtevajo kaj drugega |

---

### 3.3 Omogoči samodejno uravnoteženje podvodov (replica-auto-balance)

Ko dodamo nove diske ali ko se prostor na enem laptopu zmanjša, želimo, da Longhorn
samodejno prerazporedi podatke.

```bash
kubectl patch settings.longhorn -n longhorn-system replica-auto-balance \
  --type='merge' -p '{"value":"least-effort"}'
```

#### 🔍 Kaj se dogaja?

- **`kubectl patch`** — spremenimo obstoječo nastavitev v Longhornu
- **`replica-auto-balance`** — ime nastavitve, ki uravnoveša podvode
- **`least-effort`** — Longhorn naj se trudi uravnotežiti, vendar naj ne seli podatkov po nepotrebnem (to bi upočasnilo delovanje)

Druge možnosti so: `disabled` (ne uravnoteži) in `full` (vedno uravnoteži, tudi če to upočasni sistem). `least-effort` je zlata sredina.

---

## 4. CloudNativePG (CNPG) — pametna podatkovna baza, ki skrbi sama zase

### 4.1 Kaj je »operator« in zakaj ga rabimo?

**Operator** je kot **avtomatski skrbnik baze**. Namesto da bi ročno nameščali,
posodabljali, varnostno kopirali in popravljali bazo, to namesto nas počne operator.

Brez operatorja bi morali:
- Ročno namestiti PostgreSQL
- Ročno nastaviti podvajanje (replikacijo) med laptopoma
- Ročno popraviti bazo, če pade
- Ročno narediti varnostne kopije
- Ročno zamenjati glavno bazo (failover) ob okvari

Z operatorjem (CloudNativePG) pa:
- Sam namesti bazo
- Sam poskrbi za podvajanje
- Sam popravi bazo, če pade
- Sam naredi varnostne kopije (če nastavimo)
- Sam zamenja glavno bazo, če ena crkne — v 30 sekundah

---

### 4.2 Namesti CNPG operator

```bash
# Dodamo CNPG trgovino
helm repo add cnpg https://cloudnative-pg.github.io/charts

# Namestimo operator v svoj namespace (mapo)
helm install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system \
  --create-namespace
```

#### 🔍 Kaj se dogaja?

- **`helm repo add cnpg https://...`** — dodamo naslov trgovine, kjer je CNPG operator
- **`helm install cnpg cnpg/cloudnative-pg`** — namestimo operator v gručo
- **`--namespace cnpg-system`** — vse datoteke operatorja bodo v mapi `cnpg-system`
- **`--create-namespace`** — če mapa `cnpg-system` še ne obstaja, jo ustvari

---

### 4.3 Ustvari bazo (CNPG cluster) z dvema izvodoma

```bash
kubectl apply -f sola-cnpg-cluster.yaml
```

#### 🔍 Vsebina `sola-cnpg-cluster.yaml`:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: sola-db
  namespace: sola
spec:
  instances: 2                    # dva izvoda baze (primarna + replica)
  storage:
    size: 1Gi                     # vsaka baza dobi 1 GB prostora
    storageClass: longhorn        # shramba na Longhorn disku
  bootstrap:
    initdb:
      database: sola              # ime baze
      owner: sola                 # uporabniško ime za dostop do baze
  affinity:
    enablePodAntiAffinity: true   # replici naj bosta na različnih laptopih
    podAntiAffinityType: preferred
    topologyKey: kubernetes.io/hostname
  enablePDB: true                 # PodDisruptionBudget — pazi, da vsaj ena baza vedno teče
  failoverDelay: 30               # po 30 sekundah nedelovanja glavne baze prevzame replica
```

#### 🔍 Razlaga ključnih nastavitev:

- **`instances: 2`** — imeli bomo dve bazi: ena je glavna (primary), druga je podvod (replica). Ko se podatki zapišejo v glavno, se samodejno prenesejo še v podvod.
- **`storageClass: longhorn`** — baza bo shranjena na Longhorn disku (ki že sam podvaja podatke med oba laptopa). Tako imamo **dvojno varnost**: CNPG podvaja bazo, Longhorn pa še diske.
- **`enablePodAntiAffinity: true`** — poskrbi, da oba izvoda baze **nista na istem laptopu**. Če sta oba na istem in ta crkne, nimamo več baze.
- **`failoverDelay: 30`** — če glavna baza pade, CNPG počaka 30 sekund (da morda ni le začasna težava), nato pa podvod razglasi za novo glavno bazo.

---

## 5. Namestitev aplikacije (sola-app)

### 5.1 Zgradi sliko aplikacije

```bash
# Greemo v mapo z aplikacijo
cd /home/admin/reservation_app

# Zgradimo Docker sliko (kot bi naredili arhiv celotnega programa)
docker build -t sola-app:latest .

# Pošljemo sliko v register (shrambo slik), da jo lahko Kubernetes povleče
docker push sola-app:latest
```

#### 🔍 Kaj se dogaja?

- **`docker build -t sola-app:latest .`** — prebere `Dockerfile` v trenutni mapi in naredi sliko (archive) programa. `-t sola-app:latest` določi ime in oznako (tag). Pike (`.`) pomeni »v trenutni mapi«.
- **`docker push sola-app:latest`** — naloži sliko v spletno shrambo (Docker Hub ali naš lastni register), od koder jo bo Kubernetes prenesel na oba laptopa.

---

### 5.2 Ustvari namespace in skrivnosti (Secrets)

```bash
# Ustvarimo mapo (namespace) za aplikacijo
kubectl create namespace sola-app

# Ustvarimo skrivnosti — občutljive podatke, ki jih aplikacija potrebuje
kubectl create secret generic sola-secrets \
  --namespace sola-app \
  --from-literal=MAIL_USERNAME=oscuf \
