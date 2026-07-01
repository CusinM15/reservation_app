
---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 🌞 Poletna pavza — k3s cluster (OŠ Toneta Čufarja Jesenice)

Ta dokument vsebuje **navodila po korakih** za varen izklop in kasnejši vklop celega šolskega strežniškega sistema — tako imenovani **"počitniški izklop"**. Namenjen je ljudem, ki niso vsak dan v Kubernetesu, zato je vsak ukaz tudi **razložen v običajnem jeziku**.

Sistem, ki ga ugašamo:
| Komponenta | Opis |
|---|---|
| **2 noda** (prenosnika): `k3s-1` in `k3s-2` | Oba delujeta kot krmilnika (control-plane) in hranita podatke (etcd). Fizično: stara prenosnika. |
| **CloudNativePG (CNPG)** | Baza podatkov (PostgreSQL). Teče v 2 izvodih (repliki) za varnost. |
| **Longhorn** | Shramba diskov — kot "omara za podatke". Poskrbi, da se podatki ne izgubijo, tudi če en disk crkne. |
| **MetalLB** | Daje zunanje IP naslove aplikacijam (npr. {{LB_IP}} za dostop s spleta). |
| **Aplikacija** | Sama šolska spletna aplikacija (namespace: sola-app). |

---

## 📋 Povzetek — kaj se dogaja od začetka do konca

```
1.  Preveri stanje clustra — se prepričaj, da je vse OK
2.  Naredi backup baze — shrani kopijo za vsak slučaj
3.  Ustavi aplikacijo (scale down) — rečeš sistemu "spanec, ne smrt"
4.  Ustavi bazo (scale down CNPG) — baza gre v mirovanje, podatki ostanejo
5.  Počakaj, da se Longhorn diski odklopijo — volume-i postanejo "detached"
6.  Ustavi Kubernetes in ugasni prenosnika
7.  Izklopi iz elektrike (opcijsko)
   --- POČITNICE ---
8.  Vklopi prenosnika
9.  Zaženi Kubernetes na obeh
10. Počakaj, da je Longhorn zdrav — diski morajo biti "healthy"
11. Vklopi bazo (scale up CNPG)
12. Vklopi aplikacijo (scale up)
13. Preveri, da vse deluje
```

---

## 🤔 Zakaj sploh ugašati?

Ker so to **stari prenosniki**. Počitnike (julij, avgust) nihče ne uporablja aplikacije, zato:

- **Manj obratovanja = manj obrabe = daljša življenjska doba.** Stari ventilatorji, stari diski, stari čipi — vsaka ura delovanja šteje. Dva meseca prihranimo ogromno.
- **Manj porabe elektrike** — vsak kilovat šteje, še posebej v šoli.
- **Manj tveganja** — med nevihtami, izpadi elektrike poleti, ko ni nikogar, da bi pogledal, če je sistem v redu.

**Pomembno:** ne brišemo ničesar. Samo ustavimo. Pomisli kot na **zimsko spanje** računalnika — ko se zbudi, se vrne točno tja, kjer je bil.

---

## 1. 📊 Trenutno stanje (pred pavzo)

Preden karkoli naredimo, poglejmo, kako sistem izgleda zdaj.

| Node | IP | Vloga | Stanje |
|---|---|---|---|
| k3s-1 | {{K3S_1_IP}} | control-plane, etcd | Ready |
| k3s-2 | {{K3S_2_IP}} | control-plane, etcd | Ready |

Poglej, kaj vse teče:

```bash
kubectl get pods -A -o wide
```

Stanje Longhorn diskov (shrambe):

```bash
kubectl get volumes -n longhorn-system -o wide
# Pričakovano: oba sola-db volume-a "attached" in "healthy"
```

> **Zakaj to preverjamo?** Če je že zdaj kaj narobe (npr. volume je "faulted" ali node ni "Ready"), tega ne želimo poslabšati z izklopom. Najprej uredi težave, šele nato izklapljaj.

