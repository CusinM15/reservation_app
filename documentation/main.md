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

---

# 🚀 **ostc-app — Rezervacijski sistem OŠ Toneta Čufarja**
## **Dokumentacija za vzpostavitev, uporabo in vzdrževanje**

---

Doberdošli! Ta dokument je **glavni vhod** v celoten sistem. Če bereš to, si
verjetno ravnatelj, učitelj, IT-tehnik ali pa samo radoveden starš, ki želi
vedeti, kako sploh deluje šolski rezervacijski sistem. **Ne skrbi, če nisi
računalniški strokovnjak** — vsak tehnični izraz bom razložil sproti, kot bi
razlagal svojemu sosedu.

Sistem teče na **dveh prenosnikih HP ProBook** v omari na šoli. To ni
enostaven "klikni in končaj" programček — to je pravi mali **Kubernetes
cluster** (beri: "kubernetes klaster"), kar pomeni, da aplikacija laufa na
dveh računalnikih hkrati. Če eden crkne, drugi takoj prevzame. **To je high
availability (HA)** — visoka razpoložljivost. Kot da bi imel dva učitelja v
razredu: če en zboli, drugi brez prekinitve nadaljuje uro.

---

## 📚 **Kazalo dokumentacije**

Spodaj so povezave na vse poddokumente. Vsak pokriva en specifičen vidik:

| Dokument | Opis | Za koga |
|---|---|---|
| [🏗️ **HA arhitektura**](HA.md) | CloudNativePG, avtomatski failover, potek ob izpadu noda | DevOps, IT-tehnik |
| [🌞 **Poletna pavza**](POLETNA_PAVZA.md) | Varen izklop k3s clustra čez poletje in ponoven vklop jeseni | IT-tehnik, ravnatelj |
| [☁️ **Domena in DNS**](domena.md) | Nastavitev domene, Cloudflare, DNS zapisi | DevOps, IT-tehnik |
| [🐍 **Postavi lokalni app**](postavi-lokalni-app.md) | Namestitev na enem računalniku (brez Kubernetes) | Učitelj, programer začetnik |
| [☸️ **K3s setup**](k3s-setup.md) | Namestitev k3s clustra iz nič | DevOps, IT-tehnik |
| [⚙️ **Admin/devops navodila**](admin-devops-navodila.md) | Vzdrževanje, posodabljanje, odpravljanje težav | DevOps, IT-tehnik |
| [👩‍🏫 **Navodila za učitelje**](navodila-ucitelji.md) | Uporaba aplikacije — rezervacije in ocenjevanja | Učitelji |
| [👑 **Navodila za vodstvo**](navodila-vodstvo.md) | Upravljanje prek brskalnika (serije, zasedeni datumi) | Ravnatelj, pomočnik |
| [📱 **Opis aplikacije**](aplikacija-rezervacije.md) | Kaj aplikacija omogoča, namen, funkcionalnosti | Vsi |
| [📖 **Navodila za uporabnika**](navodila-uporabnika.md) | Prijava, gesla, dnevna uporaba | Učitelji, učenci, starši |

---

## 📑 **Kazalo vsebine** (ta dokument)

