# ➕/➖ Doaj 3. node v k3s cluster — odstranitev in ponovna namestitev

> **Namen:** koračni vrstni red za ponovno ureditev 3. noda.
> 1. **Najprej:** kako pravilno **odstranimo** obstoječi `k3s-3` iz clustra (control-plane + etcd član).
> 2. **Nato:** kako **na istem računalniku po sveži namestitvi OS** dodamo nov node nazaj kot control-plane (master + worker) z istim IP-jem.
>
> Dokument uporablja `[občutljiva vrednost]` mesta za občutljive vrednosti — spodaj je preglednica aktualne topologije.

---

## Topologija clustra

| node | IP | vloga | OS | status |
|------|-----|-------|-----|--------|
| `k3s-1` | `193.2.171.250` | control-plane, etcd | Ubuntu 24.04 LTS | aktiven |
| `k3s-2` | `193.2.171.249` | control-plane, etcd | Ubuntu 24.04 LTS | aktiven |
| `k3s-3` | `193.2.171.251` | control-plane, etcd | (bo ponovno) | **odstranjujemo** |

- **MetalLB IP pool:** `193.2.171.200-193.2.171.210` (glej `k8s/cluster/metallb-config.yaml`). LoadBalancer sola-app drži `193.2.171.250`. **Nikoli** ne uporabi IP-ja iz poola kot node-IP.
- **Verzija clustra:** `v1.35.5+k3s1` (npr. `v1.35.5+k3s1`; preberi z `kubectl get nodes`). Pri dodajanju mora biti nova namestitev **zaklenjena na to isto verzijo**.

---

# Del 1 — Odstranitev k3s-3 iz clustra

`k3s-3` je **etcd član** (control-plane) v embedded-etcd clustru. Pri odstranjevanju je ključno, da iz clustra izpade **tako node kot tudi njegov etcd član**, sicer etcd cluster ostane s 3 člani, od katerih je eden mrtev.

> ℹ️ **Zakaj cluster zdaj deluje, čeprav je k3s-3 izklopljen?** etcd ima 3 člane; za quorum (delovanje) zadostujeta 2. Zato storitve tečejo naprej, node pa je `NotReady`.

## 1.0 (Priporočeno) — varnostna kopija etcd

Pred posegom naredi rezervno kopijo etcd baze, da se lahko po potrebi vrneš nazaj. Poženi na **k3s-1** (ali k3s-2):

```bash
sudo k3s etcd-snapshot save
```

> 💡 Rezervna kopija se shrani v `/var/lib/rancher/k3s/server/db/snapshots/`. Ogled: `sudo k3s etcd-snapshot ls`.

## 1.1 Preveri trenutno stanje

```bash
kubectl get nodes -o wide
```

Pričakovano (k3s-3 je ugasnjen):

```
NAME    STATUS     ROLES                AGE   VERSION         INTERNAL-IP
k3s-1   Ready      control-plane,etcd   86d   v1.35.5+k3s1    193.2.171.250
k3s-2   Ready      control-plane,etcd   89d   v1.35.5+k3s1    193.2.171.249
k3s-3   NotReady   control-plane,etcd   21h   v1.35.5+k3s1    193.2.171.251   ← izklopljen
```

## 1.2 Odstrani node iz clustra

Poženi na **k3s-1** (ali katerem koli control-plane nodu, ki ima kubeconfig):

```bash
kubectl delete node k3s-3
```

- To iz clustra odstrani **node objekt**.
- k3s pri **embedded-etcd** samodejno odstrani tudi **etcd člana** iz clustra (controller to uskladi sam).

> ⚠️ **Nasvet:** če se po `kubectl delete node` cluster še vedno obnaša, kot da ima 3 etcd člane (član ne izgine v nekaj minutah), na k3s-1/k3s-2 znova zaženi k3s, da sprožiš uskladitev članstva:
> ```bash
> sudo systemctl restart k3s   # ~30–60 s kratek izpad API-ja
> ```
> Kako preveriti število etcd članov, je v koraku 1.3.

## 1.3 Preveri, da je odstranitev uspela

```bash
# 1. Ostaneta samo 2 noda, oba Ready
kubectl get nodes -o wide

# 2. API clustra je zdrav
kubectl get --raw='/readyz'
```