---

## 2. ✅ Pred izklopom — preverjanje in backup

### 2.1 Preveri celoten cluster

Zaženi te ukaze. Ne razumej jih kot "čarobne besede" — vsak od njih preveri en del sistema:

```bash
# Preveri, da sta oba prenosnika živa, dosegljiva in pripravljena
kubectl get nodes -o wide

# Preveri, kaj vse teče (podi = programi)
kubectl get pods -A

# Preveri Longhorn diske — ali so "healthy" (zdravi)?
kubectl get volumes.longhorn.io -n longhorn-system -o wide

# Preveri, da so zahtevki za diske (PVC) pravilno povezani
kubectl get pvc,pv -A -o wide

# Preveri bazo (CNPG) — ali ima 2 delujoči instanci?
kubectl get cluster -n sola sola-db
```

**Kaj moraš videti (checklista):**

- [ ] Oba noda: `Ready`
- [ ] Longhorn volume-i: `healthy`
- [ ] CNPG cluster: 2 ready instanci
- [ ] Ni Longhorn rebuildov v teku (ne sme biti "rebuilding" v stolpcu STATE)

### 2.2 Backup baze — varnostna kopija

**To je najpomembnejši korak.** Če gre kar koli narobe, imaš rezervno kopijo na USB-ju.

```bash
# Naredi kopijo celotne baze v datoteko
kubectl exec -n sola -it sola-db-1 -- pg_dump -U postgres -d sola --clean > /tmp/sola_backup_pred_pavzo.sql

# Preveri, da datoteka obstaja in ni prazna (cca 1 MB ali več)
ls -lh /tmp/sola_backup_pred_pavzo.sql

# KOPIRAJ NA USB KLJUČEK ali drug varen disk!
cp /tmp/sola_backup_pred_pavzo.sql /media/usb/
```

> **Zakaj USB?** Longhorn je odličen, ampak če oba prenosnika crkneta čez poletje (strele, vlaga, karkoli), je backup na USB edina rešitev. Longhorn ščiti pred okvaro enega diska, ne pred požarom v šoli.

---

## 3. ⬇️ Ustavitev aplikacije in baze — "dajmo sistem v zimsko spanje"

**Vrstni red je pomemben!** Ustavljamo v tem vrstnem redu:
```
Aplikacija → Baza (CNPG) → Počakamo Longhorn → Ugasnemo noda
```

Zakaj? Predstavljaj si **kuhinjo v restavraciji**:
1. Najprej poveš kuharjem, naj nehajo kuhati (ustaviš aplikacijo)
2. Nato zapreš shrambo (ustaviš bazo) — nihče več ne bo vzel sestavin
3. Nato počistiš in zapreš kuhinjo (Longhorn odklopi diske)
4. Nazadnje ugasneš luči (ugasneš prenosnika)
   Če bi ugasnil luči medtem ko kuharji še režejo zelenjavo, bi bil nered.

---

### 3.1 Najprej: ustavi aplikacijo

Aplikacija je spletni program, ki ga ljudje uporabljajo v brskalniku. Rečemo mu naj "gre spat":

```bash
# Scale down = rečemo sistemu "daj pode v spanec, ne zbriši jih"
# --replicas=0 pomeni: 0 izvodov = nihče ne teče
kubectl -n sola-app scale deployment sola-app --replicas=0

# Počakaj, da sistem potrdi, da so vsi podi ugasnjeni
kubectl -n sola-app rollout status deployment/sola-app
```

**Pomembno:** podi (programi) izginejo, **ampak podatki ostanejo**. Diski, nastavitve, vse ostane. Ko jeseni rečeš `--replicas=2`, se vrnejo točno taki, kot so bili.

Preveri, da aplikacije ni več:

```bash
kubectl get pods -n sola-app
# Pričakovano: noben pod ni "Running"
```

### 3.2 Nato: ustavi bazo (CNPG)

