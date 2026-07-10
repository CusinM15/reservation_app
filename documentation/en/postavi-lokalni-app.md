🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../postavi-lokalni-app.md) | [🇬🇧 English](postavi-lokalni-app.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# SET UP LOCAL APP — OSTC App School System


This document is written for a **clean local installation** — running the application on **a single computer**. No Kubernetes cluster, no PostgreSQL server. Just you and your computer.

> 🎯 **When do I use this?** When you want to show the application to colleagues, test it on your laptop, or install it at a school that doesn't have its own Kubernetes environment.

---

## Table of Contents

1. [What does "local installation" even mean?](#1-what-does-local-installation-even-mean)
2. [What you need — checklist before you start](#2-what-you-need--checklist-before-you-start)
3. [What is Docker? (for first-timers)](#3-what-is-docker-for-first-timers)
4. [Installation via Docker](#4-installation-via-docker)
5. [Installation without Docker — manual (uvicorn) ](#5-installation-without-docker--manual-uvicorn--recommended)
6. [First run — what happens behind the scenes?](#6-first-run--what-happens-behind-the-scenes)
7. [Importing teachers from the web](#7-importing-teachers-from-the-web)
8. [Important differences: Local vs. Production](#8-important-differences-local-vs-production)
8.5. [Access from other devices — mDNS setup](#85-access-from-other-devices--mdns-setup)
9. [Common issues and how to solve them](#9-common-issues-and-how-to-solve-them)

---

## 1) What does "local installation" even mean?

Imagine you have a puzzle box on a shelf. **Local installation** means you open that box and assemble it **right on your own desk** — you don't send it to a factory, you don't use industrial machines. Everything you need is within reach.

In our case:
- The **application** (a website with a calendar and reservations) runs on **your computer**.
- The **database** (where teachers and reservations are stored) is **a file on your disk**.
- **Other users** can only access it if they're on the same network and know your IP address.

> 📌 **Bottom line:** Everything is in one place. Nothing flies to the cloud. One computer, one application, one database.

---

## 2) What you need — checklist before you start

Before installing anything, check if you have the following:

| Tool                     | Why you need it                                                                                                | Where to get it                                                      |
| ------------------------ | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| **Python 3.11 or newer** | The application is written in Python — this is the "engine" that runs the code. No engine, no application.     | [python.org](https://python.org) — download and install.             |
| **Docker**               | Docker packages the app into a "container" with everything it needs. Like a ready-made meal — just heat it up. | [docker.com](https://docker.com)                                     |
| **Git**                  | A tool for downloading code from an online repository (GitHub). Like Dropbox for source code.                  | `sudo apt install git` (Linux) or [git-scm.com](https://git-scm.com) |
| **Browser**              | The application is web-based — you access it through a browser (Chrome, Firefox, Edge…).                       | You probably already have one.                                       |

> **💡 Important: choose your path**
>
> **Git** in the table above is optional — you can also download the code as a [ZIP archive](https://github.com/os-tc-jesenice/reservation_app/archive/refs/heads/main.zip) and extract it manually. However, **I recommend Git** because it makes updates easier (`git pull`). Without Git, you'll need to download the full ZIP and replace files every time.
>
> **Two paths, two tools:**
> - **Path 1 — uvicorn** (recommended): you need **Python**, Docker is **not needed**.
> - **Path 2 — Docker**: you need **Docker**, Python is **not required** (it's installed inside the container).
>
> Choose one — you don't need to install both.

### How do I check if Python is installed?

Open a **terminal** (Command Prompt on Windows, Terminal on Mac/Linux) and run:

```bash
python3 --version
```

If you see something like `Python 3.11.5` — you're ready. If you get an error, you need to install it.

### How do I check if I have Docker?

```bash
docker --version
```

If you see `Docker version 24.x.x` — great. If not, skip to [section 5](#5-installation-without-docker--manual-uvicorn--recommended) (installation without Docker) or install Docker.

### Installing on Windows — WSL (Windows Subsystem for Linux)

If you're using **Windows**, the easiest way is to run everything inside **WSL** (Windows Subsystem for Linux). It's like a small Linux inside your Windows.

```powershell
# 1. Open PowerShell as Administrator and run:
wsl --install

# 2. Once installed, start WSL:
wsl

# 3. Inside WSL (linux terminal), install Git and Docker:
sudo apt update && sudo apt install -y git docker.io

# 4. Follow the instructions below — all commands are the same as on Linux
```

> 💡 **WSL + Docker:** If you want to use Docker via WSL, install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) and enable the WSL2 backend (Settings → Resources → WSL Integration). Then you can run Docker commands from the WSL terminal.
>
> 💡 **WSL + uvicorn:** You can install Python directly inside WSL (`sudo apt install python3 python3-pip`) and follow the Linux instructions. No need to install anything on the Windows side.

---

## 3) What is Docker? (for first-timers)

> **Docker is like food packaging:** imagine you're going on a picnic. Instead of bringing separate flour, eggs, butter, sugar, a baking tray, and a stove, you simply take a **ready-baked pie** in a container. At home, you just warm it up and it's ready.

**Docker does the same thing for software.** It packs into a "container":
- Python (the interpreter)
- All libraries (additional tools Python needs)
- Configuration (settings)
- The application itself (code)

When you run it, Docker takes this container and places it in its own "micro-computer" — it runs completely independently, regardless of what's installed on your actual computer.

### 🔥 Why Docker?

1. **You don't need to install anything on your computer.** No Python libraries, no tools — everything is already in the container.
2. **It works the same everywhere.** Whether you have Windows, Mac, or Linux — Docker ensures the application sees exactly the same environment.
3. **If you mess up, just delete it.** `docker rm sola-app` and start over — no traces remain on your computer.
4. **Isolation.** The application can't "wipe" your important files — it lives in its own world inside Docker.

---

## 4) Installation via Docker

### 4a) Preparation — download the code and set up configuration

> 🐳 **Docker without sudo:** If you get a "permission denied" error when running `docker` commands, add your user to the docker group: `sudo usermod -aG docker $USER` and log back in.

> 🪟 **On Windows:** before you start, run WSL (`wsl` in cmd/PowerShell) and continue inside the WSL terminal. All commands below (git clone, cp, docker) work the same as on Linux.

First, you need to download the application code from the internet to your computer. You do this with Git:

```bash
# 1. Clone the repository (meaning: download the entire folder with the code)
git clone https://github.com/sola-app.git
cd sola-app
```

> 💡 **Tip:** `cd sola-app` means "go into the sola-app folder." If you're not sure which folder you're in, run `pwd` (Linux/Mac) or `cd` (Windows) — it shows the path.

Now we need to create a configuration file `.env`. This is like a "control panel" — it tells the application which port to listen on, what the database is, etc.

```bash
# Take the example and rename it to the real configuration file
cp .env.example .env
```

> 🧠 **Explanation:** `.env.example` is a template — a sample configuration. The `cp` (copy) command copies it to `.env`, which is the actual file the application actually reads. `.env.example` stays untouched as a backup.

`.env` should contain the following (if empty, edit it with Notepad or any editor):

```env
APP_HOST=0.0.0.0
APP_PORT=8001
BASE_URL=http://localhost:8001
DATABASE_URL=sqlite:///./data/sola.db
TABLICE_MAX=28
SCHEDULE={"0":"07:30-08:15","1":"08:20-09:05","2":"09:15-10:00","3":"10:20-11:05","4":"11:10-11:55","5":"12:00-12:45","6":"12:50-13:35","7":"14:00-14:45"}
RAZREDI=1.a,1.b,2.a,2.b,3.a,3.b,4.a,4.b,5.a,5.b,6.a,6.b,7.a,7.b,8.a,8.b,9.a
PROSTORI=tablice,racunalnica,ladja
```

> 📖 **What do these settings mean?**
> - `APP_HOST=0.0.0.0` — "listen on all network interfaces" (so you can access from other devices on the network).
> - `APP_PORT=8001` — the port the application will be available on (like a TV channel — on channel 8001).
> - `BASE_URL=http://localhost:8001` — the address where the application is visible (localhost = this computer).
> - `DATABASE_URL=sqlite:///./data/sola.db` — **where the database is**. SQLite is a simple database in a single file.
> - `TABLICE_MAX=28` — total number of tablets.
> - `SCHEDULE=...` — timetable (7:30-8:15 is period 0, etc.).
> - `RAZREDI=...` — list of all classes at the school.
> - `PROSTORI=...` — list of rooms that can be reserved (including tablets).

### 4b) Build the Docker image and run

A **Docker image** is like a "recipe" — instructions on how to assemble the container. A **Docker container** is what actually runs.

```bash
# Build the image (this takes a few minutes on the first run)
docker build -t sola-app .
```

> ⏳ **The first build takes longer** because Docker downloads Python, installs all libraries… Next time it'll be instant.

Once the image is built, run it:

```bash
docker run -d --name sola-app -p 8001:8001 \
  -v $(pwd)/data:/app/data \
  sola-app
```

> 🧠 **Parameter explanation:**
> - `-d` — **detached mode** (runs in the background, doesn't occupy the terminal).
> - `--name sola-app` — container name (so you can stop it by name later).
> - `-p 8001:8001` — **port mapping**. "If someone calls port 8001 on your computer, forward the call to the container on the same port." External:internal port.
> - `-v $(pwd)/data:/app/data` — **volume mount**. This is crucial! Your `./data` folder on the computer is linked to the `/app/data` folder in the container. **If you delete the container, the database stays on your disk.**
> - `sola-app` — the name of the image we built above.

✅ **The application is now at:** [**http://localhost:8001**](http://localhost:8001)

Default access: username `admin`, password `admin123` (**change the password immediately!**).

### 4c) Stopping and removing

```bash
docker stop sola-app    # stop the container
docker rm sola-app      # remove the container (doesn't delete the image or data)
```

> 💡 If you also want to delete the image (to save space): `docker rmi sola-app`

### 4d) Restarting (when the image is already built)

```bash
docker start sola-app
```

---

## 5) Installation without Docker — manual (uvicorn) 

If you don't have Docker or don't want to install it (or have issues with it, e.g. tmpfs overload during build), you can run the application directly with Python. This is like cooking a meal from ingredients — a bit more work, but more predictable on older or more constrained computers.

### 5a) Environment setup

> 🪟 **On Windows:** I recommend using WSL. Run `wsl` in cmd/PowerShell and follow the instructions below — all commands work the same as on Linux. If you want to run directly on Windows, use PowerShell/CMD with the appropriate Windows commands (e.g. `venv\Scripts\activate` instead of `source venv/bin/activate`).

```bash
# 1. Download the code
git clone https://github.com/sola-app.git
cd sola-app

# 2. Create a virtual environment
python3 -m venv venv
```


Activate the virtual environment:

```bash
# Linux / Mac:
source venv/bin/activate

# Windows:
# venv\Scripts\activate
```

When activated, you'll see `(venv)` at the beginning of the line in your terminal — that's the sign you're working inside your "separate space."

```bash
# 3. Install dependencies (all Python libraries the application needs)
pip install -r requirements.txt
```

> 📦 `requirements.txt` is a list of all libraries the application needs. `pip` reads them and installs them one by one, like going through a shopping list.

```bash
# 4. Create the configuration file
cp .env.example .env
# Edit .env — see the example in section 4a above
```

### 5b) Run the application

```bash
# First create the data folder (the database will be stored here)
mkdir -p data

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

> 🧠 **What do these parameters mean?**
> - `app.main:app` — **"In the file `app/main.py`, find the `app` object."** Uvicorn needs to know where the entry point to the application is.
> - `--host 0.0.0.0` — listen on all network interfaces.
> - `--port 8001` — port (if it's taken, change to 8002 or something else).
> - **`--reload`** — this is **gold for development**. It means the application **automatically restarts every time you change the code**. If you edit something in the `app/` folder, Uvicorn detects it and reloads the application. Like having an automatic "save and refresh" function. **In production, --reload is not used** — there you want it to run stably without restarts.

✅ **The application is now at:** [**http://localhost:8001**](http://localhost:8001)

Default access: `admin` / `admin123`

### 5c) Stop the application

Press **`Ctrl+C`** in the terminal. The application will shut down gracefully.

---

## 6) After starting — verify the app is working

Once you start the app (via Docker or uvicorn), open your browser and go to:

```
http://localhost:8001
```

### ✅ Checklist — what you should see:

1. **Login page** — asks for username and password. Default: `admin` / `admin123`
2. **Reservations & Assessments tabs** — after login, you should see both tabs.
3. **Weekly schedule (Reservations tab)** — a weekly table with rooms and hours should appear. Even if there are no reservations, the table should render (empty).
4. **Calendar (Assessments tab)** — a monthly calendar should appear. Even if there are no assessments, the calendar must be visible.
5. **Room tabs** — under Reservations, you should see tabs for each room (tablice, racunalnica, ladja...).
6. **/health endpoint** — open `http://localhost:8001/health` in your browser. You should see `{"status": "ok"}`.

> ⚠️ **If something is missing:** check the terminal where you started the app — the error is there. Most common causes:
> - `--workers 2` with SQLite (database gets locked) — use `--workers 1`
> - Missing `.env` file — the app uses default values
> - Port 8001 is already in use — change it in `.env`

---

## 7) First run — what happens behind the scenes?

When you first run the application (either via Docker or manually), several things happen **automatically**:

1. **An SQLite database is created.** A file called `sola.db` appears in the `data/` folder. That's the entire database — a single file on your disk.
   > 🧠 **What is SQLite?** Picture an Excel spreadsheet saved in a single file. Only instead of Excel, you use program code to read and write. **SQLite is a simple database — like an Excel spreadsheet stored in a single file.** You don't need to install a special database server (like PostgreSQL or MySQL) — everything is in that one file.

2. **An initial admin user is added.** Username: `admin`, password: `admin123` (make sure to change it immediately on first login!).

3. **Everything is ready for use.** The database is empty though — no reservations, no assessments, no teachers. It's like a fresh notebook: all pages are blank, waiting to be filled.

---

## 7) Importing teachers from the web

If your school has a **publicly posted employee list** on its website, you can import teachers automatically. The application will go to the website, read the data, and enter it into the database.

### 7a) Install additional tools

If you're using Docker, you need to connect into the container:
```bash
docker exec -it sola-app bash
```

If you're using a local installation, just activate the virtual environment and run:

```bash
pip install requests beautifulsoup4 lxml
```

> 📖 **What are these libraries?**
> - `requests` — Python's way to "call" a website and read its content.
> - `beautifulsoup4` — a tool for **parsing HTML** (web pages). Like having an orange peeler — you peel away the HTML and take only the data you need.
> - `lxml` — a fast HTML/XML reader (speeds up BeautifulSoup).

### 7b) Run the import

```bash
# If the application is running on localhost:8001:
python3 scripts/import_teachers.py --base-url http://localhost:8001
```

> 💡 **Try with --dry-run first!** `--dry-run` means "just look at what would be imported, don't change the database." Like browsing a store before you actually pay.

```bash
# Just preview who would be imported (without changing the database):
python3 scripts/import_teachers.py --base-url http://localhost:8001 --dry-run
```

### 7c) Adapt for your school

Edit the file `scripts/import_teachers.py` in Notepad or your editor:

1. **Change `SCRAPE_URL`** — this is the address of your school's webpage with the employee list.
2. **Adjust `ROLE_MAP`** if needed — title mapping.
3. **Adjust `NON_TEACHING_TABS`** if needed — tabs on the website that aren't teachers (e.g. "Administration").

### 7d) How do teachers access the application?

1. They go to **http://localhost:8001**(or your URL, if accessing from another computer).
2. They click **"Forgot password"**.
3. They enter their email address.
4. They receive an email with a link to set their password.

> ⚠️ **If you don't have an email server (SMTP):** The "Forgot password" feature won't work, because the application can't send emails. In that case, you can set passwords **manually via the admin panel** — log in as `admin` and edit each user individually.

---

## 8) Important differences: Local vs. Production

### SQLite vs. PostgreSQL

| Characteristic             | Local (SQLite)                                                             | Production (PostgreSQL on k3s)                                                |
| -------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **Where is the database?** | A single file: `data/sola.db`                                              | PostgreSQL server in a Kubernetes cluster                                     |
| **How does it work?**      | Simple — the file opens, writes, closes. Like a notepad.                   | Professional server — supports multiple concurrent users, better performance. |
| **Email**                  | ❌ Doesn't work without an SMTP server. "Forgot password" won't send email. | ✅ Arnes mail or other SMTP — password emails work.                            |
| **Number of users**        | Fewer users                                                                | More users, high availability (HA), load distribution.                        |
| **Security**               | Local or intranet access only. No HTTPS, no Cloudflare protection.         | HTTPS via Cloudflare proxy, protected from external attacks.                  |

> 🧠 **Why SQLite for local?** Because you don't need a server. The database is a file — copy it to a USB stick and take it to another computer. For testing and demonstration, it's perfectly sufficient.
>
> 🧠 **Why PostgreSQL in production?** Because it handles more concurrent queries, has better security, supports replication (multiple copies of the database for reliability), and is an industry standard. When 30 teachers at a school open reservations simultaneously, SQLite starts to lag.

### Key differences summary

| Characteristic | Local (SQLite)        | Production (PostgreSQL/k3s)  |
| -------------- | --------------------- | ---------------------------- |
| Database       | `data/sola.db`        | PostgreSQL in k3s            |
| Email          | Doesn't work without SMTP | Arnes mail               |
| Capacity       | Fewer users           | More users, HA               |
| Security       | Local access only     | HTTPS via Cloudflare proxy   |

---

## 8.5) Access from other devices — mDNS setup

So far you've been opening the application at `http://localhost:8001` — this only works on the computer where the application is running. But what if you want to open the application on a phone, tablet, or another computer on the same network?

You could type the computer's IP address into the browser (e.g. `http://192.168.1.42:8001`), but that address can change every time the computer restarts. A more elegant solution is to use **mDNS** (Multicast DNS).

### What is mDNS?

mDNS is a protocol that lets you access a computer **by name instead of by IP address** — similar to calling a friend by their name, not by their ID number.

On Linux, mDNS is handled by the `avahi-daemon` service. Once installed, your computer becomes reachable at `http://<computer-name>.local:8001` — from any device on the same network (in Arnes network, there is more rules, so the app is no accessible to everyone on network).

### Installation

```bash
# Install avahi-daemon
sudo apt install avahi-daemon

# Start it and enable it to run at every system boot
sudo systemctl enable --now avahi-daemon
```

### How do you find your computer's name?

```bash
hostname
```

If the command returns `school-pc`, the application is reachable at:


✅ **http://school-pc.local:8001**

To chnge hostname it is very simple 
```bash
sudo vim /etc/hostmane
```
You change the text (in vim presss `Esc`+ `i`to start tiping and then `Esc`+ `ZZ`/`:wq`), once it is saved reboot computer and then the name shoud be changed
### Access from other devices

- **Linux:** install `avahi-daemon` (same as above)
- **Windows:** mDNS is built into Windows 10 and newer — works without any special installation
- **Mac:** supports mDNS natively (Apple calls it Bonjour)
- **Android/iOS:** support `.local` addresses natively

> 💡 **Practical tip:** If the school computer is named `sola-pc`, simply tell teachers: "Open your browser and go to `sola-pc.local:8001`." It works even if the IP address changes overnight.

---

## 9) Common issues and how to solve them

| ❌ Issue                                           | ✅ Solution                                                                                                                                                                                                                         |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`Port already in use`**                         | Another application is already using port 8001. Change `APP_PORT=8002` in the `.env` file and try again. With Docker: add a different port mapping (`-p 8002:8001`).                                                               |
| **SQLite `database is locked`**                   | The application stopped unexpectedly while writing to the database. **Solution:** Stop the app, delete the `data/sola.db` file, and restart — the application will create a new database. **Warning:** This deletes all your data! |
| **Teachers not imported**                         | The employee list on the website might have a different structure. First run **`--dry-run`** to see what the script finds. Then adjust `SCRAPE_URL` in `scripts/import_teachers.py`.                                               |
| **Can't see rooms (tablets, computer lab, ship)** | Check `PROSTORI` in the `.env` file. If any are missing, add them separated by commas: `PROSTORI=tables,racunalnica,ladja,gym`. Then restart the application.                                                                      |
| **Can't open the application in the browser**     | Check: (1) Is the application actually running? (look at the terminal or `docker ps`). (2) Did you use the right address? Usually `http://localhost:8001`. (3) Did you change the port? Use the one you set in `.env`.             |
| **Docker: `permission denied`**                   | On Linux you need administrator privileges. Try `sudo docker ...` or add your user to the `docker` group: `sudo usermod -aG docker $USER` (log out and back in afterwards).                                                        |
| **`pip install` throws an error**                 | Maybe a system tool is missing (e.g. Python dev headers). On Linux, try: `sudo apt install python3-dev build-essential`. Then repeat `pip install -r requirements.txt`.                                                            |
| **Calendar shows "Loading..." indefinitely**        | The API call failed. Most common cause: `--workers 2` with SQLite, or the app never started (check terminal for errors). Fix: change to `--workers 1` and restart.                                                                  |
| **Docker build fails with an error**                 | Likely tmpfs overload — `/tmp` filled up during build. Try uvicorn instead of Docker, or increase tmpfs size.                                                                                                                      |

---

## Final tips

✅ **We recommend installation without Docker (uvicorn).** Docker is the standard choice for production, but on older or more constrained computers (especially those with a small tmpfs partition) it can cause issues — `/tmp` fills up during build and the build fails. Direct installation with uvicorn doesn't have this problem and is more predictable.

> 🧠 **The tmpfs issue (tmpfs overload):** When Docker builds an image, it uses `/tmp` for temporary files — pip downloads, WeasyPrint fonts, compilations. If your system has a small tmpfs partition (less than 2 GB), this causes a "No space left on device" error. Direct installation with uvicorn avoids this because it uses regular disk space.

✅ **If you have Docker and enough tmpfs space:** You can use Docker, instructions are in section 4. For most people though, uvicorn is the simpler and more reliable path.

✅ **Don't use `--reload` in production.** It's great for development (automatic restart on changes), but in production it causes unnecessary restarts and you could lose data.

✅ **Regularly back up `data/sola.db`** (or the entire `data/` folder). This is your database — if you lose it, you lose all your data. Copy the file to a USB stick or to the cloud.

✅ **Change the admin password immediately.** The default password `admin123` is known to everyone who reads this documentation.

✅ **If something breaks:** delete everything and start over. With Docker: `docker stop sola-app && docker rm sola-app && docker rmi sola-app`. Then repeat the steps from [section 4](#4-installation-via-docker). With a local installation: delete the `venv/` folder, delete `data/sola.db`, and start from [step 5a](#5a-environment-setup).

---

> **Author:** Matej Čušin  
