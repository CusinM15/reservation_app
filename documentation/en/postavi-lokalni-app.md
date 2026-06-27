🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../postavi-lokalni-app.md) | [🇬🇧 English](postavi-lokalni-app.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# 🖥️ Set Up Local App

Instructions for running the application **on a single computer** (without Kubernetes, without PostgreSQL).
Suitable for other schools, testing, or demonstration.

> **Author:** Matej Čušin  
> **School:** OŠ Toneta Čufarja, Jesenice

---

## 1) What You Need

- **Python 3.11+** or **Docker**
- Git (if you want to clone the repo)
- Browser (Chrome, Firefox, Edge)

---

## 2) Installation via Docker (recommended)

### 2a) Preparation

```bash
# 1. Clone the repo
git clone https://github.com/sola-app.git
cd sola-app

# 2. Edit .env for local use (SQLite, no email)
cp .env.example .env
```

`.env` should contain:

```env
APP_HOST=0.0.0.0
APP_PORT=8001
BASE_URL=http://localhost:{{LOCAL_DEV_PORT}}
DATABASE_URL=sqlite:///./data/sola.db
TABLICE_MAX=28
SCHEDULE={"0":"07:30-08:15","1":"08:20-09:05","2":"09:15-10:00","3":"10:20-11:05","4":"11:10-11:55","5":"12:00-12:45","6":"12:50-13:35","7":"14:00-14:45"}
RAZREDI=1.a,1.b,2.a,2.b,3.a,3.b,4.a,4.b,5.a,5.b,6.a,6.b,7.a,7.b,8.a,8.b,9.a
PROSTORI=tablice,racunalnica,ladja
```

### 2b) Build and Run

```bash
docker build -t sola-app .
docker run -d --name sola-app -p 8001:{{LOCAL_DEV_PORT}} \
  -v $(pwd)/data:/app/data \
  sola-app
```

The application is at **http://localhost:{{LOCAL_DEV_PORT}}**.

Default access: `admin` / `your_password` (change password immediately).

Stop:
```bash
docker stop sola-app && docker rm sola-app
```

---

## 3) Installation without Docker (uvicorn)

### 3a) Environment Setup

```bash
# 1. Clone the repo
git clone https://github.com/sola-app.git
cd sola-app

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Edit .env for local use
cp .env.example .env
# Edit .env — see example above in section 2a
```

### 3b) Run

```bash
# Create data directory
mkdir -p data

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

`--reload` means automatic restart on code changes (useful for development).

Application: **http://localhost:{{LOCAL_DEV_PORT}}**
Admin: `admin` / `your_password`

### 3c) Stop

`Ctrl+C` in the terminal.

---

## 4) First Run — What Happens?

On first run, the application:
1. Creates a SQLite database (`data/sola.db`)
2. Adds the initial admin user (`admin` / `your_password`)
3. Everything is ready for use

**The database is empty** — no reservations, no assessments, no teachers.

---

## 5) Importing Teachers

If you have a publicly published employee list, you can import teachers automatically.

### 5a) Install Tools

```bash
pip install requests beautifulsoup4 lxml
```

### 5b) Run Import

```bash
# If the app is running on localhost:{{LOCAL_DEV_PORT}}:
python3 scripts/import_teachers.py --base-url http://localhost:{{LOCAL_DEV_PORT}}

# Just preview who would be imported (without making changes):
python3 scripts/import_teachers.py --base-url http://localhost:{{LOCAL_DEV_PORT}} --dry-run
```

### 5c) Adapt for Your School

Edit `scripts/import_teachers.py`:
1. Change `SCRAPE_URL` to the URL of your employee list
2. Adjust `ROLE_MAP` and `NON_TEACHING_TABS` as needed

### 5d) How Teachers Log In?

1. They go to **http://localhost:{{LOCAL_DEV_PORT}}** (or your URL)
2. Click **"Forgot password"**
3. Enter their email
4. They receive an email with a link to set a password

If you don't have an email server, you can set passwords manually via the admin panel.

---

## 6) Important Notes

| Feature | Local (SQLite) | Production (PostgreSQL/k3s) |
|---|---|---|
| Database | `data/sola.db` | PostgreSQL in k3s |
| Email | Does not work without SMTP | Arnes mail |
| Capacity | Fewer users | More users, HA |
| Security | Local access only | HTTPS via Cloudflare proxy |

---

## 7) Common Issues

| Issue | Solution |
|---|---|
| `Port already in use` | Change `APP_PORT={{LB_PORT}}` in `.env` |
| SQLite `database is locked` | Stop the app, delete `data/sola.db`, restart |
| Teachers not imported | Check with `--dry-run` first |
| Cannot see rooms | Check `PROSTORI` in `.env` |
