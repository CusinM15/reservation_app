# Poletna pavza k3s klustra

Ta dokument zbere trenutni report k3s/Longhorn stanja in navodila za varno poletno pavzo aplikacije.

**Datum reporta:** 19. 06. 2026 ob 13:03  
**Repozitorij:** `reservation_app`  
**Aplikacija:** rezervacije / šolska app  
**Produkcija:** k3s cluster OSTC  
**PostgreSQL baza:** `rezervacije_app`  
**Namembnost:** julij/avgust, ko aplikacija ni potrebna.  
**Cilj:** čim bolj zmanjšati obrabo starih nodov in ohraniti podatke ter možnost čistega vklopa jeseni.

---

## 1. Trenutno stanje klustra

### Nodi

| Node | IP | Vloga | Stanje | Ocena |
|---|---:|---|---|---:|
| k3s-1 | 192.168.1.1 | control-plane, etcd | Ready | 97/100 |
| k3s-2 | 192.168.1.2 | control-plane, etcd | Ready | 82/100 |

Skupna ocena stanja: **85/100 — trenutno zeleno, z opozorilom pri k3s-2**.

Glavno opozorilo:

- `k3s-2` ima bistveno več restartov kot `k3s-1`.
- To ne pomeni nujno takojšnje odpovedi, pomeni pa, da je `k3s-2` manj zanesljiv kandidat za daljše neprekinjeno obratovanje.

---

## 2. Ocena preostale življenjske dobe

Ocene so operativne, ne strojno garantiran MTBF. Temeljijo na Kubernetes/Longhorn stanju, restartih, warningih in trenutni stabilnosti.

| Node | Trenutna ocena | Ocena po 60 dnevih pavze | Razlaga |
|---|---:|---:|---|
| k3s-1 | 120–180 dni | 180–240 dni | Stabilnejši node, malo restartov, brez pressure. |
| k3s-2 | 60–120 dni | 120–180 dni | Še OK, ampak visoko število restartov zmanjša zaupanje. |

Zaključek:

> Poletna pavza bi realno podaljšala uporabno življenjsko dobo za približno 2 meseca, ker noda ne bosta 24/7 pod napetostjo, toploto in obremenitvijo ventilatorjev/napajalnikov.

---

## 3. Longhorn in podatki

Trenutno Longhorn stanje:

```text
Longhorn pods: 21/21 Running
Longhorn volume: attached, healthy
Longhorn replike: 2 running
```

Replike Longhorn za PostgreSQL PVC baze `rezervacije_app`:

```text
replica ... running node: k3s-1
replica ... running node: k3s-2
```

Pomembno razlikovanje:

| Stvar | Trenutno |
|---|---:|
| PostgreSQL baza `rezervacije_app` | 1 |
| Longhorn replike diska | 2 |
| App replike | 2 |

To pomeni:

> Baza ni HA na nivoju PostgreSQL. Disk baze je repliciran z Longhornom.

Longhorn replike ščitijo podatke na nivoju blokovnega diska. Ne pomenijo dveh aktivnih PostgreSQL instanc.

---

## 4. Aplikacije

Trenutno stanje aplikacij:

| Pod / baza | Namespace | Status | Node |
|---|---|---|---|
| sola-app-f74bd4f55-hk6vq | sola-app | Running | k3s-2 |
| sola-app-f74bd4f55-nspl4 | sola-app | Running | k3s-1 |
| sola-postgresql-0 / baza `rezervacije_app` | sola | Running | k3s-1 |

Backup jobi so bili ob zadnjem reportu uspešni:

```text
sola-daily-report-*   Succeeded
sola-db-backup-*      Succeeded
```

---

## 5. Reboot guard

Pred poletno pavzo ni bilo najdenega aktivnega nočnega reboot/restart mehanizma.

Preverjeno:

- uporabniški crontab na lokalnem hostu: prazen;
- root crontab: nepreverjen, ker zahteva geslo;
- systemd timerji: ni najdenega nightly reboot/restart timerja;
- oddaljeni k3s-1 uporabniški crontab: prazen;
- oddaljeni k3s-1 root crontab: nepreverjen, ker zahteva geslo.

Opozorilo:

> Root crontabi ostajajo nepreverjeni. Pred poletno pavzo je smiselno ročno preveriti še root crontab, če je dostop mogoče varno omogočiti.

---

## 6. Ali se splača narediti poletno pavzo?

Da.

Če aplikacija julija in avgusta ni potrebna, je poletna pavza smiselna, ker:

- zmanjša obrabo starih računalnikov;
- zmanjša število ur delovanja napajalnikov;
- zmanjša obrabo ventilatorjev;
- zmanjša toploto v prostoru;
- zmanjša obrabo diskov;
- omogoči jesenski “fresh start”.