1. [🏗️ Arhitektura sistema — kako vse skupaj stoji in diha](#arhitektura-sistema)
2. [💻 Strojna oprema in omrežje — kaj fizično stoji v šoli](#strojna-oprema-in-omrežje)
3. [☸️ Kubernetes (k3s) Cluster — "OS za oblak" na dveh prenosnikih](#kubernetes-k3s-cluster)
4. [🚀 Aplikacija Sola App — srce sistema](#aplikacija-sola-app)
5. [🗄️ PostgreSQL HA — baza podatkov, ki ne crkne](#postgresql-ha--cloudnativepg)
6. [☁️ Cloudflare DNS — kako uporabniki najdejo do nas](#cloudflare-dns)
7. [💾 Longhorn Storage — pametno shranjevanje podatkov](#longhorn-storage)
8. [📅 Dnevni backup in reporti — avtomatsko poročilo vsako jutro](#dnevni-backup-in-reporti)
9. [🔧 Vzdrževanje in okvare — kaj narediti, ko gre kaj narobe](#vzdrževanje-in-okvare)
10. [📋 Celoten sklic ukazov — goljfija za admina](#celoten-sklic-ukazov)

---

## 🏗️ **Arhitektura sistema**

### 🖥️ **Strojna in omrežna shema**

Predstavljaj si, da imaš dva prenosnika, povezana v isto lokalno omrežje
(Arnes). Vsak poganja iste stvari: aplikacijo, bazo podatkov in shrambo. Če
en prenosnik odpove (crkne napajalnik, zamrzne OS, pade omrežni kabel), drugi
samodejno prevzame vse njegove naloge. **To je high availability (HA)** —
sistem, ki ne pozna izpada.

Tole je shema, kako so komponente povezane:

![Arhitektura K3S clustra](diagrams/arhitektura-clustra.png)

> **Opomba:** Oba noda (vozlišča) sta `control-plane, etcd` — to pomeni, da
> ni ločenih "delavskih" (worker) nodov. k3s dovoljuje poganjanje aplikacij
> tudi na krmilnih (control-plane) nodih. Če bi imeli večji sistem, bi
> ločili — ampak za šolsko rabo dva zadoščata.

### 🌊 **Prometni tok — kako podatki potujejo od učitelja do aplikacije**

Ko učitelj odpre `https://{{DOMAIN}}` v brskalniku, se zgodi tole:

```
🌐 Učitelj v brskalniku
  → vtipka {{DOMAIN}}
  → Internet
  → Cloudflare (poskrbi za SSL-varnost in proxy)
  → naš Service LoadBalancer (MetalLB na {{LB_IP}}:{{LB_PORT}})
    → sola-app Pod (na k3s-1 ALI k3s-2 — kateri je trenutno prost)
```

Če pa si v šolskem omrežju in ne greš prek spleta, lahko uporabiš direktno
povezavo:

```
  → http://{{LB_IP}}:{{LB_PORT}} → direkt na LoadBalancer
```

> 💡 **Zakaj Cloudflare proxy?** Cloudflare je vhodna vrata s stražarjem.
> Skrbi za:
> - **SSL certifikat** — zelena ključavnica v brskalniku
> - **DDoS zaščito** — preprečuje, da bi kdo preobremenil sistem
> - **Cache** — hitrejše nalaganje

> ⚡ **Pomembno:** Cloudflare proxy kaže direktno na naš **LoadBalancer
> ({{LB_IP}}, port 80)**. Promet gre direkt na MetalLB, visoka
> razpoložljivost (HA) deluje samodejno — če en node crkne, MetalLB
> premakne IP na drugega.

### 🧩 **Pregled komponent — kratek slovarček**

| Komponenta | Fizično | Kaj počne |
|---|---|---|
| **k3s-1** | HP ProBook 455 G5 ({{K3S_1_IP}}) | Krmilni node + aplikacija + primarna baza |
| **k3s-2** | HP ProBook 450 G5 ({{K3S_2_IP}}) | Krmilni node + aplikacija + rezervna baza |
| **Sola App** (FastAPI) | 2 poda (en na vsakem nodu) | Rezervacije, ocenjevanje, prijava — srce sistema |
| **Longhorn** | Oba noda | Distribuirano shranjevanje — podatki so na obeh prenosnikih hkrati |
| **MetalLB** | Oba noda | Dodeli fiksen IP naslov ({{LB_IP}}) za dostop do aplikacije |
| **Cloudflare** | Zunanji (oblak) | DNS, SSL, proxy — nima fizične prisotnosti na šoli |

---

## 💻 **Strojna oprema in omrežje**

### 📊 **Specifikacije — kaj je v vsakem prenosniku**

| Node | Model | CPU (procesor) | RAM (spomin) | Disk | Vloga |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Krmilnik, etcd, aplikacija, primarna baza |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Krmilnik, etcd, aplikacija, rezervna baza |

> 💡 **Zakaj 16GB in 8GB?** k3s-1 ima več RAM-a, ker gosti primarno
> PostgreSQL bazo. k3s-2 je lažji, ker je samo replica (podvojitev).
> Oba imata SSD disk, kar je bistveno hitreje od starih trdih diskov
> (HDD). SSD je kot avtocesta, HDD kot makadamska pot.

### 🌐 **Omrežne nastavitve — kje v omrežju so**

```bash
# Lokalno omrežje (Arnes — šolsko omrežje)
k3s-1: {{K3S_1_IP}}/24
k3s-2: {{K3S_2_IP}}/24
Gateway (izhod v svet): {{GATEWAY_IP}}
DNS (prevajalnik imen): {{DNS_IP}}

# Kubernetes interno omrežje za "posode" (Podi)
# Vsak Pod dobi svoj interni IP — tega zunaj ne vidiš
10.42.0.0/16

# Kubernetes interno omrežje za storitve (Services)
# To so fiksni naslovi znotraj clustra
10.43.0.0/16

# LoadBalancer IP pool (MetalLB) — rezerviran nabor IP-jev
# {{LB_IP}} je eden izmed teh
{{METALLB_RANGE_START}} - {{METALLB_RANGE_END}}
```

> ⚠️ **Pogosta past:** Pod CIDR (`10.42.0.0/16`) in Service CIDR
> (`10.43.0.0/16`) se NE smeta prekrivati z lokalnim omrežjem
> ({{K3S_1_IP}}/24). Če se, Kubernetes ne bo deloval pravilno. To je
> najpogostejši razlog, da k3s ne štarta.

### 🔑 **Dostop do sistema**

```bash
# SSH — oddaljeni dostop do vsakega prenosnika posebej
ssh {{SSH_USER}}@{{K3S_1_IP}}    # k3s-1
ssh {{SSH_USER}}@{{K3S_2_IP}}    # k3s-2

# Kubernetes (k3s) — orodje za upravljanje clustra
# kubeconfig (datoteka z "ključem" do clustra) je na obeh nodih
kubectl get nodes -o wide
kubectl get pods -A -o wide

# Aplikacija v brskalniku
https://{{DOMAIN}}          # prek Cloudflare + LoadBalancer (od koderkoli)
http://{{LB_IP}}:{{LB_PORT}}     # direkt (samo znotraj šolskega omrežja)
```

---

## ☸️ **Kubernetes (k3s) Cluster**

### 🤔 **Kaj sploh je Kubernetes? (za začetnike)**

Predstavljaj si, da imaš dva kuharja v restavraciji. Vsak zna pripraviti vse
jedilne liste. Če eden zboli, drugi brez težav nadaljuje. **Kubernetes je
kot vodja kuhinje** — odloča, kdo kaj kuha, kdaj se zamenjata in kaj
narediti, če nekaj zagori. Samo namesto jedilnih listov upravlja s
programskimi "posodami" (Podi in Deploymenti).

**k3s** je posebej lahka različica Kubernetes, narejena prav za majhne
naprave — kot sta naša prenosnika. Ne potrebuje veliko RAM-a, dela na
strojih, kjer bi "pravi" Kubernetes obupal.

### ✅ **Stanje nodov — preveri, če vse diha**

```bash
kubectl get nodes -o wide

# NAME    STATUS   ROLES                       AGE   VERSION        INTERNAL-IP      EXTERNAL-IP
# k3s-1   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_1_IP}}    <none>
# k3s-2   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_2_IP}}    <none>
```

> ✅ **STATUS = Ready** pomeni, da je node zdrav in pripravljen poganjati
> aplikacije. Če vidiš `NotReady`, je nekaj narobe — preveri omrežje,
> disk, ali pa je prenosnik enostavno ugasnjen.

### 🔧 **Namestitev k3s — kako smo vse skupaj postavili**

```bash
# Na k3s-1 (prvi node — "šef")
curl -sfL https://get.k3s.io | sh -s - server \
  --cluster-init \
  --disable=traefik \
  --node-ip={{K3S_1_IP}} \
  --flannel-iface=eth0

# Na k3s-2 (drugi node — "pomočnik")
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://{{K3S_1_IP}}:6443 \
  --disable=traefik \
  --node-ip={{K3S_2_IP}} \
  --flannel-iface=eth0 \
  --token <NODE_TOKEN>
```

Token (geslo za pridružitev clustru) dobiš z:
```bash
sudo cat /var/lib/rancher/k3s/server/node-token  # poženi na k3s-1
```

> 💡 **Zakaj `--disable=traefik`?** k3s privzeto namesti Traefik kot
> vhodna vrata (ingress). Mi pa uporabljamo **MetalLB** namesto tega,
> ker daje več nadzora nad IP-naslovi. Zato Traefik izklopimo — ne
> potrebujemo dveh vratarjev na istih vratih.

---

## 🚀 **Aplikacija Sola App**

### 📦 **Kako aplikacija teče**

Aplikacija živi v Kubernetes namespace (predalčku) `sola-app`. Namespace je
kot mapa na računalniku — v njej so vsi viri, ki pripadajo aplikaciji.

```bash
kubectl get deployments -n sola-app    # Deploymenti — "recepti" za pode
kubectl get pods -n sola-app -o wide   # Podi — dejanski tekoči primerki
kubectl get services -n sola-app       # Storitve — "naslovi" za dostop
```

Aplikacija teče v **dveh podih** (ena na vsakem nodu):

```bash
kubectl get pods -n sola-app -o wide

# NAME                        READY   STATUS    RESTARTS   AGE   IP           NODE
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.0.x    k3s-1
# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.1.x    k3s-2
```

> 💡 **Pod** je najmanjša enota v Kubernetesu — kot ena "posoda" s
> programom v njej. Vsak pod ima svoj interni IP (npr. `10.42.0.x`),
> ki ga druge komponente znotraj clustra vidijo.
>
> **Deployment** pa je "recept" — pove Kubernetesu: "hočem 2 poda te
> aplikacije, vedno." Če eden crkne, Kubernetes samodejno zažene
> novega.

### 🐳 **Docker Image**

- **Ime slike:** `sola-app:latest`
- **Recept za sliko:** `reservation_app/k8s/Dockerfile`
- **Kubernetes recept:** `reservation_app/k8s/sola-app.yaml`

> 💡 **Docker image** je kot shranjena igra na CD-ju — vsebuje vse, kar
> aplikacija potrebuje za zagon (program, knjižnice, nastavitve), zapakirano
> v eno datoteko. Kubernetes to "sliko" razpakira in zažene v Podu.

### 🔄 **Posodobitev aplikacije**

Ko popraviš kodo in jo objaviš:

```bash
cd reservation_app
git pull
# Počakaj, da se CI build konča (GitHub Actions avtomatsko zgradi novo sliko)
# ali pa ročno zaženi zamenjavo:
kubectl rollout restart deployment -n sola-app sola-app
kubectl rollout status deployment -n sola-app sola-app
```

> ⚡ **Rollout restart** pove Kubernetesu: "ustavi stare pode in zaženi
> nove z najnovejšo sliko." To se zgodi **brez izpada** — en pod se
> ustavi šele, ko je drugi že pripravljen. Temu se reče **rolling
> update** (valjajoča posodobitev).

---

## 🗄️ **PostgreSQL HA — CloudNativePG**

### 🧬 **Zakaj potrebujemo HA bazo?**

Predstavljaj si, da je baza podatkov **dnevnik vsega, kar se dogaja v
aplikaciji** — vsaka rezervacija, vsaka ocena, vsak uporabnik. Če ta
dnevnik izgine, je vse izgubljeno.

**CloudNativePG (CNPG)** je orodje, ki samodejno vzdržuje dve kopiji baze:
- **Primary** (glavna) — sprejema vse spremembe (pisanje in branje)
- **Replica** (podvojitev) — samo bere, podatke sproti kopira od primary

Podatki se pretakajo iz primary v replica v realnem času prek **streaming
replikacije** — kot bi imel dve tabli, kjer učitelj piše na eno, druga pa
samodejno prepiše vsako črko v istem trenutku.

### ✅ **Stanje — preveri bazo**

```bash
kubectl get pods -n sola-app -o wide | grep db

# NAME                    READY   STATUS    IP            NODE
# sola-db-1 (primary)     1/1     Running   10.42.0.x     k3s-1
# sola-db-2 (replica)     1/1     Running   10.42.1.x     k3s-2
```

Primary je vedno na k3s-1, replica na k3s-2 — dokler je vse v redu.

### 🔄 **Failover — kaj se zgodi, ko k3s-1 crkne**

Failover (izpad in prevzem) poteka samodejno. Tole je zaporedje korakov:

1. **Primarni pod `sola-db-1` postane nedosegljiv** — prenosnik je crknil,
   omrežni kabel je padel, ali je kdo odklopil napajanje.
2. **CNPG operator zazna izpad** — počaka 30 sekund (`failoverDelay`),
   da se prepriča, da ni začasen trzaj.
3. **CNPG promovira `sola-db-2` (na k3s-2) v primary** — replika postane
   glavna baza. Vse spremembe, ki so prišle do nje, ostanejo.
4. **Service `sola-db-rw` se avtomatsko preusmeri na `sola-db-2`** —
   aplikacija sploh ne opazi spremembe, še naprej deluje.
5. **App pod na k3s-1 je mrtev** → k3s ga samodejno prestavi (reschedule)
   na k3s-2.
6. **App na k3s-2 se poveže na `sola-db-rw`** (ki zdaj kaže na
   `sola-db-2`) → sistem deluje naprej.

> ⏱️ **Skupni čas izpada:** ~1–2 minuti
> - 30s failover delay (čakanje, da se prepričamo)
> - ~30s za promocijo replike v primary
> - nekaj sekund, da k3s zazna mrtvi node in prestavi pode

> ⚠️ **Pomembno:** V teh 1–2 minutah uporabniki vidijo napako ali
> "stran se nalaga". To je normalno. Po tem času sistem deluje naprej,
> kot da se ni nič zgodilo. **Podatki niso izgubljeni** — replika
> ima vse, kar je primary uspelo poslati pred izpadom.

### 🔌 **Dostop do baze**

```bash
# Primarna baza (read-write) — za aplikacijo in admin poizvedbe
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL

# Replica (read-only) — za poročila in analitiko (ne obremenjuje primary)
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL_RO
```

### 🏷️ **Servisni endpointi (CNPG)**

CNPG samodejno ustvari tri Kubernetes Services — vsaka služi drugemu
namenu:

| Service | Vloga | Kdaj se uporablja |
|---|---|---|
| `sola-db-rw.sola:5432` | **Read-Write** — vedno na primary | Aplikacija (pisanje in branje) |
| `sola-db-ro.sola:5432` | **Read-Only** — samo replica | Poročila, analitika, obsežne poizvedbe |
| `sola-db-r.sola:5432` | **Read** — katerakoli instance (primary ali replica) | Ko ni pomembno, kje se bere |

> 💡 `DATABASE_URL` v aplikaciji kaže na `sola-db-rw` — ob failoverju
> (izpadu primary) se ta storitev samodejno preusmeri na nov primary.
> **Aplikacija niti ne izve, da se je baza zamenjala.**

---

## ☁️ **Cloudflare DNS**

### 🌍 **Kako uporabniki najdejo do nas**

**DNS (Domain Name System)** je kot telefonski imenik na internetu. Ko
nekdo vtipka `{{DOMAIN}}`, DNS posreduje IP-naslov, kjer aplikacija živi.
Cloudflare je naš "imenikar" — in še več.

### 📝 **DNS zapisi**

| Tip | Ime | Vrednost | Proxy |
|---|---|---|---|
| A | `@` ({{DOMAIN}}) | {{LB_IP}} | ✅ Cloudflare proxy (LoadBalancer) |
| A | `www` | {{LB_IP}} | ✅ Cloudflare proxy |

> 💡 **A zapis** (Address record) pove: "domena x pripada IP-ju y".
> Enostavno preslikovanje.

### 🔒 **SSL/TLS — zelena ključavnica**

Cloudflare poskrbi za varnost na dva načina:

- **Edge certifikat** — med uporabnikom in Cloudflare: promet je šifriran
  (HTTPS, zelena ključavnica v brskalniku)
- **Flexible SSL** — med Cloudflare in našim strežnikom: promet je v
  navadnem HTTP (brez šifriranja), ker smo v šolskem omrežju in je to varno

**Nastavitve v Cloudflare dashboard:**

- **SSL/TLS encryption mode:** `Flexible`
- **Always Use HTTPS:** ON — vse obiskovalce preusmeri na HTTPS
- **Minimum TLS Version:** 1.2 — ne dovoli starih, nevarnih povezav

> ⚠️ **Zakaj Flexible in ne Full?** Flexible pomeni, da Cloudflare šifrira
> povezavo do uporabnika, ampak do nas (MetalLB) gre brez šifriranja.
> To je v redu, ker je promet znotraj šolskega omrežja — nihče ne more
> prisluškovati. Če bi želeli Full SSL, bi potrebovali veljaven certifikat
> tudi na našem strežniku, kar je dodaten strošek in kompleksnost.

---

## 💾 **Longhorn Storage**

### 🗃️ **Kaj je Longhorn?**

Longhorn je sistem za **distribuirano shranjevanje** — namesto da bi imel
vsak prenosnik svoj disk z ločenimi podatki, Longhorn poskrbi, da so
podatki **sinhronizirani na obeh prenosnikih**. Če eden crkne, so podatki
še vedno na drugem.

**Analogija:** Dva zaposlena imata vsak svoj seznam strank. Longhorn
poskrbi, da kadar eden doda novo stranko, se ta takoj pojavi tudi na
seznamu drugega.

### ✅ **Stanje**

```bash
kubectl get pvc -n sola-app                  # PVC-ji — "zahteve za shrambo"
kubectl get volumes.longhorn.io -n longhorn-system  # dejanski volumni v Longhornu
```

### 📦 **PVC-ji (Persistent Volume Claims) — zahteve za prostor**

| PVC | Velikost | Način dostopa | Namen |
|---|---|---|---|
| `sola-postgresql` | 5Gi | RWO | Podatki baze (tabele, indeksi) |
| `sola-postgresql-wal` | 2Gi | RWO | WAL logi (dnevnik sprememb) |

> 💡 **RWO** (ReadWriteOnce) — samo en pod lahko piše na ta disk naenkrat.
> To je pravilno za PostgreSQL, ker ne smeta dva hkrati pisati v bazo.

### 📖 **Globlja razlaga PVC-jev**

| PVC | Kaj shranjuje | Zakaj je pomembno |
|---|---|---|
| `sola-postgresql` (5Gi) | **Podatki PG baze** — vse tabele, indeksi, uporabniki, rezervacije, ocene. To je "glavni" PVC. | Brez tega ni baze. 5Gi zadostuje za celotno šolsko leto. Če bo kdaj polno, lahko povečamo. |
| `sola-postgresql-wal` (2Gi) | **Write-Ahead Logs (WAL)** — dnevnik vsake spremembe, preden se zapiše v podatkovne datoteke. | Brez WAL-a replica ne more slediti primaryju. Uporablja se za crash recovery, streaming replikacijo in point-in-time recovery. |

> 💡 **Zakaj dva ločena PVC-ja?** PostgreSQL vsako spremembo najprej
> zapiše v WAL, šele nato v glavne podatkovne datoteke. Ločena PVC-ja
> omogočata različne profile hitrosti — WAL je zaporedno pisanje
> (hitro), podatki so naključni bralno-pisalni dostopi (počasnejši).
> Prav tako omogoča ločeni backup strategiji: WAL se arhivira sproti,
> podatki se periodično posnamejo.

### 🔄 **Replikacija**

Longhorn replikacija (2 kopiji) zagotavlja, da tudi ob izgubi enega noda
podatki ostanejo. Oba PVC-ja imata dve repliki — vsaka na svojem k3s nodu.

> ⚠️ **Pomembno za vzdrževanje:** Ko ugašaš en node (npr. za poletno
> pavzo), počakaj, da Longhorn konča rebalansiranje. Sicer bodo podatki
> samo na enem nodu in ob okvari slednjega bi bili izgubljeni.

---
