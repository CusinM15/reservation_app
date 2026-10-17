# Ansible — priprava novih k3s node-ov (Contabo VPS)

Avtomatska namestitev za **2 nova k3s server node-a** (control-plane + etcd), ki se
pridružita obstoječemu clustru na **62.84.176.42**, ter HA konfiguracija clustra:

- vsak node: k3s server (3-node etcd kvorum 2/3)
- UFW: samo SSH/80/443 javno; k3s porte (6443, 10250, 8472/udp) samo med node-i
- Cloudflare Tunnel na vsakem nodu (istovrstna zanka → CF samodejno failoverja)
- CNPG baza: 3 instance (1/node) + sinhrone replike
- App: 3 replike, razporejene 1/node + HPA (min 3, max 6 — 1-2 na node)

## Predpogoji

1. Dva nova Contabo VPS (priporočeno: ≥ 4 GB RAM / 2 vCPU — kot obstoječi node).
2. Na obeh: uporabnik **deploy** s sudo (enako kot na prvem nodu).
3. Tvoj/naš SSH ključ v `~deploy/.ssh/authorized_keys` na obeh (ali `-i` ob zagonu).
4. Ansible na kontrolni mašini (lahko ta node — `pip3 install --user ansible` ali `sudo apt install ansible`).

## Koraki

### 1. Izpolni inventar in spremenljivke

```bash
nano deploy/ansible/inventory.ini        # IP-ja novih VPS-jev, user
nano deploy/ansible/group_vars/all.yml   # glej spodaj
```

- `k3s_token`: na prvem nodu `sudo cat /var/lib/rancher/k3s/server/token`
- `cf_tunnel_token`: Cloudflare dashboard → **Zero Trust → Networks → Tunnels → Create
  tunnel → Cloudflared** → skopiraj token (pri ustvarjanju tunela kasneje dodaš še
  Public Hostname: npr. `app.sola.si` → URL service: `http://127.0.0.1:30372`).

⚠️ `group_vars/all.yml` in `inventory.ini` vsebujeta skrivnosti — **ne commitaj** (že v .gitignore).

### 2. Zaženi pripravo node-ov (kontrolna mašina)

```bash
ansible-playbook -i inventory.ini playbook-nodes.yml --ask-become-pass
```

Postavi UFW, k3s (join kot server → samodejno etcd član) in cloudflared na obeh.

> ⚠️ **2-node etcd je smrtno nevaren** (kvorum 1:1 = deadlock). Kupi in priključi
> OBA node-a ISTI DAN; med priklopom prvega in drugega naj mine čim manj časa.

### 3. Na PRVEM nodu odpri UFW proti novima IP-jema

Na **62.84.176.42** (kot uporabnik s sudo):

```bash
sudo ufw allow from <IP_NODE_2> to any port 6443 proto tcp
sudo ufw allow from <IP_NODE_3> to any port 6443 proto tcp
sudo ufw allow from <IP_NODE_2> to any port 10250 proto tcp
sudo ufw allow from <IP_NODE_3> to any port 10250 proto tcp
sudo ufw allow from <IP_NODE_2> to any port 8472 proto udp
sudo ufw allow from <IP_NODE_3> to any port 8472 proto udp
# tudi na novih nodih sta 6443/10250/8472 odprta med vsemi tremi (playbook to že naredi)
```

### 4. Ko sta oba `Ready` → HA na clustru

Na prvem nodu (ali od tu, kjer imaš `kubectl` + KUBECONFIG):

```bash
ansible-playbook playbook-cluster.yml
```

To naredi: CNPG `sola-db` → **3 instance** (1/node, `minSyncReplicas: 1`),
deployment `sola-app` → **3 replike** s topologySpread (1/node), HPA **min 3 / max 6**.

### 5. Preveri

```bash
kubectl get nodes -o wide
kubectl get pods -n sola-app -o wide
kubectl get cluster sola-db -n sola-app
```

### 6. Cloudflare DNS

V CF: A zapis (ali CNAME) za izbran hostname → **Proxied** (oranžni oblak).
Tunnel vseeno prenese promet — CF edge → tunel → node.

## Test HA (po želji)

Ugasni en node (povej mi, pa izvedeva) → app mora še odgovarjati čez ostanek
(etcd 2/3, app 2/3, CNPG promota repliko).

## Opombe

- Baza uporablja `local-path` (diski node-ov) — izguba node-a = izguba NJEGOVE kopije,
  ampak sinhrone replike na ostalih dveh pokrijejo (ne izgubiš podatkov).
- Repo manifesti (`k8s/cluster`) omenjajo `longhorn` — na tem clustru ni, live = `local-path`.
- Tunel cilja na NodePort `30372` (localhost) — ne rabi svclb-ja, ne rabi odprtih portov.