     1|🌐 **Jezik / Language:** [🇸🇮 Slovenščina](main.md) | [🇬🇧 English](en/main.md)
     2|
     3|---
     4|
     5|> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
     6|> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
     7|> Secrets ali kontaktirajte administratorja.
     8|
     9|---
    10|
    11|> 🛠️ **Prilagodi dokumentacijo svojim IP-jem**
    12|>
    13|> Vsa dokumentacija uporablja centralno datoteko `.env.ip`, kjer so definirani
    14|> vsi IP-naslovi, porti in domene. Želiš dokumentacijo s svojimi podatki?
    15|>
    16|> ```bash
    17|> cd documentation
    18|> nano .env.ip                          # vnesi svoje IP-je
    19|> ./replace-ips.sh                      # dokumentacija se prilagodi
    20|> ```
    21|>
    22|> Skripta zamenja vse IP-je v `.md` datotekah. Po zagonu lahko komande
    23|> neposredno kopiraš in prilepiš v terminal — delujejo brez spreminjanja.
    24|
    25|---
    26|
    27|# 🚀 **ostc-app — Rezervacijski sistem OŠ Toneta Čufarja**
    28|## **Dokumentacija za vzpostavitev, uporabo in vzdrževanje**
    29|
    30|---
    31|
    32|Doberdošli! Ta dokument je **glavni vhod** v celoten sistem. Če bereš to, si
    33|verjetno ravnatelj, učitelj, IT-tehnik ali pa samo radoveden starš, ki želi
    34|vedeti, kako sploh deluje šolski rezervacijski sistem. **Ne skrbi, če nisi
    35|računalniški strokovnjak** — vsak tehnični izraz bom razložil sproti, kot bi
    36|razlagal svojemu sosedu.
    37|
    38|Sistem teče na **dveh prenosnikih HP ProBook** v omari na šoli. To ni
    39|enostaven "klikni in končaj" programček — to je pravi mali **Kubernetes
    40|cluster** (beri: "kubernetes klaster"), kar pomeni, da aplikacija laufa na
    41|dveh računalnikih hkrati. Če eden crkne, drugi takoj prevzame. **To je high
    42|availability (HA)** — visoka razpoložljivost. Kot da bi imel dva učitelja v
    43|razredu: če en zboli, drugi brez prekinitve nadaljuje uro.
    44|
    45|---
    46|
    47|## 📚 **Kazalo dokumentacije**
    48|
    49|Spodaj so povezave na vse poddokumente. Vsak pokriva en specifičen vidik:
    50|
    51|| Dokument | Opis | Za koga |
    52||---|---|---|
    53|| [🏗️ **HA arhitektura**](HA.md) | CloudNativePG, avtomatski failover, potek ob izpadu noda | DevOps, IT-tehnik |
    54|| [🌞 **Poletna pavza**](POLETNA_PAVZA.md) | Varen izklop k3s clustra čez poletje in ponoven vklop jeseni | IT-tehnik, ravnatelj |
    55|| [☁️ **Domena in DNS**](domena.md) | Nastavitev domene, Cloudflare, DNS zapisi | DevOps, IT-tehnik |
    56|| [🐍 **Postavi lokalni app**](postavi-lokalni-app.md) | Namestitev na enem računalniku (brez Kubernetes) | Učitelj, programer začetnik |
    57|| [☸️ **K3s setup**](k3s-setup.md) | Namestitev k3s clustra iz nič | DevOps, IT-tehnik |
    58|| [⚙️ **Admin/devops navodila**](admin-devops-navodila.md) | Vzdrževanje, posodabljanje, odpravljanje težav | DevOps, IT-tehnik |
    59|| [👩‍🏫 **Navodila za učitelje**](navodila-ucitelji.md) | Uporaba aplikacije — rezervacije in ocenjevanja | Učitelji |
    60|| [👑 **Navodila za vodstvo**](navodila-vodstvo.md) | Upravljanje prek brskalnika (serije, zasedeni datumi) | Ravnatelj, pomočnik |
    61|| [📱 **Opis aplikacije**](aplikacija-rezervacije.md) | Kaj aplikacija omogoča, namen, funkcionalnosti | Vsi |
    62|| [📖 **Navodila za uporabnika**](navodila-uporabnika.md) | Prijava, gesla, dnevna uporaba | Učitelji, učenci, starši |
    63|
    64|---
    65|
    66|## 📑 **Kazalo vsebine** (ta dokument)
    67|
    68|1. [🏗️ Arhitektura sistema — kako vse skupaj stoji in diha](#arhitektura-sistema)
    69|2. [💻 Strojna oprema in omrežje — kaj fizično stoji v šoli](#strojna-oprema-in-omrežje)
    70|3. [☸️ Kubernetes (k3s) Cluster — "OS za oblak" na dveh prenosnikih](#kubernetes-k3s-cluster)
    71|4. [🚀 Aplikacija Sola App — srce sistema](#aplikacija-sola-app)
    72|5. [🗄️ PostgreSQL HA — baza podatkov, ki ne crkne](#postgresql-ha--cloudnativepg)
    73|6. [☁️ Cloudflare DNS — kako uporabniki najdejo do nas](#cloudflare-dns)
    74|7. [💾 Longhorn Storage — pametno shranjevanje podatkov](#longhorn-storage)
    75|8. [📅 Dnevni backup in reporti — avtomatsko poročilo vsako jutro](#dnevni-backup-in-reporti)
    76|9. [🔧 Vzdrževanje in okvare — kaj narediti, ko gre kaj narobe](#vzdrževanje-in-okvare)
    77|10. [📋 Celoten sklic ukazov — goljfija za admina](#celoten-sklic-ukazov)
    78|
    79|---
    80|
    81|## 🏗️ **Arhitektura sistema**
    82|
    83|### 🖥️ **Strojna in omrežna shema**
    84|
    85|Predstavljaj si, da imaš dva prenosnika, povezana v isto lokalno omrežje
    86|(Arnes). Vsak poganja iste stvari: aplikacijo, bazo podatkov in shrambo. Če
    87|en prenosnik odpove (crkne napajalnik, zamrzne OS, pade omrežni kabel), drugi
    88|samodejno prevzame vse njegove naloge. **To je high availability (HA)** —
    89|sistem, ki ne pozna izpada.
    90|
    91|Tole je shema, kako so komponente povezane:
    92|
    93|> 📐 **Diagram:** odpri `diagrams/arhitektura-clustra.drawio` v [app.diagrams.net](https://app.diagrams.net) (File → Open)
    94|
    95|> **Opomba:** Oba noda (vozlišča) sta `control-plane, etcd` — to pomeni, da
    96|> ni ločenih "delavskih" (worker) nodov. k3s dovoljuje poganjanje aplikacij
    97|> tudi na krmilnih (control-plane) nodih. Če bi imeli večji sistem, bi
    98|> ločili — ampak za šolsko rabo dva zadoščata.
    99|
   100|### 🌊 **Prometni tok — kako podatki potujejo od učitelja do aplikacije**
   101|
   102|Ko učitelj odpre `https://{{DOMAIN}}` v brskalniku, se zgodi tole:
   103|
   104|```
   105|🌐 Učitelj v brskalniku
   106|  → vtipka {{DOMAIN}}
   107|  → Internet
   108|  → Cloudflare (poskrbi za SSL-varnost in proxy)
   109|  → naš Service LoadBalancer (MetalLB na {{LB_IP}}:{{LB_PORT}})
   110|    → sola-app Pod (na k3s-1 ALI k3s-2 — kateri je trenutno prost)
   111|```
   112|
   113|Če pa si v šolskem omrežju in ne greš prek spleta, lahko uporabiš direktno
   114|povezavo:
   115|
   116|```
   117|  → http://{{LB_IP}}:{{LB_PORT}} → direkt na LoadBalancer
   118|```
   119|
   120|> 💡 **Zakaj Cloudflare proxy?** Cloudflare je vhodna vrata s stražarjem.
   121|> Skrbi za:
   122|> - **SSL certifikat** — zelena ključavnica v brskalniku
   123|> - **DDoS zaščito** — preprečuje, da bi kdo preobremenil sistem
   124|> - **Cache** — hitrejše nalaganje
   125|
   126|> ⚡ **Pomembno:** Cloudflare proxy kaže direktno na naš **LoadBalancer
   127|> ({{LB_IP}}, port 80)**. Promet gre direkt na MetalLB, visoka
   128|> razpoložljivost (HA) deluje samodejno — če en node crkne, MetalLB
   129|> premakne IP na drugega.
   130|
   131|### 🧩 **Pregled komponent — kratek slovarček**
   132|
   133|| Komponenta | Fizično | Kaj počne |
   134||---|---|---|
   135|| **k3s-1** | HP ProBook 455 G5 ({{K3S_1_IP}}) | Krmilni node + aplikacija + primarna baza |
   136|| **k3s-2** | HP ProBook 450 G5 ({{K3S_2_IP}}) | Krmilni node + aplikacija + rezervna baza |
   137|| **Sola App** (FastAPI) | 2 poda (en na vsakem nodu) | Rezervacije, ocenjevanje, prijava — srce sistema |
   138|| **Longhorn** | Oba noda | Distribuirano shranjevanje — podatki so na obeh prenosnikih hkrati |
   139|| **MetalLB** | Oba noda | Dodeli fiksen IP naslov ({{LB_IP}}) za dostop do aplikacije |
   140|| **Cloudflare** | Zunanji (oblak) | DNS, SSL, proxy — nima fizične prisotnosti na šoli |
   141|
   142|---
   143|
   144|## 💻 **Strojna oprema in omrežje**
   145|
   146|### 📊 **Specifikacije — kaj je v vsakem prenosniku**
   147|
   148|| Node | Model | CPU (procesor) | RAM (spomin) | Disk | Vloga |
   149||---|---|---|---|---|---|
   150|| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Krmilnik, etcd, aplikacija, primarna baza |
   151|| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Krmilnik, etcd, aplikacija, rezervna baza |
   152|
   153|> 💡 **Zakaj 16GB in 8GB?** k3s-1 ima več RAM-a, ker gosti primarno
   154|> PostgreSQL bazo. k3s-2 je lažji, ker je samo replica (podvojitev).
   155|> Oba imata SSD disk, kar je bistveno hitreje od starih trdih diskov
   156|> (HDD). SSD je kot avtocesta, HDD kot makadamska pot.
   157|
   158|### 🌐 **Omrežne nastavitve — kje v omrežju so**
   159|
   160|```bash
   161|# Lokalno omrežje (Arnes — šolsko omrežje)
   162|k3s-1: {{K3S_1_IP}}/24
   163|k3s-2: {{K3S_2_IP}}/24
   164|Gateway (izhod v svet): {{GATEWAY_IP}}
   165|DNS (prevajalnik imen): {{DNS_IP}}
   166|
   167|# Kubernetes interno omrežje za "posode" (Podi)
   168|# Vsak Pod dobi svoj interni IP — tega zunaj ne vidiš
   169|10.42.0.0/16
   170|
   171|# Kubernetes interno omrežje za storitve (Services)
   172|# To so fiksni naslovi znotraj clustra
   173|10.43.0.0/16
   174|
   175|# LoadBalancer IP pool (MetalLB) — rezerviran nabor IP-jev
   176|# {{LB_IP}} je eden izmed teh
   177|{{METALLB_RANGE_START}} - {{METALLB_RANGE_END}}
   178|```
   179|
   180|> ⚠️ **Pogosta past:** Pod CIDR (`10.42.0.0/16`) in Service CIDR
   181|> (`10.43.0.0/16`) se NE smeta prekrivati z lokalnim omrežjem
   182|> ({{K3S_1_IP}}/24). Če se, Kubernetes ne bo deloval pravilno. To je
   183|> najpogostejši razlog, da k3s ne štarta.
   184|
   185|### 🔑 **Dostop do sistema**
   186|
   187|```bash
   188|# SSH — oddaljeni dostop do vsakega prenosnika posebej
   189|ssh {{SSH_USER}}@{{K3S_1_IP}}    # k3s-1
   190|ssh {{SSH_USER}}@{{K3S_2_IP}}    # k3s-2
   191|
   192|# Kubernetes (k3s) — orodje za upravljanje clustra
   193|# kubeconfig (datoteka z "ključem" do clustra) je na obeh nodih
   194|kubectl get nodes -o wide
   195|kubectl get pods -A -o wide
   196|
   197|# Aplikacija v brskalniku
   198|https://{{DOMAIN}}          # prek Cloudflare + LoadBalancer (od koderkoli)
   199|http://{{LB_IP}}:{{LB_PORT}}     # direkt (samo znotraj šolskega omrežja)
   200|```
   201|
   202|---
   203|
   204|## ☸️ **Kubernetes (k3s) Cluster**
   205|
   206|### 🤔 **Kaj sploh je Kubernetes? (za začetnike)**
   207|
   208|Predstavljaj si, da imaš dva kuharja v restavraciji. Vsak zna pripraviti vse
   209|jedilne liste. Če eden zboli, drugi brez težav nadaljuje. **Kubernetes je
   210|kot vodja kuhinje** — odloča, kdo kaj kuha, kdaj se zamenjata in kaj
   211|narediti, če nekaj zagori. Samo namesto jedilnih listov upravlja s
   212|programskimi "posodami" (Podi in Deploymenti).
   213|
   214|**k3s** je posebej lahka različica Kubernetes, narejena prav za majhne
   215|naprave — kot sta naša prenosnika. Ne potrebuje veliko RAM-a, dela na
   216|strojih, kjer bi "pravi" Kubernetes obupal.
   217|
   218|### ✅ **Stanje nodov — preveri, če vse diha**
   219|
   220|```bash
   221|kubectl get nodes -o wide
   222|
   223|# NAME    STATUS   ROLES                       AGE   VERSION        INTERNAL-IP      EXTERNAL-IP
   224|# k3s-1   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_1_IP}}    <none>
   225|# k3s-2   Ready    control-plane,etcd,master   3d    v1.32.3+k3s1   {{K3S_2_IP}}    <none>
   226|```
   227|
   228|> ✅ **STATUS = Ready** pomeni, da je node zdrav in pripravljen poganjati
   229|> aplikacije. Če vidiš `NotReady`, je nekaj narobe — preveri omrežje,
   230|> disk, ali pa je prenosnik enostavno ugasnjen.
   231|
   232|### 🔧 **Namestitev k3s — kako smo vse skupaj postavili**
   233|
   234|```bash
   235|# Na k3s-1 (prvi node — "šef")
   236|curl -sfL https://get.k3s.io | sh -s - server \
   237|  --cluster-init \
   238|  --disable=traefik \
   239|  --node-ip={{K3S_1_IP}} \
   240|  --flannel-iface=eth0
   241|
   242|# Na k3s-2 (drugi node — "pomočnik")
   243|curl -sfL https://get.k3s.io | sh -s - server \
   244|  --server https://{{K3S_1_IP}}:6443 \
   245|  --disable=traefik \
   246|  --node-ip={{K3S_2_IP}} \
   247|  --flannel-iface=eth0 \
   248|  --token <NODE_TOKEN>
   249|```
   250|
   251|Token (geslo za pridružitev clustru) dobiš z:
   252|```bash
   253|sudo cat /var/lib/rancher/k3s/server/node-token  # poženi na k3s-1
   254|```
   255|
   256|> 💡 **Zakaj `--disable=traefik`?** k3s privzeto namesti Traefik kot
   257|> vhodna vrata (ingress). Mi pa uporabljamo **MetalLB** namesto tega,
   258|> ker daje več nadzora nad IP-naslovi. Zato Traefik izklopimo — ne
   259|> potrebujemo dveh vratarjev na istih vratih.
   260|
   261|---
   262|
   263|## 🚀 **Aplikacija Sola App**
   264|
   265|### 📦 **Kako aplikacija teče**
   266|
   267|Aplikacija živi v Kubernetes namespace (predalčku) `sola-app`. Namespace je
   268|kot mapa na računalniku — v njej so vsi viri, ki pripadajo aplikaciji.
   269|
   270|```bash
   271|kubectl get deployments -n sola-app    # Deploymenti — "recepti" za pode
   272|kubectl get pods -n sola-app -o wide   # Podi — dejanski tekoči primerki
   273|kubectl get services -n sola-app       # Storitve — "naslovi" za dostop
   274|```
   275|
   276|Aplikacija teče v **dveh podih** (ena na vsakem nodu):
   277|
   278|```bash
   279|kubectl get pods -n sola-app -o wide
   280|
   281|# NAME                        READY   STATUS    RESTARTS   AGE   IP           NODE
   282|# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.0.x    k3s-1
   283|# sola-app-xxxxx-xxxxx        1/1     Running   0          2d    10.42.1.x    k3s-2
   284|```
   285|
   286|> 💡 **Pod** je najmanjša enota v Kubernetesu — kot ena "posoda" s
   287|> programom v njej. Vsak pod ima svoj interni IP (npr. `10.42.0.x`),
   288|> ki ga druge komponente znotraj clustra vidijo.
   289|>
   290|> **Deployment** pa je "recept" — pove Kubernetesu: "hočem 2 poda te
   291|> aplikacije, vedno." Če eden crkne, Kubernetes samodejno zažene
   292|> novega.
   293|
   294|### 🐳 **Docker Image**
   295|
   296|- **Ime slike:** `sola-app:latest`
   297|- **Recept za sliko:** `reservation_app/k8s/Dockerfile`
   298|- **Kubernetes recept:** `reservation_app/k8s/sola-app.yaml`
   299|
   300|> 💡 **Docker image** je kot shranjena igra na CD-ju — vsebuje vse, kar
   301|> aplikacija potrebuje za zagon (program, knjižnice, nastavitve), zapakirano
   302|> v eno datoteko. Kubernetes to "sliko" razpakira in zažene v Podu.
   303|
   304|### 🔄 **Posodobitev aplikacije**
   305|
   306|Ko popraviš kodo in jo objaviš:
   307|
   308|```bash
   309|cd reservation_app
   310|git pull
   311|# Počakaj, da se CI build konča (GitHub Actions avtomatsko zgradi novo sliko)
   312|# ali pa ročno zaženi zamenjavo:
   313|kubectl rollout restart deployment -n sola-app sola-app
   314|kubectl rollout status deployment -n sola-app sola-app
   315|```
   316|
   317|> ⚡ **Rollout restart** pove Kubernetesu: "ustavi stare pode in zaženi
   318|> nove z najnovejšo sliko." To se zgodi **brez izpada** — en pod se
   319|> ustavi šele, ko je drugi že pripravljen. Temu se reče **rolling
   320|> update** (valjajoča posodobitev).
   321|
   322|---
   323|
   324|## 🗄️ **PostgreSQL HA — CloudNativePG**
   325|
   326|### 🧬 **Zakaj potrebujemo HA bazo?**
   327|
   328|Predstavljaj si, da je baza podatkov **dnevnik vsega, kar se dogaja v
   329|aplikaciji** — vsaka rezervacija, vsaka ocena, vsak uporabnik. Če ta
   330|dnevnik izgine, je vse izgubljeno.
   331|
   332|**CloudNativePG (CNPG)** je orodje, ki samodejno vzdržuje dve kopiji baze:
   333|- **Primary** (glavna) — sprejema vse spremembe (pisanje in branje)
   334|- **Replica** (podvojitev) — samo bere, podatke sproti kopira od primary
   335|
   336|Podatki se pretakajo iz primary v replica v realnem času prek **streaming
   337|replikacije** — kot bi imel dve tabli, kjer učitelj piše na eno, druga pa
   338|samodejno prepiše vsako črko v istem trenutku.
   339|
   340|### ✅ **Stanje — preveri bazo**
   341|
   342|```bash
   343|kubectl get pods -n sola-app -o wide | grep db
   344|
   345|# NAME                    READY   STATUS    IP            NODE
   346|# sola-db-1 (primary)     1/1     Running   10.42.0.x     k3s-1
   347|# sola-db-2 (replica)     1/1     Running   10.42.1.x     k3s-2
   348|```
   349|
   350|Primary je vedno na k3s-1, replica na k3s-2 — dokler je vse v redu.
   351|
   352|### 🔄 **Failover — kaj se zgodi, ko k3s-1 crkne**
   353|
   354|Failover (izpad in prevzem) poteka samodejno. Tole je zaporedje korakov:
   355|
   356|1. **Primarni pod `sola-db-1` postane nedosegljiv** — prenosnik je crknil,
   357|   omrežni kabel je padel, ali je kdo odklopil napajanje.
   358|2. **CNPG operator zazna izpad** — počaka 30 sekund (`failoverDelay`),
   359|   da se prepriča, da ni začasen trzaj.
   360|3. **CNPG promovira `sola-db-2` (na k3s-2) v primary** — replika postane
   361|   glavna baza. Vse spremembe, ki so prišle do nje, ostanejo.
   362|4. **Service `sola-db-rw` se avtomatsko preusmeri na `sola-db-2`** —
   363|   aplikacija sploh ne opazi spremembe, še naprej deluje.
   364|5. **App pod na k3s-1 je mrtev** → k3s ga samodejno prestavi (reschedule)
   365|   na k3s-2.
   366|6. **App na k3s-2 se poveže na `sola-db-rw`** (ki zdaj kaže na
   367|   `sola-db-2`) → sistem deluje naprej.
   368|
   369|> ⏱️ **Skupni čas izpada:** ~1–2 minuti
   370|> - 30s failover delay (čakanje, da se prepričamo)
   371|> - ~30s za promocijo replike v primary
   372|> - nekaj sekund, da k3s zazna mrtvi node in prestavi pode
   373|
   374|> ⚠️ **Pomembno:** V teh 1–2 minutah uporabniki vidijo napako ali
   375|> "stran se nalaga". To je normalno. Po tem času sistem deluje naprej,
   376|> kot da se ni nič zgodilo. **Podatki niso izgubljeni** — replika
   377|> ima vse, kar je primary uspelo poslati pred izpadom.
   378|
   379|### 🔌 **Dostop do baze**
   380|
   381|```bash
   382|# Primarna baza (read-write) — za aplikacijo in admin poizvedbe
   383|kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL
   384|
   385|# Replica (read-only) — za poročila in analitiko (ne obremenjuje primary)
   386|kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL_RO
   387|```
   388|
   389|### 🏷️ **Servisni endpointi (CNPG)**
   390|
   391|CNPG samodejno ustvari tri Kubernetes Services — vsaka služi drugemu
   392|namenu:
   393|
   394|| Service | Vloga | Kdaj se uporablja |
   395||---|---|---|
   396|| `sola-db-rw.sola:5432` | **Read-Write** — vedno na primary | Aplikacija (pisanje in branje) |
   397|| `sola-db-ro.sola:5432` | **Read-Only** — samo replica | Poročila, analitika, obsežne poizvedbe |
   398|| `sola-db-r.sola:5432` | **Read** — katerakoli instance (primary ali replica) | Ko ni pomembno, kje se bere |
   399|
   400|> 💡 `DATABASE_URL` v aplikaciji kaže na `sola-db-rw` — ob failoverju
   401|> (izpadu primary) se ta storitev samodejno preusmeri na nov primary.
   402|> **Aplikacija niti ne izve, da se je baza zamenjala.**
   403|
   404|---
   405|
   406|## ☁️ **Cloudflare DNS**
   407|
   408|### 🌍 **Kako uporabniki najdejo do nas**
   409|
   410|**DNS (Domain Name System)** je kot telefonski imenik na internetu. Ko
   411|nekdo vtipka `{{DOMAIN}}`, DNS posreduje IP-naslov, kjer aplikacija živi.
   412|Cloudflare je naš "imenikar" — in še več.
   413|
   414|### 📝 **DNS zapisi**
   415|
   416|| Tip | Ime | Vrednost | Proxy |
   417||---|---|---|---|
   418|| A | `@` ({{DOMAIN}}) | {{LB_IP}} | ✅ Cloudflare proxy (LoadBalancer) |
   419|| A | `www` | {{LB_IP}} | ✅ Cloudflare proxy |
   420|
   421|> 💡 **A zapis** (Address record) pove: "domena x pripada IP-ju y".
   422|> Enostavno preslikovanje.
   423|
   424|### 🔒 **SSL/TLS — zelena ključavnica**
   425|
   426|Cloudflare poskrbi za varnost na dva načina:
   427|
   428|- **Edge certifikat** — med uporabnikom in Cloudflare: promet je šifriran
   429|  (HTTPS, zelena ključavnica v brskalniku)
   430|- **Flexible SSL** — med Cloudflare in našim strežnikom: promet je v
   431|  navadnem HTTP (brez šifriranja), ker smo v šolskem omrežju in je to varno
   432|
   433|**Nastavitve v Cloudflare dashboard:**
   434|
   435|- **SSL/TLS encryption mode:** `Flexible`
   436|- **Always Use HTTPS:** ON — vse obiskovalce preusmeri na HTTPS
   437|- **Minimum TLS Version:** 1.2 — ne dovoli starih, nevarnih povezav
   438|
   439|> ⚠️ **Zakaj Flexible in ne Full?** Flexible pomeni, da Cloudflare šifrira
   440|> povezavo do uporabnika, ampak do nas (MetalLB) gre brez šifriranja.
   441|> To je v redu, ker je promet znotraj šolskega omrežja — nihče ne more
   442|> prisluškovati. Če bi želeli Full SSL, bi potrebovali veljaven certifikat
   443|> tudi na našem strežniku, kar je dodaten strošek in kompleksnost.
   444|
   445|---
   446|
   447|## 💾 **Longhorn Storage**
   448|
   449|### 🗃️ **Kaj je Longhorn?**
   450|
   451|Longhorn je sistem za **distribuirano shranjevanje** — namesto da bi imel
   452|vsak prenosnik svoj disk z ločenimi podatki, Longhorn poskrbi, da so
   453|podatki **sinhronizirani na obeh prenosnikih**. Če eden crkne, so podatki
   454|še vedno na drugem.
   455|
   456|**Analogija:** Dva zaposlena imata vsak svoj seznam strank. Longhorn
   457|poskrbi, da kadar eden doda novo stranko, se ta takoj pojavi tudi na
   458|seznamu drugega.
   459|
   460|### ✅ **Stanje**
   461|
   462|```bash
   463|kubectl get pvc -n sola-app                  # PVC-ji — "zahteve za shrambo"
   464|kubectl get volumes.longhorn.io -n longhorn-system  # dejanski volumni v Longhornu
   465|```
   466|
   467|### 📦 **PVC-ji (Persistent Volume Claims) — zahteve za prostor**
   468|
   469|| PVC | Velikost | Način dostopa | Namen |
   470||---|---|---|---|
   471|| `sola-postgresql` | 5Gi | RWO | Podatki baze (tabele, indeksi) |
   472|| `sola-postgresql-wal` | 2Gi | RWO | WAL logi (dnevnik sprememb) |
   473|
   474|> 💡 **RWO** (ReadWriteOnce) — samo en pod lahko piše na ta disk naenkrat.
   475|> To je pravilno za PostgreSQL, ker ne smeta dva hkrati pisati v bazo.
   476|
   477|### 📖 **Globlja razlaga PVC-jev**
   478|
   479|| PVC | Kaj shranjuje | Zakaj je pomembno |
   480||---|---|---|
   481|| `sola-postgresql` (5Gi) | **Podatki PG baze** — vse tabele, indeksi, uporabniki, rezervacije, ocene. To je "glavni" PVC. | Brez tega ni baze. 5Gi zadostuje za celotno šolsko leto. Če bo kdaj polno, lahko povečamo. |
   482|| `sola-postgresql-wal` (2Gi) | **Write-Ahead Logs (WAL)** — dnevnik vsake spremembe, preden se zapiše v podatkovne datoteke. | Brez WAL-a replica ne more slediti primaryju. Uporablja se za crash recovery, streaming replikacijo in point-in-time recovery. |
   483|
   484|> 💡 **Zakaj dva ločena PVC-ja?** PostgreSQL vsako spremembo najprej
   485|> zapiše v WAL, šele nato v glavne podatkovne datoteke. Ločena PVC-ja
   486|> omogočata različne profile hitrosti — WAL je zaporedno pisanje
   487|> (hitro), podatki so naključni bralno-pisalni dostopi (počasnejši).
   488|> Prav tako omogoča ločeni backup strategiji: WAL se arhivira sproti,
   489|> podatki se periodično posnamejo.
   490|
   491|### 🔄 **Replikacija**
   492|
   493|Longhorn replikacija (2 kopiji) zagotavlja, da tudi ob izgubi enega noda
   494|podatki ostanejo. Oba PVC-ja imata dve repliki — vsaka na svojem k3s nodu.
   495|
   496|> ⚠️ **Pomembno za vzdrževanje:** Ko ugašaš en node (npr. za poletno
   497|> pavzo), počakaj, da Longhorn konča rebalansiranje. Sicer bodo podatki
   498|> samo na enem nodu in ob okvari slednjega bi bili izgubljeni.
   499|
   500|---
   501|