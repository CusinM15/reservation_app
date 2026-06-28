🌐 **Jezik / Language:** [🇸🇮 Slovenščina](admin-devops-navodila.md) | [🇬🇧 English](en/admin-devops-navodila.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# ⚙️ Admin & DevOps navodila

*"Delaj kot senior, razloženo kot petletniku."*

Celovita navodila za namestitev, vzdrževanje in odpravljanje težav — z razlago **zakaj** vsak korak sploh obstaja.

> **Avtor:** Matej Čušin  
> **Šola:** OŠ Toneta Čufarja, Jesenice

---

## 📋 Kazalo

1. [Kaj aplikacija omogoča — in kaj to pomeni v praksi](#kaj-aplikacija-omogoča)
2. [Namestitev Ubuntu Server 24.04 — z razlago vsakega koraka](#0-namestitev-ubuntu-server-2404-lts)
3. [Načini namestitve — kdaj kaj uporabiti](#načini-namestitve)
4. [📖 Kdaj uporabiti kateri način? — odločitveni vodič](#-kdaj-uporabiti-kateri-način)
5. [Vzdrževanje in avtomatizacija — cron jobi, ki skrbijo sami](#vzdrževanje-in-avtomatizacija-cron-jobi)
6. [AI agenti za pomoč — kot pripravnik, ki ne sprašuje neumnih vprašanj](#ai-agenti-za-pomoč)
7. [Dodajanje novega računalnika v k3s cluster — korak za korakom](#dodajanje-novega-računalnika-v-k3s-cluster)

---

## Kaj aplikacija omogoča — in kaj to pomeni v praksi

Aplikacija rešuje eno glavno težavo: **kdo je kdaj v katerem prostoru in kdaj so ocenjevanja.** Namesto da se učitelji lovijo po hodnikih in prepisujejo iz papirja v papir, vse lepo piše na enem mestu.

### Prostori za rezervacije

| Prostor | Kapaciteta | Kako deluje | V praksi pomeni... |
|---------|-----------|-------------|-------------------|
| **📱 Tablice** | 28 kosov | Lahko si jih deli več učiteljev v **isti uri** | Če Mateja vzame 14 tablic, jih lahko Ana še vedno vzame 14 — aplikacija pazi, da ne gre čez 28 |
| **💻 Računalnica** | 1 rezervacija na uro | Rezerviraš cel prostor zase | Ko si ti notri, drugi ne morejo — kot da imaš ključ od vrat |
| **🚢 Ladja** | 1 rezervacija na uro | Enako kot računalnica | Isti princip, drug prostor |
| **🍳 Gospodinjska učilnica** | 1 rezervacija na uro | Enako kot zgoraj | Tretji prostor, ista logika |

**Zakaj tako?** Tablice so fizični predmeti — lahko jih razdeliš. Prostori so sobe — vanje fizično ne moreš stlačiti dveh razredov hkrati.

### Ostale funkcionalnosti

- **📝 Ocenjevanja** — Učitelji napovejo pisna ocenjevanja. Aplikacija pazi, da jih ni več kot **3 na teden** in **največ 2 običajni** (tretji je lahko samo "lažji"). **Zakaj?** Da nimajo mulci 5 testov v enem dnevu.
- **🚫 Zasedeni datumi** — Ravnatelj/admin označi dneve, ko nič ne gre (prazniki, ekskurzije, športni dnevi). **Zakaj?** Da se kdo ne muči z rezervacijo na dan, ko šole sploh ni.
- **👥 Admin panel** — Dodaš/brišeš učitelje, nastavljaš vloge. **Zakaj?** Nekdo mora imeti ključe od vrat.
- **🔑 Pozabljeno geslo** — Pošlje mail za ponastavitev. **Zakaj?** Ker vsak pozabi geslo enkrat na mesec in kričanje "miha.ne.veš.gesla" čez hodnik ni profesionalno.

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
| **Jezik** | English (slovenščina ni podprta) | Ubuntu Server nima slovenskega jezika. Konzola bo vseeno angleška, vendar to ni problem — SSH dela v vseh jezikih. |
| **Omrežje** | Nastavi **statičen IP** | **Zakaj statični IP?** Strežnik mora biti vedno na istem naslovu. Če bi dobil dinamični IP (preko DHCP), bi se lahko jutri zamenjal in aplikacija bi bila nedosegljiva. Kot da bi se tvoja hiša vsak dan preselila na drugo ulico — poštar te ne bi našel. |
| **OpenSSH** | ✅ **Obvezno označi "Install OpenSSH server"** | **Zakaj OpenSSH?** Strežnik bo stal brez tipkovnice in monitorja v kotu. Edina pot do njega je prek omrežja — SSH je tvoja daljinska tipkovnica. Če ga ne namestiš, moraš fizčno nosit monitor do strežnika vsakič, ko kaj rabiš. |
| **Uporabnik** | Ustvari uporabnika in geslo | To bo tvoj admin račun. Zapiši ga nekam *(v telefon, na listek, v password manager — samo ne izgubi)*. |

### Nastavitev statičnega IP-ja

Če med namestitvijo nisi nastavil statičnega IP-ja (ali če ga rabiš spremeniti):

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
# S katerega drugega računalnika:
ssh tvoj_uporabnik@<IP_STREZNIKA>
```

**Nasvet seniorja:** Omogoči SSH ključe namesto gesla. Potem se lahko povežeš brez tipkanja gesla — in heker se ne more prijaviti, tudi če ugane geslo.

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
- ✅ **Plus:** Visoka razpoložljivost, samodejno okrevanje, enostavno dodajanje novih nodov v prihodnosti.
- ❌ **Minus:** Bolj zapleteno za postavitev. Rabiš vsaj 2 računalnika. Več znanja za vzdrževanje.
- **Dobro za:** Večje šole, kritične sisteme, kjer izpad ni opcija.

> **Podrobna navodila za vsak način:**
> - Lokalno: [postavi-lokalni-app.md](postavi-lokalni-app.md)
> - k3s: [k3s-setup.md](k3s-setup.md)
> - HA arhitektura: [HA.md](HA.md)

---

## 📖 Kdaj uporabiti kateri način?

*"Ne uporabi gradbenega žerjava za obešanje slike."*

> 📊 **Diagram: odlocitveni-vodic.drawio** — odločitveni diagram
> Kopiraj kodo → https://app.diagrams.net/ → **File → Open → From Device**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" agent="Hermes Agent" version="24.2.5">
  <diagram name="odlocitveni-vodic" id="diagram-odlocitveni-vodic.drawio">
    <mxGraphModel dx="1000" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="d7-1" value="Kateri način namestitve?" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E3F2FD;strokeColor=#1E88E5;fontSize=14;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="200" y="10" width="200" height="50" as="geometry" />
        </mxCell>
        <mxCell id="d7-2" value="Samo en računalnik?" style="rhombus;whiteSpace=wrap;html=1;fillColor=#FFF9C4;strokeColor=#F57F17;fontSize=12;" vertex="1" parent="1">
          <mxGeometry x="220" y="90" width="160" height="60" as="geometry" />
        </mxCell>
        <mxCell id="d7-3" value="✅ Da → LOKALNO (uvicorn/Docker)<br>Enostavno, brez Kubernetes" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E8F5E9;strokeColor=#4CAF50;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="30" y="200" width="240" height="60" as="geometry" />
        </mxCell>
        <mxCell id="d7-4" value="2+ računalnikov?" style="rhombus;whiteSpace=wrap;html=1;fillColor=#FFF9C4;strokeColor=#F57F17;fontSize=12;" vertex="1" parent="1">
          <mxGeometry x="440" y="90" width="160" height="60" as="geometry" />
        </mxCell>
        <mxCell id="d7-5" value="✅ Da → KUBERNETES (k3s)<br>Visoka razpoložljivost" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E8F5E9;strokeColor=#4CAF50;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="380" y="200" width="280" height="60" as="geometry" />
        </mxCell>
        <mxCell id="d7-6" value="Ne, ampak bom dodajal →<br>KUBERNETES (k3s) — začni zdaj" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF3E0;strokeColor=#FF9800;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="380" y="300" width="280" height="60" as="geometry" />
        </mxCell>
        <mxCell id="d7-7" value="Imaš star laptop v omari?" style="rhombus;whiteSpace=wrap;html=1;fillColor=#FFF9C4;strokeColor=#F57F17;fontSize=12;" vertex="1" parent="1">
          <mxGeometry x="100" y="320" width="200" height="60" as="geometry" />
        </mxCell>
        <mxCell id="d7-8" value="Samo za test → LOKALNO" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E8F5E9;strokeColor=#4CAF50;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="30" y="430" width="200" height="50" as="geometry" />
        </mxCell>
        <mxCell id="d7-9" value="Za res → k3s (tudi 1 node > nič)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF3E0;strokeColor=#FF9800;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="280" y="430" width="220" height="50" as="geometry" />
        </mxCell>
        <mxCell id="d7-e1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#1E88E5;" edge="1" parent="1" source="d7-1" target="d7-2">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="d7-e2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#4CAF50;exitX=0;exitY=0.5;entryX=1;entryY=0.5;" edge="1" parent="1" source="d7-2" target="d7-3">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="d7-e3" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#F57F17;" edge="1" parent="1" source="d7-2" target="d7-4">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="d7-e4" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#4CAF50;" edge="1" parent="1" source="d7-4" target="d7-5">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="d7-e5" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#FF9800;" edge="1" parent="1" source="d7-4" target="d7-6">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="d7-e6" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#F57F17;exitX=0;exitY=1;" edge="1" parent="1" source="d7-2" target="d7-7">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="d7-e7" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#4CAF50;" edge="1" parent="1" source="d7-7" target="d7-8">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="d7-e8" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#FF9800;" edge="1" parent="1" source="d7-7" target="d7-9">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

**Zlato pravilo:** Če nisi prepričan, začni z mDNS. Je kompromis med enostavnostjo in zanesljivostjo. Na k3s lahko preideš kasneje brez izgube podatkov.

---

## Vzdrževanje in avtomatizacija (cron jobi)

*"Najboljši strežnik je tisti, za katerega ti ni treba nič delati."*

Cron jobi so kot budilke — vsak dan ob določeni uri se zbudi in nekaj naredi. Postavili smo dva:

### 📦 Dnevna varnostna kopija baze (`sola-db-backup`)

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

**Zakaj to potrebujemo?** Če eden od treh strežnikov crkne, aplikacija še vedno deluje — ampak ti tega ne veš. Poročilo ti pove: "Hej, node 2 je crknil. Popravi ga, preden crkne še node 3."

---

## AI agenti za pomoč

*"Kot pripravnik, ki ne sprašuje neumnih vprašanj — in dela 24/7."*

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

*"Kmetija raste — dodajamo novo živino."*

### 1. Priprava novega računalnika

Preden nov računalnik sploh pomisli na k3s, mora imeti osnovno namestitev:

1. **Namesti Ubuntu Server 24.04** na nov računalnik  
   *(enak postopek kot v poglavju 0 — uporabi isti USB ključek)*

2. **Nastavi statičen IP**  
   *(nov računalnik dobi svoj fiksen naslov — npr. 192.168.1.30)*  
   **Zakaj?** Če dobi dinamični IP, ga bo k3s izgubil ob naslednjem vklopu in cluster ga ne bo več prepoznal.

3. **Omogoči SSH**  
   **Zakaj?** Ker boš vse nadaljnje korake delal prek SSH — ne nosi monitorja v drugo nadstropje.

### 2. Pridobitev tokena — "vstopnica" v cluster

Token je kot **geslo za vstop v cluster**. Vsak nov računalnik ga rabi, da se dokaže: "Hej, jaz sem dober fant, spusti me noter."

```bash
# Poženi na kateremkoli MASTER nodu (obstoječem)
sudo cat /var/lib/rancher/k3s/server/token
```

**Dobiš nekaj takega:** `K107f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f::server:token`

**Nasvet seniorja:** Token je **občutljiv podatek**. Z njim lahko kdorkoli priključi svoj računalnik v tvoj cluster. Ne shranjuj ga v javnih repozitorijih ali na listkih na monitorju.

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

Vsako vozlišče **lahko** vsebuje vse. To je lepota k3s — ni ločenih "master" in "worker" računalnikov, vsak je lahko vse:

| Vloga | Kaj dela | Ali nujno? |
|-------|---------|-----------|
| **Control-plane** | Upravlja cluster — odloča kje bodo tekli zabojniki | ✅ Ja, vsaj 1 v clusterju |
| **Worker** | Poganja zabojnike — dejansko izvaja kodo aplikacije | ✅ Ja |
| **Longhorn** | Shranjuje podatke — diskovni prostor za bazo | ⚠️ Potrebuje dodaten disk (ne sistemskega) |
| **MetalLB speaker** | Omogoča LoadBalancer IP — zunanji naslov za aplikacijo | ⚠️ Potreben samo na 1 nodu v omrežju |

**V praksi:** Dodaten disk za Longhorn pomeni, da ne smeš uporabiti sistemskega diska (/dev/sda) za shranjevanje podatkov. Če ima drugi disk (/dev/sdb ali /dev/nvme1n1), ga dodeli Longhornu. Sicer bo ob polnjenju sistemskega diska crknil celoten OS in s tem tudi Longhorn.

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

> 📊 **Diagram: repo-struktura.drawio** — struktura projekta
> Kopiraj kodo → https://app.diagrams.net/ → **File → Open → From Device**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" agent="Hermes Agent" version="24.2.5">
  <diagram name="repo-struktura" id="diagram-repo-struktura.drawio">
    <mxGraphModel dx="1000" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="d8-1" value="reservation_app/<br><span style='color:#757575;'>📁 korenska mapa projekta</span>" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E8F0FE;strokeColor=#4285F4;fontSize=12;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="250" y="10" width="160" height="50" as="geometry" />
        </mxCell>
        <mxCell id="d8-2" value="📁 app/<br><span style='color:#757575;'>Python aplikacija (FastAPI)</span>" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E8F5E9;strokeColor=#4CAF50;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="10" y="90" width="220" height="40" as="geometry" />
        </mxCell>
        <mxCell id="d8-3" value="📄 main.py<br><span style='color:#757575;'>Vstopna točka</span>" style="text;whiteSpace=wrap;html=1;fontSize=10;" vertex="1" parent="1">
          <mxGeometry x="30" y="140" width="190" height="20" as="geometry" />
        </mxCell>
        <mxCell id="d8-4" value="📄 config.py<br><span style='color:#757575;'>Nastavitve (IP-ji, gesla)</span>" style="text;whiteSpace=wrap;html=1;fontSize=10;" vertex="1" parent="1">
          <mxGeometry x="30" y="165" width="190" height="20" as="geometry" />
        </mxCell>
        <mxCell id="d8-5" value="📄 database.py<br><span style='color:#757575;'>Povezava z bazo</span>" style="text;whiteSpace=wrap;html=1;fontSize=10;" vertex="1" parent="1">
          <mxGeometry x="30" y="190" width="190" height="20" as="geometry" />
        </mxCell>
        <mxCell id="d8-6" value="📄 models.py<br><span style='color:#757575;'>Organizacija podatkov</span>" style="text;whiteSpace=wrap;html=1;fontSize=10;" vertex="1" parent="1">
          <mxGeometry x="30" y="215" width="190" height="20" as="geometry" />
        </mxCell>
        <mxCell id="d8-7" value="📄 race.py<br><span style='color:#757575;'>Zaščita pred dvojnimi kliki</span>" style="text;whiteSpace=wrap;html=1;fontSize=10;" vertex="1" parent="1">
          <mxGeometry x="30" y="240" width="190" height="20" as="geometry" />
        </mxCell>
        <mxCell id="d8-8" value="📁 routers/<br><span style='color:#757575;'>Poti do funkcionalnosti</span>" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E8F5E9;strokeColor=#4CAF50;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="260" y="130" width="180" height="40" as="geometry" />
        </mxCell>
        <mxCell id="d8-9" value="📁 templates/<br><span style='color:#757575;'>HTML predloge (izgled strani)</span>" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E8F5E9;strokeColor=#4CAF50;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="470" y="130" width="220" height="40" as="geometry" />
        </mxCell>
        <mxCell id="d8-10" value="📁 scripts/<br><span style='color:#757575;'>Pomožni skripti</span>" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF3E0;strokeColor=#FF9800;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="10" y="300" width="220" height="40" as="geometry" />
        </mxCell>
        <mxCell id="d8-11" value="📁 k8s/<br><span style='color:#757575;'>Kubernetes config</span>" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF3E0;strokeColor=#FF9800;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="260" y="300" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="d8-12" value="📁 documentation/<br><span style='color:#757575;'>Dokumentacija</span>" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF3E0;strokeColor=#FF9800;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="490" y="300" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="d8-13" value="📄 Dockerfile" style="text;whiteSpace=wrap;html=1;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="260" y="370" width="90" height="20" as="geometry" />
        </mxCell>
        <mxCell id="d8-14" value="📄 requirements.txt" style="text;whiteSpace=wrap;html=1;fontSize=11;" vertex="1" parent="1">
          <mxGeometry x="370" y="370" width="110" height="20" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

**Privzeti admin:** uporabnik `admin`, geslo `admin123`.  
**Takoj po namestitvi spremenite geslo!**  
*(To ni hec. Prva stvar, ki jo vsak heker proba, je admin/admin123.)*

---

> *"Če lahko to razložiš petletniku, ga res razumeš." — vsak dober DevOps inženir*
