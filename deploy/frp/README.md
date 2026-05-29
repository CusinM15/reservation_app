# FRP konfiguracija za sola-app.ostc.si na k3s

## Arhitektura

```
Internet ──► DNS: sola-app.ostc.si → 185.69.149.101 (javni strežnik)
                  │
      ┌───────────┴────────────┐
      │  Javni strežnik        │
      │  185.69.149.101        │
      │                        │
      │  frps:                 │
      │    bindPort = 7000     │─────► k3s master (frpc)
      │    vhostHTTPPort = 8080│           │
      │                        │           └──► 10.43.122.112:8002
      │  Caddy:                │                (K8s ClusterIP Service)
      │    :80 → redirect 443  │                    │
      │    :443 → rev_proxy    │              ┌─────┴──────┐
      │           localhost:8080│              │ Pod sola-app │
      └────────────────────────┘              │ port 8002    │
                                              └──────────────┘
```

---

## 1. Preveri labele na podih

```bash
kubectl get pods -n sola-app --show-labels
```

Pričakovan rezultat: `app=sola-app`

---

## 2. Kubernetes Service

Service že obstaja kot LoadBalancer s ClusterIP `10.43.122.112`.
Preveri:

```bash
kubectl get svc -n sola-app sola-app
```

Če ga slučajno ni, ga ustvari:

```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: sola-app
  namespace: sola-app
spec:
  selector:
    app: sola-app
  ports:
    - port: 8002
      targetPort: 8002
  type: ClusterIP
EOF
```

---

## 3. frpc.toml (na k3s masterju)

Kopiraj pripravljeno konfiguracijo:

```bash
cp deploy/frp/frpc.toml ~/frp_0.69.0_linux_amd64/frpc.toml
```

Vsebina (lokalni IP = ClusterIP servisa):

```toml
serverAddr = "185.69.149.101"
serverPort = 7000
auth.token = "SolaApp2025!MojeSuperGeslo123"

[[proxies]]
name = "sola-app"
type = "http"
localIP = "10.43.122.112"
localPort = 8002
customDomains = ["sola-app.ostc.si"]
```

Če se ClusterIP kdaj spremeni, ga najdeš z:

```bash
kubectl get svc -n sola-app sola-app -o jsonpath='{.spec.clusterIP}'
```

---

## 4. Systemd service za frpc

Tako se frpc požene ob bootu in se avtomatsko restart-a če pade:

```bash
sudo cp deploy/frp/frpc.service /etc/systemd/system/frpc.service
sudo systemctl daemon-reload
sudo systemctl enable frpc
sudo systemctl start frpc
sudo systemctl status frpc
```

Logi:

```bash
sudo journalctl -u frpc -n 50 -f --no-pager
```

---

## 5. HTTPS — Caddy na javnem strežniku (185.69.149.101)

**Predpogoj:** SSH dostop do 185.69.149.101.

### 5.1 Spremeni frps.toml

Trenutno frps posluša na portu 80 (vhostHTTPPort = 80). Ker Caddy potrebuje port 80 za Let's Encrypt HTTP-01 challenge, prestavimo frps na 8080:

```bash
# Na javnem strežniku uredi frps.toml:
nano /path/to/frps.toml
```

Vsebina:

```toml
bindPort = 7000
vhostHTTPPort = 8080
```

Restartaj frps:

```bash
# Če je systemd service:
sudo systemctl restart frps

# Če je ročno zagnan:
pkill frps
nohup ./frps -c frps.toml > frps.log 2>&1 &
```

### 5.2 Namesti Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
  sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
  sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

### 5.3 Kopiraj Caddyfile

```bash
# Kopiraj Caddyfile iz repota na javni strežnik
# Ali pa ročno ustvari /etc/caddy/Caddyfile:

sudo tee /etc/caddy/Caddyfile <<'EOF'
sola-app.ostc.si {
    reverse_proxy localhost:8080 {
        header_up Host sola-app.ostc.si
    }
}

sola-app.ostc.si:80 {
    redir https://sola-app.ostc.si{uri} permanent
}
EOF

sudo systemctl restart caddy
sudo systemctl status caddy
```

### 5.4 Odpri firewall porte

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 7000/tcp
```

---

## 6. Test

```bash
# Preveri frpc na k3s masterju:
sudo systemctl status frpc
sudo journalctl -u frpc -n 20 --no-pager

# Preveri HTTP (preusmeri na HTTPS):
curl -I http://sola-app.ostc.si

# Preveri HTTPS:
curl -I https://sola-app.ostc.si
```

---

## Pripomočki — hitri ukazi

```bash
# Preveri ClusterIP servisa:
kubectl get svc -n sola-app sola-app

# Preveri labele na podih:
kubectl get pods -n sola-app --show-labels

# Preveri porte na podih:
kubectl get pods -n sola-app -o jsonpath='{.items[*].spec.containers[*].ports}'

# Logi frpc:
sudo journalctl -u frpc -n 50 -f

# Restart frpc ce se kaj spremeni v frpc.toml:
sudo systemctl restart frpc
```
