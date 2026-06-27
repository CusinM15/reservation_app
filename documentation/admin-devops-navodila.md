# ⚙️ Admin & DevOps navodila

Celovita navodila za namestitev, vzdrževanje in odpravljanje težav.

> **Avtor:** Matej Čušin  
> **Šola:** OŠ Toneta Čufarja, Jesenice

---

## 📋 Kazalo

1. [Kaj aplikacija omogoča](#kaj-aplikacija-omogoča)
2. [Namestitev Ubuntu Server 24.04](#0-namestitev-ubuntu-server-2404-lts)
3. [Načini namestitve](#načini-namestitve)
4. [Vzdrževanje in avtomatizacija](#vzdrževanje-in-avtomatizacija-cron-jobi)
5. [AI agenti za pomoč](#ai-agenti-za-pomoč)
6. [Dodajanje novega noda](#dodajanje-novega-računalnika-v-k3s-cluster)

---

## Kaj aplikacija omogoča

- **Rezervacije** prostorov:
  - **Tablice** – didaktične tablice (kapaciteta: 28 kosov, lahko si jih deli več učiteljev v isti uri)
  - **Računalnica** – ena rezervacija na uro
  - **Ladja** – ena rezervacija na uro
  - **Gospodinjska učilnica** – ena rezervacija na uro
- **Ocenjevanja** – napovedovanje pisnih ocenjevanj z omejitvami (max 3/teden, max 2 običajni)
- **Zasedeni datumi** – Vodstvo/admin lahko označi dneve kot zasedene
- **Admin panel** – upravljanje uporabnikov
- **Pozabljeno geslo** – ponastavitev preko emaila

## 0. Namestitev Ubuntu Server 24.04 LTS

### Priprava namestitvenega medija

1. Prenesi Ubuntu Server 24.04 LTS z https://ubuntu.com/download/server
2. Ustvari zagonski USB z Rufus (https://rufus.ie/)
3. Namesti na ciljni računalnik (v BIOSu nastavi USB kot prvi boot device)

### Potek namestitve

Med namestitvijo:
- Izberi **English** (slovenščina ni podprta)
- Nastavi statični IP (če želiš)
- Obvezno označi **"Install OpenSSH server"**
- Ustvari uporabnika in geslo

### Nastavitev statičnega IP-ja

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

Primer:
```yaml
network:
  ethernets:
    eth0:
      addresses:
        - 193.2.171.250/24
      routes:
        - to: default
          via: 193.2.171.1
      nameservers:
        addresses:
          - 193.2.171.10
          - 8.8.8.8
  version: 2
```

```bash
sudo netplan apply
```

### Nastavitev laptopa kot strežnik

```bash
sudo nano /etc/systemd/logind.conf
# Odkomentiraj: HandleLidSwitch=ignore
sudo systemctl restart systemd-logind
```

### SSH – oddaljen dostop

```bash
# Če med namestitvijo nisi označil:
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

---

## Načini namestitve

Aplikacija deluje na treh načinih:

| Način | Zahtevnost | Za kaj je primeren |
|---|---|---|
| **Lokalno (uvicorn)** | ⭐ Enostavno | En računalnik v zbornici |
| **mDNS** | ⭐⭐ Srednje | Več računalnikov znotraj šolskega omrežja |
| **Kubernetes (k3s)** | ⭐⭐⭐ Zahtevno | Visoka razpoložljivost, 2+ računalnikov |

> **Podrobna navodila za vsak način:**
> - Lokalno: [postavi-lokalni-app.md](postavi-lokalni-app.md)
> - k3s: [k3s-setup.md](k3s-setup.md)
> - HA arhitektura: [HA.md](HA.md)

---

## Vzdrževanje in avtomatizacija (cron jobi)

### Dnevna varnostna kopija baze (`sola-db-backup`)

- **Schedule:** `0 4 * * *` (dnevno ob 4:00)
- Pošlje pg_dump baze na BACKUP_EMAIL

### Dnevno poročilo o stanju (`sola-daily-report`)

- **Schedule:** `0 4 * * *` (dnevno ob 4:00)
- Poročilo o stanju nodov, Longhorn replik in aplikacij

---

## AI agenti za pomoč

### Hermes Agent

[Hermes Agent](https://github.com/NousResearch/hermes-agent) je CLI orodje za pomoč pri vzdrževanju.

**Primeri uporabe:**

```bash
# "Preveri stanje klustra"
hermes "kubectl get nodes, preveri longhorn in povej stanje"

# "Dodaj novega uporabnika v app"
hermes "dodaj uporabnika Ana Zupančič v aplikacijo, email ana@sola.si, vloga teacher"

# "Nastavi dnevno varnostno kopijo"
hermes "nastavi cronjob za dnevno backup baze ob 3h zjutraj"

# "Preveri zakaj app ne dela"
hermes "poglej loge sola-app podov in ugotovi zakaj se restartajo"
```

**Namestitev:**

```bash
curl -fsSL https://hermes-agent.io/install.sh | sh
```

---

## Dodajanje novega računalnika v k3s cluster

### Priprava

1. Namesti Ubuntu Server 24.04 na nov računalnik
2. Nastavi statičen IP
3. Omogoči SSH

### Pridobitev tokena

```bash
sudo cat /var/lib/rancher/k3s/server/token   # na kateremkoli masterju
```

### Priključitev kot dodatni master

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://<IP_MASTERJA>:6443 \
  --token <TOKEN> \
  --node-ip <NOVI_IP> \
  --disable traefik --disable=servicelb
```

### Kar mora vsebovati vozlišče

Vsako vozlišče **lahko** vsebuje vse:
- **Control-plane vloga** – upravlja cluster
- **Worker vloga** – poganja zabojnike
- **Longhorn** – shranjuje podatke (potrebuje dodaten disk)
- **MetalLB speaker** – omogoča LoadBalancer IP

### Po dodajanju

```bash
# Namesti Longhorn predpogoje
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid

# Preveri
kubectl get nodes
# Nov node mora biti Ready
```

---

## Struktura repozitorija

```
reservation_app/
├── app/                  # Python aplikacija (FastAPI)
│   ├── main.py           # Vstopna točka
│   ├── config.py         # Nastavitve
│   ├── database.py       # Povezava z bazo
│   ├── models.py         # DB modeli
│   ├── schemas.py        # API sheme
│   ├── race.py           # Race condition protection
│   ├── routers/          # API endpointi
│   │   ├── auth.py
│   │   ├── rezervacije.py
│   │   ├── ocenjevanja.py
│   │   └── blocked_dates.py
│   └── templates/        # HTML predloge
├── scripts/              # Pomožni skripti
├── k8s/                  # Kubernetes konfiguracija
├── documentation/        # Dokumentacija
├── Dockerfile
└── requirements.txt
```

**Privzeti admin:** uporabnik `admin`, geslo `admin123`.  
**Takoj po namestitvi spremenite geslo!**
