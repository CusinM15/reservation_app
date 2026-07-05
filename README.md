# Šolski App – Reservation & Assessment Management

Spletna aplikacija za OŠ Toneta Čufarja Jesenice za rezervacije prostorov (tablice, računalnica, ladja) in napovedovanje ocenjevanj.

> 📚 **Celotna dokumentacija:** [documentation/main.md](documentation/main.md)
>
> Dokumentacija vsebuje: arhitekturo, HA setup, k3s namestitev, poletno pavzo,
> navodila za učitelje, vodstvo, admin navodila in več.

---

## 📦 Tehnologije

| Sloj | Tehnologija |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Podatkovna baza | PostgreSQL (produkcija) / SQLite (development) |
| Frontend | Jinja2 template, plain HTML/CSS/JS |
| Avtentikacija | cookie-based session z bcrypt hashom |
| Email | SMTP preko Arnesa (`mail.arnes.si`) |
| Storage | Longhorn (Kubernetes persistent volume) |

---

## 🚀 Namestitev in zagon

### Prvi zagon

```bash
# 1. Pojdi v mapo projekta
cd /home/admin_os/reservation_app

# 2. Ustvari virtualno okolje (samo prvič)
python3 -m venv .res_app

# 3. Aktiviraj in namesti odvisnosti
source .res_app/bin/activate
pip install -r requirements.txt

# 4. Preveri .env datoteko (prilagodi po potrebi)
cat .env

# 5. Zaženi aplikacijo
.res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002
```

### Ponovni zagon

```bash
# Če je proces že zagnan, ga najprej ubij
fuser -k 8002/tcp 2>/dev/null
sleep 2

# Nato zaženi
cd /home/admin_os/reservation_app
nohup .res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 > /tmp/sola-app.log 2>&1 &
```

### Preverjanje, ali aplikacija teče

```bash
# Preveri process
ps aux | grep uvicorn | grep -v grep
# ali
ss -tlnp | grep 8002

# Preveri health endpoint
curl -s http://127.0.0.1:8002/health
# Pričakovan odgovor: {"status":"ok","version":"0.1.0"}
```

### Dnevnik (log)

```bash
# Zadnjih N vrstic
tail -50 /tmp/sola-app.log

# Spremljaj v realnem času
tail -f /tmp/sola-app.log
```

---

## 🛠️ Vzdrževanje

### Posodobitev kode (git pull)

```bash
cd /home/admin_os/reservation_app

# 1. Povleci spremembe
git pull

# 2. Počisti morebitne stare datoteke (če je kaj izbrisano v repu)
git clean -fd

# 3. Restartaj aplikacijo
fuser -k 8002/tcp 2>/dev/null
sleep 2
nohup .res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 > /tmp/sola-app.log 2>&1 &

# 4. Preveri, da je vse OK
sleep 3
curl -s http://127.0.0.1:8002/health
```

### Spreminjanje konfiguracije

Vse nastavitve so v `.env` datoteki. Po spremembi je potreben restart aplikacije.

| Ključ | Privzeto | Opis |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Naslov za bind |
| `APP_PORT` | `8001` | Vrata za HTTP |
| `DATABASE_URL` | `sqlite:///./data/sola.db` | Povezava do baze (SQLite ali PostgreSQL) |
| `BASE_URL` | `http://localhost:8001` | Javni URL aplikacije (za email povezave) |
| `TABLICE_MAX` | `28` | Kapaciteta tablic |
| `SCHEDULE` | JSON objekt | Urnik – indeks ure → časovni interval |
| `RAZREDI` | CSV | Seznam vseh razredov |
| `PROSTORI` | CSV | Seznam prostorov (tablice,racunalnica,ladja) |
| `MAIL_*` | – | Nastavitve za Arnes SMTP |

---

## 👤 Uporabniki

### Privzeti admin

Ob prvem zagonu se samodejno ustvari admin uporabnik:

| Polje | Vrednost |
|---|---|
| Uporabniško ime | `admin` |
| Geslo | `admin123` |
| Vloga | `admin` |

**Takoj po namestitvi spremenite geslo!**

### Ustvarjanje novih uporabnikov

1. Prijavite se kot admin.
2. V navigaciji kliknite **Admin panel**.
3. Izpolnite obrazec "Dodaj uporabnika".

### Vloge

| Vloga | Opis |
|---|---|
| `teacher` | Osnovni učitelj – lahko rezervira prostore in napoveduje ocenjevanja |
| `vodstvo` | Kot učitelj + lahko briše tuje rezervacije/ocenjevanja + upravlja zasedene datume |
| `admin` | Polne pravice + admin panel za upravljanje uporabnikov |

---

## 🗄️ Podatkovna baza

### Produkcija (k3s)

Produkcijska baza je PostgreSQL, ki teče v k3s clusterju. Storage je preko Longhorn persistent volume.

**Dump baze:**
```bash
kubectl exec deploy/postgres -- pg_dump -U sola sola > ./sola-backup.sql
```

**Obnovitev:**
```bash
cat ./sola-backup.sql | kubectl exec -i deploy/postgres -- psql -U sola sola
```

### Development (lokalno)