Ni pa priporočljivo samo ugasniti elektrike. Postopek mora biti graceful.

---

## 7. Priporočen postopek za poletno pavzo

### 7.1 Pred izklopom

Pred izklopom preveriti:

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl get volumes.longhorn.io -n longhorn-system -o wide
kubectl get replicas.longhorn.io -n longhorn-system -o wide
kubectl get pvc,pv -A -o wide
```

Preveriti:

- oba/t trije noda so `Ready`;
- Longhorn volume je `healthy`;
- Longhorn replike so `running`;
- ni Longhorn rebuilda;
- PostgreSQL backup je uspešen;
- backup je shranjen tudi izven klustra ali vsaj izven istega tveganja.

---

### 7.2 Ustaviti aplikacijo

Najprej ustaviti app deployment:

```bash
kubectl -n sola-app scale deployment sola-app --replicas=0
```

Počakati, da app podi niso več Running.

---

### 7.3 Ustaviti PostgreSQL

Nato ustaviti PostgreSQL StatefulSet, ki nosi bazo `rezervacije_app`:

```bash
kubectl -n sola scale statefulset sola-postgresql --replicas=0
```

To omogoči, da se baza `rezervacije_app` lepo zapre in Longhorn volumen čisteje odklopi.

PVC se ne zbriše. Podatki ostanejo.

---

### 7.4 Ugasniti k3s na nodih

Trenutno je `k3s-2` začetni/primarni etcd node, zato ugasniti najprej ostale node, nazadnje `k3s-2`.

Na `k3s-1`:

```bash
sudo systemctl stop k3s
sudo poweroff
```

Počakati, da se node res izklopi.

Na `k3s-2`:

```bash
sudo systemctl stop k3s
sudo poweroff
```

Če bo do poletne pavze dodan tretji master node, ga ugasniti pred zadnjim/primarnim etcd nodom.

---

## 8. Vklop jeseni

### 8.1 Vklopiti primarni/začetni etcd node

Najprej vklopiti `k3s-2`:

```bash
sudo systemctl start k3s
```

Počakati, da je node healthy.

### 8.2 Vklopiti ostale node

Nato vklopiti `k3s-1`:

```bash
sudo systemctl start k3s
```

Če bo tretji node, vklopiti tudi njega.

---

### 8.3 Preveriti cluster

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl get volumes.longhorn.io -n longhorn-system -o wide
kubectl get replicas.longhorn.io -n longhorn-system -o wide
```

Počakati, da so:

- noda `Ready`;
- Longhorn volume `healthy`;
- Longhorn replike `running`;
- ni rebuilda v teku.

---

### 8.4 Vrniti PostgreSQL

```bash
kubectl -n sola scale statefulset sola-postgresql --replicas=1
kubectl -n sola rollout status statefulset/sola-postgresql
```

Preveriti, da je baza `rezervacije_app` spet dostopna aplikaciji.

---

### 8.5 Vrniti aplikacijo

```bash
kubectl -n sola-app scale deployment sola-app --replicas=2
kubectl -n sola-app rollout status deployment/sola-app
```

Nato preveriti aplikacijo in backup/report cronjob.

---

## 9. Pomembna opozorila

1. **Longhorn ni backup**
   - Longhorn ščiti pred odpovedjo diska/noda.
   - Pred poletno pavzo narediti backup baze izven klustra.

2. **Ne ugašati med Longhorn rebuildom**
   - Če Longhorn popravlja repliko, počakati, da je volume spet `healthy`.

3. **Ne izklopiti kar z stikala**
   - Najprej graceful shutdown aplikacije, baze in k3s.
   - Šele nato `poweroff`.

4. **Domena bo med pavzo nedosegljiva**
   - Cloudflare Tunnel na k3s-1 bo ugasnjen.
   - Zunanji uporabniki ne bodo mogli do aplikacije.

5. **Hermes AI agent na enem nodu**
   - Če je agent pinned na en node, bo med pavzo nedostopen.
   - Če mora biti HA, ga kasneje postaviti v več replik ali brez trdega node affinity.

6. **Dva masterja nista popoln HA**
   - Pri dveh etcd memberjih izguba enega pomeni izgubo quoruma.
   - Po dodanem tretjem masterju bo odpornost bistveno boljša.

---

## 10. Sklep

Za julij/avgust je priporočena poletna pavza:

```text
scale down app
→ scale down PostgreSQL
→ graceful stop k3s na vseh nodih
→ poweroff
→ jeseni vklop v obratnem vrstnem redu
→ preveriti Longhorn, bazo in app
```

To je čista pavza, ki ohrani podatke in zmanjša obrabo starih nodov.
