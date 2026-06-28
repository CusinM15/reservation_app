🌐 **Jezik / Language:** [🇸🇮 Slovenščina](main.md) | [🇬🇧 English](en/main.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

> 🛠️ **Prilagodi dokumentacijo svojim IP-jem**
>
> Vsa dokumentacija uporablja centralno datoteko `.env.ip`, kjer so definirani
> vsi IP-naslovi, porti in domene. Želiš dokumentacijo s svojimi podatki?
>
> ```bash
> cd documentation
> nano .env.ip                          # vnesi svoje IP-je
> ./replace-ips.sh                      # dokumentacija se prilagodi
> ```
>
> Skripta zamenja vse IP-je v `.md` datotekah. Po zagonu lahko komande
> neposredno kopiraš in prilepiš v terminal — delujejo brez spreminjanja.
>
> > 💡 **Opomba:** Placeholderji ({{LB_IP}}, {{K3S_1_IP}}, itd.) ostanejo tudi v `.drawio` diagramih — skripta `replace-ips.sh` jih pusti nedotaknjene, ker so del slik.

---

# 🚀 **ostc-app — Rezervacijski sistem**
## **OŠ Toneta Čufarja — Dokumentacija**

---

## 📚 **Kazalo dokumentacije**

Ta datoteka je **glavni vstopni dokument** — kot recepcija v šoli, ki ti pove, kje kaj najdeš. Spodaj so povezave na specializirane poddokumente:

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
7. [Cloudflare DNS](#cloudflare-dns)
8. [Longhorn Storage](#longhorn-storage)
9. [Dnevni backup in reporti](#dnevni-backup-in-reporti)
10. [Vzdrževanje in okvare](#vzdrževanje-in-okvare)
11. [Celoten sklic ukazov](#celoten-sklic-ukazov)
12. [📖 Razlaga pojmov](#razlaga-pojmov)

---

## 🏗️ **Arhitektura sistema**

> **V enem stavku:** Dva prenosnika (HP ProBook) delata kot ekipa — če eden crkne, drugi brez prekinitve prevzame vse, kar je prvi počel.

### **Kako si zamisliti celoten sistem? (za ne-tehnične bralce)**

Predstavljaj si, da imaš v šoli dve **recepciji**. Na vsaki recepciji sedi uslužbenec (to je **Pod** — zabojnik z aplikacijo), ki sprejema obiskovalce (uporabnike, ki želijo rezervirati termin). Oba uslužbenca delata isto stvar — če je eden odsoten, drugi kar naprej dela. Za njima so **zabojniki s spisi učencev (baza podatkov)**, ki so v dveh izvodih — če en zgori, imaš rezervno kopijo. Celotno dogajanje vodi **dirigent orkestra (Kubernetes)**, ki pazi, da vsi zabojniki delajo usklajeno.

Spodaj je tehnična shema. Nad njo pa je razlaga.

> **Preprosta razlaga diagrama spodaj:**
> - Dva računalnika (k3s-1 in k3s-2) sta povezana v gručo — kot dve mizi v isti pisarni.
> - Na vsakem računalniku teče **ena kopija aplikacije (sola-app Pod)** in **ena kopija baze (sola-db)**.
> - Baza podatkov ima enega **šefa (PRIMARY)** in enega **pomočnika (REPLICA)**, ki ves čas prepisuje vse, kar šef naredi.
> - Vsi podatki so shranjeni v **Longhorn** — sistemu, ki poskrbi, da imaš 2 kopiji na 2 različnih računalnikih, tako da tudi če en računalnik crkne, podatki niso izgubljeni.
> - Ko uporabnik odpre brskalnik, gre promet prek **Cloudflare** (varnostni filter + SSL) na **MetalLB LoadBalancer** (recepcija), ki ga pošlje na eno od dveh kopij aplikacije.

### **Strojna in omrežna shema**

![Celotna k3s arhitektura — 2 noda, app podi, baza, LoadBalancer, Cloudflare](diagrams/arhitektura-clustra.png)


> **Opomba:** Oba noda sta `control-plane, etcd` — ni ločenih worker nodov. k3s poganja uporabniške pode tudi na control-plane nodih. To je čisto v redu za manjši cluster — pri 100+ nodih bi jih ločili, za šolski sistem z dvema HP ProBookoma pa je to tudi čisto ok (poleg tega je HA potem precej lažja).

> **Iz prakse:** Oba HP ProBooka imata `control-plane` vlogo, ker k3s to omogoča brez težav. V velikih podjetjih (Google, Amazon) imajo ločene control-plane node, ampak tam gre za tisoče nodov. Za šolski cluster je to povsem OK — prihraniš strojno opremo in poenostaviš nastavitev.

### **Prometni tok**

> **Preprosta razlaga:** Ko učitelj vnese `https://ostc-app.org` v brskalnik, se zgodi tole: brskalnik najprej vpraša Cloudflare (telefonski imenik interneta), kje je ta stran. Cloudflare pogleda v svoj imenik, vidi IP {{LB_IP}}, in pošlje uporabnika tja. Tam ga pričaka **MetalLB** (recepcija), ki ga preusmeri na eno od dveh kopij aplikacije — katerakoli je trenutno prosta.

![Prometni tok: uporabnik → Cloudflare → LoadBalancer → app pod](diagrams/prometni-tok.png)


> **Cloudflare proxy** kaže direktno na **LoadBalancer (`{{LB_IP}}`, port 80)** — promet gre direktno na MetalLB, HA deluje samodejno — če en node crkne, MetalLB premakne IP na drugega.

> **Nasvet:** Vedno uporabljaj Cloudflare proxy (oranžni oblak) — ne samo DNS-only (sivi oblak). Proxy ti da brezplačen SSL, DDoS zaščito, in skrije tvoj pravi IP pred hekerji. Če daš samo DNS, tvoj IP {{LB_IP}} javno razkriješ in vsak ga lahko direktno napade.

### **Pregled komponent**

|  | Komponenta | Lokacija | Namen |
|---|---|---|---|
| | **k3s-1** | HP ProBook 455 G5 ({{K3S_1_IP}}) | Control-plane, app pod, PG primary (glavni računalnik) |
| | **k3s-2** | HP ProBook 450 G5 ({{K3S_2_IP}}) | Control-plane, app pod, PG replica (pomožni računalnik) |
| | **Sola App (FastAPI)** | 2 poda (oba noda) | Rezervacije, ocenjevanje, prijava |
| | **Longhorn** | Oba noda | Distribuirano shranjevanje (PVC-ji) — podatki v 2 kopijah |
| | **MetalLB** | Oba noda | LoadBalancer IP ({{LB_IP}}) — vhodna vrata |
| | **Cloudflare** | Zunanji | DNS, SSL, proxy — varnost na internetu |

---

## 💻 **Strojna oprema in omrežje**

> **V enem stavku:** Dva običajna prenosnika HP ProBook, vsak s po 256GB diskom, povezana v šolsko Arnes omrežje — to je vse, kar rabiš za celoten sistem.

### **Specifikacije**

> **ELI5:** Predstavljaj si, da imaš dva pisarniška računalnika. Prvi (k3s-1) ima 16GB RAM — to je kot večja miza, na katero lahko daš več papirjev. Drugi (k3s-2) ima 8GB RAM — manjša miza, ampak še vedno dovolj za rutinsko delo.

| Node | Model | CPU | RAM | Disk | Vloga |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Control-plane, etcd, app, PG primary (glavni) |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Control-plane, etcd, app, PG replica (pomožni) |

> **Iz prakse:** k3s-1 ima 16 GB RAM-a, k3s-2 pa 8 GB RAM-a. To ni napaka — primarna baza (PG primary) na k3s-1 rabi več RAM-a za cache in WAL buffere. Ko k3s-2 postane primary (ob failoverju), bo deloval malo počasneje, ampak sistem bo še vedno delal.

### **Omrežne nastavitve**

> **ELI5:** Vsak računalnik v omrežju ima svoj hišni naslov (IP). k3s-1 je na naslovu {{K3S_1_IP}}, k3s-2 pa na {{K3S_2_IP}}. Skupaj z drugimi napravami v šoli tvorijo sosesko (/24 pomeni, da je v isti soseski do 254 naprav). Gateway ({{GATEWAY_IP}}) je glavna vrata v šoli, skozi katera gre ves promet proti internetu.

```bash
# Lokalno omrežje (Arnes)
k3s-1: {{K3S_1_IP}}/24
k3s-2: {{K3S_2_IP}}/24
Gateway: {{GATEWAY_IP}}
DNS: {{DNS_IP}}

# Kubernetes Pod CIDR — zasebni naslovi znotraj clustra
# (aplikacije v Kubernetesu dobijo te naslove, niso vidni od zunaj)
10.42.0.0/16

# Kubernetes Service CIDR — notranji naslovi za storitve
10.43.0.0/16

# LoadBalancer IP pool (MetalLB) — javni naslovi, ki so vidni v omrežju
{{METALLB_RANGE_START}} - {{METALLB_RANGE_END}}
```

> **Pogosta napaka:** Pod CIDR (10.42.0.0/16) in Service CIDR (10.43.0.0/16) se ne smeta prekrivati z lokalnim omrežjem ({{K3S_1_IP}}/24). Če se, Kubernetes ne bo mogel pravilno usmerjati prometa. Vedno preveri s `ip route` na nodih, preden nastaviš k3s.

### **Dostop**

```bash
# SSH v oba noda
ssh {{SSH_USER}}@{{K3S_1_IP}}    # k3s-1
ssh {{SSH_USER}}@{{K3S_2_IP}}    # k3s-2

# Kubernetes (k3s) — kubeconfig je na obeh nodih
kubectl get nodes -o wide
kubectl get pods -A -o wide

# Aplikacija v brskalniku
https://ostc-app.org          # prek Cloudflare + LoadBalancer (priporočeno)
http://{{LB_IP}}:{{LB_PORT}}     # direktno (samo interno omrežje, brez SSL)
```

---

## ☸️ **Kubernetes (k3s) Cluster**

> **V enem stavku:** k3s je lažja različica Kubernetesa (dirigent orkestra za aplikacije), ki teče na obeh HP ProBookih in skrbi, da aplikacija vedno deluje — tudi če en računalnik odpove.

> **ELI5 — Kubernetes/k3s:** Predstavljaj si orkester. Vsak glasbenik je ena aplikacija (Pod). **Kubernetes** je **dirigent** — on odloča, kdo kaj igra, kdaj igra, in kaj narediti, če kdo zamudi ali zboli. **k3s** je ista stvar, ampak lažja — kot če bi imel manjši orkester, ki ne rabi ogromne koncertne dvorane. Na prenosniku HP ProBook k3s dela odlično, medtem ko bi polni Kubernetes (k8s) bil pretežak.

### **Stanje nodov**

> **ELI5:** `kubectl get nodes` je kot pregled prisotnosti v razredu — pokaže, kateri računalniki so v gruči in ali so pripravljeni za delo.

```bash
kubectl get nodes -o wide

# NAME    STATUS   ROLES                       AGE   VERSION        INTERNAL-IP      EXTERNAL-IP
# k3s-1   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_1_IP}}    <none>
# k3s-2   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_2_IP}}    <none>
```

### **Namestitev k3s**

> **Preprosta razlaga:** Na prvem računalniku (k3s-1) zaženeš k3s s `--cluster-init` — to pomeni "ustvari novo gručo". Na drugem (k3s-2) pa se pridružiš obstoječi gruči s `--server https://{{K3S_1_IP}}:6443` — to je kot "prosim, poveži me s šefom na tem naslovu".

```bash
# Na k3s-1 (prvi node — ustvari novo gručo)
curl -sfL https://get.k3s.io | sh -s - server \
  --cluster-init \
  --disable=traefik \
  --node-ip={{K3S_1_IP}} \
  --flannel-iface=eth0

# Na k3s-2 (drugi node — pridruži se obstoječi gruči)
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://{{K3S_1_IP}}:6443 \
  --disable=traefik \
  --node-ip={{K3S_2_IP}} \
  --flannel-iface=eth0 \
  --token <NODE_TOKEN>
```

Token dobite z: `sudo cat /var/lib/rancher/k3s/server/node-token` (na k3s-1).

> **Opomba:** `--disable=traefik` izklopi vgrajeni ingress, ker uporabljamo MetalLB LoadBalancer. Če bi pustili Traefik vklopljen, bi imeli dva sistema, ki se potegujeta za isti port — zmeda, ki smo se je izognili.

> **ELI5:** Vsak računalnik ima eno ali več **omrežnih vtičnic (interface-ov)** — kot vrata v hiši. Ena vtičnica je za **Ethernet kabel** (fizična žica), druga za **WiFi** (brezžična). **Flannel** je notranji omrežni kablovod v Kubernetesu — povezuje vse zabojnike (Pode) med seboj, tudi če so na različnih računalnikih. `--flannel-iface=eth0` mu pove: "uporabi Ethernet kabel, ne WiFi." Če tega ne poveš, lahko Flannel izbere WiFi (ki je počasnejši in manj zanesljiv) in cela gruča ne bo delala pravilno.

> **Nasvet:** Vedno dodaj `--flannel-iface=eth0`. Zakaj? Ker ima prenosnik pogosto več omrežnih kartic — eno za WiFi (npr. `wlan0`) in eno za ethernet kabel (`eth0`). Flannel (omrežni sistem v Kubernetesu) ne ve, katero naj uporabi. Če izbere WiFi, ki je počasen ali nestabilen, cluster ne bo delal. Z `--flannel-iface=eth0` mu poveš: "uporabi ethernet kabel, ne WiFi." Preveri, kako se tvoji omrežni kartici imenujeta z ukazom `ip a` na vsakem računalniku.

---

## 🚀 **Aplikacija Sola App**

> **V enem stavku:** Spletna aplikacija (FastAPI + HTML), ki teče v dveh kopijah na obeh računalnikih — če ena crkne, druga nemoteno prevzame.


> **ELI5:** Predstavljaj si **seznam na papirju** na oglasni deski, kamor se učitelji vpisujejo za rezervacije telovadnice ali učilnice. Pri papirju velja: kar napišeš, ostane. Če si se zmotil, lahko samo prečrtaš (kar je grdo in nepregledno) ali vzameš nov list. Aplikacija je kot **isti seznam, ampak digitalen** — lahko dodaš rezervacijo, jo **kadarkoli spremeniš** ali **zbrišeš** z enim klikom, pa je vse lepo čisto in pregledno. Brez prečrtavanja, brez novih listov, brez packanja.  
In ker je digitalen, ga lahko zaženeš v **dveh kopijah (Podi)** na dveh računalnikih. Kot da imaš na hodniku dve enaki oglasni deski — če eno nekdo poškoduje ali sname, druga še vedno visi in učitelji normalno rezervirajo. Učitelji (uporabniki) tega sploh ne opazijo — samo odprejo aplikacijo in delajo naprej.

### **Deployment**

Namespace: `sola-app`

```bash
kubectl get deployments -n sola-app
kubectl get pods -n sola-app -o wide
kubectl get services -n sola-app
```

Aplikacija teče v **1-3 podih**, odvisno od obremenitve. **HorizontalPodAutoscaler (HPA)** samodejno prilagaja število:

| Obremenitev | Replik | Kdaj |
|-------------|--------|------|
| 🟢 Nizka (popoldne, vikend, počitnice) | **1** | en node dela, drugi počiva |
| 🟡 Običajna (pouk, rezervacije) | **2** | ena kopija na vsakem nodu |
| 🔴 Visoka (ocene, začetek leta) | **3** | 2 na enem, 1 na drugem — Kubernetes sam razporedi |

> **ELI5 — HPA:** Kot kavomat v šoli — ko je malo ljudi, dela en. Ko pride malica, se samodejno vključi še drugi in tretji. Ko gneče zmanjka, se odvečni izklopijo. HPA dela isto za aplikacijo.

```bash
kubectl get hpa -n sola-app
# NAME            REFERENCE              TARGETS              MIN   MAX   REPLICAS
# sola-app-hpa    Deployment/sola-app    45%/60% CPU           1     3     2
#                                        60%/70% MEM

```bash
kubectl get pods -n sola-app -o wide

# NAME                        READY   STATUS    RESTARTS   AGE   IP           NODE
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.0.x    k3s-1
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.1.x    k3s-2
```

### **Docker Image**

> **ELI5 — Docker Image:** To je kot **recept za torto**. Isti recept uporabiš, da spečeš dve torti (dva Pod-a) na dveh različnih mestih. Vsaka torta je identična — isti program, iste nastavitve, ista koda. Dockerfile vsebuje ta recept.

- **Image:** `sola-app:latest`
- **Dockerfile:** `reservation_app/k8s/Dockerfile`
- **Deployment YAML:** `reservation_app/k8s/sola-app.yaml`

### **Posodobitev aplikacije**

> **ELI5 — rollout restart:** Ko želiš posodobiti aplikacijo, ne rabiš ugašati strežnika. Kubernetes to naredi **brez prekinitve (zero-downtime)** — najprej zažene nov Pod, počaka, da je pripravljen, šele nato ugasi starega. Kot menjava gum na avtu med vožnjo — zamenjaš eno po eno, avto ves čas vozi.

```bash
cd reservation_app
git pull
# Počakaj, da se CI build konča (GitHub Actions)
# ali pa ročno:
kubectl rollout restart deployment -n sola-app sola-app
kubectl rollout status deployment -n sola-app sola-app
```

> **Nasvet:** Nikoli ne briši starih podov ročno. Uporabi `rollout restart`. Kubernetes sam pazi, da je vedno vsaj en Pod aktiven. Če zbrišeš oba hkrati, imaš izpad. `rollout status` ti pove, kdaj je posodobitev končana — ne ugibaj, počakaj na izpis "rollout successfully rolled out".

---

## 🗄️ **PostgreSQL HA — CloudNativePG**

> **V enem stavku:** Baza podatkov (PostgreSQL) teče v visoko-razpoložljivi konfiguraciji — ena glavna (primary) na k3s-1 in ena podvojena (replica) na k3s-2, pri čemer CloudNativePG avtomatsko poskrbi za zamenjavo, če glavna odpove.

> **ELI5 — PostgreSQL:** Baza podatkov je kot **šolska mapa z vsemi rezervacijami in ocenami**. Namenjena je shranjevanju podatkov.
>
> **ELI5 — HA (High Availability):** Visoka razpoložljivost pomeni, da imaš **dve mapi** — eno originalno (primary) in eno fotokopijo (replica). Vsakič, ko nekaj zapišeš v original, fotokopija to takoj dobi. Če original zgori (crkne), vzameš fotokopijo in nadaljuješ, kjer si končal.
>
> **ELI5 — CloudNativePG (CNPG):** To je **pametni pomočnik**, ki pazi na obe mapi. Če opazi, da je original crknil, samodejno reče "fotokopija, zdaj si ti šef!" in preusmeri vse uporabnike na fotokopijo. Vse to brez človeškega posredovanja.

### **Stanje**

```bash
kubectl get pods -n sola-app -o wide | grep db

# NAME                    READY   STATUS    IP            NODE
# sola-db-1 (primary)     1/1     Running   10.42.0.x     k3s-1
# sola-db-2 (replica)     1/1     Running   10.42.1.x     k3s-2
```

Zgrajena z **CloudNativePG** operatorjem. Primary vedno na k3s-1, replica na k3s-2.

### **Failover**

> **ELI5 — Failover:** Failover je **samodejna menjava straže**. Predstavljaj si dva stražarja. Prvi (primary) stoji na vratih. Drugi (replica) sedi v pisarni in ves čas spremlja, kaj prvi dela (prepisuje dnevnik). Če prvi omedli, drugi takoj skoči na vrata in nadaljuje, kot da se ni nič zgodilo — obiskovalci (uporabniki) tega sploh ne opazijo.

Ob izpadu k3s-1:

1. **Primarni pod `sola-db-1` postane nedosegljiv** — računalnik je crknil.
2. **CNPG operator zazna izpad** (30s `failoverDelay`) — pomočnik opazi, da se stražar ne oglaša.
3. **CNPG promovira `sola-db-2` (na k3s-2) v primary** — pomočnik prevzame.
4. **Service `sola-db-rw` se avtomatsko preusmeri na `sola-db-2`** — vsa vrata se preusmerijo na novega stražarja.
5. **App pod na k3s-1 je mrtev → k3s ga reschedule-a na k3s-2** — Kubernetes ugotovi, da je prvi računalnik mrtev, in prestavi aplikacijo na drugega.
6. **App na k3s-2 se poveže na `sola-db-rw` (ki kaže na `sola-db-2`) → deluje naprej** — sistem teče dalje.

**Skupni čas izpada:** ~1–2 minuti (30s failover delay + ~30s za promocijo + čas, da k3s zazna mrtvi node)

> **Iz prakse:** 1-2 minuti izpada se sliši veliko, ampak v praksi je to za šolski sistem povsem sprejemljivo. Učitelj, ki osveži stran po 2 minutah, bo spet delal normalno — podatki niso izgubljeni, ker je Longhorn poskrbel za replikacijo. V primerjavi s starim sistemom (izpad za cel dan, dokler ne pride IT) je to ogromen napredek.

### **Dostop**

```bash
# Primarna baza (rw) — kamor se zapisuje
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL

# Replica (read-only) — samo za branje (poročila, analitika)
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL_RO
```

### **Servisni endpointi (CNPG)**

> **ELI5:** CNPG ustvari tri imenike:
> - **sola-db-rw** = "glavni vhod" — vsi, ki želijo kaj napisati ali prebrati, gredo skozi ta vhod. Vedno kaže na primary.
> - **sola-db-ro** = "stranski vhod" — samo za branje. Kaže na replica (pomožno bazo), kar razbremeni primary.
> - **sola-db-r** = "katerikoli vhod" — lahko greš na primary ali replica, kdor je prej na vrsti.

CNPG samodejno ustvari tri Kubernetes Services za dostop do baze:

| Service | Vloga |
|---|---|
| `sola-db-rw.sola:5432` | **Read-Write** — vedno na primary (uporablja ga app) |
| `sola-db-ro.sola:5432` | Read-Only — samo replica (za poročila, analitiko) |
| `sola-db-r.sola:5432` | Read — katerakoli instance (primary ali replica) |

`DATABASE_URL` v aplikaciji kaže na `sola-db-rw` — ob failoverju se avtomatsko preusmeri na nov primary, app ne izve za spremembo.

---

## 🌐 **MetalLB LoadBalancer**

> **V enem stavku:** MetalLB je **recepcija** za tvoj Kubernetes cluster — dodeli mu javni IP ({{LB_IP}}) in usmerja obiskovalce na pravo aplikacijo, tudi če se aplikacija seli med računalniki.

> **ELI5 — LoadBalancer:** V velikem podjetju imaš recepcijo, ki obiskovalce usmerja v pravo pisarno. **LoadBalancer** je ista stvar za aplikacije. Ko uporabnik pride na IP {{LB_IP}}, LoadBalancer pogleda, katera kopija aplikacije (Pod) je prosta, in ga pošlje tja. Če je ena kopija zasedena ali crknjena, pošlje na drugo.
>
> **ELI5 — MetalLB:** MetalLB je ena izmed vrst LoadBalancerjev, specializirana za kraje, kjer nimaš oblačnega strežnika (AWS, Google Cloud), ampak imaš svoje računalnike (on-premise). Za razliko od AWS Load Balancerja, ki ga najameš od Amazona, MetalLB teče kar na tvojih HP ProBookih.

MetalLB je nameščen v namespace-u `metallb-system`. Dodeli zunanji IP {{LB_IP}} za Service `sola-app` v `sola-app` namespace-u.

**Zakaj MetalLB in ne Traefik/Ingress?**

k3s ima vgrajen Traefik ingress controller, ampak smo ga izklopili (`--disable=traefik`). Razlog: Traefik je odličen za HTTP promet, ampak za čisto majhen cluster z 2 nodoma je MetalLB + Service LoadBalancer preprostejši — manj gibljivih delov, manj možnosti za napake. Če bo sistem kdaj zrasel na 5+ nodov z več aplikacijami, potem razmisli o Ingress controllerju.

---

## ☁️ **Cloudflare DNS**

> **V enem stavku:** Cloudflare je **telefonski imenik interneta** — ko nekdo vnese `ostc-app.org` v brskalnik, Cloudflare pove, kje (na katerem IP-ju) to aplikacijo najde, in poskrbi za varnostno povezavo (SSL).

> **ELI5 — DNS:** DNS (Domain Name System) je kot telefonski imenik za internet. Ti vpišeš ime (`ostc-app.org`), DNS vrne številko (IP naslov). Namesto da se spomniš številke {{LB_IP}}, se spomniš imena `ostc-app.org`. Veliko lažje, kajne?
>
> **ELI5 — Cloudflare proxy:** Ko vklopiš Cloudflare proxy (oranžni oblak), Cloudflare ne dela samo imenika — ampak tudi **stoji pred tvojim strežnikom kot varnostnik**. Vse povezave gredo skozi Cloudflare, ki:
> - Šifrira promet (SSL) — nihče ne more prisluhniti.
> - Skrije tvoj pravi IP — hekerji ne vedo, kje točno je tvoj strežnik.
> - Blokira DDoS napade — če nekdo pošlje milijon zahtev na sekundo, Cloudflare to zadrži.

### **DNS zapisi**

| Tip | Ime | Vrednost | Proxy |
|---|---|---|---|
| A | `@` (ostc-app.org) | {{LB_IP}} | ✅ Cloudflare proxy (LoadBalancer) |
| A | `www` | {{LB_IP}} | ✅ Cloudflare proxy |

### **SSL/TLS**

Cloudflare skrbi za:

- **Edge certifikat** — med uporabnikom in Cloudflare (HTTPS). To je zelena ključavnica v brskalniku.
- **Flexible SSL** — Cloudflare → {{LB_IP}} (port 80) prek HTTP (brez certifikata na originu). To pomeni, da imaš HTTPS na zunanji strani, ampak znotraj šolskega omrežja gre promet nešifriran — kar je v šolskem omrežju v redu, ker je fizično zaščiteno.

Nastavitve v Cloudflare dashboard:

- **SSL/TLS encryption mode:** `Flexible`
- **Always Use HTTPS:** ON
- **Minimum TLS Version:** 1.2

> **Nasvet:** Flexible SSL je v redu za šolsko okolje, ampak če bi kdaj dodal podatke, ki zahtevajo PCI-DSS ali HIPAA skladnost, bi moral uporabiti Full (strict) SSL z let's encrypt certifikatom na origin strežniku. Za rezervacije terminov in ocene na OŠ pa je Flexible SSL povsem dovolj.

> **Pogosta napaka:** Če nastaviš SSL/TLS na "Full" brez certifikata na originu, Cloudflare ne bo mogel vzpostaviti povezave in uporabniki bodo dobili 502 napako. Začni s "Flexible" (najlažje) in nadgradi, ko boš na origin dodal certifikat.

---

## 💾 **Longhorn Storage**

> **V enem stavku:** Longhorn je sistem za shranjevanje, ki poskrbi, da ima vsak podatek 2 kopiji na 2 različnih računalnikih — če en disk crkne, podatki niso izgubljeni.

> **ELI5 — Longhorn:** Predstavljaj si, da imaš pomemben šolski dnevnik. Longhorn je kot **fotokopirni stroj, ki vsako stran takoj po zapisu fotokopira na drugo mizo**. Če ena miza (računalnik) zagori, imaš fotokopijo na drugi mizi. Brez Longhorna bi bil tvoj dnevnik samo na enem mestu — če ta disk crkne, so podatki za vedno izgubljeni.
>
> **ELI5 — PVC (PersistentVolumeClaim):** PVC je **virtualni trdi disk** v Kubernetesu. Aplikacija reče "rabim 5GB prostora za shranjevanje" in Kubernetes + Longhorn to zagotovita — tudi če se aplikacija preseli na drug računalnik, podatki ostanejo. To je kot če bi imel prenosni disk, ki ga lahko priklopiš na katerikoli računalnik.

### **Stanje**

```bash
kubectl get pvc -n sola-app
kubectl get volumes.longhorn.io -n longhorn-system
```

### **PVC-ji**

| PVC | Size | Access Mode | Uporaba |
|---|---|---|---|
| `sola-postgresql` | 5Gi | RWO | PG data |
| `sola-postgresql-wal` | 2Gi | RWO | WAL logi |

**Razlaga PVC-jev za ne-tehnične:**

| PVC | Kaj shranjuje | Zakaj je pomembno |
|---|---|---|
| `sola-postgresql` (5Gi) | **Podatki PG baze** — vse tabele, indeksi, uporabniki, rezervacije, ocene. To je "glavni" PVC. | Brez tega ni baze. 5Gi zadostuje za celotno šolsko leto. |
| `sola-postgresql-wal` (2Gi) | **Write-Ahead Logs (WAL)** — dnevnik vsake spremembe, preden se zapiše v podatkovne datoteke. | Brez WAL-a replica ne more slediti primaryju. Uporablja se za crash recovery, streaming replikacijo in point-in-time recovery. |

> **ELI5 — WAL (Write-Ahead Log):** Predstavljaj si, da pišeš test. Najprej napišeš odgovor na **list za beležke (WAL)**, šele nato ga prepišeš v **čisto mapo (glavni podatki)**. Če te zmotiš med pisanjem, imaš še vedno beležko, iz katere lahko obnoviš, kar si hotel napisati. WAL je ta beležka — dnevnik sprememb, preden se zapišejo v glavno bazo.

**Zakaj dva ločena PVC-ja?** PostgreSQL vsako spremembo najprej zapiše v WAL, šele nato v glavne podatkovne datoteke. Ločena PVC-ja omogočata različne I/O profile — WAL je zaporedno pisanje (hitro), podatki so naključni bralno-pisalni dostopi. Prav tako omogoča ločeni backup strategiji: WAL se arhivira sproti, podatki se periodično snapshottajo.

**Longhorn replikacija** (2 kopiji) zagotavlja, da tudi ob izgubi enega noda podatki ostanejo. Oba PVC-ja imata dve repliki — vsaka na svojem k3s nodu.

> **Iz prakse:** 5Gi za podatke in 2Gi za WAL se sliši malo, ampak za šolski sistem z nekaj sto uporabniki in rezervacijami je to več kot dovolj. PostgreSQL je presenetljivo učinkovit s prostorom — cela baza za leto dni dela bo verjetno pod 1GB. Če boš kdaj blizu meje, spremljaš z `kubectl get pvc` in povečaš velikost — Longhorn omogoča online resize brez izpada.

---

## 📅 **Dnevni backup in reporti**

> **V enem stavku:** Vsako noč ob 4:00 zjutraj sistem samodejno pošlje summary na Discord — število rezervacij, prijavljenih uporabnikov in morebitne napake.

> **ELI5:** Predstavljaj si, da imaš **nočnega čuvaja**, ki vsako jutro ob 4:00 pregleda celotno šolo in napiše poročilo: "Danes je v šoli 150 učencev, 45 rezervacij, vse deluje." To poročilo pošlje na Discord (šolski chat). Tako veš, da sistem deluje, še preden prideš v službo.

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

> **Nasvet:** Discord webhook je odličen za alerting v šolskem okolju — zastonj, preprost, vsi ga imajo na telefonu. Ampak ne zaupaj mu 100%. Enkrat na teden preveri tudi `kubectl get events -n sola-app --sort-by='.lastTimestamp'` — tam vidiš stvari, ki jih Discord report morda ne pokaže (OOMKilled, CrashLoopBackOff, neuspešni volume mounti).

---

## 🔧 **Vzdrževanje in okvare**

> **V enem stavku:** Večino težav rešiš z enim ukazom `kubectl get ...` — poglej, kaj ne dela, in sistem sam poskrbi za ostalo.

### **Dnevne operacije**

> **ELI5:** To so tvoji **jutranji pregledi**, kot preden odpelješ avto — preveriš olje, zrak v gumah, luči. Tukaj preveriš, ali so vsi računalniki v gruči živi, ali aplikacije tečejo, ali diski niso polni.

```bash
# Preveri stanje nodov — ali so vsi računalniki živi?
kubectl get nodes -o wide

# Preveri pode v sola-app — ali aplikacije tečejo?
kubectl get pods -n sola-app -o wide

# Preveri stanje Longhorn — ali so diski v redu?
kubectl get volumes.longhorn.io -n longhorn-system

# Preveri CloudNativePG — ali baza deluje?
kubectl get cluster -n sola-app
```

### **Ob izpadu noda**

> **ELI5:** Če eden od računalnikov crkne, se zgodi **samodejna menjava straže**. Ne paničari — sistem je zasnovan tako, da preživi izpad enega računalnika. Počakaj minuto, preveri, popravi crknjeni računalnik, ko imaš čas.

1. **Ostali node prevzame** — app pod se preseli, PG failover se zgodi sam
2. **Počakaj minuto** — CNPG failover (30s zamuda + promocija) in Longhorn se rekonfigurirata
3. **Preveri** — `kubectl get pods -n sola-app -o wide`
4. **Popravi** izpadli node po potrebi (zamenjaj disk, popravi napajanje, ponovno namesti k3s)

### **Popolna zaustavitev (poletna pavza)**

Glej [🌞 Poletna pavza](POLETNA_PAVZA.md).

> **Iz prakse:** Poletna pavza je pogosto spregledana, ampak je ključna za dolgo življenjsko dobo strojne opreme. HP ProBooki v omari brez hlajenja čez poletje zlahka dosežejo 50°C v mirovanju. Izklop za 2 meseca podaljša življenjsko dobo diskov in baterij. Pred izklopom **obvezno** naredi snapshot Longhorn volumnov in dump baze — "bolje imeti in ne rabiti, kot rabiti in ne imeti."

---

## 📋 **Celoten sklic ukazov**

```bash
# === Stanje ===
kubectl get nodes -o wide                           # Kateri računalniki so v gruči?
kubectl get pods -n sola-app -o wide                # Katere aplikacije tečejo in kje?
kubectl get services -n sola-app                    # Katere storitve so na voljo?
kubectl get pvc -n sola-app                         # Koliko diskovnega prostora je zasedenega?
kubectl get cluster -n sola-app                     # Kako je z bazo?
kubectl get events -n sola-app --sort-by='.lastTimestamp'  # Kaj se je nazadnje zgodilo?

# === Upravljanje aplikacije ===
kubectl rollout restart deployment -n sola-app sola-app          # Ponovni zagon brez izpada
kubectl rollout status deployment -n sola-app sola-app           # Spremljaj posodobitev
kubectl logs -n sola-app deployment/sola-app --tail=50           # Zadnjih 50 vrstic loga
kubectl logs -n sola-app deployment/sola-app --previous          # Log prejšnjega (crknjenega) Pod-a

# === Upravljanje baze ===
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL                    # Poveži se na bazo
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL -c "SELECT * FROM users;"  # Poženi poizvedbo

# === Longhorn ===
kubectl get volumes.longhorn.io -n longhorn-system               # Stanje diskov
kubectl get engineimages.longhorn.io -n longhorn-system           # Različica Longhorn engine
kubectl get nodes.longhorn.io -n longhorn-system                  # Longhorn status na vsakem nodu

# === Git (na k3s-2) ===
cd /home/admin/reservation_app
git pull                                    # Potegni zadnjo kodo
```

---

## 📖 **Razlaga pojmov**

*Razlaga tehničnih izrazov za ne-tehnične bralce — če ti kaj v dokumentaciji ni jasno, poglej tukaj.*
*💡 **ELI5** = *Explain Like I'm 5* (razloži kot petletniku) — pomeni, da je razlaga napisana čim bolj preprosto, brez strokovnega žargona.*

| Pojem | Razlaga |
|---|---|
|| **Arnes** | **Akademsko raziskovalna omrežna infrastruktura Slovenije** — slovenski izobraževalni internet. Šola je prek Arnesa povezana v internet. |
|| **Cloudflare** | **Varnostnik pred tvojim strežnikom** — šifrira promet (SSL), skrije tvoj IP, blokira napade, pospešuje nalaganje. |
|| **CloudNativePG (CNPG)** | **Pametni pomočnik za PostgreSQL bazo** — avtomatsko upravlja replikacijo, failover, backup in obnovitev. |
|| **Cluster** | **Gruča računalnikov, ki delajo kot eno** — dva HP ProBooka, povezana v isto Kubernetes gručo. Kubernetes skrbi, da aplikacije tečejo na kateremkoli računalniku je na voljo. |
|| **ConfigMap / Secret** | **Kubernetes objekti za shranjevanje nastavitev** — ConfigMap za javne nastavitve (npr. BASE_URL), Secret za občutljive podatke (gesla, ključi). Secret je zakodiran, ConfigMap je berljiv. |
|| **Control-plane** | **"Možgani" clustra** — nadzorni del, ki sprejema vse odločitve. Na obeh HP ProBookih imamo control-plane, kar pomeni, da imamo dva "možgana" — če en crkne, drugi prevzame. |
|| **Discord webhook** | **Samodejno pošiljanje sporočil na Discord** — naša aplikacija pošlje nočno poročilo na šolski Discord kanal. |
|| **DNS** | **Telefonski imenik interneta** — pretvori ime `ostc-app.org` v IP naslov {{LB_IP}} (npr.). |
|| **Docker Image** | **Recept za aplikacijo** — vsebuje program, knjižnice, nastavitve. Iz enega recepta lahko narediš več identičnih zabojnikov (Podov). |
||| **ELI5** | *Explain Like I'm 5* (razloži kot petletniku) — način razlage, kjer se izogneš strokovnim izrazom in uporabiš vsakdanje analogije. Npr. Kubernetes ni "sistem za orkestracijo kontejnerjev", ampak "dirigent orkestra za aplikacije". |
|| **etcd** | **Spominska knjiga clustra** — shranjuje vse podatke o tem, kaj kje teče, kakšne so nastavitve, kdo je živ in kdo mrtev. Je možgani Kubernetesa. |
|| **Failover** | **Samodejna menjava straže** — ko primarni sistem crkne, pomožni samodejno prevzame njegovo vlogo. V našem primeru CNPG promovira replica v primary. |
|| **FastAPI** | **Ogrodje za spletne aplikacije v Pythonu** — v njem je napisana sola-app. Hitro, moderno, podpira samodejno dokumentacijo. |
|| **Git** | **Sistem za sledenje spremembam kode** — kot "Track Changes" v Wordu, ampak za programsko kodo. |
|| **GitHub Actions** | **Samodejno testiranje in gradnja ob vsaki spremembi** — ko nekdo naloži novo kodo na GitHub, se avtomatsko zgradi nov Docker Image. |
|| **Helm** | **"App Store" za Kubernetes** — orodje za nameščanje pripravljenih paketov (npr. Longhorn, CNPG) v Kubernetes. Namesto da ročno pišeš YAML, samo poveš "namesti Longhorn". |
|| **HPA (HorizontalPodAutoscaler)** | **Samodejno prilagajanje števila kopij aplikacije** — pazi na porabo CPU/RAM in doda ali odstrani replike (1-3) glede na obremenitev. Kot kavomat v šoli — ko je gužva, se vključi še en. |
|| **HTTPS** | **Varna spletna povezava** — HTTP + SSL. Zelena ključavnica v brskalniku pomeni, da je povezava varna. |
|| **k3s** | **Lažja različica Kubernetesa** — posebej narejena za manjše računalnike in IoT naprave. Uporabljamo jo na HP ProBookih, ker je polni Kubernetes pretežak za prenosnike. Isti `kubectl` ukazi delujejo za oboje. |
|| **Kubernetes (k8s)** | **Dirigent orkestra za aplikacije** — sistem, ki avtomatsko upravlja, kje in kako tečejo tvoje aplikacije. Če ena crkne, jo samodejno zažene drugje. |
|| **LoadBalancer** | **Recepcija v stavbi** — usmerja obiskovalce (uporabnike) na pravo aplikacijo. V našem primeru MetalLB na IP {{LB_IP}}. |
|| **Longhorn** | **Sistem, ki poskrbi, da imaš 2 kopiji podatkov na 2 različnih računalnikih** — distribuirano shranjevanje za Kubernetes, narejeno za manjše clustre. |
|| **MetalLB** | **LoadBalancer za domače (on-premise) okolje** — alternativa oblačnim LoadBalancerjem (AWS, Google). Teče kar na tvojih računalnikih. |
|| **Node** | **Fizični računalnik v gruči** — v našem primeru k3s-1 (HP ProBook 455 G5) in k3s-2 (HP ProBook 450 G5). |
|| **Pod** | **Zabojnik z aplikacijo** — najmanjša enota v Kubernetesu. V njem teče ena kopija aplikacije (npr. sola-app ali sola-db). Vsak pod ima svoj zasebni IP naslov. |
|| **Primary (baza)** | **Glavna baza** — edina, v katero se lahko zapisuje. Vse spremembe gredo skozi njo. |
|| **PVC (PersistentVolumeClaim)** | **Virtualni trdi disk** — zahtevek za prostor na disku v Kubernetesu. Podatki ostanejo tudi, če se aplikacija preseli na drug računalnik. |
|| **Replica** | **Kopija, ki budno spremlja original** — druga baza podatkov, ki ves čas prepisuje vse spremembe iz primaryja. Pripravljena prevzeti, če original crkne. |
|| **Replica (baza)** | **Pomožna baza** — samo za branje. Ves čas prepisuje spremembe iz primaryja. Če primary crkne, postane nov primary. |
|| **SSH** | **Varen dostop do oddaljenega računalnika prek ukazne vrstice** — kot da bi sedel pred tistim računalnikom, čeprav si v drugi sobi. |
|| **SSL/TLS** | **Šifrirana povezava (ključavnica v brskalniku)** — poskrbi, da nihče ne more prisluhniti komunikaciji med uporabnikom in strežnikom. |
|| **Uvicorn** | **Strežnik, ki poganja FastAPI aplikacijo** — bere Python kodo in jo streže kot spletno stran. Kot natakar, ki hrano (odgovore) nosi do strank. |
|| **WAL (Write-Ahead Log)** | **Dnevnik sprememb, preden se zapišejo** — PostgreSQL vsako spremembo najprej zapiše v WAL, šele nato v glavne podatkovne datoteke. To omogoča obnovitev po crashu in replikacijo. |
|| **YAML** | **Človeku berljiv format za zapis konfiguracije** — nekaj podobnega kot JSON, ampak bolj pregleden. V Kubernetesu vse nastavitve pišejo v YAML formatu. |
|| **Zero-downtime (rollout)** | **Posodobitev brez prekinitve delovanja** — Kubernetes najprej zažene novo verzijo, počaka da deluje, šele nato ugasi staro. Uporabniki nič ne občutijo. |

---

*Dokumentacija za ostc-app — OŠ Toneta Čufarja Jesenice*
*Zadnja posodobitev: 27. junij 2026*