Baza je srce sistema. Tu so vsi podatki (ocene, rezervacije, uporabniki). CNPG upravlja bazo v dveh izvodih (replikah), zato ustavljanje poteka malo drugače kot pri navadni aplikaciji — **ne brišemo, samo patcheramo na 0**.

```bash
# "Patch cluster na instances=0" = rečemo bazi "daj se ustaviti, ampak ne zbriši diskov"
# To NI brisanje! Instance=0 pomeni "začasno ustavi" — kot da bi dali kuhinjo v mirovanje,
# ne da bi jo porušili. Diski (PVC-ji) ostanejo pripeti in shranjeni.
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":0}}'

# Počakaj, da podi baze izginejo (opazuj v živo)
kubectl get pods -n sola -w
# Pritisni Ctrl+C, ko vidiš, da ni več Running podov

# Preveri, da so diski (PVC-ji) ŠE VEDNO prisotni!
kubectl get pvc -n sola
# Pričakovano: sola-db-1 in sola-db-2 — oba "Bound" (pripeta, čeprav prazna)
```

> ✅ PVC-ji (diski) ostanejo. To pomeni, da so **tvoji podatki varni v Longhornu**. Ko bazo spet vklopiš, se pripne na iste diske z istimi podatki.

### 3.3 Počakaj, da se Longhorn diski odklopijo

Ko baza ni več aktivna, Longhorn po nekaj minutah **sam odklopi diske**. To je normalno in pričakovano.

```bash
kubectl get volumes -n longhorn-system -o wide
```

V stolpcu `STATE` boš videl:

- **Prej:** `attached` (diski so pripeti k baznim podom — normalno med delovanjem)
- **Kasneje:** `detached` (diski so odklopljeni — **to je OK**, pomeni, da so varni v shrambi in nihče ne piše vanje)

**Zakaj je "detached" OK?** Predstavljaj si knjigo v knjižnici. Ko jo nekdo bere, je "attached" (pripeta k bralcu). Ko jo vrne na polico, je "detached" (na polici, varna, nihče je ne uniči). Podatki so še vedno tam. Ko jeseni spet potrebujemo bazo, Longhorn samodejno pripne diske nazaj.

> ⚠️ **Ne nadaljuj, dokler vsi volume-i niso "detached"!** Če bi ugasnil prenosnik, medtem ko Longhorn še nekaj zapisuje na disk, bi lahko izgubil podatke.

---

## 4. 🔌 Izklop nodov

### 4.1 Ustavi Kubernetes in ugasni

Zdaj, ko so vsi programi ustavljeni in diski varni, lahko ugasnemo prenosnika.

**Vrstni red: najprej k3s-1, nato k3s-2.** Zakaj? Oba sta krmilnika (control-plane), zato vrstni red ni smrtno pomemben, je pa dobra navada, da vedno delamo v istem vrstnem redu — manj možnosti za napako.

```bash
# NA k3s-1 (fizično ali prek SSH):
# 1. Ustavi Kubernetes storitev
sudo systemctl stop k3s
# 2. Ugasni prenosnik
sudo poweroff

# Počakaj, da je k3s-1 popolnoma ugasnjen (ne oddaja več pinga)

# NA k3s-2:
sudo systemctl stop k3s
sudo poweroff
```

> **Nasvet:** Če imaš dostop prek SSH, poglej, da se po poweroff res ugasne (poskusi ponoven SSH — zavrnjen je znak, da je računalnik ugasnjen).

### 4.2 Opcijsko: izklopi iz elektrike

Če so poletne nevihte pogoste, lahko prenosnika tudi **fizično izklopiš iz elektrike**. Prenosniki imajo notranjo baterijo, ki bo ob morebitnem sunkovitem vklopu elektrike zaščitila sistem.

---

## 5. ⬆️ Vklop jeseni — "prebujanje iz zimskega spanja"

**Vrstni red vklopa je obraten od izklopa:**
```
Vklopi noda → Poženi Kubernetes → Počakaj Longhorn → Vklopi bazo → Vklopi aplikacijo
```

