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
> neposredno kopiraš in prilepiš v terminal.
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
| [🌞 **Poletna pavza**](poletna-pavza.md) | Varen izklop k3s clustra čez poletje in ponoven vklop jeseni |
| [☁️ **Domena in DNS**](domena.md) | Nastavitev domene, Cloudflare, DNS zapisi |
| [🐍 **Postavi lokalni app**](postavi-lokalni-app.md) | Namestitev na enem računalniku (brez Kubernetes) |
| [☸️ **K3s setup**](k3s-setup.md) | Namestitev k3s clustra iz nič |
| [⚙️ **Admin/devops navodila**](admin-devops-navodila.md) | Vzdrževanje, posodabljanje, odpravljanje težav |
| [👩‍🏫 **Navodila za učitelje**](navodila-ucitelji.md) | Uporaba aplikacije — rezervacije in ocenjevanja |
| [👑 **Navodila za vodstvo**](navodila-vodstvo.md) | Upravljanje prek brskalnika (serije, zasedeni datumi) |
| [📱 **Opis aplikacije**](aplikacija-rezervacije.md) | Kaj aplikacija omogoča, namen, funkcionalnosti |

---

## 📑 **Kazalo vsebine**

1. [Sistemska arhitektura](#sistemska-arhitektura)
2. [Strojna oprema in omrežje](#strojna-oprema-in-omrežje)
3. [Domena in Cloudflare](#domena-in-cloudflare)
4. [Longhorn Storage](#longhorn-storage)
5. [Dnevni backup in reporti](#dnevni-backup-in-reporti)
6. [Audit log — dnevnik sprememb](#audit-log--dnevnik-sprememb)
7. [Vzdrževanje in okvare](#vzdrževanje-in-okvare)
7. [Poletna pavza](#poletna-pavza)
8. [Celoten sklic ukazov](#celoten-sklic-ukazov)
9. [Razlaga pojmov](#razlaga-pojmov)

---

## 🏗️ **Sistemska arhitektura**

> **V enem stavku:** Dva prenosnika HP ProBook, povezana v Kubernetes gručo z visoko razpoložljivostjo (če eden crkne, drugi prevzame).

> **ELI5:** Predstavljaj si **dva učitelja, ki imata enak dnevnik** (aplikacijo) in **ista dva pomočnika** (baza) — eden je glavni, drugi budno spremlja vse, kar glavni naredi. Če glavni zboli (crkne), pomočnik takoj prevzame njegovo mesto. Učenci (uporabniki) tega sploh ne opazijo. Vse skupaj je shranjeno v **dveh sefih** (Longhorn), tako da tudi če en sef crkne, podatki niso izgubljeni.

> **Razlaga diagrama:**
> - Dva računalnika (k3s-1 in k3s-2) skupaj v gruči — kot dve mizi  pisarni.
> - Na vsakem računalniku tečeta **ena kopija aplikacije (sola-app Pod)** in **ena kopija podatkovne baze (sola-db)**.
> - Podatkovna baza ima eno **primarno (PRIMARY)** in eno **replikacijsko (REPLICA)** instanco, ki nenehno kopira vse, kar primarna izvede.
> - Vsi podatki so shranjeni v **Longhornu** – sistemu, ki zagotavlja, da imate 2 kopiji na 2 različnih računalnikih, tako da tudi če en računalnik odpove, ne pride do izgube podatkov.
> - Ko uporabnik odpre brskalnik, promet poteka prek **Cloudflara** (varnostni filter + SSL) do **MetalLB LoadBalancerja** (recepcija), ki ga usmeri na eno od obeh kopij aplikacije.

### **Strojna in omrežna shema**

![Celotna k3s arhitektura — 2 noda, app podi, baza, LoadBalancer, Cloudflare](diagrams/arhitektura-clustra.png)


> **Opomba:** Oba noda sta `control-plane, etcd` — ni ločenih worker nodov. k3s poganja uporabniške pode tudi na control-plane nodih. To je čisto v redu za manjši cluster — pri 100+ nodih bi jih ločili, za šolski sistem z dvema HP ProBookoma pa je to tudi čisto ok (poleg tega je HA potem precej lažja).

> **Namig:** Oba HP ProBooka imata `control-plane` vlogo, ker k3s to omogoča brez težav. V velikih podjetjih (Google, Amazon) imajo ločene control-plane node, ampak tam gre za tisoče nodov. Za šolski cluster je to povsem OK — prihraniš strojno opremo in poenostaviš nastavitev.

### **Prometni tok**

> **Preprosta razlaga:** Ko učitelj vnese `https://{{DOMAIN}}` v brskalnik, se zgodi tole: brskalnik najprej vpraša Cloudflare (telefonski imenik interneta), kje je ta stran. Cloudflare pogleda v svoj imenik, vidi IP {{LB_IP}}, in pošlje uporabnika tja. Tam ga pričaka **MetalLB** (recepcija), ki ga preusmeri na eno od dveh kopij aplikacije — katerakoli je trenutno prosta.

![Prometni tok: uporabnik → Cloudflare → LoadBalancer → app pod](diagrams/prometni-tok.png)


> **Cloudflare proxy** kaže direktno na **LoadBalancer (`{{LB_IP}}`, port 80)** — promet gre direktno na MetalLB, HA deluje samodejno — če en node crkne, MetalLB premakne IP na drugega.

> **Nasvet:** Vedno uporabljaj Cloudflare proxy (oranžni oblak) — ne samo DNS-only (sivi oblak). Proxy ti da brezplačen SSL, DDoS zaščito, in skrije tvoj pravi IP pred hekerji. Če daš samo DNS, tvoj IP {{LB_IP}} javno razkriješ in vsak ga lahko direktno napade.

### **Pregled komponent**

|  | Komponenta | Lokacija | Namen |
|---|---|---|---|
| | **k3s-1** | HP ProBook 455 G5 ({{K3S_1_IP}}) | Control-plane, app pod, PG primary (glavni računalnik) |
| | **k3s-2** | HP ProBook 450 G5 ({{K3S_2_IP}}) | Control-plane, app pod, PG replica (pomožni računalnik) |
| | **Sola App (FastAPI)** | 2 poda (oba noda) | Rezervacije, ocenjevanja, prijava |
| | **Longhorn** | Oba noda | Distribuirano shranjevanje (PVC-ji) — podatki v 2 kopijah |
| | **MetalLB** | Oba noda | LoadBalancer IP ({{LB_IP}}) — vhodna vrata |
| | **Cloudflare** | Zunanji | DNS, SSL, proxy — varnost na internetu |

---

## 💻 **Strojna oprema in omrežje**

> **V enem stavku:** Dva navadna prenosnika HP ProBook, vsak s 256GB diskom, povezana v šolsko Arnes omrežje — to je vse, kar potrebuješ za celoten sistem.

> **ELI5:** Predstavljaj si, da imaš dva pisarniška računalnika. Prvi (k3s-1) ima 16GB RAM — to je kot večja miza, na katero lahko daš več papirjev. Drugi (k3s-2) ima 8GB RAM — manjša miza, ampak še vedno dovolj za rutinsko delo.

| Node | Model | CPU | RAM | Disk | Vloga |
|---|---|---|---|---|---|
| **k3s-1** | HP ProBook 455 G5 | AMD Ryzen 5 2500U | 16GB | 256GB SSD | Control-plane, etcd, app, PG primary (glavni) |
| **k3s-2** | HP ProBook 450 G5 | Intel Core i5-8250U | 8GB | 256GB SSD | Control-plane, etcd, app, PG replica (pomožni) |

> **Namig:** k3s-1 ima 16 GB RAM-a, k3s-2 pa 8 GB RAM-a. To ni napaka — primarna baza (PG primary) na k3s-1 rabi več RAM-a za cache in WAL buffere. Ko k3s-2 postane primary (ob failoverju), bo deloval malo počasneje, ampak sistem bo še vedno delal.

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

> **Pogosta napaka:** Pod CIDR (10.42.0.0/16) in Service CIDR (10.43.0.0/16) se ne smeta prekrivati z lokalnim omrežjem ({{K3S_1_IP}}/24). Če se, Kubernetes ne bo mogel pravilno usmerjati prometa. Vedno preveri z `ip route` na nodih, preden nastaviš k3s.

### **Dostop**

```bash
# SSH na k3s-1 (glavni)
ssh {{SSH_USER}}@{{K3S_1_IP}}

# SSH na k3s-2 (pomožni)
ssh {{SSH_USER}}@{{K3S_2_IP}}

# Preveri, ali vsi poganjajo
kubectl get nodes
```

> **Nasvet:** Uporabljaj SSH ključe namesto gesel — je varneje in hitreje. Na k3s-2 že imaš nastavljeno, da se lahko povežeš na k3s-1 brez gesla (SSH ključ).

---

## ☁️ **Domena in Cloudflare**

> **V enem stavku:** Cloudflare je **telefonski imenik interneta** — ko nekdo vnese `{{DOMAIN}}` v brskalnik, Cloudflare pove, kje (na katerem IP-ju) to aplikacijo najde, in poskrbi za varnostno povezavo (SSL).

> **ELI5 — DNS:** DNS (Domain Name System) je kot telefonski imenik za internet. Ti vpišeš ime (`{{DOMAIN}}`), DNS vrne številko (IP naslov). Namesto da se spomniš številke {{LB_IP}}, se spomniš imena `{{DOMAIN}}`. Veliko lažje, kajne?

Cloudflare DNS nastavitve (preveri na [dash.cloudflare.com](https://dash.cloudflare.com)):

| Tip | Ime | Vrednost | Proxy status |
|-----|-----|---------|-------------|
| A | `@` ({{DOMAIN}}) | {{LB_IP}} | ✅ Cloudflare proxy (LoadBalancer) |
| CNAME | `www` | {{LB_IP}} | ✅ Cloudflare proxy (preusmeri www na aplikacijo) |


> **Cloudflare proxy** je kot varnostnik pred vrati — skrije tvoj pravi IP, šifrira promet (SSL), blokira napade. **Vedno prižgi oranžni oblak** ☁️🟠

Cloudflare SSL/TLS nastavitve:

- **SSL/TLS encryption mode:** `Flexible`
- **Always Use HTTPS:** ON
- **Minimum TLS Version:** 1.2

> **Nasvet:** Flexible SSL je v redu za šolsko okolje, ampak če bi kdaj dodal podatke, ki zahtevajo PCI-DSS ali HIPAA skladnost, bi moral uporabiti Full (strict) SSL z let's encrypt certifikatom na origin strežniku. Za rezervacije terminov in ocene na OŠ pa je Flexible SSL povsem dovolj.
>
> **Kaj sta PCI-DSS in HIPAA?**
> - **PCI-DSS** = varnostni standard za **plačilne kartice** (Visa, Mastercard). Če bi šola pobirala plačila prek aplikacije (npr. prehrana, izleti), bi ga morala upoštevati.
> - **HIPAA** = ameriški zakon o **zasebnosti zdravstvenih podatkov**. Ker je aplikacija v Sloveniji in ne v ZDA, ga ni treba upoštevati — omenjen je samo kot primer, kaj vse zahteva višjo raven SSL.
>
> Za šolski sistem s prostori in ocenami oboje **ni relevantno** — lahko mirno spiš. 😴

> **Pogosta napaka:** Če nastaviš SSL/TLS na "Full" brez certifikata na originu, Cloudflare ne bo mogel vzpostaviti povezave in uporabniki bodo dobili 502 napako. Začni s "Flexible" (najlažje) in nadgradi, ko boš na origin dodal certifikat.

---

## 💾 **Longhorn Storage**

> **V enem stavku:** Longhorn je sistem za shranjevanje, ki poskrbi, da ima vsak podatek 2 kopiji na 2 različnih računalnikih — če en disk crkne, podatki niso izgubljeni.

> **ELI5 — Longhorn:** Predstavljaj si, da imaš **pomembno šolsko matično knjigo**. Longhorn je kot **fotokopirni stroj, ki vsako stran takoj fotokopira še na drugo pisalno mizo**. Če ena miza (računalnik) zagori, imaš fotokopijo na drugi mizi. Brez Longhorna bi bila tvoja matična knjiga samo na enem mestu — če ta disk crkne, so podatki za vedno izgubljeni.
>
> **ELI5 — PVC (PersistentVolumeClaim):** PVC je **virtualni trdi disk** v Kubernetesu. Aplikacija reče "rabim 5GB prostora" in Kubernetes + Longhorn ji ga zagotovita — tudi če se aplikacija preseli na drug računalnik, podatki ostanejo. Kot prenosni disk, ki ga lahko priklopiš na katerikoli računalnik.

### **Status**

```bash
kubectl get pvc -n sola-app
kubectl get volumes.longhorn.io -n longhorn-system
```

### **PVC-ji**

| PVC | Size | Access Mode | Uporaba |
|---|---|---|---|
| `sola-postgresql` | 5Gi | RWO | PG podatki |
| `sola-postgresql-wal` | 2Gi | RWO | WAL logi |

**Razlaga PVC-jev za ne-tehnične bralce:**

| PVC | Kaj shranjuje | Zakaj je pomembno |
|---|---|---|
| `sola-postgresql` (5Gi) | **Podatki PG baze** — vse tabele, indeksi, uporabniki, rezervacije, ocene. To je "glavni" PVC. | Brez tega ni baze. 5Gi zadostuje za celotno šolsko leto. |
| `sola-postgresql-wal` (2Gi) | **Write-Ahead Logs (WAL)** — dnevnik vsake spremembe, preden se zapiše v podatkovne datoteke. | Brez WAL-a replica ne more slediti primaryju. Uporablja se za crash recovery, streaming replikacijo in point-in-time recovery. |

> **ELI5 — PV (PersistentVolume):** V Kubernetesu imamo dva koncepta:
> - **PV** = **dejanski fizični disk** — pravi prostor na disku na enem od računalnikov.
> - **PVC** = **zahtevek** za ta disk — aplikacija reče "rabim 5GB".
>
> Tukaj **ne ustvarjaš PV-jev ročno** — **Longhorn to naredi namesto tebe**.
> Ko ustvariš PVC (npr. `sola-postgresql`), Longhorn v ozadju:
> 1. Ustvari PV na disku enega noda
> 2. Ustvari repliko na drugem nodu
> 3. Poveže PVC s tistim PV-jem
>
> Preveriš lahko z `kubectl get pv` — videl boš PV-je z imeni kot `pvc-...`, ki jih je ustvaril Longhorn.

> **ELI5 — WAL (Write-Ahead Log):** Predstavljaj si, da pišeš test. Najprej napišeš odgovor na **list za beležke (WAL)**

**Zakaj dva ločena PVC-ja?** PostgreSQL vsako spremembo najprej zapiše v WAL, šele nato v glavne podatkovne datoteke. Ločena PVC-ja omogočata različne I/O profile — WAL je zaporedno pisanje (hitro), podatki so naključni bralno-pisalni dostopi. Prav tako omogoča ločeni backup strategiji: WAL se arhivira sproti, podatki se periodično snapshottajo.

**Longhorn replikacija** (2 kopiji) zagotavlja, da tudi ob izgubi enega noda podatki ostanejo. Oba PVC-ja imata dve repliki — vsaka na svojem k3s nodu.

> **Namig:** 5Gi za podatke in 2Gi za WAL se sliši malo, ampak za šolski sistem z nekaj sto uporabniki in rezervacijami je to več kot dovolj. PostgreSQL je presenetljivo učinkovit s prostorom — cela baza za leto dni dela bo verjetno pod 1GB. Če boš kdaj blizu meje, spremljaš z `kubectl get pvc` in povečaš velikost — Longhorn omogoča online resize brez izpada.

---

## 📅 **Dnevni backup in reporti**

> **V enem stavku:** Vsako noč ob 4:00 zjutraj sistem samodejno pošlje varnostno kopijo baze na `BACKUP_EMAIL` in dnevno poročilo o stanju na `STANJE_MAIL` (obe spremenljivki iz `.env` datoteke). 

> **ELI5:** Predstavljaj si, da imaš **nočnega čuvaja**, ki vsako jutro ob 4:00:
> 1. **Fotokopira celotno šolsko matično knjigo** in ti jo pošlje v nabiralnik (email).
> 2. **Preveri ali vsi računalniki v šoli delujejo** in ti pošlje poročilo na email.
>

### **Dnevni backup baze (`sola-db-backup`)**

```bash
# Cron: 04:00 vsak dan (Europe/Ljubljana)
# Pošlje pg_dump celotne baze na BACKUP_EMAIL
kubectl get cronjob -n sola-app sola-db-backup
```

Naredi popoln posnetek baze (vse tabele, uporabniki, rezervacije, ocene) in ga pošlje na email. Če podatki crknejo (disk odpove, kdo zbriše bazo), imaš v emailu varnostno kopijo iz prejšnje noči.

### **Dnevni report stanja (`sola-daily-report`)**

```bash
# Cron: 04:00 vsak dan (Europe/Ljubljana)
# Pošlje poročilo o stanju nodov, Longhorn replik in aplikacij na STANJE_MAIL
kubectl get cronjob -n sola-app sola-daily-report
```

Poročilo vključuje:

- 📊 **Stanje nodov** — ali oba strežnika dihata
- 💾 **Stanje Longhorn replik** — ali so podatki pravilno podvojeni
- 🟢 **Stanje aplikacije** — ali vse deluje
- ⚠️ **Napake** — morebitne težave

> **Nasvet:** Email backup je **zanesljiv in preprost** — ne potrebuješ dodatnih orodij, vsak zna odpreti email. Ampak email se lahko izgubi v spam mapi. Zato enkrat na teden preveri še `kubectl get events -n sola-app --sort-by='.lastTimestamp'` — tam vidiš stvari, ki jih email report morda ne pokaže (OOMKilled, CrashLoopBackOff, neuspešni volume mounti).
>
> **Kaj pomenijo te napake?**
>
> | Napaka | Pomen | V praksi |
> |--------|-------|----------|
> | **OOMKilled** | Out Of Memory — aplikaciji je **zmanjkalo RAM-a**, Kubernetes jo je ugasnil | Aplikacija porabi več pomnilnika, kot mu je dodeljenega (npr. 128 MB namesto 256 MB). Popraviš s povečanjem `memory` limita v Deployment YAML. |
> | **CrashLoopBackOff** | Aplikacija se **nenehno sesipa in znova nalaga** — vsakič hitro crkne, Kubernetes jo poskuša znova zagnati | Kot da bi se računalnik sam od sebe ugašal takoj po vklopu. Vzrok je skoraj vedno napaka v kodi ali napačna nastavitev. Pogledaš log: `kubectl logs -n sola-app <pod-name>` |
> | **Neuspešni volume mounti** | Aplikacija ne more **priklopiti diska** — Longhorn diska ni našel ali je pokvarjen | Kot da bi hotel odpreti mapo na disku, pa je disk odklopljen. Preveriš z `kubectl get pv,pvc -n sola-app` in `kubectl get volumes.longhorn.io -n longhorn-system`. |

---

## 📋 **Audit log — dnevnik sprememb**


![Audit log pregled — filter, tabela, iskanje po akcijah](diagrams/audit-log-zgodovina.png)

> **V enem stavku:** Vsaka pomembna akcija (ustvarjanje/brisanje rezervacij, ocenjevanj, uporabnikov, blokiranje datumov) se samodejno zapiše v bazo skupaj s podatki o tem, **kdo** je to naredil in **kdaj**.

> **ELI5:** Predstavljaj si, da imaš **knjigo prihodov in odhodov** v šoli. Vsakič, ko nekdo nekaj spremeni (doda rezervacijo, zbriše ocenjevanje, ustvari uporabnika), se to zapiše v knjigo — s časom in imenom. Lahko greš kadarkoli nazaj in preveriš, kaj se je dogajalo. Brez ugibanj, brez "kdo je to zbrisal".

**Dostop:** Samo **admin** — v Admin panelu klikni **"Dnevnik dogodkov"** (poveže na `/history`). Vodstvo audit loga ne vidi.

> **Nasvet:** Audit log je **append-only** — vanj se samo dodaja, nikoli ne briše. Tudi če admin zbriše uporabnika, ostane zapis o tem v audit logu. To je namerno — revizijska sled mora biti nespremenljiva.

### Kako dostopam do audit loga?

1. Prijavi se v aplikacijo kot **admin**
2. Klikni **Admin panel** v zgornjem meniju
3. V Admin panelu klikni **"Dnevnik dogodkov"**

**Kdo lahko vidi audit log?**
- **Admin** — ja (prek Admin panel → Dnevnik dogodkov)
- **Vodstvo** — **ne**
- **Učitelji** — **ne**


**Kaj se beleži:**

| Akcija | Opis |
|--------|------|
| `create_rezervacija` | Ustvarjena enkratna rezervacija |
| `delete_rezervacija` | Izbrisana rezervacija |
| `create_series` | Ustvarjena tedenska/celodnevna serija |
| `delete_series` | Izbrisana celotna serija |
| `create_ocenjevanje` | Napovedano ocenjevanje |
| `delete_ocenjevanje` | Izbrisano ocenjevanje |
| `create_blocked_dates` | Dodani zasedeni datumi |
| `delete_blocked_date` | Odstranjen zaseden datum |
| `create_user` | Ustvarjen nov uporabnik (admin) |
| `update_user` | Posodobljen uporabnik (admin) |
| `delete_user` | Izbrisan uporabnik (admin) |
| `activate_user` | Aktiviran uporabnik (admin) |
| `deactivate_user` | Deaktiviran uporabnik (admin) |

**Ne beleži se:** branje podatkov (kdo si je kaj ogledal), neuspeli poskusi prijave — samo dejanske spremembe.

---

## 🔧 **Vzdrževanje in okvare**

> **V enem stavku:** Večino težav rešiš z enim ukazom `kubectl get ...` — poglej, kaj ne dela, in sistem sam poskrbi za ostalo.

### **Dnevne operacije**

> **ELI5:** To je tvoje **jutranje preverjanje**, kot pred vožnjo avtomobila — preveriš olje, tlak v gumah, luči. Tukaj preveriš, ali so vsi računalniki v gruči živi, ali aplikacije tečejo, ali diski niso polni.

```bash
# Preveri, ali so vsi računalniki v gruči živi
kubectl get nodes

# Preveri, ali aplikacija teče (vsi Podi naj bodo Running)
kubectl get pods -n sola-app

# Preveri, ali imamo dovolj diskovnega prostora
kubectl get pvc -n sola-app

# Preveri, ali so Longhorn diski v redu
kubectl get volumes.longhorn.io -n longhorn-system

# Preglej najnovejše dogodke (napake, opozorila)
kubectl get events -n sola-app --sort-by='.lastTimestamp'
```

### **Ko nekaj crkne**

> **ELI5:** Ne paničari. Kubernetes je zasnovan tako, da se sam popravlja. Večino težav reši z enim ukazom `kubectl get ...` — poglej, kaj je narobe, in ukrepaj po spodnjih navodilih.

#### **Če sam Pod crkne (aplikacija ne dela)**

```bash
# Poišči problematičen Pod
kubectl get pods -n sola-app

# Poglej log (zakaj je crknil?)
kubectl logs -n sola-app deploy/sola-app --tail=50

# Ponovni zagon (varno, brez izpada)
kubectl rollout restart deployment -n sola-app sola-app

# Počakaj, da se novi Podi zaženejo
kubectl rollout status deployment -n sola-app sola-app
```

#### **Če je cel node mrtev (k3s-1 ali k3s-2)**

```bash
# Preveri, ali je node še v gruči
kubectl get nodes

# Če je node NotReady, počakaj 2 minuti — k3s bo samodejno
# premaknil pode na drug node. Preveri z:
kubectl get pods -n sola-app -o wide

# Če se po 5 minutah podi ne premaknejo, ročno zbriši pode:
kubectl delete pod -n sola-app --all
# Kubernetes jih bo samodejno ustvaril na živih nodih
```

> **Nasvet:** Ne briši Podov po nepotrebnem. Kubernetes bo sam poskrbel za premik na drug node v 2-3 minutah. Ročno brisanje uporabi samo, če se podi "zataknejo" v stanju Terminating ali CrashLoopBackOff več kot 5 minut. Če si v dvomih, raje počakaj — Kubernetes je pametnejši, kot si misliš.

#### **Če je baza v težavah**

```bash
# Preveri stanje CNPG clustra
kubectl get cluster -n sola

# Poglej, kateri podi so živi
kubectl get pods -n sola -o wide

# Preveri Longhorn stanje volumnov
kubectl get volumes.longhorn.io -n longhorn-system

# Če je primary padel, bo CNPG samodejno promoviral replica v primary
# Počakaj do 2 minuti. Preveri z:
kubectl logs -n sola deploy/sola-db-1 --tail=50   # primarna baza
kubectl logs -n sola deploy/sola-db-2 --tail=50   # pomožna baza
```

#### **Če so vsi Podi v stanju Pending**

Vzrok je skoraj vedno pomanjkanje virov (CPU/RAM) ali Longhorn težava:

```bash
# Preveri, kaj se dogaja
kubectl describe pod -n sola-app <pod-name>

# Preveri vire na nodih
kubectl top nodes

# Preveri Longhorn
kubectl get volumes.longhorn.io -n longhorn-system
```

**Status izpod:** Če je node dosegljiv in ima vire, Kubernetes sam uredi — počakaj 2 minuti.

> **ELI5:** Stanje **Pending** pomeni, da Kubernetes poskuša postaviti Pod, vendar ne najde primernega računalnika (npr. vsi so zasedeni ali pa Longhorn ni na voljo). Kot da bi hotel rezervirati učilnico, pa so vse zasedene — čakaš, da se ena sprosti.

---

## 🔁 **Visoka razpoložljivost (HA)**

> Glej [🏗️ **HA arhitektura**](HA.md) za podrobnosti o CloudNativePG, avtomatskem failoverju in poteku ob izpadu noda.

> **V enem stavku:** Sistem zdrži izpad kateregakoli računalnika (k3s-1 ali k3s-2) brez izgube podatkov — aplikacija je nedosegljiva največ 1–2 minuti, medtem ko se baza in aplikacija preselita na preživeli računalnik.

**Potek ob izpadu:**

> **ELI5:** Predstavljaj si, da imaš **dva pomočnika v pisarni**. Eden (PG primary) piše vse v dnevnik, drugi (PG replica) prepisuje. Če prvi zbole in odide domov, drugi takoj prevzame njegovo mesto — nič se ne izgubi. Edino kar opaziš je, da je imel malo zmede prvih 30 sekund, potem pa vse teče naprej kot prej.

1. **Node crkne** (izpad elektrike, sesutje OS, disk odpove)
2. k3s **zazna mrtvi node** v ~30s (node timeout)
3. MetalLB **premakne LB IP** na živi node
4. **CNPG promovira** replica v primary (~30s)
5. **Aplikacijski Podi** se preselijo na živi node
6. Sistem stabilen v ~60s — vse skupaj do 2 min

**Skupni čas izpada:** ~1–2 minuti (30s failover delay + ~30s za promocijo + čas, da k3s zazna mrtvi node)

> **Namig:** 1-2 minuti izpada se sliši veliko, ampak v praksi je to za šolski sistem povsem sprejemljivo. Učitelj, ki osveži stran po 2 minutah, bo spet delal normalno — podatki niso izgubljeni, ker je Longhorn poskrbel za replikacijo. V primerjavi s starim sistemom (izpad za cel dan, dokler ne pride IT) je to ogromen napredek.

### **Dostop**

```bash
# Med failoverjem preveri, kaj se dogaja
kubectl get events -n sola --sort-by='.lastTimestamp'
kubectl get cluster -n sola
kubectl get pods -n sola -o wide
```

---

## 🌞 **Poletna pavza**

Glej [🌞 Poletna pavza](poletna-pavza.md).

> **Namig:** Poletna pavza je pogosto spregledana, ampak je ključna za dolgo življenjsko dobo strojne opreme. HP ProBooki v omari brez hlajenja čez poletje zlahka dosežejo 50°C v mirovanju. Izklop za 2 meseca podaljša življenjsko dobo diskov in baterij. Pred izklopom **obvezno** naredi snapshot Longhorn volumnov in dump baze — "bolje imeti in ne rabiti, kot rabiti in ne imeti."

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
kubectl exec -it -n sola-app deploy/sola-app -- /bin/sh          # Poveži se v terminal zabojnika

# === Upravljanje baze ===
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL                    # Poveži se na bazo
kubectl exec -it -n sola-app deploy/sola-app -- psql $SOLA_DATABASE_URL -c "SELECT * FROM users;"  # Poženi poizvedbo

# === Longhorn ===
kubectl get volumes.longhorn.io -n longhorn-system                # Stanje diskov
kubectl get engineimages.longhorn.io -n longhorn-system           # Različica Longhorn engine
kubectl get nodes.longhorn.io -n longhorn-system                  # Longhorn status na vsakem nodu

# === Git (na katerem koli nod-u v terminalu) ===
cd /home/admin/reservation_app
git pull                                    # Potegni zadnjo kodo
```

---

## 📖 **Razlaga pojmov**

*Razlaga tehničnih izrazov za ne-tehnične bralce — če ti kaj v dokumentaciji ni jasno, poglej tukaj — pomeni, da je razlaga napisana čim bolj preprosto, brez strokovnega žargona.*

| Pojem | Razlaga |
|---|---|
| **Arnes** | **Akademsko raziskovalna omrežna infrastruktura Slovenije** — slovenski izobraževalni internet. Šola je prek Arnesa povezana v internet. |
| **Cloudflare** | **Varnostnik pred tvojim strežnikom** — šifrira promet (SSL), skrije tvoj IP, blokira napade, pospešuje nalaganje. |
| **CloudNativePG (CNPG)** | **Pametni pomočnik za PostgreSQL bazo** — avtomatsko upravlja replikacijo, failover, backup in obnovitev. |
| **Cluster** | **Gruča računalnikov, ki delajo kot eno** — dva HP ProBooka, povezana v isto Kubernetes gručo. Kubernetes skrbi, da aplikacije tečejo na kateremkoli računalniku je na voljo. |
| **ConfigMap / Secret** | **Kubernetes objekti za shranjevanje nastavitev** — ConfigMap za javne nastavitve (npr. BASE_URL), Secret za občutljive podatke (gesla, ključi). Secret je zakodiran, ConfigMap je berljiv. |
| **Control-plane** | **"Možgani" clustra** — nadzorni del, ki sprejema vse odločitve. Na obeh HP ProBookih imamo control-plane, kar pomeni, da imamo dva "možgana" — če en crkne, drugi prevzame. |
| **DNS** | **Telefonski imenik interneta** — pretvori ime `{{DOMAIN}}` v IP naslov {{LB_IP}} (npr.). |
| **Docker Image** | **Recept za aplikacijo** — vsebuje program, knjižnice, nastavitve. Iz enega recepta lahko narediš več identičnih zabojnikov (Podov). |
| **ELI5** | *Explain Like I'm 5* (razloži kot petletniku) — način razlage, kjer se izogneš strokovnim izrazom in uporabiš vsakdanje analogije. Npr. Kubernetes ni "sistem za orkestracijo kontejnerjev", ampak "dirigent orkestra za aplikacije". |
| **etcd** | **Spominska knjiga clustra** — shranjuje vse podatke o tem, kaj kje teče, kakšne so nastavitve, kdo je živ in kdo mrtev. Je možgani Kubernetesa. |
| **Failover** | **Samodejna menjava straže** — ko primarni sistem crkne, pomožni samodejno prevzame njegovo vlogo. V našem primeru CNPG promovira replica v primary. |
| **FastAPI** | **Ogrodje za spletne aplikacije v Pythonu** — v njem je napisana sola-app. Hitro, moderno, itd..|
| **Git** | **Sistem za sledenje spremembam kode** — kot "Track Changes" v Wordu, ampak za programsko kodo. |
| **GitHub Actions** | **Samodejno testiranje in gradnja ob vsaki spremembi** — ko nekdo naloži novo kodo na GitHub, se avtomatsko zgradi nov Docker Image. |
| **Helm** | **"App Store" za Kubernetes** — orodje za nameščanje pripravljenih paketov (npr. Longhorn, CNPG) v Kubernetes. Namesto da ročno pišeš YAML, samo poveš "namesti Longhorn". |
| **HIPAA** | **Ameriški zakon o varovanju zdravstvenih podatkov** — *Health Insurance Portability and Accountability Act*. Določa, kako se smejo hraniti in pošiljati zdravstveni podatki. Ker smo slovenska šola in ne bolnišnica, HIPAA ne velja za nas — so pa načela tega zakona (šifriranje, nadzor dostopa, beleženje) dobra praksa za vsak sistem. |
| **HPA (HorizontalPodAutoscaler)** | **Samodejno prilagajanje števila kopij aplikacije** — pazi na porabo CPU/RAM in doda ali odstrani replike (2-4) glede na obremenitev. Kot kavomat v šoli — ko je gužva, se vključi še en. |
| **HTTPS** | **Varna spletna povezava** — HTTP + SSL. Zelena ključavnica v brskalniku pomeni, da je povezava varna. |
| **IoT (Internet of Things)** | **Pametne naprave, povezane v internet** — npr. pametni termostati, kamere, senzorji. k3s je posebej narejen za take naprave (malo porabijo, niso zmogljivi), ampak deluje tudi na prenosnikih — kot gorilnik za kampiranje, ki ga lahko uporabiš tudi doma v kuhinji. |
| **k3s** | **Lažja različica Kubernetesa** — posebej narejena za manjše računalnike in IoT naprave. Uporabljamo jo na HP ProBookih, ker je polni Kubernetes pretežak za prenosnike. Isti `kubectl` ukazi delujejo za oboje. |
| **Kubernetes (k8s)** | **Dirigent orkestra za aplikacije** — sistem, ki avtomatsko upravlja, kje in kako tečejo tvoje aplikacije. Če ena crkne, jo samodejno zažene drugje. |
| **LoadBalancer** | **Recepcija v stavbi** — usmerja obiskovalce (uporabnike) na pravo aplikacijo. V našem primeru MetalLB na IP {{LB_IP}}. |
| **Longhorn** | **Sistem, ki poskrbi, da imaš 2 kopiji podatkov na 2 različnih računalnikih** — distribuirano shranjevanje za Kubernetes, narejeno za manjše clustre. |
| **MetalLB** | **LoadBalancer za domače (on-premise) okolje** — alternativa oblačnim LoadBalancerjem (AWS, Google). Teče kar na tvojih računalnikih. |
| **Primary (baza)** | **Glavna baza** — edina, v katero se lahko zapisuje. Vse spremembe gredo skozi njo. |
| **PV (PersistentVolume)** | **Pravi disk na pravem računalniku** — Longhorn ga samodejno ustvari, ko narediš PVC. Za razliko od PVC-ja (zahtevek) je PV dejanski kos diska na enem od nodov. Preveriš ga z `kubectl get pv`. |
| **PVC (PersistentVolumeClaim)** | **Virtualni trdi disk** — zahtevek za prostor na disku v Kubernetesu. Podatki ostanejo tudi, če se aplikacija preseli na drug računalnik. |
| **Replica** | **Kopija, ki budno spremlja original** — druga baza podatkov, ki ves čas prepisuje vse spremembe iz primaryja. Pripravljena prevzeti, če original crkne. |
| **Replica (baza)** | **Pomožna baza** — samo za branje. Ves čas prepisuje spremembe iz primaryja. Če primary crkne, postane nov primary. |
| **SSH** | **Varen dostop do oddaljenega računalnika prek ukazne vrstice** — kot da bi sedel pred tistim računalnikom, čeprav si v drugi sobi. |
| **SSL/TLS** | **Šifrirana povezava (ključavnica v brskalniku)** — poskrbi, da nihče ne more prisluhniti komunikaciji med uporabnikom in strežnikom. |
| **Uvicorn** | **Strežnik, ki poganja FastAPI aplikacijo** — bere Python kodo in jo streže kot spletno stran. Kot natakar, ki hrano (odgovore) nosi do strank. |
| **WAL (Write-Ahead Log)** | **Dnevnik sprememb, preden se zapišejo** — PostgreSQL vsako spremembo najprej zapiše v WAL, šele nato v glavne podatkovne datoteke. To omogoča obnovitev po crashu in replikacijo. |
| **YAML** | **Človeku berljiv format za zapis konfiguracije** — nekaj podobnega kot JSON, ampak bolj pregleden. V Kubernetesu vse nastavitve pišejo v YAML formatu. |
| **Zero-downtime (rollout)** | **Posodobitev brez prekinitve delovanja** — Kubernetes najprej zažene novo verzijo, počaka da deluje, šele nato ugasi staro. Uporabniki nič ne občutijo. |

---

> **Avtor:** Matej Čušin  