Lokalno se uporablja SQLite za lažji razvoj. Baza se nahaja v `./data/sola.db`.

### Konfiguracija v .env

```bash
# Za SQLite (development):
DATABASE_URL=sqlite:///./data/sola.db

# Za PostgreSQL (produkcija):
DATABASE_URL=postgresql://sola:sola@postgres:5432/sola
```

Baza se ustvari **samodejno** ob prvem zagonu. Tabele:

- `users` – uporabniki
- `reservations` – rezervacije prostorov
- `assessments` – napovedana ocenjevanja
- `blocked_dates` – zasedeni datumi

### Varnostno kopiranje (development - SQLite)

```bash
# Varnostna kopija
cp ./data/sola.db ./data/sola.db.backup-$(date +%Y%m%d-%H%M)

# Obnovitev
cp ./data/sola.db.backup-YYYYMMDD-HHMM ./data/sola.db
```

**Pred obnovitvijo ustavite aplikacijo!**

```bash
fuser -k 8002/tcp 2>/dev/null
cp ./data/sola.db.backup-20250525-1200 ./data/sola.db
# nato ponovno zaženite aplikacijo
```

---

## 💥 Reševanje težav

### Aplikacija se ne zažene

**1. Preveri dnevnik:**
```bash
cat /tmp/sola-app.log
```

**2. Pogoste napake:**

| Napaka | Vzrok | Rešitev |
|---|---|---|
| `Address already in use` | Vrata so zasedena | `fuser -k 8002/tcp` |
| `No module named uvicorn` | Virtualno okolje ni aktivirano ali ni nameščeno | `.res_app/bin/pip install -r requirements.txt` |
| `No such file or directory: './data/sola.db'` | Manjka mapa `data` | `mkdir -p ./data` |
| `Permission denied` | Ni pravic za pisanje v bazo | `chown -R admin_os:admin_os ./data` |

**3. Preveri health:**
```bash
curl -s http://127.0.0.1:8002/health
```

### Email ne deluje

1. Preverite nastavitve v `.env`:
   - `MAIL_SERVER=mail.arnes.si`
   - `MAIL_PORT=587`
   - `MAIL_USERNAME=oscuf`
   - `MAIL_PASSWORD=...`

2. Testirajte povezavo:
```bash
python3 -c "
import smtplib, ssl
from app.config import settings
context = ssl.create_default_context()
s = smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=10)
s.starttls(context=context)
s.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
print('SMTP OK')
s.quit()
"
```

### Baza je zaklenjena (database is locked)

SQLite ne podpira sočasnega pisanja iz več procesov. Preverite, da ne tečeta dva instance aplikacije:

```bash
ps aux | grep uvicorn
fuser -k 8002/tcp 2>/dev/null
sleep 1
# nato poženite samo eno instanco
```

---

## 🔄 Zamenjava master strežnika (ko glavni crkne)

Aplikacija teče v **k3s Kubernetes** okolju z dvema workerjema in enim masterjem. Podatkovna baza je **PostgreSQL**, storage preko **Longhorn** persistent volume.

### ✅ Če master strežnik crkne (z Longhorn volume)

Longhorn volume je repliciran na vseh nodih, zato podatki niso izgubljeni. Nov master se samodejno postavi, če je k3s pravilno konfiguriran.

```bash
# 1. Preveri stanje nodov
kubectl get nodes

# 2. Preveri, če podi tečejo na workerjih
kubectl get pods -o wide

# 3. Po popravilu masterja ali obnovitvi iz backupa:
kubectl delete pod -l app=sola-app
# k3s bo samodejno zagnal nov pod
```

### ✅ Obnova iz backupa baze

```bash
# 1. Poišči Longhorn PVC
kubectl get pvc

# 2. Ustvari backup pod za dostop do volumna
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: backup-pod
spec:
  containers:
  - name: backup
    image: postgres:16
    command: ["sleep", "3600"]
    volumeMounts:
    - name: sola-data
      mountPath: /data
  volumes:
  - name: sola-data
    persistentVolumeClaim:
      claimName: sola-pvc
EOF

# 3. Kopiraj backup v pod
kubectl cp ./sola-backup.sql backup-pod:/data/

# 4. Obnovi bazo
kubectl exec backup-pod -- psql -h postgres -U sola -d sola -f /data/sola-backup.sql

# 5. Počisti
kubectl delete pod backup-pod
```

### ✅ Kako pridobiti dump baze

```bash
# Dump baze za varnostno kopijo
kubectl exec deploy/postgres -- pg_dump -U sola sola > ./sola-backup.sql

# Obnovitev
cat ./sola-backup.sql | kubectl exec -i deploy/postgres -- psql -U sola sola
```

### ✅ Če stari strežnik ne deluje več in ni Longhorn replike

1. Ponovno postavite k3s cluster.
2. Namestite PostgreSQL preko Helm ali manifesta.
3. Klonirajte aplikacijo, zgradite Docker sliko in deployajte.
4. Uvozite uporabnike preko admin panela (ali `scripts/import_users.py`).
5. **Podatki o rezervacijah in ocenjevanjih bodo izgubljeni** – redno delajte dump baze!