Zakaj ta vrstni red? Predstavljaj si, da odklepaš trgovino:
1. Najprej odkleneš vrata (vklopiš prenosnika)
2. Nato prižgeš luči (zaženeš Kubernetes)
3. Nato preveriš, da je hladilnik priklopljen in deluje (preveriš Longhorn)
4. Nato odpreš skladišče (vklopiš bazo)
5. Nato prižgeš registrsko blagajno in odpreš vrata za stranke (vklopiš aplikacijo)

Če bi poskusil prižgati registrsko blagajno, preden je hladilnik priklopljen, bi se sistem sesul.

---

### 5.1 Fizični vklop prenosnikov

Pojdi do prenosnikov in ju vklopi (tipka za vklop — običajno na strani ali na tipkovnici). Počakaj, da se oba sistema naložita (približno 1–2 minuti).

### 5.2 Zaženi Kubernetes

Najprej zaženi na enem, nato na drugem:

```bash
# NA k3s-2 (vrstni red ni kritičen, ampak začnimo z drugim):
sudo systemctl start k3s

# Počakaj, da je node viden in "Ready"
kubectl get nodes
# k3s-2 bi moral biti "Ready"

# NA k3s-1:
sudo systemctl start k3s

# Počakaj, da sta oba "Ready"
kubectl get nodes
# Pričakovano: oba node-a "Ready"
```

> **Zakaj ne zaženemo obeh hkrati?** Ker želimo videti, če kateri od njiju povzroča težave. Če zaženeš oba naenkrat in eden crkne, ne veš, kateri je kriv.

### 5.3 Preveri Longhorn — diski morajo biti zdravi

Longhorn je najbolj občutljiv del sistema. Ko se Kubernetes zažene, Longhorn samodejno **pripne diske nazaj** (prestavijo se iz "detached" v "attached" in nato v "healthy").

```bash
kubectl get volumes -n longhorn-system -o wide
```

**Kaj boš videl:**
1. Najprej: volume-i so "detached" — to je OK, Longhorn jih še ni priklopil
2. Čez ~30 sekund do 5 minut: postanejo "attached" — pripeti nazaj
3. Nato: "healthy" — vsi podatki so prebrani in preverjeni

**Počakaj, da so VSI volume-i "healthy".** To je znak, da je shramba pripravljena.

> **Zakaj to traja?** Longhorn mora prebrati podatke z diska, preveriti, ali so vsi deli (replike) v skladu, in če je potrebno, popraviti manjša odstopanja. To je kot previjanje varnostne kopije nazaj na disk — traja nekaj časa.

**Če je kakšen volume "faulted" (pokvarjen):**
To je redko, ampak možno. Pojdi na poglavje "Če gre kaj narobe" spodaj.

### 5.4 Vklopi bazo (CNPG)

Ko je Longhorn zdrav, lahko vklopiš bazo. To je obratno od koraka 3.2 — namesto `instances:0` damo `instances:2`:

```bash
# Vrni CNPG cluster na 2 instanci (dva izvoda baze)
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":2}}'

# Opazuj, kako se podi baze zaženejo (počakaj, da sta oba Running)
kubectl get pods -n sola -w
# Pritisni Ctrl+C, ko vidiš sola-db-1 in sola-db-2 v stanju Running

# Preveri, da je CNPG cluster zdrav
kubectl get cluster -n sola sola-db
# Pričakovano: 2 ready instance, status "healthy"
```

> **Dobra novica:** CNPG (CloudNativePG) samodejno vzpostavi replikacijo med obema instancama. Ni potreben noben ročen ukaz. To pomeni, da se podatki samodejno sinhronizirajo med prvim in drugim izvodom baze.

### 5.5 Vklopi aplikacijo

Ko baza deluje, lahko zaženemo aplikacijo:

