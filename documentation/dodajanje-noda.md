# ➕ Dodajanje novega noda v k3s cluster

> **Namen:** koračni vrstni red za predstavitev — kako dodamo nov node v obstoječi k3s cluster kot **control-plane (master + worker)**, razširimo replike aplikacije (**2 na node**), poskrbimo za **Longhorn repliko** na novem nodu in namestimo **Hermes agenta**, ki se poveže v isti pogovor in ima isto pomnilnik (memory).
>
> Vrstni red spodaj sledi obstoječi dokumentaciji — vsak korak ima povezavo na podroben dokument.

---

## Vrstni red korakov

### 0. Ubuntu Server 24.04 LTS + statični IP + SSH

📄 **[admin-devops-navodila.md](admin-devops-navodila.md) → poglavje »0. Namestitev Ubuntu Server 24.04 LTS«**

- Priprava namestitvenega medija in potek namestitve.
- **Statični IP** — nov node dobi fiksen naslov `{{K3S_3_IP}}` (enako kot `{{K3S_1_IP}}` in `{{K3S_2_IP}}`).
- SSH oddaljen dostop, da lahko vse delamo prek terminala.

**Kaj se zgodi:** nov node je pripravljen, vedno dosegljiv na istem IP-ju in dostopen prek SSH.

---

### 1. Pridobi token iz obstoječega clustra

📄 **[k3s-setup.md](k3s-setup.md) → poglavje »1.2 Pridobi token«**

Na katerem koli obstoječem nodu (npr. `{{K3S_1_IP}}`):

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

Token je kot **geslo za vstop v cluster** — nov node ga rabi, da se lahko pridruži.

---

### 2. Priključi nov node kot control-plane (master + worker)

📄 **[k3s-setup.md](k3s-setup.md) → poglavje »1.3 Namesti k3s na drugem nodu«**
📄 **[admin-devops-navodila.md](admin-devops-navodila.md) → poglavje »3. Priključitev kot dodaten master«**

Na **novem** računalniku:

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://{{K3S_1_IP}}:6443 \
  --token <TOKEN> \
  --node-ip {{K3S_3_IP}} \
  --disable traefik --disable=servicelb
```

**Kaj se zgodi:** k3s se namesti v načinu `server` (control-plane) in se pridruži obstoječemu clustru. Ker je control-plane, lahko tudi **odloča** (master) in **poganja aplikacije** (worker) — tako kot obstoječa noda.

> ⚠️ **Pozor (požarni zid):** če je na novem nodu omogočen UFW, odpri vrata `6443/tcp` (API) in `9345/tcp` (k3s supervisor), sicer se node ne more pridružiti. Preveri z `sudo ufw status`.

---

### 3. Preveri cluster

📄 **[k3s-setup.md](k3s-setup.md) → poglavje »1.4 Preveri«**

S katerega koli noda:

```bash
kubectl get nodes
```

**Pričakovano:**
```
NAME    STATUS   ROLES                AGE
k3s-1   Ready    control-plane,etcd   81d
k3s-2   Ready    control-plane,etcd   84d
k3s-3   Ready    control-plane,etcd   1m   ← NOV!
```

Če je `NotReady`, počakaj minuto ali dve — etcd se mora uskladiti. Po 5 minutah: `systemctl status k3s` in `journalctl -u k3s --tail=50`.

---

### 4. Longhorn — predpogoji in replika na novem nodu

📄 **[k3s-setup.md](k3s-setup.md) → poglavje »3.1 Predpogoji na vsakem nodu«**
📄 **[main.md](main.md) → poglavje »Longhorn Storage«**

**Najprej predpogoji na NOVEM nodu** (Longhorn rabi ta orodja za oddaljene diske):

```bash
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

**Nato preveri, da Longhorn vidi nov node:**

```bash
kubectl -n longhorn-system get nodes.longhorn.io
```

**Replika na novem nodu:** Longhorn samodejno uporablja nov node za **nove** volumne. Da bo imel **obstoječi** volume (baza!) kopijo tudi na novem nodu:

- Longhorn UI (prek `kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80`) → Storage → Volume → **Replica Count: 3** (ali vklopi »Replica Auto-Balance: least-effort« v Settings).
- Preveri: vsak volume ima 3 replike, ena na novem nodu.

> ℹ️ Privzeto je Replica Count 2 (2 kopiji na 2 različnih nodih). S 3 nodi lahko dvigneš na 3 — ena kopija na vsakem nodu.

---

### 5. Razširi replike aplikacije — 2 na node

📄 **[HA.md](HA.md) → poglavje »1. Aplikacija (sola-app)«**
📄 **[admin-devops-navodila.md](admin-devops-navodila.md) → poglavje »Vzdrževanje in avtomatizacija (HPA)«**

Trenutno HPA skrbi za 2–4 replike. Za **2 repliki na vsakem nodu** (3 nodi → 6):

```bash
# 1. HPA naj drži 6 replik (min = max = 6, ker želimo fiksno 2 na node)
kubectl edit hpa -n sola-app sola-app-hpa
#    minReplicas: 6
#    maxReplicas: 6

# 2. Takoj povečaj (HPA to potrdi v minuti)
kubectl scale deployment -n sola-app sola-app --replicas=6

# 3. Preveri — 2 poda na vsakem nodu
kubectl get pods -n sola-app -o wide
```

**Kaj se zgodi:** deployment ima prednostno anti-afiniteto (vsak pod se rad usede na drug node), zato se 6 podov razporedi **2 + 2 + 2** na tri node. Če node pade, njegova poda zaženeta drugje.

---

### 6. Hermes agent na novem nodu

🔗 Uradna dokumentacija: https://hermes-agent.nousresearch.com/docs/

**6.1 Namestitev:**

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

**6.2 Povezava v ta pogovor (Discord):**

```bash
hermes gateway setup    # izberi Discord in vnesi bot token (enako kot pri obstoječih agentih)
hermes gateway start
hermes gateway status   # active (running)
```

> ⚠️ **Pozor:** Discord dovoljuje samo **eno aktivno povezavo na bot token**. Če ima nov agent svoj bot token (svoj Discord bot, povabljen v isto skupino), delata oba hkrati brez težav.

**6.3 Ista memory (pomnilnik) kot k3s-1 agent:**

Na k3s-1 (tukaj):

```bash
hermes profile export default
# → ustvari npr. hermes-default-20260828.tar.gz
```

Na novem nodu:

```bash
scp {{SSH_USER}}@{{K3S_1_IP}}:~/hermes-default-*.tar.gz .
hermes profile import hermes-default-*.tar.gz
```

Poleg tega prenesi še API ključe (niso del profila):

```bash
scp {{SSH_USER}}@{{K3S_1_IP}}:~/.hermes/.env ~/.hermes/.env
```

> ℹ️ Profil vsebuje memory, skills, config in zgodovino — nov agent se tako obnaša kot obstoječi.

**6.4 Preveri:** pozdravi agenta v tem pogovoru (mora odgovoriti) in preveri spomin: `hermes chat -q "Kdo sem? Kaj veš o meni?"`.

---

### 7. Končna verifikacija — vse na enem mestu

```bash
# 1. Trije nodi, vsi control-plane
kubectl get nodes

# 2. Aplikacija — 2 poda na vsakem nodu
kubectl get pods -n sola-app -o wide

# 3. Longhorn — nov node viden, volume imajo 3 replike
kubectl -n longhorn-system get nodes.longhorn.io
kubectl -n longhorn-system get volumes.longhorn.io -o wide

# 4. Hermes — aktiven in odgovarja v pogovoru
hermes gateway status
```

**Cilj dosežen:** nov node kot control-plane (master + worker), 2 repliki aplikacije na node, Longhorn replika na novem nodu, statični IP, Hermes agent z isto memory v istem pogovoru. 🎉

---

> **Avtor:** Matej Čušin  
> **Šola:** OŠ Toneta Čufarja, Jesenice