**Ce hočeš definitivno potrditi, da je etcd res 2-članski** (na k3s-1/k3s-2; potrebuješ `etcdctl` — `sudo apt install -y etcd-client`):

```bash
sudo ETCDCTL_API=3 etcdctl \
  --cacert=/var/lib/rancher/k3s/server/tls/etcd/server-ca.crt \
  --cert=/var/lib/rancher/k3s/server/tls/etcd/client.crt \
  --key=/var/lib/rancher/k3s/server/tls/etcd/client.key \
  --endpoints=https://127.0.0.1:2379 member list
```

Pričakovano: na seznamu sta **2 člana** (k3s-1, k3s-2).

## 1.4 Opozorilo — začasni 2-nodni cluster

Po odstranitvi je etcd 2-članski → **quorum = 2/2**. To pomeni: dokler sta oba aktivna, vse deluje, a **ni nobene odpornosti na izpad**. Če pade še k1 od k3s-1/k3s-2, dokler 3. nod ni spet dodan, cluster izgubi quorum in API neha delovati.

> ⚠️ **Nasvet:** v tem vmesnem času ne ugašaj/ne ponovno zaženi nobenega od preostalih dveh nodov, dokler 3. nod ni priključen nazaj.

## 1.5 (Opcijsko) Stroj pred reinstalacijo

Ker boš na istem računalniku **ponovno namestil OS**, čiščenje lokalne k3s namestitve na k3s-3 **ni potrebno** — reinstalacija OS pobriše vse. Če pa bi rad počistil še prej (npr. da stare datoteke ne bi vplivale na novo namestitev):

```bash
sudo /usr/local/bin/k3s-uninstall.sh
```

Potem lahko stroj ugasneš in ponovno namesti OS.

---

# Del 2 — Dodajanje novega računalnika (sveža namestitev)

> 📄 Podrobnejši opis korakov je v **[dodajanje-noda.md](dodajanje-noda.md)**; spodaj je jedro z **vsemi pastmi**, ki so nas že ugriznile.

## 2.0 Namesti OS + statični IP + SSH

- Namesti **Ubuntu Server 24.04 LTS** (uskladi z ostalimi nodi).
- **Statični IP:** `193.2.171.251` (enako kot prej — zunaj MetalLB poola `193.2.171.200-193.2.171.210`).
- Omogoči SSH (`openssh-server`), da delaš prek terminala.

> ℹ️ Glej **[admin-devops-navodila.md](admin-devops-navodila.md) → »0. Namestitev Ubuntu Server 24.04 LTS«**.

## 2.1 (Na k3s-1) Pridobi token

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

Token je kot **geslo za vstop v cluster**.

## 2.2 (Na novem nodu) Odpri vrata požarnega zidu

Če je UFW aktiven, odpri `6443/tcp` (API) in `9345/tcp` (k3s supervisor) — sicer se node ne more pridružiti (najpogostejši razlog, da namestitev steče, a node nikoli ni viden v clustru).

```bash
sudo ufw status
sudo ufw allow 6443/tcp
sudo ufw allow 9345/tcp
```

## 2.3 (Na novem nodu) Longhorn predpogoji

Longhorn je že nameščen v clustru (cluster-scoped) — **NE `helm install` ponovno**. Predpogoji na novem nodu:

```bash
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
systemctl status iscsid      # mora biti active (running)
```

## 2.4 (Na novem nodu) Konfiguracija — PASTE-SAFE

⚠️ **Najpogostejša past:** dolga `curl | sh -s - server \ --server ... --token ...` v eni vrstici se pri lepljenju **razbije** (terminal vstavi prave prelome vrstic ~200 znakov) → flagi padejo ven, install steče brez njih in zažene **samostojen cluster**. Zato **nikoli ne dajaj flag-ov na ukazno vrstico** — vse v `config.yaml`, nameščevalni ukaz pa naj bo kratek.

Ustvari `config.yaml` (heredoc — prelomi vrstic mu ne škodijo):

```bash
sudo mkdir -p /etc/rancher/k3s
sudo tee /etc/rancher/k3s/config.yaml >/dev/null <<'EOF'
server: https://193.2.171.250:6443
token: "K10126dfa574bbc9644fd63c1534b24a41d9b4c7e4a35d49e5771b35e7d213b8f1e::server:2d4fc811b3447e13eabf305d8e59d19a"
node-ip: 193.2.171.251
disable:
  - traefik
  - servicelb
write-kubeconfig-mode: "644"
EOF
cat /etc/rancher/k3s/config.yaml    # ← PREVERI: token cel na ENA vrstici
```