```bash
# Scale up = rečemo sistemu "zbudi pode"
# --replicas=2: dva izvoda aplikacije (za večjo zanesljivost)
kubectl -n sola-app scale deployment sola-app --replicas=2

# Počakaj, da so vsi podi Running in da je aplikacija pripravljena
kubectl -n sola-app rollout status deployment/sola-app
# Pričakovano: "deployment sola-app successfully rolled out"
```

### 5.6 Preveri, da vse deluje

Zdaj je čas za končni pregled:

```bash
# 1. Health check aplikacije — vprašamo sistem "si živ?"
curl -s http://{{LB_IP}}:8002/health
# Odgovor: {"status":"ok","version":"0.1.0"}

# 2. Preveri, da domena deluje (spletna stran)
curl -sI https://{{DOMAIN}}
# Odgovor: HTTP/2 307 → preusmeritev na /auth/login (normalno!)

# 3. Preveri podatke v bazi — so vsi uporabniki in rezervacije še tu?
kubectl exec -n sola sola-db-1 -- psql -U postgres -d sola -c \
  "SELECT count(*) FROM users; SELECT count(*) FROM reservations;"
# Pričakovano: številki, ki nista 0 (toliko uporabnikov in rezervacij kot pred pavzo)
```

---

## 6. ⚠️ Pomembna opozorila

1. **Longhorn NI backup.** Longhorn ščiti pred odpovedjo enega diska (če en prenosnik crkne, podatki ostanejo na drugem). **Ne ščiti pa pred:**
   - Človeško napako (nekdo pomotoma zbriše bazo)
   - Programsko napako (bug v aplikaciji izbriše podatke)
   - Fizično krajo ali požarom
   → Zato imej **vedno zunanji backup** (kot smo naredili v koraku 2.2)

2. **Ne ugašaj med Longhorn rebuildom.** Če Longhorn ravno popravlja repliko (vidiš "rebuilding" v stolpcu STATE), **počakaj!** Ugašanje med rebuildom lahko poškoduje podatke. Počakaj, da je volume spet `healthy`.

3. **Ne izklapljaj kar s stikala!** Vedno naredi **graceful shutdown**:
   ```
   Scale down app → scale down baza → počakaj da se Longhorn odklopi → stop k3s → poweroff
   ```
   To je kot: ne meči knjige skozi okno, ampak jo zapri in lepo odloži na polico.

4. **Domena med pavzo ne bo dosegljiva.** Cloudflare proxy kaže na LoadBalancer ({{LB_IP}}), ki bo med pavzo ugasnjen. Ko se aplikacija jeseni zažene, se LoadBalancer samodejno zažene z njo. Domena bo spet delovala v nekaj minutah po vklopu.

5. **Po vklopu preveri cronjob-e.** Sistem ima nastavljene redne naloge (backup baze, dnevna poročila). Preveri, da so se zagnali:
   ```bash
   kubectl get cronjobs -A
   kubectl get jobs -A
   ```

6. **CNPG samodejno vzpostavi replikacijo.** Ni potreben ročen ukaz `pg_basebackup` ali kaj podobnega. CloudNativePG poskrbi za vse sam.

---

## 7. 🆘 Če gre kaj narobe — odpravljanje težav

Tukaj so najpogostejše težave in kako jih rešiti.

### Težava: Longhorn volume ostane "detached" tudi po 15 minutah

**Vzrok:** Longhorn čaka, da se disk pripne, ampak nekaj blokira.
**Rešitev:** Poskusi ročno pripeti volume:
```bash
# Poišči ime volumen-a
kubectl get volumes -n longhorn-system

# Ročno pripeti (attach)
kubectl annotate volume -n longhorn-system <ime-volumna> longhorn.io/volume-scheduling-error-

# Če ne pomaga, preveri Longhorn UI:
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# Odpri v brskalniku: http://localhost:8080
# Pojdi na "Volume" in poglej, kaj piše v "Conditions"
```

### Težava: Longhorn volume je "faulted" (pokvarjen)

