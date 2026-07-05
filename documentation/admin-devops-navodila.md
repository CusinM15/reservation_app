🌐 **Jezik / Language:** [🇸🇮 Slovenščina](admin-devops-navodila.md) | [🇬🇧 English](en/admin-devops-navodila.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# ⚙️ Admin & DevOps navodila


## 📋 Kazalo

1. [Kaj aplikacija omogoča — in kaj to pomeni v praksi](#kaj-aplikacija-omogoča)
2. [Namestitev Ubuntu Server 24.04 — z razlago vsakega koraka](#0-namestitev-ubuntu-server-2404-lts)
3. [Načini namestitve — kdaj kaj uporabiti](#načini-namestitve)
4. [📖 Kdaj uporabiti kateri način? — odločitveni vodič](#-kdaj-uporabiti-kateri-način)
5. [Vzdrževanje in avtomatizacija — cron jobi, ki skrbijo sami](#vzdrževanje-in-avtomatizacija-cron-jobi)
6. [AI agenti za pomoč](#ai-agenti-za-pomoč)
7. [Dodajanje novega računalnika v k3s cluster — korak za korakom](#dodajanje-novega-računalnika-v-k3s-cluster)

---

## Kaj aplikacija omogoča — in kaj to pomeni v praksi

Aplikacija rešuje eno glavno težavo: **kdo je kdaj v katerem prostoru in kdaj so ocenjevanja.** Namesto da se učitelji lovijo po hodnikih in prepisujejo iz papirja na papir, vse lepo piše na enem mestu.

### Prostori za rezervacije

| Prostor | Kapaciteta | Kako deluje | V praksi pomeni... |
|---------|-----------|-------------|-------------------|
| **📱 Tablice** | 28 kosov | Lahko si jih deli več učiteljev v **isti uri** | Če Mateja vzame 14 tablic, jih lahko Ana še vedno vzame 14 — aplikacija pazi, da ne gre čez 28 |
| **💻 Računalnica** | 1 rezervacija na uro | Rezerviraš cel prostor zase | Ko si ti notri, drugi ne morejo  |
| **🚢 Ladja** | 1 rezervacija na uro | Enako kot računalnica | Isti princip, drug prostor |
| **🍳 Gospodinjska učilnica** | 1 rezervacija na uro | Enako kot zgoraj | Isti princip, drug prostor |

**Zakaj tako?** Tablice so fizični predmeti — lahko jih razdeliš. Prostori so sobe — vanje fizično ne moreš stlačiti dveh razredov hkrati.

### Ostale funkcionalnosti

| **📝 Ocenjevanja** — Učitelji napovejo pisna ocenjevanja. Aplikacija pazi, da jih ni več kot **3 na teden** in **največ 2 običajni** (tretji je lahko samo lažje ocenjevanje). **Zakaj?** Da nimajo učenci 5 testov v enem dnevu.
| **🚫 Zasedeni datumi** — Vodstvo/admin označi dneve, ko nič ne gre (ekskurzije, športni dnevi ...). **Zakaj?** Da se nihče ne muči z rezervacijo na dan, ko pouka ni.
- **👥 Admin panel** — Dodaš/brišeš učitelje, nastavljaš vloge. **Zakaj?** Nekdo mora imeti ključe od vrat.
| **🔑 Pozabljeno geslo** — Pošlje email za ponastavitev. **Zakaj?** Ker vsak kdaj pozabi geslo.

---

## 0. Namestitev Ubuntu Server 24.04 LTS

*"Vsaka dobra hiša stoji na trdnih temeljih."*

### Priprava namestitvenega medija

1. **Prenesi Ubuntu Server 24.04 LTS** z https://ubuntu.com/download/server  
   *(LTS = Long Term Support — 5 let posodobitev, ne rabiš vsako leto znova nameščati)*

2. **Ustvari zagonski USB** z Rufus (https://rufus.ie/)  
   *(Rufus naredi USB, s katerega računalnik lahko zažene namestitev)*

3. **Namesti na ciljni računalnik** — v BIOS-u nastavi USB kot prvi boot device  
   *(BIOS pove računalniku: "najprej poglej USB, šele potem disk")*

### Potek namestitve — z razlago vsake izbire

| Korak | Izbira | Zakaj? |
|-------|--------|--------|
| **Izbira OS** | **Ubuntu Server** (NE Desktop) | **Zakaj Ubuntu Server?** Ker nima namizja (= manj programov, ki jedo RAM → več RAMa za aplikacijo). Manj programov pomeni tudi manj lukenj za hekerje — pri Desktop različici je več vrat, skozi katera lahko kdo vdre. Server je kot prazna soba z enimi vrati; Desktop je kot soba polna omar in oken. |
| **Jezik** | English (slovenščina ni podprta) | Ubuntu Server nima slovenskega jezika. |
| **Omrežje** | Nastavi **statičen IP** | **Zakaj statični IP?** Strežnik mora biti vedno na istem naslovu. Če bi dobil dinamični IP (preko DHCP), bi se lahko jutri zamenjal in aplikacija bi bila nedosegljiva. Kot da bi se tvoja hiša vsak dan preselila na drugo ulico — poštar te ne bi našel. |
| **OpenSSH** | ✅ **Obvezno označi "Install OpenSSH server"** | **Zakaj OpenSSH?** Strežnik bo stal brez tipkovnice in monitorja v kotu. Edina pot do njega je prek omrežja — SSH je tvoja daljinska tipkovnica.  |
| **Uporabnik** | Ustvari uporabnika in geslo | To bo tvoj admin račun. Zapiši ga nekam *(v telefon, na listek, v password manager — samo ne izgubi)*. |

### Nastavitev statičnega IP-ja

Če med namestitvijo nisi nastavil statičnega IP-ja (ali če ga rabiš spremeniti):


**Če `nano` ni nameščen, ga namesti s `sudo apt install nano` (ali uporabi `vim`).**

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

Primer konfiguracije (zamenjaj `{{VAR}}` z dejanskimi vrednostmi):

```yaml
network:
  ethernets:
    eth0:
      addresses:
        - {{LB_IP}}/24
      routes:
        - to: default
          via: {{K3S_1_IP}}
      nameservers:
        addresses:
          - {{LB_IP}}
          - 8.8.8.8
  version: 2
```

```bash
sudo netplan apply
```

**Kaj se zgodi?** Računalnik dobi fiksen naslov v omrežju. Drugi računalniki ga vedno najdejo na istem mestu.

### Nastavitev laptopa kot strežnik

Če uporabljaš laptop (prenosnik) kot strežnik:

```bash
sudo nano /etc/systemd/logind.conf
# Poišči vrstico #HandleLidSwitch=ignore in odstrani '#'
# Na koncu mora pisati: HandleLidSwitch=ignore
sudo systemctl restart systemd-logind
```

**Zakaj HandleLidSwitch=ignore?** Ko laptop zapreš, gre privzeto v spanje. To je super za baterijo, ampak grozno za strežnik. Strežnik mora delati 24/7 — tudi ko zapreš pokrov. Ta nastavitev reče: "pokrov je zaprt? Vseeno delaj naprej."

**V praksi:** Laptop stoji v omari s pritrjenim pokrovom. Brez te nastavitve bi ob vsakem zaprtju pokrova aplikacija padla v spanec in nihče je ne bi mogel več doseči, dokler nekdo fizično ne odpre pokrova.

### SSH — oddaljen dostop

```bash
# Če med namestitvijo nisi označil (čeprav bi moral):
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

**Preveri, da dela:**

```bash
# S katerega drugega računalnika (v omrežju):
ssh tvoj_uporabnik@<IP_STREZNIKA>
```

**Nasvet:** Omogoči SSH ključe namesto gesla. Potem se lahko povežeš brez tipkanja gesla — in heker se ne more prijaviti, tudi če ugane geslo.

---

## Načini namestitve

Aplikacija deluje na treh načinih. Vsak ima svoje prednosti in slabosti — kot orodja v škatli: kladivo je super za žeblje, ampak za vijake rabiš izvijač.

### Primerjava načinov

| Način | Zahtevnost | Za kaj je primeren | Analogija |
|------|-----------|-------------------|-----------|
| **Lokalno (uvicorn)** | ⭐ Enostavno | En računalnik v zbornici | Kot en koledar na mizi — če ga nekdo odnese, je konec. Ampak je preprost in dela takoj. |
| **mDNS** | ⭐⭐ Srednje | Več računalnikov znotraj šolskega omrežja | Kot več koledarjev v isti pisarni — vsak vidi iste podatke, ampak če glavni pade, pade vse. |
| **Kubernetes (k3s)** | ⭐⭐⭐ Zahtevno | Visoka razpoložljivost, 2+ računalnikov | Kot 2 koledarja na 2 mizah — če eno mizo kdo odnese, druga še vedno stoji. Aplikacija sama poskrbi, da sta oba enaka. |

### Kratek opis vsakega načina

**🏠 Lokalno (uvicorn)**
Poženeš aplikacijo kot en sam proces na enem računalniku. Podatki so v SQLite datoteki na istem disku.
- ✅ **Plus:** Namestiš v 5 minutah, ni odvisnosti, dela takoj.
- ❌ **Minus:** Če računalnik crkne — aplikacije ni več. Če disk crkne — podatkov ni več. Brez varnostne kopije si v težavah.
- **Dobro za:** Testiranje, majhne šole, začasne postavitve.

**🌐 mDNS**
Aplikacija teče na enem strežniku, do nje pa lahko dostopaš z drugih naprav prek imena kot `sola.local`.
- ✅ **Plus:** Ne rabiš pomniti IP-ja. Drugi računalniki v omrežju jo najdejo samodejno.
- ❌ **Minus:** Še vedno ena točka odpovedi. Če strežnik pade — nihče ne more do aplikacije.
- **Dobro za:** Manjše šole, kjer je en IT strežnik dovolj.

**☸️ Kubernetes (k3s)**
Aplikacija teče na več računalnikih (nodih). Če eden crkne, drugi prevzamejo. Kubernetes sam poskrbi, da aplikacija vedno teče.
- ✅ **Plus:** Visoka razpoložljivost, samodejno okrevanje, enostavno dodajanje novih nodov (računalnikov) v prihodnosti.
- ❌ **Minus:** Bolj zapleteno za postavitev. Rabiš vsaj 2 računalnika. Več znanja za vzdrževanje.
- **Dobro za:** Večje šole, kritične sisteme, kjer izpad ni opcija.

> **Podrobna navodila za vsak način:**
> - Lokalno: [postavi-lokalni-app.md](postavi-lokalni-app.md)
> - k3s: [k3s-setup.md](k3s-setup.md)
> - HA arhitektura: [HA.md](HA.md)

---

## 📖 Kdaj uporabiti kateri način?

*"Ne uporabi gradbenega žerjava za obešanje slike."*

![Odločitveni diagram: kateri način namestitve izbrati](diagrams/odlocitveni-vodic.png)


**Zlato pravilo:** Če nisi prepričan, začni z mDNS. Je kompromis med enostavnostjo in zanesljivostjo. Na k3s lahko preideš kasneje brez izgube podatkov.

---

## Vzdrževanje in avtomatizacija (cron jobi)

*"Najboljši strežnik je tisti, za katerega ti ni treba nič delati."*

Cron jobi so kot budilke — vsak dan ob določeni uri se zbudi in nekaj naredi. Postavili smo dva:

### **HorizontalPodAutoscaler (HPA) — samodejno skaliranje aplikacije**

Število kopij aplikacije se **samodejno prilagaja** glede na obremenitev:

```bash
kubectl get hpa -n sola-app
# NAME            REFERENCE              TARGETS              MIN   MAX   REPLICAS
# sola-app-hpa    Deployment/sola-app    7%/60% CPU            2     4     2
#                                        61%/70% MEM
```

HPA uporablja **CPU (60%) in pomnilnik (70%)** kot merilo:
- **2 repliki** — nizka obremenitev (počitnice, popoldne, vikend)
| **3 replike** — normalen pouk (ena kopija na vsakem nodu, na enem pa dve)
- **4 replike** — visoka obremenitev (ocene, začetek šolskega leta)

### **Dnevna varnostna kopija baze (`sola-db-backup`)**

| Lastnost | Vrednost | Pomen v praksi |
|---------|---------|---------------|
| **Schedule** | `0 4 * * *` | Vsako noč ob 4:00, ko nihče ne uporablja aplikacije |
| **Kaj naredi** | Pošlje pg_dump baze na BACKUP_EMAIL | Naredi "posnetek" baze in ga pošlje na email |

**Zakaj ob 4h zjutraj?** Ker takrat noben učitelj ne rezervira termina. Če bi bazo kopiral sredi dneva, bi lahko kdo ravno takrat nekaj shranjeval in backup bi bil nedosleden.

**V praksi to pomeni:** Če podatki crknejo (disk odpove, nekdo zbriše bazo, požar), imaš v emailu varnostno kopijo iz prejšnje noči. Največ kar izgubiš je en dan podatkov.

### 📊 Dnevno poročilo o stanju (`sola-daily-report`)

| Lastnost | Vrednost | Pomen v praksi |
|---------|---------|---------------|
| **Schedule** | `0 4 * * *` | Isto kot backup — ob 4:00 |
| **Kaj naredi** | Poročilo o stanju nodov, Longhorn replik in aplikacij | Preveri, ali vsi strežniki dihajo in ali so podatki pravilno podvojeni |

**Zakaj to potrebujemo?** Če eden od dveh strežnikov crkne, aplikacija še vedno deluje — ampak ti tega ne veš. Poročilo ti pove: "Hej, node 2 je crknil. Popravi ga, preden crkne še 1."

---

## AI agenti za pomoč

*"Ko česa ne veš, za pomoč vprašaj AI agenta (priporočam Hermes — tudi plačljiv model ne porabi veliko). Vedno je na voljo, pozna kodo in arhitekturo — 24/7."*

### Kaj je AI agent?

AI agent je kot **pomočnik, ki razume kaj hočeš in to naredi sam.** Ne rabiš se spomniti točnega kubectl ukaza ali brati 50 strani dokumentacije — samo poveš kaj rabiš in agent to izvede.

**Primer:** Namesto da pišeš:
```bash
kubectl get pods -n sola
kubectl logs sola-app-xyz123 -n sola --tail=50
kubectl describe pod sola-app-xyz123 -n sola
```

Agentu samo rečeš:
```bash
hermes "poglej kaj je narobe s sola-app podom"
```

In on sam pogleda, analizira in pove kaj je narobe. **Kot bi vzel avto na servis in rekel 'čudno brni' — mojster sam ve, kaj pogledati.**

### Hermes Agent

[Hermes Agent](https://github.com/NousResearch/hermes-agent) je CLI orodje za pomoč pri vzdrževanju. Teče v terminalu in razume navodila v naravnem jeziku.

**Primeri uporabe:**

```bash
# Če je dodan alias in imate nastavljen privzet model — odpre se AI chat v terminalu (enako kot prek spleta, le da vidi tudi datoteke na strežniku)
hermes 

# "Preveri stanje klustra"
hermes "kubectl get nodes, preveri longhorn in povej stanje"

# "Dodaj novega uporabnika v app"
hermes "dodaj uporabnika Ana Zupančič v aplikacijo, email ana@sola.si, vloga teacher"

# "Nastavi dnevno varnostno kopijo"
hermes "nastavi cronjob za dnevno backup baze ob 3h zjutraj"

# "Preveri zakaj app ne dela"
hermes "poglej loge sola-app podov in ugotovi zakaj se restartajo"
```

**Zakaj je to uporabno?** Namesto da odpiraš 5 terminalskih oken, tipkaš kubectl ukaze, brskaš po logih in googlaš napake — samo poveš agentu kaj rabiš in on to naredi v nekaj sekundah.

**Namestitev:**

```bash
curl -fsSL https://hermes-agent.io/install.sh | sh
```

*To je vse. Konfiguracija in nastavitve so v dokumentaciji Hermes Agent — tukaj jih ne ponavljamo, ker se spreminjajo pogosteje kot šolski urnik.*

---

## Dodajanje novega računalnika v k3s cluster


### 1. Priprava novega računalnika

Preden nov računalnik sploh dodati v k3s, mora imeti osnovno namestitev:

1. **Namesti Ubuntu Server 24.04** na nov računalnik  
   *(enak postopek kot v poglavju 0 — uporabi isti USB ključek)*

2. **Nastavi statičen IP**  
   *(nov računalnik dobi svoj fiksen naslov — npr. 192.168.1.30)*  
   **Zakaj?** Če dobi dinamični IP, ga bo k3s izgubil ob naslednjem vklopu in cluster ga ne bo več prepoznal.

3. **Omogoči SSH**  
   **Zakaj?** Ker boš vse nadaljnje korake delal prek SSH.

### 2. Pridobitev tokena — "vstopnica" v cluster

Token je kot **geslo za vstop v cluster**. Vsak nov računalnik ga rabi, da se dokaže: "Hej, jaz sem dober fant, spusti me noter."

```bash
# Poženi na kateremkoli MASTER nodu (načeloma so to vsi)
sudo cat /var/lib/rancher/k3s/server/token
```

**Dobiš nekaj takega:** `K107f8a7b6c5d4e3fereref1b0c9d8e7f6a5b4c3d2e1f::server:token`

**Nasvet:** Token je **občutljiv podatek**. Z njim lahko kdorkoli priključi svoj računalnik v tvoj cluster. Ne shranjuj ga v javnih repozitorijih ali na listkih na monitorju.

### 3. Priključitev kot dodaten master

Na **novem** računalniku poženi:

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://<IP_MASTERJA>:6443 \
  --token <TOKEN> \
  --node-ip <NOVI_IP> \
  --disable traefik --disable=servicelb
```

**Kaj ta ukaz naredi?** Kot bi rekel: "Hej k3s, prosim namesti se na ta računalnik. Poveži me z obstoječim clusterjem na IP-ju MASTERJA. Tukaj je token, da veš da smem. Moj IP je ta. In ne namesti traefik in servicelb — to že imamo."

**Zakaj `--disable traefik --disable=servicelb`?** Ker ta opravila že tečejo na prvem masterju. Če jih namestiš še enkrat, se bosta stepla kdo je glavni. Kot bi imel dva kapitana na isti ladji.

### 4. Kar mora vsebovati vozlišče — vse v enem

Vsako vozlišče **lahko** vsebuje vse. To je lepota k3s — ni ločenih "master" in "worker" računalnikov, vsak je vse:

| Vloga | Kaj dela | Ali nujno? |
|-------|---------|-----------|
| **Control-plane** | Upravlja cluster — odloča kje bodo tekli zabojniki | ✅ Ja, vsaj 1 v clusterju |
| **Worker** | Poganja zabojnike — dejansko izvaja kodo aplikacije | ✅ Ja |
| **Longhorn** | Shranjuje podatke — diskovni prostor za bazo | ✅ **Ja, na vsakem nodu** — potrebuje dodaten disk (ne sistemskega) |
| **MetalLB speaker** | Omogoča LoadBalancer IP — zunanji naslov za aplikacijo | ✅ **Ja, na vsakem nodu** — vsak node mora samostojno streči IP |

**Zakaj vse na vsakem nodu?** Ker če en node crkne, mora drugi prevzeti **vse** njegove vloge — tudi Longhorn (da podatki ostanejo dostopni) in MetalLB (da aplikacija dobi IP). Brez tega bi izpad enega noda povzročil več kot le upočasnitev.

**V praksi — diski:** Dodaten disk za Longhorn pomeni, da ne smeš uporabiti sistemskega diska (/dev/sda) za shranjevanje podatkov. Vsak node rabi svoj ločen disk (/dev/sdb ali /dev/nvme1n1). Če nima dodatnega diska, Longhorn na tistem nodu ne more shranjevati — in tisti node ne more samostojno delovati.

### 5. Po dodajanju — preverjanje in priprava diska

```bash
# Namesti Longhorn predpogoje (potrebno za shranjevanje)
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid

# Preveri, da je nov node viden in pripravljen
kubectl get nodes
```

**Pričakovan rezultat:**
```
NAME     STATUS   ROLES                  AGE   VERSION
master1  Ready    control-plane,master   30d   v1.30.0+k3s1
master2  Ready    control-plane,master   2d    v1.30.0+k3s1
node3    Ready    control-plane,master   1h    v1.30.0+k3s1   ← NOV!
```

Če STATUS ni `Ready`, počakaj minuto ali dve. k3s rabi čas, da postavi vse komponente. Če čez 5 minut še ni Ready, preveri:

```bash
systemctl status k3s
journalctl -u k3s --tail=50
```

---

## Struktura repozitorija

![Struktura projekta reservation_app](diagrams/repo-struktura.png)


**Privzeti admin:** uporabnik `admin`, geslo `admin123`.  
**Takoj po namestitvi spremenite geslo!**  
*(To ni hec. Prva stvar, ki jo vsak heker proba, je admin/admin123.)*

---


> **Avtor:** Matej Čušin  