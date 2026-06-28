🌐 **Jezik / Language:** [🇸🇮 Slovenščina](POLETNA_PAVZA.md) | [🇬🇧 English](en/POLETNA_PAVZA.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 🌞 Poletna pavza — k3s cluster

Ta dokument vsebuje navodila za **varen izklop** aplikacije in k3s clustra čez poletje (julij/avgust), ko aplikacija ni potrebna. Cilj je zmanjšati obrabo starih računalnikov **in** ohraniti vse podatke.

> ⚠️ **Ta dokument je bil posodobljen za CNPG arhitekturo.** Če uporabljate staro Bitnami PostgreSQL, glejte starejšo različico.

---

## 📋 Povzetek (za nestrpne)

```text
 PRED PAVZO:
1. Preveri, da je vse OK (stanje clustra, Longhorn, podi)
2. Naredi backup baze — za vsak slučaj
3. Scale down app → počasi ugasneš aplikacijo
4. Scale down CNPG na 0 → ugasneš bazo, podatki ostanejo
5. Počakaj, da se Longhorn volume-ji odklopijo
6. Stop k3s in poweroff — lepo, po vrsti

 JESENI:
7. Fizično vklopi računalnika
8. Start k3s na obeh nodih
9. POČAKAJ, da je Longhorn healthy (ne hiti!)
10. Scale up CNPG → baza nazaj
11. Scale up app → aplikacija nazaj
12. Preveri, da vse dela
```

---

## 1. Trenutno stanje (pred pavzo)

| Node | IP | Vloga | Stanje |
|---|---|---|---|
| k3s-1 | {{K3S_1_IP}} | control-plane,etcd | Ready |
| k3s-2 | {{K3S_2_IP}} | control-plane,etcd | Ready |

Trenutni podi:

```bash
kubectl get pods -A -o wide
```

Longhorn volume:

```bash
kubectl get volumes -n longhorn-system -o wide
# Pričakovano: oba sola-db volume-a "attached", "healthy"
```

---

## 2. Pred izklopom — preverjanje (kot preden greš na dopust preveriš, da si zaprl vodo)

### 2.1 Preveri stanje clustra

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl get volumes.longhorn.io -n longhorn-system -o wide
kubectl get pvc,pv -A -o wide
kubectl get cluster -n sola sola-db
```

Preveri:
- Oba noda sta `Ready`
- Longhorn volume-i so `healthy`
- CNPG cluster ima 2 ready instanci
- **Ni Longhorn rebuildov v teku** — če Longhorn kaj popravlja, **počakaj**. Če potegneš med rebuildom, je to kot bi prekinil defragmentacijo diska — podatki so lahko v čudnem stanju.

### 2.2 Backup baze

**Zakaj?** Longhorn ni backup. Longhorn je kot rezervna guma — pomaga, če ti poči na cesti, ampak če nekdo ukrade cel avto, rezervna guma ne pomaga. Za večje sranje (človeška napaka, kriptovirus, požar) rabiš pravi backup.

```bash
# Backup prek CNPG (priporočeno)
kubectl exec -n sola -it sola-db-1 -- pg_dump -U postgres -d sola --clean > /tmp/sola_backup_pred_pavzo.sql

# Preveri velikost
ls -lh /tmp/sola_backup_pred_pavzo.sql

# Shrani tudi izven clustra (npr. na USB ključek)
```

> 💡 **Nasvet seniorja:** Dump shrani na dve mesti — eno v cluster, eno ven. "Two is one, one is none."

---

## 3. Ustavitev aplikacije in baze

### 3.1 Scale down app — "ugasni aplikacijo lepo, ne kar s stikala"

**Zakaj scale down in ne kar kubectl delete?** Če kar zbrišeš deployment (ali kar potegneš kabel), lahko aplikacija pusti nerejene transakcije, polovične zapise v bazo, ali poškodovana stanja. To je kot da bi iztrgal stran iz računovodske knjige med pisanjem — veš kje je bilo, ampak številke niso več prave.

`scale --replicas=0` pa reče Kubernetesu: "Počasi ugasni aplikacijo, daj ji čas, da zaključi kar je delala." Košnja s signalom `SIGTERM`, počaka da konča, šele potem `SIGKILL` če je trmasta.

```bash
kubectl -n sola-app scale deployment sola-app --replicas=0
kubectl -n sola-app rollout status deployment/sola-app
# Počakaj, da ni več Running podov
```

### 3.2 Scale down CNPG na 0 — "ugasni bazo, pusti podatke pri miru"

**Zakaj patch `instances:0` in ne kar zbrišemo cluster?** Ker s tem rečeš CNPG: "Ugasi bazo, ampak **pusti podatke na disku**." PVC-ji (trdi diski) ostanejo, Kubernetes jih pusti pripetih, podatki so še vedno tam. Kot bi izklopil računalnik iz elektrike — trdi disk je še vedno notri, podatki so na njem.

Če bi zbrisali cluster, bi CNPG pobral s seboj tudi PVC-je (odvisno od konfiguracije) in adijo podatki.

CNPG ne uporablja StatefulSet-a. Cluster se ustavi z:

```bash
# Patch cluster na 0 instanc (ustavi brez brisanja PVC-jev)
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":0}}'

# Počakaj, da podi izginejo
kubectl get pods -n sola -w

# Preveri, da so PVC-ji še vedno prisotni
kubectl get pvc -n sola
# Pričakovano: sola-db-1 in sola-db-2 (Bound)
```

> ✅ **Zakaj so PVC-ji še vedno `Bound`?** Zato, ker nismo zbrisali PVC-ja — samo rekli smo PostgreSQL naj se ustavi. PVC je v Kubernetesu kot rezervacija parkirnega mesta: avta (poda) ni več, ampak parking (PVC) je še vedno tvoj. Ko prideš nazaj, se lahko parkiraš na isto mesto. Če bi zbrisali PVC, bi nekdo drug lahko parkiral tja (in tvoji podatki bi šli v nič).

### 3.3 Počakaj, da se Longhorn volume odklopijo (detach)

**Zakaj?** Ko CNPG podi izginejo, Longhorn ve, da noben pod več ne rabi teh diskov. Zato jih **odklopi** — to je kot bi izključil zunanji trdi disk iz USB-ja. Disk (volume) je še vedno tam, podatki so na njem, ampak ni več priklopljen na noben računalnik. Ko jeseni poženeš bazo nazaj, bo Longhorn sam spet priklopil diske.

```bash
kubectl get volumes -n longhorn-system -o wide
# Počakaj, da sola-db volume-i postanejo "detached"
```

> 💡 Če se kakšen volume ne odklopi sam od sebe v minuti ali dveh, ni panike — bo pač ostal `attached`. Longhorn je včasih malo počasen. Samo poglej, da ni `faulted` ali `degraded`.

---

## 4. Izklop nodov — "ugasnemo strežnike lepo po vrsti"

### 4.1 Stop k3s in poweroff

**Zakaj najprej `systemctl stop k3s` in šele potem `poweroff`?** `systemctl stop k3s` pošlje Kubernetes servisu znak, naj se lepo zapre — shrani stanje, zapre vse povezave, konča kar je treba. Če samo potegneš poweroff, je to kot bi prenosniku zaprl pokrov med pisanjem dokumenta — mogoče nič narobe, mogoče pa Word javi 'obnovi dokument' naslednjič.

Vrstni red: **najprej k3s-1, nato k3s-2**.

**Zakaj ravno k3s-1 prvi?** Ni kritično — oba sta control-plane, Kubernetes lahko preživi brez enega. Ampak za red in doslednost začnemo s k3s-1. Kot da imaš dva ključa od iste ključavnice — noben ni bolj pomemben, ampak vedno vzameš istega iz žepa.

```bash
# Na k3s-1:
sudo systemctl stop k3s
sudo poweroff

# Počakaj, da je k3s-1 ugasnjen (lučke ugasnejo, ventilator se ustavi)

# Na k3s-2:
sudo systemctl stop k3s
sudo poweroff
```

> **Vrstni red ni kritičen** (oba sta control-plane), vendar priporočam k3s-1 → k3s-2 za doslednost.

---

## 🚨 Kritični opozorili (preberi, preden narediš neumnost)

### 1. 🛑 Ne ugašati med šolskim letom!

Ta procedura je **samo za poletno pavzo (julij/avgust)**. Med šolskim letom aplikacija teče in jo ljudje uporabljajo. Edina izjema je, če solar panel backup odpove in nimamo elektrike — takrat je treba narediti **hiter** graceful shutdown, ampak to je izjema, ne pravilo.

Če ugasneš med šolskim letom po pomoti: **takoj vklopi nazaj** in preveri, da se je vse pravilno pobralo.

### 2. 📢 Ne pozabi izklopiti cron job-ov in obvestil!

Preden ugasneš, preveri, kaj vse pošilja obvestila:
- 📧 Email alerti (če baza neodzivna → pošilja mail)
- 🤖 Slack/Discord boti (dnevni reporti, health check faili)
- ⏰ Cron jobi (backup, čiščenje, statistika)
- 📊 Monitoring (Uptime Kuma, Grafana alerti)

Če tega ne izklopiš, bodo **celo poletje** letela obvestila, da je aplikacija nedosegljiva. Vsak dan. Vsako uro. Vsi na mailu bodo znoreli, ti pa na plaži.

---

## 5. Vklop jeseni — "zbudimo dinozavre"

### 5.1 Fizično vklopi oba noda

Pritisni gumb. Počakaj, da se zaženeta. To lahko traja minuto ali dve — stari računalniki niso več tako hitri kot so bili.

### 5.2 Zaženi k3s

**Zakaj ni važno kateri prvi?** Oba sta control-plane, etcd (shramba stanja) je replikiran na obeh. Prvi, ki zažene k3s, bo poskusil prevzeti etcd vlogo — če je drugi še mrtev, bo prvi sam krpal naprej. Ko drugi vstane, se mu pridruži.

Lahko pa začneš s k3s-2, če se ti zdi — jaz začnem s k3s-2, ampak ni pravilo.

```bash
# Na k3s-2 (ali katerem koli):
sudo systemctl start k3s

# Počakaj, da je node Ready
kubectl get nodes

# Na k3s-1:
sudo systemctl start k3s

# Počakaj, da sta oba Ready
kubectl get nodes
```

### 5.3 ⏳ Počakaj, da Longhorn okreva — **to je najpomembnejši korak!**

**Zakaj je treba čakati?** Ko se k3s zbudi, Longhorn začne pregledovati diske. Vsak volume mora preveriti:
1. Ali so vsi diski (replike) dosegljivi?
2. Ali so podatki na vseh replicah enaki?
3. Ali je katera replika stara, ker je bil node dlje časa ugasnjen?

Ta proces se imenuje **healing** (celjenje). Longhorn rabi čas, da preveri stanje diskov — **ne hiti**. Če poženeš bazo preden je Longhorn pripravljen, bodo podi v `CrashLoopBackOff` ker disk še ni pripravljen. Kot bi prižgal mikrofon, preden je priklopljen na zvočnike — nič ne bo delalo.

```bash
kubectl get volumes -n longhorn-system -o wide
# Počakaj, da so volume "healthy" (lahko traja nekaj minut)
# Stanje "detached" → Longhorn bo samodejno priklopil nazaj
# Stanje "healthy" → pripravljeno, gremo naprej

# Če je kakšen volume "degraded" — Longhorn še obnavlja replike, počakaj
# Če je kakšen volume "faulted" — nekaj je narobe, pokliči pomoč
```

> 💡 **Koliko časa?** Običajno 1-3 minute. Če je bil cluster dol ugasnjen (celo poletje), lahko traja malo dlje. Če traja več kot 10 minut, nekaj ni v redu.

### 5.4 Vklopi bazo (CNPG scale up)

**Zakaj patch `instances:2`?** Ker smo prej pustili PVC-je na miru, lahko zdaj rečemo CNPG: "Tukaj so tvoji stari diski, zaženi bazo nazaj." CNPG bo našel PVC-je, jih priklopil in dvignil PostgreSQL na njih. Podatki so tam, kjer so bili.

```bash
# Vrni CNPG cluster na 2 instanci
kubectl patch cluster -n sola sola-db --type merge \
  -p '{"spec":{"instances":2}}'

# Počakaj, da sta oba poda Running
kubectl get pods -n sola -w

# Preveri stanje clustra
kubectl get cluster -n sola sola-db
# Pričakovano: 2 ready instance, healthy
```

### 5.5 Vklopi aplikacijo

```bash
kubectl -n sola-app scale deployment sola-app --replicas=2
kubectl -n sola-app rollout status deployment/sola-app
```

### 5.6 Preveri aplikacijo — "poglej, če je vse na svem mestu"

```bash
# Health check
curl -s http://{{LB_IP}}:{{LB_PORT}}/health
# {"status":"ok","version":"0.1.0"}

# Spletna stran
curl -sI https://ostc-app.org
# HTTP/2 307 → redirect na /auth/login

# Preveri podatke v bazi
kubectl exec -n sola sola-db-1 -- psql -U postgres -d sola -c \
  "SELECT count(*) FROM users; SELECT count(*) FROM reservations;"
```

> 💪 **Dodaten nasvet:** Po vklopu preveri še, da cron job-i spet delajo in da ni nobenih sumljivih napak v logih: `kubectl logs -n sola-app deployment/sola-app --tail=50 | grep -i error`

---

## 6. Pomembna opozorila

1. **Longhorn ni backup.** Longhorn je kot zunanji trdi disk — tudi če izklopiš prenosnik, podatki ostanejo na disku. Ampak če ti prenosnik pade v vodo ali ti ga ukradejo, zunanji disk ne pomaga. Longhorn ščiti pred odpovedjo diska/noda, **ne** pred človeško napako, kriptovirusom ali požarom. **Vedno imej zunanji backup baze.**

2. **Ne ugašati med Longhorn rebuildom.** Če Longhorn popravlja repliko, počakaj da je volume spet `healthy`. Prekinitev rebuild-a je kot bi iztrgal USB med kopiranjem — podatki so lahko v čudnem stanju.

3. **Ne izklopiti kar z gumba na računalniku.** Vedno graceful shutdown: scale down app → scale down baza → stop k3s → poweroff. Vsak korak da sistemu čas, da se lepo zapre.

4. **Domena bo med pavzo nedosegljiva.** Cloudflare proxy kaže na LoadBalancer ({{LB_IP}}), ki bo ugasnjen. Če kdo poskusi dostopati do ostc-app.org čez poletje, bo dobil napako. To je pričakovano.

5. **Po vklopu preveri cron job-e.** Backup in report se zaženeta sama po shedule-u, ampak vseeno preveri, da se niso ponesreči podvojili ali zamaknili.

6. **CNPG samodejno vzpostavi replikacijo.** Ko poženeš 2 instanci, CNPG sam poskrbi za replikacijo med njima. Ni potreben ročen ukaz — to reši CNPG operator namesto tebe.