---

## ➕ Dodajanje worker strežnika (load balancing)

Aplikacija že teče v **k3s** z dvema workerjema. Če želite dodati dodatne workerje:

### V k3s okolju (obstoječi cluster)

```bash
# 1. Namesti nov worker node
curl -sfL https://get.k3s.io | K3S_URL=https://<master-ip>:6443 K3S_TOKEN=<token> sh -

# 2. Preveri, da je node dodan
kubectl get nodes

# 3. Posodobi deployment, če želiš več replik
kubectl scale deployment sola-app --replicas=3
```

### V kolikor nimate k3s (development)

Aplikacija podpira PostgreSQL, zato lahko zaženete več workerjev:

```bash
# Več worker procesov na istem stroju (za development)
.res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 --workers 4

# Več instanc na različnih vratih pred nginx proxyjem
.res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 &
.res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8003 &
```

### Kubernetes/k3s deployment konfiguracija

Kubernetes manifesti so zdaj organizirani v mapi `k8s/` po Kustomize vzorcu:

- `k8s/app/base/` — osnovni objekti: Namespace, ConfigMap, Deployment, Service, CronJob.
- `k8s/app/overlays/production-lb/` — produkcijski deploy z MetalLB `LoadBalancer` servisom.
- `k8s/cluster/metallb-config.yaml` — MetalLB IP pool, če ga cluster še nima.

Pred deployom v klasterju ustvari Secret `sola-secrets` v namespaceu `sola-app`. Vanj spadajo občutljive vrednosti, ki niso v repozitoriju: `DATABASE_URL`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_SERVER`, `MAIL_PORT`, `MAIL_FROM` in `BACKUP_EMAIL`.

Primeri ukazov:

```bash
# Enkrat za MetalLB, če ga cluster še nima:
kubectl apply -f k8s/cluster/metallb-config.yaml

# Ustvari Secret z dejanskimi vrednostmi:
kubectl -n sola-app create secret generic sola-secrets \
  --from-literal=DATABASE_URL='postgresql://sola:<geslo>@postgres:5432/sola' \
  --from-literal=MAIL_USERNAME='<uporabnik>' \
  --from-literal=MAIL_PASSWORD='<geslo>' \
  --from-literal=MAIL_SERVER='mail.arnes.si' \
  --from-literal=MAIL_PORT='587' \
  --from-literal=MAIL_FROM='<mail@domena.si>' \
  --from-literal=BACKUP_EMAIL='<backup@domena.si>'

# Deploy z LoadBalancer servisom:
kubectl apply -k k8s/app/overlays/production-lb

kubectl apply -k k8s/app/overlays/production-lb
```
Za pregled generiranih manifestov brez spreminjanja klasterja:

```bash
kubectl kustomize k8s/app/overlays/production-lb
```

---

## 🔧 Service (systemd) – priporočen način zagona

Če želite, da aplikacija teče kot sistemska storitev in se samodejno zažene ob reboot-u:

```bash
# 1. Ustvari systemd service datoteko
sudo tee /etc/systemd/system/sola-app.service > /dev/null <<'EOF'
[Unit]
Description=Šolski App FastAPI
After=network.target

[Service]
Type=simple
User=admin_os
WorkingDirectory=/home/admin_os/reservation_app
ExecStart=/home/admin_os/reservation_app/.res_app/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002
Restart=always
RestartSec=5
StandardOutput=append:/tmp/sola-app.log
StandardError=append:/tmp/sola-app.log

[Install]
WantedBy=multi-user.target
EOF

# 2. Omogoči in zaženi
sudo systemctl daemon-reload
sudo systemctl enable sola-app
sudo systemctl start sola-app

# 3. Preveri status
sudo systemctl status sola-app

# 4. Po pull-u restart
sudo systemctl restart sola-app
```

---

## 📁 Struktura projekta

```
reservation_app/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, middleware, startup
│   ├── config.py            # Nastavitve iz .env
│   ├── database.py          # SQLAlchemy engine, session
│   ├── models.py            # ORM modeli (User, Reservation, Assessment, BlockedDate)
│   ├── schemas.py           # Pydantic sheme
│   ├── race.py              # Race condition detection
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py          # Prijava, gesla, admin CRUD uporabnikov
│   │   ├── rezervacije.py   # Rezervacije prostorov
│   │   ├── ocenjevanja.py   # Napovedi ocenjevanj
│   │   └── blocked_dates.py # Zasedeni datumi
│   └── templates/
│       ├── index.html       # Glavna stran s koledarji
│       ├── login.html       # Prijavna stran
│       └── admin_users.html # Admin panel
├── data/
│   └── sola.db              # SQLite baza
├── k8s/                     # Kubernetes/k3s manifesti in Kustomize overlayi
├── scripts/                 # Skripte za backup, uvoz uporabnikov itd.
├── .env                     # Konfiguracija
├── .res_app/                # Virtualno okolje
├── requirements.txt
├── navodila.md              # Navodila za uporabnike
└── README.md                # Tehnična dokumentacija
```

---

## 📧 Kontakt

Za tehnično podporo ali težave z aplikacijo kontaktirajte administratorja.
