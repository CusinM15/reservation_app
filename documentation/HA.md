🌐 **Jezik / Language:** [🇸🇮 Slovenščina](HA.md) | [🇬🇧 English](en/HA.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# HA arhitektura — ostc-app (sola-app)

## Kaj sploh pomeni "visoka razpoložljivost"?

Prevedeno v človeščino: **če en računalnik crkne, drugi takoj prevzame, uporabniki pa niti ne opazijo.** 

Aplikacija in baza tečeta na dveh fizičnih nodih (HP ProBook 455 G5 in 450 G5). Če eden od njiju crkne, gre na servis, mu zmanjka elektrike – drugi node pobere vse skupaj brez da bi kdo moral karkoli ročno prestavljati.


---

## 1. Aplikacija (sola-app) — "dva tečeta, eden pade, drugi vleče"

Aplikacija teče v **dveh kopijah (pod-ih)**, ena na vsakem nodu. To ni luksuz, to je osnovni minimum za HA.


- **`replicas: 2`** — Kubernetes dobi ukaz "hočem dva poga, vsakega na svojem nodu"
- Če eden crkne (node pade), Kubernetes samodejno zažene manjkajoči pod na preživelem nodu
- **Health check** na `/health` endpoint — če vrne 200 OK, je pod živ. Če ne, ga Kubernetes ubije in zažene znova

> 💡 **ELI5:** Kot da imaš dva natakarja. Eden zboli — drugi streže vse mize sam, dokler prvi ne pride nazaj. Gostje (uporabniki) sploh ne opazijo razlike, ker je hrana (odgovor) vedno na mizi.

---

## 2. Dostop (omrežje) — "promet vedno najde pot"

> 📊 **Diagram:** [`diagrams/ha-network.drawio`](diagrams/ha-network.drawio) — odpri v https://app.diagrams.net/

- **Cloudflare** kaže na fiksni IP `{{LB_IP}}` — to je javna vstopna točka
- **MetalLB** (Layer2 način) ta IP oglašuje na enem od nodov
- Če tisti node crkne, **se IP samodejno preseli na drugega**, kot da bi selili telefonsko številko na drugo centralo — klicatelji (uporabniki) ne vedo in jih ne briga, kje fizično stoji telefon

> 💡 **ELI5:** Predstavljaj si, da imaš hišo s poštnim nabiralnikom na vratih. Če se ti vrata zamašijo, poštar (Cloudflare) pismo (promet) vrže skozi okno. Pismo vedno pride noter, tudi če so vrata zaklenjena.

---

## 3. PostgreSQL baza — CNPG (CloudNativePG)

**To je najbolj kritičen del.** Aplikacija lahko preživi brez enega pod-a, ne more pa brez baze. Zato imamo PostgreSQL v HA konfiguraciji prek **CloudNativePG (CNPG) operatorja**.

> 📊 **Diagram:** [`diagrams/cnpg-cluster.drawio`](diagrams/cnpg-cluster.drawio) — odpri v https://app.diagrams.net/

### Kako deluje streaming replication?

Replica ves čas gleda kaj primary dela in **posnema vsako potezo**. Vsak `INSERT`, `UPDATE`, `DELETE` na primary se v realnem času prenese na repliko. Če primary crkne, ima replika že vse podatke — manjka ji samo še "dovoljenje" da začne pisati.

### Storitve (Services) za bazo

| Service | Cilj | Namen |
|---------|------|-------|
| `sola-db-rw` | Samo trenutni primary | **Pisanje + branje.** Sprejema `INSERT`/`UPDATE`/`DELETE`. Po failoverju samodejno kaže na novega primary-ja. Uporablja ga app prek `DATABASE_URL`. |
| `sola-db-ro` | Vse ready instance | **Samo branje.** Kubernetes round-robin razporeja bralne zahtevke (`SELECT`) med primary in repliko. Za poročila in heavy read obremenitve. |
| `sola-db-r` | Vse instance (tudi ne-ready) | **Samo branje.** Redko v uporabi. |

V praksi app uporablja izključno `sola-db-rw` prek `DATABASE_URL`.

---

### Failover — "stražar, ki pazi na bazo"

CNPG operator je kot **stražar, ki pazi na bazo**. Ves čas preverja ali je primary živ. Če primarni pade, takoj postavi rezervo.

```yaml
failoverDelay: 30      # počaka 30 sekund, da se prepriča da primary res ne bo prišel nazaj
enablePDB: true        # prepreči da bi oba poda crknila hkrati
podAntiAffinityType: preferred  # raje imej poda na različnih nodih
```

#### Potek failoverja (korak za korakom)

1. **K3s-1 crkne** — primarni pod `sola-db-1` izgine v nič
2. **CNPG zazna izpad** — 30 sekund failover delay, da ni lažnega alarma
3. **Promocija** — `sola-db-2` (na k3s-2) dobi naziv "primary" in začne sprejemati zapisovanje (~2 minuti)
4. **Service `sola-db-rw`** se samodejno preusmeri na `sola-db-2`
5. **App na k3s-1** — pod je mrtev, k3s ga reschedule-a na k3s-2
6. **App na k3s-2** — poveže se na `sola-db-rw` (ki zdaj kaže na `sola-db-2`) → business as usual

**Skupni izpad:** ~1–2 minuti. V IT svetu je to za HA brez downtime SLA kar solidno.

> 💡 **ELI5:** Kot letalo z dvema motorjema. Eden crkne — pilot (CNPG) samo poveča moč na drugem. Potniki (uporabniki) občutijo rahlo tresljaje (par minut nedosegljivosti), potem pa letijo naprej kot da se ni nič zgodilo.

#### Recovery (ko se crknjeni node vrne)

Ko k3s-1 spet pride gor, se zgodi tole brez kakršnegakoli ročnega ukaza:

1. CNPG opazi, da je node spet na voljo
2. `sola-db-1` se samodejno pridruži kot **replika** — ne postane samodejno primary, ampak začne posnemati trenutni primary
3. Vse kar moreš reči je "lepo, dela"

---

## 4. etcd consensus — "večina odloča"

K3s uporablja **embedded etcd** za shranjevanje stanja celotnega clustra (kateri podi so kje, kakšni so servisi, itd.).

Etcd deluje na principu **kvoruma**. Za 2 noda to pomeni:

- **2 noda = kvorum 2** — oba morata potrditi spremembo
- **Če eden crkne** — drugi še vedno lahko bere in piše, ker je 1 od 2 tehnično večina... počakaj, **to ni čisto res**

> ⚠️ **Tehnična poanta:** Klasičen 2-node etcd cluster je *technically* v coni tveganja, ker ob izgubi enega noda izgubiš kvorum za *pisanje* (potrebuješ > N/2 = ceil(3/2) = 2 za 3-node). V praksi k3s z 2 nodoma deluje, ker k3s etcd tolerira izpad 1 noda za **branje**, za pisanje pa rabi potrditev. Ampak za naš use-case (2 ProBooka, noben SLA) je to čisto OK.

**Kar si je treba zapomniti:** 2 noda lahko normalno delujeta tudi če eden crkne, dokler preživeli node prevzame vse operacije.

> 💡 **ELI5:** etcd je kot klub s pravili. Za vsako odločitev (spremembo v集群u) mora glasovati večina članov. Pri dveh članih eden crkne — drugi še vedno lahko sam odloča (kvorum obstaja). Ampak če crkneta oba, je klub zaprt, dokler nekdo ne pride nazaj.

---

## 5. Konfiguracija na kratko

**App povezava na bazo:**
```
DATABASE_URL=postgresql://sola:***@sola-db-rw.sola:{{K8S_DB_PORT}}/sola
```
Service `sola-db-rw` vedno kaže na trenutni primary. App se nikoli ne rabi ukvarjati s tem, kateri node je primary.

**Aplikacijski secret:**
- Namespace: `sola-app`
- Secret: `sola-secrets`
- Vsebina: `DATABASE_URL`, `MAIL_*`, `BACKUP_EMAIL`

**CNPG Cluster:**
- Namespace: `sola`
- Ime: `sola-db`
- 2 instanci, vsaka na svojem nodu
- Longhorn storage (1Gi) vsaka
- Auto-failover: 30s

**Operator:**
- Namespace: `cnpg-system`
- Ime: `cnpg/cloudnative-pg`
- Verzija: helm chart, najnovejša stabilna

---

## 6. Testiranje HA — "udari in poglej kaj se zgodi"

Če želiš simulirati izpad:

```bash
# Ugasni en node (npr. k3s-1)
ssh k3s-1 "sudo poweroff"

# Preveri, da app ostane dostopen
curl -I https://{{DOMAIN}}

# Po ~2 min preveri stanje
kubectl get pods -n sola -o wide      # sola-db-2 naj bo primary
kubectl get pods -n sola-app -o wide  # sola-app pod na k3s-2

# Ko je node spet gor, preveri stanje
kubectl get cluster -n sola sola-db    # CNPG naj ima 2 ready instance
```

---

## 7. Pomembne opombe

- **Cloudflare** kaže na LoadBalancer IP `{{LB_IP}}` — če se ta IP spremeni, je treba posodobiti Cloudflare DNS
- **Longhorn** poskrbi za PVC-je — podatki so varni tudi ob izgubi enega noda
- **Ni custom failover skript** — vse upravlja CNPG operator (pusti ga pri miru, dela kar mora)
- **Failover je popolnoma avtomatski** — ni potrebno ročno posredovanje
- **Stara Bitnami PostgreSQL** je bila odstranjena po migraciji na CNPG (ne išči je)

---

## 📖 Vprašanja in odgovori

### Kaj če oba noda crkneta?

Potem nimaš sreče. Aplikacija je mrtva, baza je mrtva, uporabniki vidijo "stran ni dosegljiva". Ko pridejo nodi nazaj gor, k3s etcd potrebuje rokoborbo (recovery), Longhorn PVC-ji se morajo ponovno pripeti, CNPG pa bo poskusil restartati bazo. Podatki so varni (Longhorn replikacija), ampak **dokler oba noda nista gor, nič ne dela.** Če se to dogaja pogosto, rabiš 3. node ali pa cloud rešitev.

### Kako vem kateri node ima bazo (primary)?

```bash
kubectl get cluster -n sola sola-db -o json | jq '.status.currentPrimary'
```
ali pa
```bash
kubectl exec -n sola -it deploy/sola-app -- psql $DATABASE_URL -c "SELECT pg_is_in_recovery();"
```
`f` = primary, `t` = replica.

### Ali izgubim podatke če node crkne?

**Ne, če crkne samo en node.** Longhorn skrbi za replikacijo podatkov (tipično 2 ali 3 kopije). Tudi če crkne node, kjer je primarna baza, ima replika na drugem nodu vse podatke (malenkost zakasnitve zaradi asinhrone streaming replikacije — max nekaj sekund, v praksi ponavadi <1s). To se imenuje **RPO (Recovery Point Objective)** — v najslabšem primeru izgubiš zadnjih nekaj sekund transakcij. Za to aplikacijo je to sprejemljivo.

### Zakaj 2 noda in ne 3?

Ker imamo dva HP ProBooka in je tretji predrag. Za produkcijo s 5 nines bi rabil 3 (ali 5) nodov za etcd kvorum. Ampak to je šolski sistem — 2 noda je dovolj, da preprečimo izpad ob eni okvari. Če bi hotel biti **res** varen, bi rabil 3 node za etcd in 3+ instance baze za quorum-based failover. Ampak potem bi rabil še en ProBook in elektriko zanj. Zaenkrat smo OK.

---

*Dokumentacija napisana v slogu "DevOps senior razlaga sosedu za mizo" — ker če ne moreš razložiti enostavno, ga ne razumeš dovolj dobro.*