**Vzrok:** Eden od diskov je fizično odpovedal ali so podatki poškodovani.
**Rešitev:**
1. Preveri, katera replika je okvarjena
2. Če ena replika deluje, lahko iz nje obnoviš:
```bash
kubectl get volumes -n longhorn-system -o yaml | grep -A 5 "robustness"
# Poglej, katera replika je "healthy"
```
3. V Longhorn UI (glej zgoraj) izberi "Detach" in nato "Attach" — pogosto se popravi samo
4. Če ni rešitve, **obnovi bazo iz USB backupa** (korak 2.2)

### Težava: CNPG se ne zažene (podi ostanejo "Pending" ali "CrashLoopBackOff")

**Vzrok:** PVC-ji so poškodovani ali Longhorn še ni pripravljen.
**Rešitev:**
```bash
# Preveri, kaj je narobe
kubectl describe pod -n sola sola-db-1

# Preveri PVC stanje
kubectl get pvc -n sola

# Če PVC ni "Bound", preveri Longhorn
kubectl get volumes -n longhorn-system -o wide

# Počakaj, da Longhorn volume-i postanejo "healthy", nato poskusi znova:
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":0}}'
# Počakaj 30 sekund
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":2}}'
```

### Težava: Aplikacija se zažene, ampak vrže napako "database connection refused"

**Vzrok:** Baza še ni pripravljena, ko aplikacija poskuša vzpostaviti povezavo.
**Rešitev:** Počakaj še nekaj minut in poskusi znova. Če ne pomaga:
```bash
# Preveri, ali je baza dosegljiva
kubectl exec -n sola-app deploy/sola-app -- nc -zv sola-db-rw.sola 5432
# Če je "Connection refused", baza še ni ready

# Preveri stanje baze
kubectl get cluster -n sola sola-db
```

### Težava: Node se ne zbudi (ne odziva se na SSH)

**Vzrok:** Morda je napaka na omrežju ali prenosnik ni pravilno vklopljen.
**Rešitev:**
1. Fizično preveri prenosnik — ali so lučke? Ali se sliši ventilator?
2. Poskusi ga držati 10 sekund pritisnjen gumb za vklop (trdi reset), nato spet vklopi
3. Pomisli na možnost, da je baterija čez poletje popolnoma izpraznjena — priklopi polnilnik in počakaj 10 minut

### Težava: Po vklopu manjkajo podatki v bazi

**Vzrok:** Zelo redko — lahko je prišlo do poškodbe diska ali napake pri Longhorn replikaciji.
**Rešitev:** Obnovi iz USB backupa:
```bash
# Kopiraj backup v pod baze
kubectl cp /media/usb/sola_backup_pred_pavzo.sql sola/sola-db-1:/tmp/

# Obnovi bazo
kubectl exec -n sola -it sola-db-1 -- psql -U postgres -d sola -f /tmp/sola_backup_pred_pavzo.sql
```

---

## 8. 📝 Hitra kontrolna lista (checklist)

### Pred izklopom (pomlad)
- [ ] Oba noda `Ready`
- [ ] Longhorn volume-i `healthy`
- [ ] Backup baze narejen in shranjen na USB
- [ ] App scale down na 0
- [ ] Baza scale down na 0 (instances: 0)
- [ ] Longhorn volume-i `detached`
- [ ] k3s ustavljen na obeh nodih
- [ ] Prenosnika ugasnjena

### Po vklopu (jeseni)
- [ ] Oba prenosnika vklopljena
- [ ] k3s teče na obeh nodih
- [ ] Oba noda `Ready`
- [ ] Longhorn volume-i `healthy`
- [ ] Baza scale up na 2
- [ ] App scale up na 2
- [ ] Health check OK (`curl /health`)
- [ ] Spletna stran dosegljiva
- [ ] Cronjob-i delujejo

---

*Dokument pripravil DevOps team, OŠ Toneta Čufarja Jesenice.*
*Zadnja posodobitev: {{DATE}}*