> 💡 Ključi v config.yaml so dolge oblike flag imen (`server`, `token`, `node-ip`, `disable`, `write-kubeconfig-mode`). `write-kubeconfig-mode: "644"` reši tudi znano past »kubectl permission denied« po restartu.

## 2.5 (Na novem nodu) Kratek install — zakleni verzijo

**Obvezno** zakleni `INSTALL_K3S_VERSION` na verzijo clustra (sicer node vleče najnovejšo, kar lahko prepreči join):

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.35.5+k3s1 sh -s - server
```

k3s pri zagonu prebere `config.yaml` — ni dolgih flag-ov na ukazni vrstici, torej se ne more zlomiti.

## 2.6 (Na k3s-1) Preveri

```bash
kubectl get nodes -o wide
```

Pričakovano (po ~60 s za uskladitev etcd quoruma):

```
NAME    STATUS   ROLES                AGE   VERSION
k3s-1   Ready    control-plane,etcd   86d   v1.35.5+k3s1
k3s-2   Ready    control-plane,etcd   89d   v1.35.5+k3s1
k3s-3   Ready    control-plane,etcd   1m    v1.35.5+k3s1   ← SPET nazaj!
```

Če je `NotReady`, počakaj 1–2 min. Po 5 min: `journalctl -u k3s --no-pager -n 50 | grep -iE "fatal|error|etcd|token"`.

> ⚠️ **Nasvet:** če node ne registrira, poženi na novem nodu `curl -sk https://193.2.171.250:6443/healthz` — če vrne `401`, je API dosegljiv (problem je drugje); če nič, točki 2.2 (požarni zid) še enkrat.

## 2.7 Longhorn — replika na novem nodu

Node samodejno registrira Longhorn v ~10–15 min. Preveri:

```bash
kubectl -n longhorn-system get nodes.longhorn.io        # nov node viden
kubectl -n longhorn-system get pods -o wide | grep longhorn   # manager+csi na novem nodu
```

> ⚠️ **Past:** `default-replica-count` ostane 2 → **obstoječi volume** (baza!) ima kopijo samo na starih nodih. To NE spremenijo nove replike. Dvigni na 3, da bo tudi nov node dobil kopijo:
> ```bash
> kubectl patch settings.longhorn -n longhorn-system default-replica-count --type='merge' -p '{"value":"3"}'
> kubectl patch settings.longhorn -n longhorn-system replica-auto-balance --type='merge' -p '{"value":"least-effort"}'
> ```

## 2.8 Razširi replike aplikacije (2 na node)

HPA naj drži 6 replik (3 node × 2): glej **[HA.md](HA.md) → »1. Aplikacija (sola-app)«**. Preveri `kubectl get pods -n sola-app -o wide` → 2 poda na vsakem nodu.

## 2.9 MetalLB preveri

`node-ip` 193.2.171.251 je zunaj poola — dobro. Preveri še speaker na vsakem nodu:

```bash
kubectl get pods -n metallb-system -o wide     # speaker Running na VSAKEM nodu (tudi novem)
```

Neškodljiv log artefakt ob priklopu novega speakerja: `ServiceL2Status ... value is immutable` — ignoriraj (kozmetičen).

## 2.10 (Opcijsko) Hermes agent na novem nodu

Če naj nov node vodi tudi Hermes agenta z isto memory/zgodovino: glej **[dodajanje-noda.md](dodajanje-noda.md) → korak 6** (export/import profila + prenos `.env`). ⚠️ Discord dopušča **eno aktivno povezavo na bot token** — bodisi nov agent s svojim tokenom, bodisi samo eden online.

---

## Končna verifikacija

```bash
# 1. Trije nodi, vsi control-plane
kubectl get nodes -o wide

# 2. Aplikacija — 2 poda na vsakem nodu
kubectl get pods -n sola-app -o wide

# 3. Longhorn — nov node viden, volume imajo 3 replike
kubectl -n longhorn-system get nodes.longhorn.io -o wide
kubectl -n longhorn-system get volumes.longhorn.io -o wide
```

---

> **Avtor:** Matej Čušin
> **Šola:** OŠ Toneta Čufarja, Jesenice
