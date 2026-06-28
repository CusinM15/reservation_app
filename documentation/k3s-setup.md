🌐 **Jezik / Language:** [🇸🇮 Slovenščina](k3s-setup.md) | [🇬🇧 English](en/k3s-setup.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# ☸️ K3s Setup — Šolski App

> **Glej, k3s ti bom postavil v 20 minutah. Ampak najprej razložimo kaj delaš in zakaj.**

---

## 🧠 Kaj je Kubernetes (in k3s)? — Za tiste, ki niste spali pri informatiki

### Kubernetes / k3s — hotelski receptor za tvoje aplikacije
Predstavljaj si, da imaš aplikacijo (spletno stran, bazo, API). Daš jo Kubernetesu in on poskrbi:
- Če aplikacija crkne → jo sam zažene drugje.
- Če je preveč obiska → samodejno doda še eno kopijo.
- Če je potreben popravek → počasi zamenja stare kopije z novimi, brez izpada.

**k3s** je samo lažja, manjša različica Kubernetes — kot SmartCar namesto tovornjaka. Namenjena je manjšim setupom in robnim napravam. Ampak logika je čisto ista.

### Control-plane — možgani clustra
To je "uprava" tvojega clustra. Odloča: kam gre kateri pod, kaj se zgodi če nekaj crkne, kdo je trenutno glavni. Če control-plane crkne, cluster še vedno deluje (aplikacije tečejo naprej), ampak ne moreš več spreminjati stanja — kot podjetje brez direktorja.

### etcd — spomin clustra
etcd je majhna baza, ki hrani čisto vse: "kateri pod teče kje", "kakšna je konfiguracija", "kdo je glavni node". Če etcd izgine, cluster ne ve kdo je in kaj dela. Zato imamo etcd na obeh nodih (replikacija).

### Pod — zabojnik z aplikacijo
Najmanjša enota v Kubernetesu. Vsebuje enega ali več Docker containerjev (zabojnikov) z vsem kar aplikacija rabi — koda, knjižnice, nastavitve. Vsak pod dobi svoj IP.

### Node — fizični računalnik
To je dejanski računalnik v tvojem omrežju. V našem primeru: 2 HP ProBook laptopa. Vsak node ima nameščen k3s in lahko poganja pode.

### MetalLB — daje fiksne IP-je aplikacijam v clustru
Ko v Kubernetesu rečeš "ta aplikacija naj bo dostopna na zunanjem naslovu", potrebuješ **LoadBalancer**. Ampak Kubernetes sam po sebi ne zna dodeljevati IP-jev iz tvojega omrežja. MetalLB to počne — kot da bi rekel "daj tej aplikaciji fiksni IP 192.168.1.50".

### Longhorn — distribuiran trdi disk
Namesto da vsak pod uporablja lokalni disk (ki crkne, če pod skoči na drug node), Longhorn poskrbi, da je vsak podatek v **2 kopijah na 2 različnih računalnikih**. Če en node crkne, podatki še vedno obstajajo na drugem.

### Ingress — vhodna vrata
Ampak kaj če nočeš za vsako aplikacijo svojega IP-ja? Ingress je kot recepcija — vse pride na ena vrata, Ingress pa pogleda "aha, ta zahteva gre za sola-app, tista za drug servis" in jih pošlje naprej na pravo mesto.

---

## 📋 Arhitektura (trenutna)

> 📊 **Diagram:** [`diagrams/k3s-arhitektura.drawio`](diagrams/k3s-arhitektura.drawio) — odpri v https://app.diagrams.net/

---

## 📋 Predpogoji

- 2 fizični mašini z **Ubuntu 24.04 LTS** (tvoja HP ProBook laptopa)
- Vsaka mašina: min **2 CPU**, **4GB RAM**, **20GB disk**
- **sudo** dostop na obeh (boš rabil za namestitev)
- Mašini v istem omrežju (da se vidita — ping brez problema)
- Docker nameščen (za build slike):
  ```bash
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER
  ```
  To ti namesti Docker in doda tvoj uporabnik v skupino `docker`, da ti ni treba vsakič pisat `sudo docker`.

---

## 1. Namestitev k3s (oba noda kot control-plane)

**Zakaj oba noda kot control-plane?** V klasičnem Kubernetes setupu imaš en "glavni" node (control-plane) in več "delavcev" (workers). Ampak če imaš samo 2 noda, je škoda, da en samo "odloča" in drugi samo "dela". Zato oba nastavimo kot control-plane — oba lahko poganjata aplikacije in oba lahko prevzameta vodenje, če eden crkne.

### 1.1 Namesti k3s na prvem nodu (k3s-1)

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --disable=traefik \         # Izklopimo vgrajeni prometni usmerjevalnik (Traefik). Ne rabimo ga, ker bomo uporabili MetalLB za dodeljevanje IP-jev.
  --disable=servicelb \       # Izklopimo k3s-ov lastni LoadBalancer — tudi tega ne rabimo, ker MetalLB dela bolje.
  --write-kubeconfig-mode=644 \  # Dovoli branje kubeconfig datoteke navadnemu uporabniku (ni treba vsakič sudo).
  --cluster-cidr=10.42.0.0/16 \ # Razred IP-jev za pode (notranje omrežje znotraj clustra).
  --service-cidr=10.43.0.0/16 \ # Razred IP-jev za servise (drugo notranje omrežje za servise).
  --node-ip={{K3S_1_IP}}        # Kateri IP naj uporablja ta node. Vstavi notranji IP prvega laptopa (npr. 192.168.1.10).
```

**Kaj se zgodi zdaj?** curl prenesi skripto z get.k3s.io, skripta pa namesti k3s v `server` načinu (kot control-plane). Vse `--disable` zastavice izklapljajo stvari, ki jih ne rabimo. `--node-ip` pove k3s-u "glej, tvoj IP je ta", kar je pomembno, če ima mašina več omrežnih kartic.

### 1.2 Pridobi token (ključ za pridružitev drugega noda)

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```
To je kot **geslo za vstop v cluster**. Drugi node ga rabi, da se lahko pridruži prvemu. Skopiraj ga nekam — rabil ga boš v naslednjem koraku.

### 1.3 Namesti k3s na drugem nodu (k3s-2)

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://{{K3S_1_IP}}:6443 \  # Poveži se na prvi node (k3s-1) na vratih 6443 — to so privzeta Kubernetes API vrata.
  --token <TOKEN> \                     # Token iz prejšnjega koraka — dokazilo, da smeš vstopiti v cluster.
  --disable=traefik \                   # Isti razlog kot na prvem nodu — ne rabimo Traefika.
  --disable=servicelb \                 # Tudi Servicelb ne rabimo.
  --write-kubeconfig-mode=644 \
  --node-ip={{K3S_2_IP}}               # IP drugega laptopa.
```

**Pomembno:** `--server https://{{K3S_1_IP}}:6443` pomeni "ne zaženi novega clustra, ampak se pridruži obstoječemu". Brez tega bi drugi node poskusil postati svoj lasten cluster — in imel bi 2 ločena clustra namesto enega.

### 1.4 Preveri

```bash
kubectl get nodes
# NAME    STATUS   ROLES                AGE
# k3s-1   Ready    control-plane,etcd   1m
# k3s-2   Ready    control-plane,etcd   30s
```

**Če vidiš oba kot `Ready` — čestitam, cluster stoji! 🎉** Če je kateri `NotReady`, počakaj minuto in poskusi še enkrat — včasih etcd rabi nekaj sekund, da se uskladi.

---

## 2. Namestitev MetalLB (LoadBalancer)

**Zakaj MetalLB?** Kubernetes sam nima pojma o tvojem fizičnem omrežju. Ko rečeš "daj tej aplikaciji zunanji IP", MetalLB pogleda IP range, ki si mu ga dal, in reče "ta IP je prost, dam ga tej aplikaciji". Brez MetalLB bi aplikacija dobila samo notranji IP, ki je nedostopen od zunaj.

```bash
# 1. Namesti MetalLB v cluster
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml

# 2. Počakaj, da so vsi MetalLB podi zagnani (--all pomeni "vsi podi v namespace-u")
kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=120s

# 3. Uporabi konfiguracijo — pove MetalLB-ju kateri IP-ji so na voljo
kubectl apply -f k8s/cluster/metallb-config.yaml
```

**Počakaj s `wait --for=condition=ready pod --all`** — to blokira, dokler niso vsi MetalLB podi zares pripravljeni. Če greš naprej brez tega, bo MetalLB config padel na neobstoječo storitev in boš čakal v nedogled.

---

## 3. Namestitev Longhorn (distribuiran disk)

**Zakaj Longhorn?** Če imaš aplikacijo, ki shranjuje podatke (baza, slike, dokumenti), in ta pod crkne in se zažene na drugem nodu — kje so zdaj podatki? Na prvem nodu, ki je mrtev. **Longhorn to reši tako, da vsak podatek hrani v 2 kopijah na 2 različnih računalnikih.** Če eden crkne, drugi še vedno dela.

### 3.1 Predpogoji na vsakem nodu

```bash
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

- **open-iscsi** — orodje, ki omogoča Longhornu, da se poveže z oddaljenimi diski prek iSCSI protokola (kot bi rekel "priklopi tuji disk prek omrežja").
- **nfs-common** — podpora za NFS (Network File System), ki ga Longhorn uporablja za nekatere operacije.

**To namesti na OBA noda.** Longhorn na vsakem nodu uporablja lokalni disk, ampak za replikacijo rabi ta orodja.

### 3.2 Namesti Helm, nato Longhorn

**Helm je kot app store za Kubernetes.** Namesto da ročno pišeš YAML datoteke za vsako komponento, samo poveš "daj mi Longhorn" in Helm poskrbi za vse.

```bash
# Namesti Helm (če ga še nimaš)
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | sudo bash

# Dodaj Longhorn repozitorij v Helm
helm repo add longhorn https://charts.longhorn.io
helm repo update

# Ustvari namespace za Longhorn
kubectl create namespace longhorn-system

# Namesti Longhorn s Helm chartom
helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --version 1.9.0 \
  --set defaultSettings.defaultReplicaCount=2 \      # Privzeto: vsak podatek v 2 kopijah
  --set persistence.defaultClassReplicaCount=2 \      # Enako za persistence volumes
  --set defaultSettings.replicaSoftAntiAffinity=true \ # "Raje" daj replike na različna noda (če je možno)
  --set persistence.defaultClass=true                 # Longhorn naj bo privzeti StorageClass
```

**Zakaj replicaCount=2?** Ker imamo 2 noda. 1 kopija = brez zaščite. 2 kopiji = če en node crkne, so podatki na drugem. 3 kopije bi bile še boljše, ampak za 2 noda fizično ne greš — kam bi dal tretjo kopijo?

### 3.3 Omogoči replica-auto-balance

```bash
kubectl patch settings.longhorn -n longhorn-system replica-auto-balance \
  --type='merge' -p '{"value":"least-effort"}'
```

**Kaj to pomeni?** Longhounova "pamet" za razporejanje kopij. Če je eden od nodov poln, Longhorn samodejno premakne kakšno kopijo na drugega. `least-effort` = "naredi kar je najlažje, ne prerazporejaj po nepotrebnem".

---

## 4. CloudNativePG (PostgreSQL baza)

### 4.1 Namesti CNPG operator

CNPG (CloudNativePG) je Kubernetes operator za PostgreSQL. **Operator** je kot "robot-vzdrževalec" — sam skrbi za bazo: varnostne kopije, replikacijo, failover (ko ena baza crkne, druga prevzame).

```bash
# Dodaj CNPG repozitorij v Helm
helm repo add cnpg https://cloudnative-pg.github.io/charts

# Namesti CNPG operator v svoj namespace
helm install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system \
  --create-namespace   # Ustvari namespace, če še ne obstaja
```

### 4.2 Ustvari CNPG cluster

```bash
kubectl apply -f sola-cnpg-cluster.yaml
```

Primer `sola-cnpg-cluster.yaml`:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: sola-db
  namespace: sola
spec:
  instances: 2                    # Dve kopiji baze (ena primarna, ena rezervna)
  storage:
    size: 1Gi                    # Vsaka dobi 1GB diska (na Longhornu = podvojeno)
    storageClass: longhorn        # Shranjuj na Longhorn (ne lokalno!)
  bootstrap:
    initdb:
      database: sola             # Ime baze ob prvem zagonu
      owner: sola                # Lastnik baze
  affinity:
    enablePodAntiAffinity: true   # "Ne daj obeh baz na isti računalnik"
    podAntiAffinityType: preferred # "Raje ne, ampak če ni druge možnosti, pa čeprav"
    topologyKey: kubernetes.io/hostname  # Glede na fizični računalnik
  enablePDB: true                # PodDisruptionBudget — poskrbi, da vsaj ena baza vedno teče
  failoverDelay: 30              # ⏱ 30 sekund čakanja, preden CNPG razglasi, da je primarni
                                  # node mrtev in postavi rezervnega za glavnega.
                                  # To prepreči lažne alarme ob kratkotrajnih izpadih.
```

**Zakaj `failoverDelay: 30`?** Predstavljaj si, da glavna baza za trenutek zamrzne (network glitch, visok CPU load). CNPG počaka 30 sekund, preden reče "a je ta node res mrtev ali se samo matra?". Če se v 30 sekundah zbudi — super, ni bilo treba nič menjat. Če ne — šele takrat se zgodi zamenjava. To prepreči **lažne alarme** in po nepotrebnem preklapljanje.

---

## 5. Namestitev aplikacije

### 5.1 Build slike

```bash
cd /home/admin/reservation_app
docker build -t sola-app:latest .   # Zgradi Docker sliko iz Dockerfile-a v trenutni mapi
docker push sola-app:latest         # Pošlji sliko v registri, da jo Kubernetes lahko potegne
```

### 5.2 Ustvari namespace in Secret

```bash
kubectl create namespace sola-app

kubectl create secret generic sola-secrets \
  --namespace sola-app \
  --from-literal=MAIL_USERNAME=oscuf \
  --from-literal=MAIL_PASSWORD=*** \
  --from-literal=MAIL_SERVER=mail.arnes.si \
  --from-literal=MAIL_PORT=587 \
  --from-literal=MAIL_FROM=sola@example.com \
  --from-literal=BACKUP_EMAIL=admin@sola.si \
  --from-literal=DATABASE_URL=postgresql://sola:***@sola-db-rw.sola:5432/sola
```

**`--from-literal`** — podatke zapiše direktno v ukazni vrstici. V produkciji bi namesto tega uporabil `--from-file` ali jih vzel iz Azure Key Vault / HashiCorp Vault, ampak za šolsko aplikacijo je to dovolj.

**`DATABASE_URL`** — pove aplikaciji, kje je baza. `sola-db-rw` je servis, ki kaže na **trenutno primarno** bazo (rw = read-write). `sola.sola` = ime servisa v namespace-u `sola`.

### 5.3 Deploy z overlay-i

```bash
kubectl apply -k k8s/app/overlays/production-lb
```

**`-k` = Kustomize.** To ni navaden `apply` — Kustomize ti omogoča, da imaš osnovno konfiguracijo in potem "overlay" (nadgradnjo) za vsako okolje (dev, staging, production). Tukaj uporabljamo `production-lb` overlay, ki doda MetalLB LoadBalancer.

---

## 6. Vzdrževanje

### Posodobitev aplikacije

```bash
cd /home/admin/reservation_app
git pull                          # Potegni zadnjo kodo
docker build -t sola-app:latest . # Zgradi novo sliko
docker push sola-app:latest       # Pošlji v registri
kubectl rollout restart -n sola-app deployment/sola-app  # Počasi zamenjaj stare pode z novimi
kubectl rollout status -n sola-app deployment/sola-app   # Spremljaj, da so vsi novi podi zagnani
```

**`rollout restart`** — Kubernetes ne ubije vseh podov naenkrat. En po en jih zamenja (rolling update), tako da aplikacija nikoli ni popolnoma nedosegljiva.

### Dodajanje novega noda

```bash
# Na masterju pridobi token
sudo cat /var/lib/rancher/k3s/server/node-token

# Na novem nodu:
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://<MASTER_IP>:6443 \
  --token <TOKEN> \
  --node-ip <NOVI_IP> \
  --disable traefik --disable=servicelb

# Namesti Longhorn predpogoje
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

**Ne pozabi:** Ko dodaš tretji node, razmisli o povečanju Longhorn replicaCount na 3 — potem imaš podatke na vseh treh nodih.

---

## 7. Pogoste težave

| Težava | Rešitev |
|--------|---------|
| Pod se ne zažene | `kubectl logs -n sola-app <pod>` — poglej log, kaj se zgodi ob zagonu |
| DB se ne poveže | Preveri `sola-db-rw` endpoint: `kubectl get endpoints -n sola sola-db-rw` — ali servis sploh obstaja? |
| MetalLB ne dodeli IP | `kubectl -n metallb-system get ipaddresspool` — preveri, če si sploh definiral IP range |
| Longhorn volume stuck | Preveri v Longhorn UI: `kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80` — odpri `localhost:8080` v brskalniku |

---

## 🚨 Pogoste napake pri namestitvi

### ❌ 1. Pozabljen `--disable=servicelb`
Če ne izklopiš k3s-ovega vgrajenega ServiceLB, se bosta MetalLB in k3s kregala za iste servise. MetalLB ne bo dobil IP-ja, ker ga bo k3s ServiceLB prej pobral. **Rešitev:** vedno uporabi oba: `--disable=traefik --disable=servicelb`.

### ❌ 2. Zamenjani IP-ji nodov
`--node-ip={{K3S_1_IP}}` na prvem nodu in `--node-ip={{K3S_2_IP}}` na drugem — pomešati ju pomeni, da bo k3s mislil, da je prvi node na naslovu drugega. Podi se ne bodo mogli povezati. **Rešitev:** pred namestitvijo zaženi `ip a` in prepiši točen IP vsake mašine.

### ❌ 3. Nepotrpežljivost — ne počakaš, da so podi `Ready`
MetalLB, Longhorn in CNPG rabijo čas, da se zaženejo. Če greš naprej brez `kubectl wait --for=condition=ready pod --all`, bo naslednji ukaz padel, ker storitev še ne obstaja. **Rešitev:** po vsaki namestitvi zaženi `kubectl get pods -n <namespace>` in počakaj na `Running`/`Ready`.

### ❌ 4. Longhorn nameščen samo na enem nodu
open-iscsi in nfs-common je treba namestiti na **vsakem** nodu posebej. Če pozabiš na drugem, Longhorn na tistem nodu ne bo mogel pripeti diskov. **Rešitev:** zaženi `sudo apt-get install -y open-iscsi nfs-common` na obeh.

### ❌ 5. Napačna `DATABASE_URL` v Secret-u
Če v `DATABASE_URL` napišeš napačen hostname (npr. `sola-db` namesto `sola-db-rw`), se aplikacija ne bo mogla povezati na bazo. **Rešitev:** vedno preveri ime servisa: `kubectl get svc -n sola` ti pokaže točna imena.

---

## 📖 Slovarček pojmov

| Pojem | Pomen (ELI5) |
|-------|-------------|
| **Kubernetes (k8s)** | Hotelski receptor za aplikacije — upravlja, kje in kako tečejo |
| **k3s** | Lažja verzija Kubernetes — kot SmartCar namesto tovornjaka |
| **Control-plane** | Možgani clustra — odloča kam gre kaj |
| **etcd** | Spomin clustra — če ta izgine, cluster ne ve kdo je |
| **Pod** | Zabojnik z aplikacijo in vsem kar rabi |
| **Node** | Fizični računalnik v clustru |
| **Cluster** | Skupina računalnikov (nodov), ki delujejo kot eno |
| **MetalLB** | Daje fiksne IP-je aplikacijam v clustru — kot receptor, ki vsaki sobi dodeli sobo |
| **Longhorn** | Distribuiran trdi disk — vsak podatek v 2 kopijah na 2 različnih računalnikih |
| **Ingress** | Vhodna vrata — vsi gredo skozi ena vrata, Ingress jih pošlje naprej |
| **LoadBalancer** | Servis, ki aplikaciji dodeli zunanji IP |
| **Namespace** | Mapa v Kubernetesu — ločuje različne projekte med seboj |
| **Helm** | App store za Kubernetes — poveš kateri paket hočeš in Helm ga namesti |
| **Operator** | Robot-vzdrževalec — avtomatsko skrbi za kompleksne storitve (baze, monitoring) |
| **Secret** | Kubernetes shramba za gesla in ključe — ni v čisti tekstovni datoteki |
| **Replica** | Kopija — več kopij = boljša zanesljivost |
| **Failover** | Ko ena komponenta crkne, druga samodejno prevzame |
| **Rolling update** | Počasi zamenjujemo stare pode z novimi — brez izpada |
| **StorageClass** | Tip diska v Kubernetesu (npr. "hiter SSD" ali "počasen HDD" ali "Longhorn") |
| **ClusterCIDR** | Razred IP-jev za pode — notranje omrežje znotraj clustra |
| **ServiceCIDR** | Razred IP-jev za servise — drugo notranje omrežje |
| **Kubeconfig** | Datoteka z nastavitvami za dostop do clustra — kot osebna izkaznica |
| **Token** | Geslo za pridružitev clustra — brez njega ne moreš noter |
