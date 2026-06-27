🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../admin-devops-navodila.md) | [🇬🇧 English](admin-devops-navodila.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# ⚙️ Admin & DevOps Guide

Comprehensive instructions for installation, maintenance, and troubleshooting.

> **Author:** Matej Čušin  
> **School:** OŠ Toneta Čufarja, Jesenice

---

## 📋 Table of Contents

1. [What the application offers](#what-the-application-offers)
2. [Installing Ubuntu Server 24.04](#0-installing-ubuntu-server-2404-lts)
3. [Installation methods](#installation-methods)
4. [Maintenance and automation](#maintenance-and-automation-cron-jobs)
5. [AI agents for assistance](#ai-agents-for-assistance)
6. [Adding a new node](#adding-a-new-computer-to-the-k3s-cluster)

---

## What the application offers

- **Reservations** for rooms:
  - **Tablets** – didactic tablets (capacity: 28 units, can be shared by multiple teachers in the same period)
  - **Computer room** – one reservation per period
  - **Ship** – one reservation per period
  - **Home economics classroom** – one reservation per period
- **Assessments** – scheduling written assessments with limits (max 3/week, max 2 regular)
- **Blocked dates** – Management/Admin can mark days as blocked
- **Admin panel** – user management
- **Forgot password** – reset via email

## 0. Installing Ubuntu Server 24.04 LTS

### Preparing the installation media

1. Download Ubuntu Server 24.04 LTS from https://ubuntu.com/download/server
2. Create a bootable USB with Rufus (https://rufus.ie/)
3. Install on the target computer (in BIOS set USB as first boot device)

### Installation process

During installation:
- Select **English** (Slovenian is not supported)
- Set a static IP (if desired)
- Make sure to check **"Install OpenSSH server"**
- Create a user and password

### Setting up a static IP

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

Example:
```yaml
network:
  ethernets:
    eth0:
      addresses:
        - {{LB_IP}}/24
      routes:
        - to: default
          via: {{K3S_1_IP}}
      nameservers:
        addresses:
          - {{LB_IP}}
          - 8.8.8.8
  version: 2
```

```bash
sudo netplan apply
```

### Setting up a laptop as a server

```bash
sudo nano /etc/systemd/logind.conf
# Uncomment: HandleLidSwitch=ignore
sudo systemctl restart systemd-logind
```

### SSH – remote access

```bash
# If you didn't check it during installation:
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

---

## Installation methods

The application works in three modes:

| Mode | Difficulty | Suitable for |
|---|---|---|
| **Local (uvicorn)** | ⭐ Easy | Single computer in the staff room |
| **mDNS** | ⭐⭐ Medium | Multiple computers within the school network |
| **Kubernetes (k3s)** | ⭐⭐⭐ Advanced | High availability, 2+ computers |

> **Detailed instructions for each mode:**
> - Local: [postavi-lokalni-app.md](postavi-lokalni-app.md)
> - k3s: [k3s-setup.md](k3s-setup.md)
> - HA architecture: [HA.md](HA.md)

---

## Maintenance and automation (cron jobs)

### Daily database backup (`sola-db-backup`)

- **Schedule:** `0 4 * * *` (daily at 4:00)
- Sends pg_dump of the database to BACKUP_EMAIL

### Daily status report (`sola-daily-report`)

- **Schedule:** `0 4 * * *` (daily at 4:00)
- Report on node status, Longhorn replicas, and applications

---

## AI agents for assistance

### Hermes Agent

[Hermes Agent](https://github.com/NousResearch/hermes-agent) is a CLI tool for maintenance assistance.

**Usage examples:**

```bash
# "Check cluster status"
hermes "kubectl get nodes, check longhorn and report status"

# "Add a new user to the app"
hermes "add user Ana Zupančič to the application, email ana@sola.si, role teacher"

# "Set up daily backup"
hermes "set up a cronjob for daily database backup at 3am"

# "Check why the app is not working"
hermes "check logs of sola-app pods and find out why they are restarting"
```

**Installation:**

```bash
curl -fsSL https://hermes-agent.io/install.sh | sh
```

---

## Adding a new computer to the k3s cluster

### Preparation

1. Install Ubuntu Server 24.04 on the new computer
2. Set a static IP
3. Enable SSH

### Getting the token

```bash
sudo cat /var/lib/rancher/k3s/server/token   # on any master
```

### Joining as an additional master

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --server https://<MASTER_IP>:{{K3S_API_PORT}} \
  --token <TOKEN> \
  --node-ip <NEW_IP> \
  --disable traefik --disable=servicelb
```

### What a node should contain

Each node **can** contain everything:
- **Control-plane role** – manages the cluster
- **Worker role** – runs containers
- **Longhorn** – stores data (requires an additional disk)
- **MetalLB speaker** – enables LoadBalancer IP

### After adding

```bash
# Install Longhorn prerequisites
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid

# Verify
kubectl get nodes
# New node should be Ready
```

---

## Repository structure

```
reservation_app/
├── app/                  # Python application (FastAPI)
│   ├── main.py           # Entry point
│   ├── config.py         # Settings
│   ├── database.py       # Database connection
│   ├── models.py         # DB models
│   ├── schemas.py        # API schemas
│   ├── race.py           # Race condition protection
│   ├── routers/          # API endpoints
│   │   ├── auth.py
│   │   ├── rezervacije.py
│   │   ├── ocenjevanja.py
│   │   └── blocked_dates.py
│   └── templates/        # HTML templates
├── scripts/              # Helper scripts
├── k8s/                  # Kubernetes configuration
├── documentation/        # Documentation
├── Dockerfile
└── requirements.txt
```

**Default admin:** user `admin`, password `admin123`.  
**Change the password immediately after installation!**
