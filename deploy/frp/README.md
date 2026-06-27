# FRP konfiguracija (ZASTARELO — uporabljamo Cloudflare)

> ⚠️ **Ta način dostopa je zamenjan s Cloudflare proxy-jem.**  
> FRP ni več aktiven. Dokumentacija je ohranjena samo za referenco.

## Arhitektura (takratna)

```
Internet ──► DNS: ostc-app.org → Cloudflare
                  │
                  ▼
          Cloudflare proxy → k3s-1:443
                  │
                  ▼
          nginx → Service LoadBalancer (MetalLB)
                  │
                  ▼
          Pod sola-app (port 8002)
```

---

## 1. Preveri labele na podih

```bash
kubectl get pods -n sola-app --show-labels
```

Pričakovan rezultat: `app=sola-app`

---

## 2. Kubernetes Service

Service že obstaja kot LoadBalancer s ClusterIP `<CLUSTER_IP>`.
Preveri:

```bash
kubectl get svc -n sola-app sola-app
```

Če ga slučajno ni oziroma če je Service trenutno LoadBalancer, apliciraj FRP overlay, ki ga spremeni v `ClusterIP`:

```bash
kubectl apply -k k8s/app/overlays/frp
```

Preveri:

```bash
kubectl get svc -n sola-app sola-app
```

---

## 3. frpc.toml (na k3s masterju)

Kopiraj pripravljeno konfiguracijo:

```bash
cp deploy/frp/frpc.toml ~/frp_0.69.0_linux_amd64/frpc.toml
```

Vsebina (lokalni IP = ClusterIP servisa):

```toml
serverAddr = "SERVER.EXAMPLE.COM"
serverPort = 7000
auth.token = "<AUTH_TOKEN>"

[[proxies]]
name = "sola-app"
type = "http"
localIP = "<CLUSTER_IP>"
localPort = 8002
customDomains = ["ostc-app.org"]
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

## 5. HTTPS — Caddy na javnem strežniku (SERVER.EXAMPLE.COM)

**Predpogoj:** SSH dostop do SERVER.EXAMPLE.COM.

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
ostc-app.org {
    reverse_proxy localhost:8080 {
        header_up Host ostc-app.org
    }
}

ostc-app.org:80 {
    redir https://ostc-app.org{uri} permanent
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
curl -I http://ostc-app.org

# Preveri HTTPS:
curl -I https://ostc-app.org
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
