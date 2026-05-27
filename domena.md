# Domena – zamenjava iz `.local` na `ostc.si`

Navodila za vse lokacije, kjer je potrebno spremeniti domeno, ko bo reverse proxy na `ostc.si` pripravljen.

---

## 📋 Pregled vseh lokacij

| # | Lokacija | Stara vrednost | Nova vrednost |
|---|----------|---------------|---------------|
| 1 | `.env` – `BASE_URL` | `https://ostonecufar.local` | `https://ostc.si` |
| 2 | `app/config.py` – `BACKUP_EMAIL` | `admin@ostonecufar.local` | `admin@ostc.si` |
| 3 | `app/main.py` – admin email | `admin@ostonecufar.local` | `admin@ostc.si` |
| 4 | `k3s_setup.md` – `BASE_URL` v ConfigMap | `https://ostonecufar.local` | `https://ostc.si` |
| 5 | `k3s_setup.md` – `BACKUP_EMAIL` v Secret | `admin@ostonecufar.local` | `admin@ostc.si` |
| 6 | `k3s_setup.md` – hostname v arhitekturi | `ostonecufar` | `k3s-master` |
| 7 | k3s node hostname | `ostonecufar` | `k3s-master` |
| 8 | Kubernetes ConfigMap | `BASE_URL=https://ostonecufar.local` | `BASE_URL=https://ostc.si` |
| 9 | Kubernetes Secret | `BACKUP_EMAIL=admin@ostonecufar.local` | `BACKUP_EMAIL=admin@ostc.si` |
| 10 | Nginx reverse proxy `server_name` | – | `ostc.si` |
| 11 | Nginx `proxy_pass` | – | MetalLB IP (npr. `192.168.1.200:8002`) |

---

## 1. Spremeni `.env` (razvojno okolje)

```bash
# V /home/admin_os/reservation_app/.env nastavi:
BASE_URL=https://ostc.si
```

---

## 2. Spremeni kodo

`app/config.py`:
```python
BACKUP_EMAIL = os.getenv("BACKUP_EMAIL", "admin@ostc.si")
```

`app/main.py`:
```python
email="admin@ostc.si",
```

(Kot že storjeno v zadnjem commitu.)

---

## 3. Sprememba hostname strežnika

### Če imaš sudo dostop:

```bash
# Spremeni hostname na master nodu
sudo hostnamectl set-hostname k3s-master

# Na worker nodih:
sudo hostnamectl set-hostname k3s-worker-1  # worker1
sudo hostnamectl set-hostname k3s-worker-2  # worker2
```

### Če nimaš sudo (na tej mašini):

1. Uredi `/etc/hostname`:
   ```bash
   echo "k3s-master" | sudo tee /etc/hostname
   ```

2. Uredi `/etc/hosts`:
   ```bash
   # Spremeni vrstico:
   # 127.0.1.1 ostonecufar
   # v:
   # 127.0.1.1 k3s-master
   ```

3. Ponovni zagon (ali `sudo reboot`).

---

## 4. Spremeni Kubernetes ConfigMap in Secret

Ko je cluster postavljen:

```bash
# Posodobi ConfigMap (BASE_URL)
kubectl -n sola-app set env configmap/sola-config BASE_URL=https://ostc.si

# Posodobi Secret (BACKUP_EMAIL) – najlažje ponovno ustvariti:
kubectl -n sola-app delete secret sola-secrets
kubectl create secret generic sola-secrets \
  --namespace sola-app \
  --from-literal=MAIL_USERNAME=oscuf \
  --from-literal=MAIL_PASSWORD=wzdmccdt \
  --from-literal=MAIL_SERVER=mail.arnes.si \
  --from-literal=MAIL_PORT=587 \
  --from-literal=MAIL_FROM=os-toneta.cufarja-jesenice@guest.arnes.si \
  --from-literal=BACKUP_EMAIL=admin@ostc.si

# Restartaj deployment
kubectl -n sola-app rollout restart deployment/sola-app
```

---

## 5. Nginx reverse proxy

### 5.1 Namesti nginx na master (če še ni)

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 5.2 Ustvari nginx config

Ustvari `/etc/nginx/sites-available/sola-app`:

```nginx
server {
    listen 80;
    server_name ostc.si;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ostc.si;

    ssl_certificate /etc/letsencrypt/live/ostc.si/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ostc.si/privkey.pem;

    location / {
        proxy_pass http://<METALLB_IP>:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Zamenjaj `<METALLB_IP>` z dejanskim IP-jem, ki ga dodeli MetalLB.

### 5.3 Omogoči in SSL

```bash
sudo ln -s /etc/nginx/sites-available/sola-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo certbot --nginx -d ostc.si
```

### 5.4 Preveri

```bash
curl -I https://ostc.si
# Pričakovan odgovor: HTTP/2 200
```

---

## 6. DNS nastavitev

Na Cloudflare (ali drugem DNS providerju) nastavi:

| Tip | Ime | Vrednost |
|-----|-----|----------|
| A | `ostc.si` | Javni IP master strežnika (npr. `193.2.171.250`) |

Če uporabljaš Cloudflare:
- Enable **Proxy** (oranžni oblak) za SSL in DDoS zaščito
- Ali **DNS Only** (sivi oblak), če imaš certbot za SSL

---

## 7. Preverjanje po spremembi

```bash
# 1. DNS ping
ping ostc.si

# 2. HTTP odziv
curl -I https://ostc.si

# 3. Health endpoint
curl https://ostc.si/health

# 4. Prijava
curl -X POST https://ostc.si/auth/login -d "username=admin&password=admin123"

# 5. Pozabljeno geslo (pošlje email s povezavo)
curl -X POST https://ostc.si/auth/forgot-password -d "email=test@example.com"
```

---

## 8. Primer delujoče konfiguracije

Ko je vse narejeno:

```
https://ostc.si → nginx (master, :443) → MetalLB IP (:8002) → k3s pod
https://ostc.si/health → {"status":"ok","version":"0.1.0"}
https://ostc.si/auth/login → Prijavna stran
```
