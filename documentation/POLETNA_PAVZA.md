🌐 **Jezik / Language:** [🇸🇮 Slovenščina](POLETNA_PAVZA.md) | [🇬🇧 English](en/POLETNA_PAVZA.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 🌞 Poletna pavza — k3s cluster

Ta dokument vsebuje navodila za varen izklop aplikacije in k3s clustra čez poletje (julij/avgust), ko aplikacija ni potrebna. Cilj je zmanjšati obrabo starih računalnikov in ohraniti podatke.

> ⚠️ **Ta dokument je bil posodobljen za CNPG arhitekturo.** Če uporabljate staro Bitnami PostgreSQL, glejte starejšo različico.

---

## 📋 Povzetek

```text
1. Preveri stanje clustra
2. Backup baze
3. Ustavi aplikacijo (scale down)
4. Ustavi bazo (scale down CNPG)
5. Ugasni k3s na nodih
6. Poweroff
--- jeseni ---
7. Vklopi node v obratnem vrstnem redu
8. Počakaj da je Longhorn healthy
9. Vklopi bazo (scale up CNPG)
10. Vklopi aplikacijo (scale up)
11. Preveri vse
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
# Pričakovano: oba sola-db volumea "attached", "healthy"
```

---

## 2. Pred izklopom — preverjanje

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
- Longhorn volume so `healthy`
- CNPG cluster ima 2 ready instance
- Ni Longhorn rebuildov v teku

### 2.2 Backup baze

Pred izklopom naredi svež backup:

```bash
# Backup prek CNPG (priporočeno)
kubectl exec -n sola -it sola-db-1 -- pg_dump -U postgres -d sola --clean > /tmp/sola_backup_pred_pavzo.sql

# Preveri velikost
ls -lh /tmp/sola_backup_pred_pavzo.sql

# Shrani tudi izven clustra (npr. na USB ključek)
```

---

## 3. Ustavitev aplikacije in baze

### 3.1 Ustavi app

```bash
kubectl -n sola-app scale deployment sola-app --replicas=0
kubectl -n sola-app rollout status deployment/sola-app
# Počakaj, da ni več Running podov
```

### 3.2 Ustavi bazo (CNPG)

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

> ✅ PVC-ji ostanejo — podatki so varni v Longhornu.

### 3.3 Počakaj, da se Longhorn volume odklopijo

```bash
kubectl get volumes -n longhorn-system -o wide
# Počakaj, da sola-db volume-i postanejo "detached"
```

---

## 4. Izklop nodov

### 4.1 Ustavi k3s in ugasni

Najprej `k3s-1`, nato `k3s-2`:

```bash
# Na k3s-1:
sudo systemctl stop k3s
sudo poweroff

# Počakaj, da je k3s-1 ugasnjen

# Na k3s-2:
sudo systemctl stop k3s
sudo poweroff
```

> **Vrstni red ni kritičen** (oba sta control-plane), vendar priporočam k3s-1 → k3s-2 za doslednost.

---

## 5. Vklop jeseni

### 5.1 Vklopi oba noda

Fizično vklopi računalnika. Ko se sistema naložita:

### 5.2 Zaženi k3s

```bash
# Na k3s-2 (poljuben vrstni red):
sudo systemctl start k3s

# Počakaj, da je node Ready
kubectl get nodes

# Na k3s-1:
sudo systemctl start k3s

# Počakaj, da sta oba Ready
kubectl get nodes
```

### 5.3 Preveri Longhorn

```bash
kubectl get volumes -n longhorn-system -o wide
# Počakaj, da so volume "healthy" (lahko traja nekaj minut)
# Če je kakšen volume "detached", bo Longhorn samodejno priklopil
```

### 5.4 Vklopi bazo (CNPG)

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

### 5.6 Preveri aplikacijo

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

---

## 6. Pomembna opozorila

1. **Longhorn ni backup** — Longhorn ščiti pred odpovedjo diska/noda, ne pred človeško napako. Vedno imej zunanji backup baze.

2. **Ne ugašati med Longhorn rebuildom** — če Longhorn popravlja repliko, počakaj da je volume spet `healthy`.

3. **Ne izklopiti kar z stikala** — vedno graceful shutdown: scale down app → scale down baza → stop k3s → poweroff.

4. **Domena bo med pavzo nedosegljiva** — Cloudflare proxy kaže na LoadBalancer ({{LB_IP}}), ki bo ugasnjen.

5. **Po vklopu preveri cronjob-e** — backup in report se zaženeta sama po shedule-u.

6. **CNPG samodejno vzpostavi replikacijo** — ni potreben ročen ukaz.
