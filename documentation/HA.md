🌐 **Jezik / Language:** [🇸🇮 Slovenščina](HA.md) | [🇬🇧 English](en/HA.md)
---
> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.
---
# 🏗️ Visoka razpoložljivost (HA) — ostc-app (sola-app)
## 📖 Kaj sploh pomeni "visoka razpoložljivost"?
Predstavljajte si, da imate dva natakarja v šolski jedilnici. Če eden zboli, drugi še vedno streže kosilo — učenci sploh ne opazijo, da nekoga manjka. **Visoka razpoložljivost** (angl. *High Availability* — HA) je isto, samo za računalnike: če en strežnik crkne, drugi brez težav prevzame njegovo delo. Uporabniki (učitelji, starši, učenci) niti ne opazijo, da je bil kakšen strežnik v ozadju mrtev.
Naš sistem uporablja **dva fizična računalnika** (v Kubernetes svetu jih imenujemo **nodi** — vozlišča), ki sodelujeta:
- **k3s-1** ({{K3S_1_IP}}) — HP ProBook 455 G5 (prvi računalnik)
- **k3s-2** ({{K3S_2_IP}}) — HP ProBook 450 G5 (drugi računalnik)
**Cilj:** tudi če en računalnik popolnoma odpove (pade elektrika, crkne disk, se sesuje program), aplikacija še naprej deluje brezhibno. Največ kar se zgodi je kratka prekinitev — kakšno minuto, dve — nato pa vse teče naprej, kot da se ni nič zgodilo. In vse to brez da bi kdo moral ročno kaj popravljati.
---
## 🧠 Kako smo tole sploh sestavili — velika slika

Sistem ima **štiri plasti**, ki delajo skupaj kot ekipa:

![Prometni tok HA](diagrams/ha-prometni-tok.png)
Vsaka plast ve, kaj mora narediti, če en računalnik odpove. Poglejmo si vsako posebej.
---
## 1. 🐳 Aplikacija (sola-app) — sama se postavi na noge
### Zakaj dva kosa aplikacije?
Vsak računalnik ima en **pod** (to je kot "embalaža" v kateri teče aplikacija). Skupaj imamo **2 poda** — enega na k3s-1 in enega na k3s-2. Ko pride obiskovalec na spletno stran, ga lahko postreže katerikoli od teh dveh.
```
Deployment "sola-app" (2 poda)
├── Pod na k3s-1 (znotraj omrežja: 10.42.0.x)
└── Pod na k3s-2 (znotraj omrežja: 10.42.1.x)
```
### Kaj se zgodi, ko en računalnik crkne?
1. Kubernetes (orodje ki upravlja z vsemi posodami) **v 30–40 sekundah opazi**, da je računalnik k3s-1 mrtev.
2. Reče si: "Aha, na k3s-1 je bil en pod. Preselim ga na k3s-2."
3. Vzame isto aplikacijo in jo zažene na k3s-2.
4. Zdaj imamo **oba poda na k3s-2**. Sistem deluje naprej, samo malo bolj natrpano je na enem računalniku.
### Kako vemo, da aplikacija res deluje?
Vsak pod ima **health check** (zdravstveni pregled). Aplikacija ima posebno stran `/health`, ki odgovori `200 OK` (kar pomeni "vse je v redu"). Kubernetes vsakih nekaj sekund preveri to stran. Če odgovor ni pravilen, ve, da je nekaj narobe in ukrepa.
---
## 2. 🌍 Omrežje — kako uporabniki pridejo do aplikacije
### Potovanje zahtevka od brskalnika do aplikacije
Ko učitelj odpre https://{{DOMAIN}} v brskalniku, se zgodi tole:
```
Brskalnik → Cloudflare (poskrbi za HTTPS varnost)
              → MetalLB LoadBalancer ({{LB_IP}}:{{LB_PORT}})
                → Service "sola-app" (razporejevalnik)
                  → Pod na k3s-1 ali pod na k3s-2
```
**Cloudflare** — To je varnostna služba. Poskrbi, da je povezava šifrirana (HTTPS — tisti zeleni ključavnički v brskalniku). Cloudflare ne ve, da imamo dva strežnika — on samo pošlje promet na IP naslov {{LB_IP}}.
**MetalLB LoadBalancer** — To je "prometni policaj" na fiksnem naslovu {{LB_IP}}:{{LB_PORT}}. Ko dobi zahtevek, ga pošlje na enega od računalnikov, ki ima aplikacijo. Če k3s-1 pade, policaj samodejno pošilja ves promet samo na k3s-2. Uporabnik tega sploh ne opazi.
**Zakaj to deluje?** MetalLB uporablja **layer2 failover** — to pomeni, da se ob izpadu računalnika IP naslov samodejno prestavi na drugega. To je podobno, kot če bi imeli hišno številko na dveh hišah hkrati — poštar vedno dostavi tja, kjer je nekdo doma.
---
## 3. 🗄️ PostgreSQL baza — CloudNativePG (CNPG) — srce sistema
### Zakaj je baza najpomembnejši del?
Aplikacija brez baze je kot avto brez koles — izgleda lepo, ampak ne gre nikamor. V bazi so vsi podatki: učenci, učitelji, rezervacije, urniki. Če baza pade, pade celoten sistem.
Zato imamo **dve kopiji baze**:
- **Primary (glavna)** — `sola-db-1` na k3s-1 — **edina, v katero se lahko zapisuje**
- **Replica (pomožna)** — `sola-db-2` na k3s-2 — **kopija, ki sproti posnema vse spremembe**
### Kako replica ves čas ostaja enaka primary?
To se imenuje **streaming replikacija** (v živo potekajoče kopiranje). Predstavljajte si:
1. Učitelj rezervira športno dvorano → aplikacija pošlje ukaz `INSERT` v bazo.
2. `sola-db-1` (primary) shrani to rezervacijo.
3. **V istem trenutku** pošlje kopijo te spremembe (tok podatkov — "stream") na `sola-db-2`.
4. `sola-db-2` reče: "Aha, nova rezervacija!" in jo shrani pri sebi.
5. **Čez manj kot sekundo** imata obe bazi popolnoma enake podatke.
To je kot bi imeli dva dnevnika, kjer eden narekuje, drugi pa zapisuje istočasno. Če prvi izgine, drugi ima vse zapisano do zadnje črke.
### Kako se aplikacija poveže z bazo?
Aplikacija ne kliče direktno `sola-db-1` ali `sola-db-2`. Namesto tega uporablja **tri servisne naslove** (kot bi klicala "centralo", ki jo preusmeri na pravo mesto):
| Service (naslov) | Kam kaže? | Namen | Uporaba v appu |
|---|---|---|---|
| `sola-db-rw` | **Samo primary** — vedno na trenutno glavno bazo | **Pisanje + branje** — edini naslov, ki sprejema nove podatke (`INSERT`, `UPDATE`, `DELETE`). Po failoverju se samodejno preusmeri na novo primarno bazo. | `DATABASE_URL` — **glavna povezava** |
| `sola-db-ro` | **Vse pripravljene baze** (primary + replica) | **Samo branje** — razporeja bralne zahtevke (`SELECT`) med obe bazi. Uporabno za poročila, da ne obremenjujemo primarne baze. | `DATABASE_URL_RO` — redko, večinoma za poročila |
| `sola-db-r` | **Vse baze** (tudi tiste ki še niso čisto pripravljene) | **Samo branje** — podobno kot `ro`, ampak manj strogo. Manj pomembno. | — |
**Ključno pravilo:** samo `sola-db-rw` sprejema zapisovanje. Če bi aplikacija poskušala zapisati kaj v `sola-db-ro`, bi baza to zavrnila z napako. V praksi aplikacija uporablja izključno `sola-db-rw` prek `DATABASE_URL`.
### 🔄 Avtomatski failover — ko glavna baza pade
**To je najpomembnejši del celotnega HA sistema.** Poglejmo si zgodbo, kaj se zgodi, ko računalnik k3s-1 (na katerem je primarna baza) nenadoma crkne:
**Korak 1 — 😵 k3s-1 umre**
Računalnik k3s-1 se sesuje. Primarna baza `sola-db-1` je nenadoma nedosegljiva. Aplikacija na k3s-2 še vedno poskuša pošiljati podatke na `sola-db-rw`, vendar ti zahtevki padejo v prazno.
**Korak 2 — ⏱️ CNPG čaka 30 sekund**
CNPG operator (to je "pametni upravitelj" baze, ki teče v ozadju) opazi, da je `sola-db-1` utihnil. Toda ne ukrepa takoj — **namerno počaka 30 sekund** (`failoverDelay: 30`). Zakaj? Zato, da ne bi po nepotrebnem zamenjal baze, če gre samo za kratek izpad (recimo omrežni sunek). Če bi operator takoj zamenjal bazo ob vsakem trenutnem izpadu, bi povzročal več škode kot koristi.
**Korak 3 — 🏆 Promocija replike v primary**
Po 30 sekundah CNPG reče: "OK, k3s-1 je res mrtev. `sola-db-2`, od zdaj naprej SI TI glavna baza!" Ta postopek imenujemo **promocija** (povišanje) in traja približno 30 sekund. V tem času baza:
- Preveri, da so vsi podatki dosledni
- Se pripravi na sprejemanje zapisovanja
- Sporoči okolici: "Jaz sem zdaj glavna!"
**Korak 4 — 🔁 Service `sola-db-rw` se preusmeri**
Ko je `sola-db-2` uradno primary, se service `sola-db-rw` (naslov, ki ga uporablja aplikacija) **samodejno** preusmeri na `sola-db-2`. Aplikacija na k3s-2 ne opazi ničesar — še naprej uporablja isti naslov `sola-db-rw`, samo da ta zdaj kaže na novo bazo.
**Korak 5 — 🩹 Aplikacija na k3s-1 se preseli**
Kubernetes na k3s-2 (edini preživeli računalnik) opazi, da je pod na k3s-1 mrtev. Vzame njegovo kopijo aplikacije in jo požene na k3s-2. Zdaj imamo oba poda aplikacije na istem računalniku.
**Korak 6 — ✅ Sistem deluje naprej**
Uporabniki (učitelji, starši) so opazili samo kratko prekinitev — mogoče kakšno minuto, v najslabšem primeru dve. In to je to. Sistem deluje naprej kot da se ni nič zgodilo.
```
Časovnica failoverja:
T=0    — k3s-1 crkne ❌
T=30s  — CNPG se odloči za promocijo 🤔
T=60s  — sola-db-2 postane primary ✅
T=90s  — App pod se preseli na k3s-2 🚚
T=2min  — Vse deluje, uporabniki spet zadovoljni 🎉
```
### 🔧 Kaj se zgodi, ko stari računalnik spet pride nazaj? (Recovery)
To je zgodba, ki jo veliko ljudi spregleda, a je enako pomembna. Ko k3s-1 spet deluje (recimo po popravilu ali ponovnem zagonu):
1. **CNPG samodejno opazi nov računalnik** — operator vidi, da je na voljo dodaten node.
2. **`sola-db-1` se ne postavi nazaj kot primary!** — To je pomembno. Kdor je bil prej glavni, ne postane spet glavni kar tako. To bi povzročilo zmedo.
3. Namesto tega se `sola-db-1` **samodejno pridruži kot replica** (pomožna baza). Reče: "Živjo `sola-db-2`, ti si zdaj šef. Jaz bom samo poslušal in kopiral vse spremembe, ki si jih naredil, ko mene ni bilo."
4. **Streaming replikacija se zažene v obratni smeri** — zdaj `sola-db-2` pošilja podatke `sola-db-1`, da se ta ujame.
5. Ko se `sola-db-1` popolnoma ujame (dohiti vse spremembe), postane **ready** (pripravljen) in lahko pomaga pri branju.
**Vse to je popolnoma avtomatsko.** Ni treba klicati nobenih čarobnih ukazov, ni treba nič ročno prestavljati. CNPG operator vse naredi sam. 👨‍💻✨
### 📋 Povzetek failover pravil
| Situacija | Kaj se zgodi | Je avtomatsko? |
|---|---|---|
| Primarna baza crkne | Replica postane nova primary ✅ | ✅ DA — CNPG sam |
| Stari node pride nazaj | Stara primary postane replica ✅ | ✅ DA — CNPG sam |
| Oba noda crkneta hkrati | Sistem je mrtev ❌ | ❌ Potreben ročen poseg |
| Aplikacija crkne | Kubernetes jo ponovno zažene ✅ | ✅ DA — k3s sam |
| Omrežje pade | Ovisi od vzroka — delno avtomatsko | ⚠️ Delno |
---
## 4. 💾 Longhorn — kako so podatki varni tudi ob okvari diska
**Longhorn** je distribuiran (razpršen) sistem za shranjevanje. Preprosto povedano: poskrbi, da so podatki baze shranjeni na obeh računalnikih hkrati, tako da tudi če en disk crkne, podatki niso izgubljeni.
Vsaka baza ima svoj **PVC** (Persistent Volume Claim — "zahtevek za trajno shrambo") velikosti 1Gi (1 gibibajt). To je kot da ima vsaka baza svojo mapo na disku, ki je varna tudi, če se računalnik ugasne.
---
## 5. ⚙️ Konfiguracija — kje kaj piše
### Povezava aplikacije na bazo
Aplikacija ve, kako do baze, prek te povezave:
```env
DATABASE_URL=postgresql://sola:***@sola-db-rw.sola:{{K8S_DB_PORT}}/sola
```
Tukaj:
- `sola` — uporabniško ime
- `***` — geslo (skrito v Kubernetes Secrets)
- `sola-db-rw.sola` — servisni naslov znotraj Kubernetes omrežja (sistema)
- `{{K8S_DB_PORT}}` — vrata (port)
- `/sola` — ime baze
**Pomembno:** Aplikacija vedno uporablja `sola-db-rw` — naslov, ki vedno kaže na trenutno primarno bazo. Tako ji ni treba vedeti, katera baza je trenutno glavna.
### Kje so shranjena gesla?
| Podatek | Lokacija |
|---|---|
| Geslo za bazo | Namespace `sola-app`, Secret `sola-secrets` |
| Email nastavitve | Namespace `sola-app`, Secret `sola-secrets` |
| Nastavitve baze (CNPG) | Namespace `sola`, Cluster `sola-db` |
| Operator baze | Namespace `cnpg-system` |
### CNPG Cluster — nastavitve
| Lastnost | Vrednost |
|---|---|
| Namespace | `sola` |
| Ime clustra | `sola-db` |
| Število instanc | 2 (ena na vsakem nodu) |
| Shramba | Longhorn, 1Gi vsaka |
| Zamik failoverja | 30 sekund |
| Node anti-affinity | `preferred` (raje na različnih nodih, ni pa nujno) |
| PodDisruptionBudget | Vklopljen (preprečuje izpad obeh baz hkrati) |
**Kaj je PodDisruptionBudget (PDB)?** To je pravilo, ki pravi: "Nikoli ne dovoli, da sta obe bazi hkrati nedosegljivi." Tudi če Kubernetes izvaja vzdrževalna dela, bo poskrbel, da vsaj ena baza ostane prižgana. Podobno kot pravilo v letalu: "nikoli ne zapusti letala brez pilota v kabini."
---
## 6. 🧪 Testiranje HA — kako preverimo, da res deluje
### Simulacija izpada (če želite preizkusiti)
Če želite preveriti, ali sistem res preživi izpad enega računalnika:
```bash
# 1️⃣ Ugasni node k3s-1 (simulacija izpada)
ssh k3s-1 "sudo poweroff"
# 2️⃣ Preveri, da aplikacija še vedno odgovarja
curl -I https://{{DOMAIN}}
# 3️⃣ Počakaj ~2 minuti in preveri stanje
kubectl get pods -n sola -o wide
# sola-db-2 naj bo PRIMARY
# sola-db-1 naj bo Missing ali Unknown
kubectl get pods -n sola-app -o wide
# Oba poda naj bosta na k3s-2
# 4️⃣ Ko k3s-1 spet zaženeš, preveri okrevanje
kubectl get cluster -n sola sola-db
# CNPG naj kaže 2 ready instanci
```
### Pričakovani rezultati testa
| Test | Pričakovan rezultat |
|---|---|
| Aplikacija med izpadom | Kratka prekinitev (~1–2 min), nato spet dosegljiva |
| Baza po izpadu | `sola-db-2` postane primary, `sola-db-1` izgine |
| Aplikacija po izpadu | Oba poda na k3s-2, aplikacija deluje |
| Po vrnitvi k3s-1 | `sola-db-1` se samodejno pridruži kot replica |
| Obnovitev | Obe bazi ready, aplikacija normalno deluje |
---
## 7. 📝 Pomembne opombe in opozorila
### ⚠️ Kaj je treba vedeti
1. **Cloudflare DNS** — Cloudflare kaže na LoadBalancer IP {{LB_IP}}. Če se ta IP kdaj spremeni, je treba **ročno posodobiti** Cloudflare DNS nastavitve. To ni avtomatsko.
2. **Longhorn poskrbi za podatke** — tudi če en računalnik crkne, so podatki varni. Longhorn ima svoje mehanizme za popravilo (repair), ki jih upravlja sam.
3. **Ni ročnih skript** — vse failover logiko upravlja CNPG operator. Ni dodatnih skript, ki bi jih moral kdo pisati ali vzdrževati.
4. **Failover je popolnoma avtomatski** — v normalnih okoliščinah ni potrebe po ročnem posredovanju. Sistem sam poskrbi zase.
5. **Če crkneta oba noda hkrati** — to je edini scenarij, ki zahteva ročni poseg. V tem primeru je treba ročno popraviti bazo in aplikacijo.
6. **Zgodovina** — Stara Bitnami PostgreSQL je bila odstranjena po migraciji na CNPG. To je dobro, ker CNPG ponuja veliko boljšo podporo za HA.
---

## 📊 Arhitekturni diagram (povzetek)

![HA arhitektura](diagrams/ha-arhitektura.png)
---
> 📌 **Zadnja misel:** Visoka razpoložljivost ni čarovnija. Je sistem dobro premišljenih pravil, ki skupaj poskrbijo, da uporabniki (naši učitelji, starši in učenci) vedno dobijo kar potrebujejo — tudi ko nekaj v ozadju crkne. In ko enkrat vse nastaviš, večinoma deluje samo od sebe. 🎯
