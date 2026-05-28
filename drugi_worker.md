# DRUGI WORKER — dodajanje novega worker vozlišča v k3s

## Predpogoji

- k3s master že teče (`k3s-master`)
- Prvi worker (`worker-1`) že obstaja
- Nov stroj (`worker-2`) ima nameščen **Debian/Ubuntu** in dostop do omrežja
- Master in worker-1 že imata oznaki (taints/labels) po potrebi

---

## 1) Pridobi NODE_TOKEN z masterja

Na **k3s-master**:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

Izpiše dolg token, npr. `K1071abcd...abcd::server:abcd...abcd`.

---

## 2) Namesti k3s agent na worker-2

Na **worker-2** (nov stroj):

```bash
# Določi IP masterja (zamenjaj s pravim IP-jem masterja)
MASTER_IP="192.168.1.100"
NODE_TOKEN="K1071...:server:..."

# Namesti k3s agent
curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" K3S_TOKEN="${NODE_TOKEN}" sh -
```

Počakaj ~30 sekund. Preveri:

```bash
sudo systemctl status k3s-agent
```

---

## 3) Preveri na masterju, da je worker-2 viden

Na **k3s-master**:

```bash
kubectl get nodes
```

Pričakovan izpis:

```
NAME         STATUS   ROLES                  AGE    VERSION
k3s-master   Ready    control-plane,master   25h    v1.32.3+k3s1
worker-1     Ready    <none>                 24h    v1.32.3+k3s1
worker-2     Ready    <none>                 1m     v1.32.3+k3s1
```

Če je `NotReady`, počakaj še minuto in preveri:

```bash
kubectl describe node worker-2
```

---

## 4) Dodaj oznako (label) — obvezno za naš deployment

Naš `sola-deployment.yaml` uporablja `podAntiAffinity`, kar razporedi pod-e
na različne vozle. Če želiš, da gredo pod-i samo na workerje (ne na master),
dodaj labelo:

```bash
# Na masterju označi worker-2
kubectl label node worker-2 node-role.kubernetes.io/worker=worker

# Preveri
kubectl get nodes --show-labels | grep worker
```

---

## 5) Preveri, da deployment uporablja oba workerja

```bash
# Poglej kje trenutno tečejo pod-i
kubectl get pods -n sola-app -o wide

# Po potrebi restartaj (da se pod-i razporedijo na oba workerja)
kubectl rollout restart deployment/sola-app -n sola-app
kubectl rollout status deployment/sola-app -n sola-app
```

Po restartu bi moral videti pod-e razporejene na worker-1 in worker-2:

```
NAME                        READY   STATUS    RESTARTS   AGE   NODE
sola-app-xxxxx-xxxx         1/1     Running   0          1m    worker-1
sola-app-xxxxx-xxxx         1/1     Running   0          1m    worker-2
```

---

## 6) Preveri število replik

Če imaš zdaj 2 workerja in želiš 2 repliki na vsakem (skupaj 4):

```bash
kubectl scale deployment/sola-app -n sola-app --replicas=4
```

Ali uredi `sola-deployment.yaml`:

```yaml
spec:
  replicas: 4
```

in apliciraj:

```bash
kubectl apply -f sola-deployment.yaml
```

---

## 7) Test delovanja

```bash
# Preveri health
curl -sS http://193.2.171.200:8002/health

# Preveri, da so vsi pod-i Running
kubectl get pods -n sola-app

# Preveri porabo virov
kubectl top nodes
```

---

## Povzetek komand (copy-paste)

Na **k3s-master**:
```bash
# 1) Pridobi token
sudo cat /var/lib/rancher/k3s/server/node-token
```

Na **worker-2**:
```bash
# 2) Namesti k3s agent
MASTER_IP="192.168.1.100"  # ← SPREMENI
NODE_TOKEN="..."            # ← SPREMENI
curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" K3S_TOKEN="${NODE_TOKEN}" sh -
```

Na **k3s-master**:
```bash
# 3) Preveri
kubectl get nodes

# 4) Označi
kubectl label node worker-2 node-role.kubernetes.io/worker=worker

# 5) Po potrebi povečaj replike
kubectl scale deployment/sola-app -n sola-app --replicas=4

# 6) Restartaj
kubectl rollout restart deployment/sola-app -n sola-app
kubectl rollout status deployment/sola-app -n sola-app
```
