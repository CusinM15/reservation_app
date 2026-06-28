     1|🌐 **Jezik / Language:** [🇸🇮 Slovenščina](k3s-setup.md) | [🇬🇧 English](en/k3s-setup.md)
     2|
     3|---
     4|
     5|> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
     6|> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
     7|> Secrets ali kontaktirajte administratorja.
     8|
     9|---
    10|
    11|# ☸️ K3s Setup — Šolski Rezervacijski Sistem (ostc-app)
    12|
    13|> **Kaj sploh je Kubernetes in zakaj ga rabimo?**
    14|>
    15|> Kubernetes (krajše K8s) je **orodje za vodenje zbirke programov** — kot bi imeli pametnega hišnika,
    16|> ki pazi, da vsi programi na strežnikih tečejo, se samodejno zaženejo, če padejo, in porazdelijo
    17|> obiskovalce med več strežnikov. Če en strežnik crkne, Kubernetes poskrbi, da program še vedno
    18|> deluje na drugem. Brez njega bi morali vse to delati ročno — in ob 3h zjutraj, ko pade baza, to
    19|> ni zabavno.
    20|>
    21|> **Kaj je k3s?**
    22|>
    23|> k3s je **lažja verzija Kubernetes** — kot Fiat Punto namesto BMW-ja, ampak za šolo čisto dovolj.
    24|> Originalni Kubernetes (»vanilla K8s«) je ogromen, težek in požre veliko spomina. k3s je zmanjšan
    25|> na eno samo izvršljivo datoteko, porabi manj kot polovico RAM-a, pa vseeno naredi čisto vse,
    26|> kar rabimo. Odlično za manjše strežnike, kot sta naša HP ProBook laptopa.
    27|
    28|## 📋 Arhitektura (trenutna)
    29|
    30|Naš sistem teče na **dveh HP ProBook laptopih** — oba igrata vlogo krmilnika (control-plane) in
    31|hkrati nosita podatke (etcd). Nimamo ločenih delavskih nodov (worker nodes). To je lažja
    32|konfiguracija, ki za šolski sistem povsem zadostuje.
    33|
    34|> 📐 **Diagram:** odpri `diagrams/k3s-setup-arhitektura.drawio` v [app.diagrams.net](https://app.diagrams.net) (File → Open)
    35|
    36|
    91|
    92|### Razlaga arhitekture v preprosti slovenščini:
    93|
    94|| Sestavina | Vloga | Enostavna razlaga |
    95||-----------|-------|-------------------|
    96|| **Cloudflare** | Vhodna vrata (DNS + zaščita) | Ko nekdo vnese `ostc-app.org`, Cloudflare pove, na katerem IP-ju aplikacija živi. Ščiti nas tudi pred napadi. |
    97|| **MetalLB** | Razdeljevalec prometa | Dodeli javni IP in usmerja obiskovalce na enega od dveh strežnikov. |
    98|| **k3s-1 in k3s-2** | Strežnika (HP ProBook laptopa) | Dejanski računalniki, ki poganjajo aplikacijo. Oba sta enakovredna — če eden crkne, drugi prevzame. |
    99|| **sola-app** | Sama aplikacija (FastAPI) | Program, prek katerega učitelji rezervirajo prostore in opremo. |
   100|| **sola-db-1 / sola-db-2** | Podatkovna baza (PostgreSQL) | Hrani vse rezervacije, uporabnike in nastavitve. Baza se samodejno podvaja (replicira) med oba strežnika. |
   101|| **Longhorn** | Shramba (disk) | Poskrbi, da se datoteke in podatki shranjujejo na obeh laptopih, tako da jih ne izgubimo, če eden odpove. |
   102|
   103|---
   104|
   105|## 📋 Predpogoji — Kaj moramo imeti pripravljeno, preden začnemo?
   106|
   107|Preden sploh začnemo z nameščanjem, moramo imeti:
   108|
   109|- **2 fizični mašini z Ubuntu 24.04 LTS** — v našem primeru dva HP ProBook laptopa
   110|- Vsaka mašina: vsaj **2 CPU jedri**, **4 GB RAM**, **20 GB diska** (več je vedno bolje)
   111|- **sudo dostop** na obeh — to pomeni, da imamo skrbniške pravice (lahko nameščamo programe)
   112|- Mašini morata biti v **istem omrežju** — da se lahko med seboj pogovarjata
   113|- **Docker** nameščen (potrebujemo ga za gradnjo slik aplikacije):
   114|
   115|```bash
   116|# Docker namestimo z uradnim skriptom — požene se in vse uredi samodejno
   117|curl -fsSL https://get.docker.com | sudo sh
   118|# Dodamo svojega uporabnika v skupino 'docker', da nam ni treba ves čas pisati 'sudo'
   119|sudo usermod -aG docker $USER
   120|```
   121|
   122|> ⚠️ Po `usermod` se **odjavite in ponovno prijavite**, da začne veljati.
   123|
   124|---
   125|
   126|## 1. Namestitev k3s (oba noda kot control-plane)
   127|
   128|### 1.1 Namesti k3s na prvem nodu (k3s-1)
   129|
   130|To je trenutek, ko prvi laptop postane **gospodar (master)** k8s gruče.
   131|
   132|```bash
   133|curl -sfL https://get.k3s.io | sh -s - server \
   134|  --disable=traefik \
   135|  --disable=servicelb \
   136|  --write-kubeconfig-mode=644 \
   137|  --cluster-cidr=10.42.0.0/16 \
   138|  --service-cidr=10.43.0.0/16 \
   139|  --node-ip={{K3S_1_IP}}
   140|```
   141|
   142|#### 🔍 Kaj se dogaja?
   143|
   144|Ukaz naredi naslednje:
   145|
   146|1. **`curl -sfL https://get.k3s.io`** — z uradne k3s spletne strani prenese namestitveni skript
   147|2. **`| sh -s - server`** — požene skript in mu reče, naj namesti **strežniško** (server) različico. Če bi napisali `agent` namesto `server`, bi namestili le delavca (worker), ki ne more sam sprejemati odločitev.
   148|3. **`--disable=traefik`** — **IZKLOPIMO** vgrajeni Traefik (spletni vratar / reverse proxy). Zakaj? Ker bomo namesto njega uporabili **MetalLB**, ki je boljši za naše potrebe. Če tega ne izklopimo, bi imeli dva vratarja, ki bi se prepirala, kdo upravlja promet.
   149|4. **`--disable=servicelb`** — **IZKLOPIMO** vgrajeni Service Load Balancer. Spet — uporabili bomo kakovostnejši MetalLB namesto osnovne k3s rešitve.
   150|5. **`--write-kubeconfig-mode=644`** — omogoči, da lahko naš uporabnik (ne samo root) uporablja `kubectl` ukaze. Brez tega bi morali vsakemu ukazu dodati `sudo`.
   151|6. **`--cluster-cidr=10.42.0.0/16`** — določi **naslovni prostor za zbirke (pode)**. Vsak programski zabojnik (pod) dobi svoj IP znotraj tega območja.
   152|7. **`--service-cidr=10.43.0.0/16`** — določi **naslovni prostor za storitve (services)**. Storitve so javna vrata do programov.
   153|8. **`--node-ip={{K3S_1_IP}}`** — pove k3s, kateri IP naj uporabi za ta računalnik. To je **notranji omrežni IP** (npr. 192.168.1.10), ne javni.
   154|
   155|#### ⚠️ Kaj se zgodi, če izpustimo `--disable=traefik`?
   156|
   157|Na vsakem nodu bi se zagnal Traefik, ki bi poskušal odpreti vrata 80 in 443. Potem bi namestili še MetalLB in oba bi se borila za ista vrata. Aplikacija ne bi delovala, logi bi bili polni napak »port already in use«. **Zato Traefik in ServiceLB vedno izklopimo.**
   158|
   159|#### ⚠️ Kaj se zgodi, če izpustimo `--write-kubeconfig-mode=644`?
   160|
   161|Vsak `kubectl` ukaz bi zahteval `sudo`. Ker bomo `kubectl` uporabljali ves čas, bi bilo to zelo nepraktično. To je nastavitev za udobje, ne nujnost.
   162|
   163|---
   164|
   165|### 1.2 Pridobi token — »vstopnica« za nove člane gruče
   166|
   167|Token je **kot geslo za zabavo**, ki novemu računalniku dovoli vstop v gručo (cluster).
   168|Brez njega se drugi strežnik ne more povezati s prvim.
   169|
   170|```bash
   171|# Preberemo token iz datoteke, ki jo je k3s ustvaril med namestitvijo
   172|sudo cat /var/lib/rancher/k3s/server/node-token
   173|```
   174|
   175|#### 🔍 Kaj se dogaja?
   176|
   177|K3s je med namestitvijo ustvaril skrivno datoteko `/var/lib/rancher/k3s/server/node-token`. V njej je niz znakov, podoben temu:
   178|
   179|```
   180|K107f8a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0::server:node:1234567890abcdef
   181|```
   182|
   183|Ta niz bomo uporabili v naslednjem koraku, ko bomo drugi laptop dodajali v gručo.
   184|
   185|---
   186|
   187|### 1.3 Namesti k3s na drugem nodu (k3s-2)
   188|
   189|Zdaj drugi laptop povežemo v gručo. Vidite, kako uporabimo token?
   190|
   191|```bash
   192|curl -sfL https://get.k3s.io | sh -s - server \
   193|  --server https://{{K3S_1_IP}}:6443 \
   194|  --token <TOKEN> \
   195|  --disable=traefik \
   196|  --disable=servicelb \
   197|  --write-kubeconfig-mode=644 \
   198|  --node-ip={{K3S_2_IP}}
   199|```
   200|
   201|#### 🔍 Kaj se dogaja?
   202|
   203|Razlika od prve namestitve:
   204|
   205|1. **`--server https://{{K3S_1_IP}}:6443`** — to pove drugemu laptopu: »Poveži se s prvim laptopom na vratih 6443 (to so privzeta k3s vrata za pogovarjanje med strežniki).« Brez tega bi drugi laptop poskušal ustvariti **novo, ločeno gručo** — in ne bi pridružil obstoječi.
   206|2. **`--token <TOKEN>`** — »vstopnica«, ki smo jo pridobili v prejšnjem koraku. Brez pravilnega tokena prvi strežnik zavrne povezavo.
   207|
   208|Vse ostalo (`--disable=traefik`, `--disable=servicelb`, ...) je enako kot na prvem.
   209|
   210|---
   211|
   212|### 1.4 Preveri, da oba laptopa delujeta skupaj
   213|
   214|```bash
   215|kubectl get nodes
   216|# NAME    STATUS   ROLES                AGE
   217|# k3s-1   Ready    control-plane,etcd   1m
   218|# k3s-2   Ready    control-plane,etcd   30s
   219|```
   220|
   221|#### 🔍 Kaj se dogaja?
   222|
   223|`kubectl get nodes` vpraša gručo: »Kdo si ti in kdo so tvoji prijatelji?«
   224|
   225|Če vidimo oba noda s STATUS `Ready`, pomeni, da se drugi laptop uspešno pridružil prvemu in oba delujeta. Izpis `ROLES: control-plane,etcd` pomeni, da oba laptopa:
   226|- **control-plane** — sprejemata odločitve (kaj naj se zgodi, če nekaj pade)
   227|- **etcd** — hranita podatke o stanju gruče (kaj je nameščeno, kje teče)
   228|
   229|#### ⚠️ Če node ni `Ready`?
   230|
   231|Pogledamo log-e:
   232|```bash
   233|sudo journalctl -u k3s --no-pager | tail -50
   234|```
   235|Najpogostejši vzroki:
   236|- Napačen token
   237|- Napačen `--node-ip`
   238|- Ogenj (firewall) blokira vrata 6443
   239|- Laptopa nista v istem omrežju
   240|
   241|---
   242|
   243|## 2. Namestitev MetalLB — »prometni policist« za našo gručo
   244|
   245|MetalLB je **orodje, ki programom v Kubernetes dodeli prave omrežne naslove (IP)**.
   246|Predstavljajte si ga kot prometnega policista, ki obiskovalce usmerja na pravi strežnik.
   247|
   248|Brez MetalLB-ja bi vsi programi dobili samo notranje IP-je (znotraj gruče) in ne bi bili
   249|dostopni od zunaj. Z MetalLB-jem dobijo svoj pravi IP v našem omrežju.
   250|
   251|```bash
   252|# 1. Namestimo MetalLB v gručo (prenese in zažene vse potrebno)
   253|kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml
   254|
   255|# 2. Počakamo, da so vsi MetalLB delčki (pods) pripravljeni
   256|kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=120s
   257|
   258|# 3. Uporabimo našo konfiguracijo (IP range, ki ga lahko MetalLB deli)
   259|kubectl apply -f k8s/cluster/metallb-config.yaml
   260|```
   261|
   262|#### 🔍 Kaj se dogaja?
   263|
   264|1. **`kubectl apply -f https://...`** — prenesemo in namestimo MetalLB iz uradnega vira.
   265|2. **`kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=120s`** — počakamo do 2 minuti, da se MetalLB zažene. Brez tega bi naslednji ukaz morda sprožil napako, ker MetalLB še ne bi bil pripravljen.
   266|3. **`kubectl apply -f k8s/cluster/metallb-config.yaml`** — uporabimo konfiguracijsko datoteko, ki MetalLB-ju pove: »Kateri IP naslovi so na voljo za razdeljevanje?«
   267|
   268|Datoteka `k8s/cluster/metallb-config.yaml` mora vsebovati IP range, npr.:
   269|
   270|```yaml
   271|apiVersion: metallb.io/v1beta1
   272|kind: IPAddressPool
   273|metadata:
   274|  name: primary
   275|  namespace: metallb-system
   276|spec:
   277|  addresses:
   278|  - {{LB_IP}}-{{LB_IP}}  # npr. 192.168.1.200-192.168.1.200
   279|---
   280|apiVersion: metallb.io/v1beta1
   281|kind: L2Advertisement
   282|metadata:
   283|  name: l2-advert
   284|  namespace: metallb-system
   285|spec:
   286|  ipAddressPools:
   287|  - primary
   288|```
   289|
   290|---
   291|
   292|## 3. Namestitev Longhorn — pametna shramba, ki ne izgubi podatkov
   293|
   294|Longhorn je **sistem za shranjevanje podatkov v Kubernetes**. Omogoča, da se podatki
   295|samodejno podvajajo (replicirajo) med oba laptopa. Če eden crkne, podatki ostanejo
   296|na drugem.
   297|
   298|### 3.1 Predpogoji na vsakem nodu — orodja, ki jih Longhorn potrebuje
   299|
   300|```bash
   301|# open-iscsi: orodje, ki Linuxu omogoča povezovanje z oddaljenimi diski
   302|# (iSCSI je protokol za dostop do diskov prek omrežja)
   303|sudo apt-get install -y open-iscsi
   304|
   305|# nfs-common: orodje za dostop do datotek prek omrežja
   306|# (NFS je protokol za souporabo map in datotek po omrežju)
   307|sudo apt-get install -y nfs-common
   308|
   309|# Zaženemo iscsid (strežnik za iSCSI povezave) in mu rečemo,
   310|# naj se samodejno zažene ob vsakem zagonu računalnika
   311|sudo systemctl enable --now iscsid
   312|```
   313|
   314|#### 🔍 Kaj se dogaja?
   315|
   316|- **open-iscsi** — Longhorn uporablja iSCSI protokol za komunikacijo z diski prek omrežja. Brez tega programa Longhorn ne more dostopati do prostora na disku.
   317|- **nfs-common** — dodatno orodje za deljenje datotek prek omrežja. Nekatere starejše Longhorn funkcije ga uporabljajo.
   318|- **systemctl enable --now iscsid** — `enable` pomeni, da se bo iscsid zagnal ob vsakem vklopu računalnika. `--now` pomeni, da ga zaženemo takoj, brez ponovnega zagona.
   319|
   320|#### ⚠️ Kaj se zgodi, če tega ne namestimo?
   321|
   322|Longhorn se bo namestil, vendar ne bo mogel ustvariti nobenega diska (volume). Podatkov ne bo kam shraniti. Vse, kar potrebuje prostor na disku, bo ostalo v stanju »Pending«.
   323|
   324|---
   325|
   326|### 3.2 Namesti Helm (upravitelj paketov za Kubernetes) in Longhorn
   327|
   328|Helm je kot »trgovina z aplikacijami« za Kubernetes. Namesto da ročno nameščamo vsako
   329|datoteko posebej, s Helmovimi grafi (charts) namestimo vse naenkrat.
   330|
   331|```bash
   332|# Namestitev Helma (upravitelja paketov)
   333|curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | sudo bash
   334|
   335|# Dodamo Longhorn trgovino (repo)
   336|helm repo add longhorn https://charts.longhorn.io
   337|
   338|# Osvežimo seznam razpoložljivih paketov
   339|helm repo update
   340|
   341|# Ustvarimo mapo (namespace) za Longhorn
   342|kubectl create namespace longhorn-system
   343|
   344|# Namestimo Longhorn s posebnimi nastavitvami
   345|helm install longhorn longhorn/longhorn \
   346|  --namespace longhorn-system \
   347|  --version 1.9.0 \
   348|  --set defaultSettings.defaultReplicaCount=2 \
   349|  --set persistence.defaultClassReplicaCount=2 \
   350|  --set defaultSettings.replicaSoftAntiAffinity=true \
   351|  --set persistence.defaultClass=true
   352|```
   353|
   354|#### 🔍 Kaj pomenijo te nastavitve?
   355|
   356|| Nastavitev | Pomen | Enostavna razlaga |
   357||------------|-------|-------------------|
   358|| `defaultReplicaCount=2` | Vsak kos podatkov naj bo shranjen v **2 izvodih** | Če en laptop crkne, drugi še vedno ima podatke |
   359|| `defaultClassReplicaCount=2` | Enako, ampak za privzeti razred shranjevanja | Dvojna varnost |
   360|| `replicaSoftAntiAffinity=true` | Podvode (replike) naj bodo na različnih laptopih | Če sta oba izvoda na istem laptopu in ta crkne, so podatki izgubljeni. Ta nastavitev jih poskuša razporediti na različne nod-e. |
   361|| `defaultClass=true` | Longhorn naj bo **privzeti način shranjevanja** v celotni gruči | Vsi programi bodo samodejno uporabljali Longhorn, razen če izrecno zahtevajo kaj drugega |
   362|
   363|---
   364|
   365|### 3.3 Omogoči samodejno uravnoteženje podvodov (replica-auto-balance)
   366|
   367|Ko dodamo nove diske ali ko se prostor na enem laptopu zmanjša, želimo, da Longhorn
   368|samodejno prerazporedi podatke.
   369|
   370|```bash
   371|kubectl patch settings.longhorn -n longhorn-system replica-auto-balance \
   372|  --type='merge' -p '{"value":"least-effort"}'
   373|```
   374|
   375|#### 🔍 Kaj se dogaja?
   376|
   377|- **`kubectl patch`** — spremenimo obstoječo nastavitev v Longhornu
   378|- **`replica-auto-balance`** — ime nastavitve, ki uravnoveša podvode
   379|- **`least-effort`** — Longhorn naj se trudi uravnotežiti, vendar naj ne seli podatkov po nepotrebnem (to bi upočasnilo delovanje)
   380|
   381|Druge možnosti so: `disabled` (ne uravnoteži) in `full` (vedno uravnoteži, tudi če to upočasni sistem). `least-effort` je zlata sredina.
   382|
   383|---
   384|
   385|## 4. CloudNativePG (CNPG) — pametna podatkovna baza, ki skrbi sama zase
   386|
   387|### 4.1 Kaj je »operator« in zakaj ga rabimo?
   388|
   389|**Operator** je kot **avtomatski skrbnik baze**. Namesto da bi ročno nameščali,
   390|posodabljali, varnostno kopirali in popravljali bazo, to namesto nas počne operator.
   391|
   392|Brez operatorja bi morali:
   393|- Ročno namestiti PostgreSQL
   394|- Ročno nastaviti podvajanje (replikacijo) med laptopoma
   395|- Ročno popraviti bazo, če pade
   396|- Ročno narediti varnostne kopije
   397|- Ročno zamenjati glavno bazo (failover) ob okvari
   398|
   399|Z operatorjem (CloudNativePG) pa:
   400|- Sam namesti bazo
   401|- Sam poskrbi za podvajanje
   402|- Sam popravi bazo, če pade
   403|- Sam naredi varnostne kopije (če nastavimo)
   404|- Sam zamenja glavno bazo, če ena crkne — v 30 sekundah
   405|
   406|---
   407|
   408|### 4.2 Namesti CNPG operator
   409|
   410|```bash
   411|# Dodamo CNPG trgovino
   412|helm repo add cnpg https://cloudnative-pg.github.io/charts
   413|
   414|# Namestimo operator v svoj namespace (mapo)
   415|helm install cnpg cnpg/cloudnative-pg \
   416|  --namespace cnpg-system \
   417|  --create-namespace
   418|```
   419|
   420|#### 🔍 Kaj se dogaja?
   421|
   422|- **`helm repo add cnpg https://...`** — dodamo naslov trgovine, kjer je CNPG operator
   423|- **`helm install cnpg cnpg/cloudnative-pg`** — namestimo operator v gručo
   424|- **`--namespace cnpg-system`** — vse datoteke operatorja bodo v mapi `cnpg-system`
   425|- **`--create-namespace`** — če mapa `cnpg-system` še ne obstaja, jo ustvari
   426|
   427|---
   428|
   429|### 4.3 Ustvari bazo (CNPG cluster) z dvema izvodoma
   430|
   431|```bash
   432|kubectl apply -f sola-cnpg-cluster.yaml
   433|```
   434|
   435|#### 🔍 Vsebina `sola-cnpg-cluster.yaml`:
   436|
   437|```yaml
   438|apiVersion: postgresql.cnpg.io/v1
   439|kind: Cluster
   440|metadata:
   441|  name: sola-db
   442|  namespace: sola
   443|spec:
   444|  instances: 2                    # dva izvoda baze (primarna + replica)
   445|  storage:
   446|    size: 1Gi                     # vsaka baza dobi 1 GB prostora
   447|    storageClass: longhorn        # shramba na Longhorn disku
   448|  bootstrap:
   449|    initdb:
   450|      database: sola              # ime baze
   451|      owner: sola                 # uporabniško ime za dostop do baze
   452|  affinity:
   453|    enablePodAntiAffinity: true   # replici naj bosta na različnih laptopih
   454|    podAntiAffinityType: preferred
   455|    topologyKey: kubernetes.io/hostname
   456|  enablePDB: true                 # PodDisruptionBudget — pazi, da vsaj ena baza vedno teče
   457|  failoverDelay: 30               # po 30 sekundah nedelovanja glavne baze prevzame replica
   458|```
   459|
   460|#### 🔍 Razlaga ključnih nastavitev:
   461|
   462|- **`instances: 2`** — imeli bomo dve bazi: ena je glavna (primary), druga je podvod (replica). Ko se podatki zapišejo v glavno, se samodejno prenesejo še v podvod.
   463|- **`storageClass: longhorn`** — baza bo shranjena na Longhorn disku (ki že sam podvaja podatke med oba laptopa). Tako imamo **dvojno varnost**: CNPG podvaja bazo, Longhorn pa še diske.
   464|- **`enablePodAntiAffinity: true`** — poskrbi, da oba izvoda baze **nista na istem laptopu**. Če sta oba na istem in ta crkne, nimamo več baze.
   465|- **`failoverDelay: 30`** — če glavna baza pade, CNPG počaka 30 sekund (da morda ni le začasna težava), nato pa podvod razglasi za novo glavno bazo.
   466|
   467|---
   468|
   469|## 5. Namestitev aplikacije (sola-app)
   470|
   471|### 5.1 Zgradi sliko aplikacije
   472|
   473|```bash
   474|# Greemo v mapo z aplikacijo
   475|cd /home/admin/reservation_app
   476|
   477|# Zgradimo Docker sliko (kot bi naredili arhiv celotnega programa)
   478|docker build -t sola-app:latest .
   479|
   480|# Pošljemo sliko v register (shrambo slik), da jo lahko Kubernetes povleče
   481|docker push sola-app:latest
   482|```
   483|
   484|#### 🔍 Kaj se dogaja?
   485|
   486|- **`docker build -t sola-app:latest .`** — prebere `Dockerfile` v trenutni mapi in naredi sliko (archive) programa. `-t sola-app:latest` določi ime in oznako (tag). Pike (`.`) pomeni »v trenutni mapi«.
   487|- **`docker push sola-app:latest`** — naloži sliko v spletno shrambo (Docker Hub ali naš lastni register), od koder jo bo Kubernetes prenesel na oba laptopa.
   488|
   489|---
   490|
   491|### 5.2 Ustvari namespace in skrivnosti (Secrets)
   492|
   493|```bash
   494|# Ustvarimo mapo (namespace) za aplikacijo
   495|kubectl create namespace sola-app
   496|
   497|# Ustvarimo skrivnosti — občutljive podatke, ki jih aplikacija potrebuje
   498|kubectl create secret generic sola-secrets \
   499|  --namespace sola-app \
   500|  --from-literal=MAIL_USERNAME=oscuf \
   501|