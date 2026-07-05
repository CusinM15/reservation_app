🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../aplikacija-rezervacije.md) | [🇬🇧 English](aplikacija-rezervacije.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# 📱 Reservation and Assessment Scheduling Application

## Purpose — what is this app actually for?

Before this application existed, everything at the school was done the old way:
teachers wandered the hallways, stopped outside the staff room and asked each other
"When are you writing your test?", "Have you already booked the computer room?",
"Are the tablets free?". There were sticky notes, whiteboard calendars, and general
confusion. Then someone forgot to enter an assessment into the gradebook, and
students ended up taking four tests in a single week — parents, the principal,
and the law were furious.

**The application solves two key problems:**

1. **Assessment network diagram** — teachers enter when they plan to hold a test,
   and the app automatically ensures there are no overlaps or policy violations
   (max 3 assessments per week, max 2 regular ones, no 3 consecutive days, etc.).
   Instead of sticky notes on a whiteboard — one click.
2. **Room reservations** — tablets, computer room, ship and
   home economics classroom. Every teacher can see in real time what's free and
   what's taken.

The application was developed for **OŠ Toneta Čufarja Jesenice** (a primary school
in Jesenice, Slovenia). It is deliberately kept as simple as possible — because the
author won't be at the school forever. When he eventually leaves, anyone reasonably
comfortable with a computer person should be able to maintain and use it. Nothing
complicated, nothing mysterious.

**Server:** The app runs on **Ubuntu Server** installed on old computers that are
too weak for Windows 11 but still perfectly capable for this job. Hardware that
would otherwise end up in the trash gets a new, useful life. Sustainable and
practical.

---

## Technologies — what powers this application?

Below are the technologies the application uses. For a computer professional these
are everyday words; for everyone else, each one comes with a short plain-language
explanation — every technology has its purpose, just like every teacher at school
has their subject.

### How the layers stack up

When you open the application in your browser, here's what happens:
1. Your browser sends a request across the network
2. **MetalLB** makes sure the request finds the right server at the right address
3. **k3s (Kubernetes)** decides which part of the app should handle the request
4. **FastAPI (Python)** processes the request — looks at what you want and prepares
   a response
5. If data is needed (assessments, users, reservations), **PostgreSQL** or **SQLite**
   provides it from the database

| Layer | Technology | What this means in plain language |
|-------|-----------|-----------------------------------|
| **Backend** | Python 3.12, FastAPI, Uvicorn | **Python** is a programming language — a set of instructions for the computer. **FastAPI** is a web framework that tells the app how to respond to clicks (like a receptionist directing calls to the right person). **Uvicorn** is the guard that waits for incoming requests and forwards them. |
| **Database** | PostgreSQL (production) / SQLite (development) | **PostgreSQL** is a digital archive — all data gets stored there: who reserved what, when an assessment is scheduled, passwords, etc. In production (when the app is actually live) we use PostgreSQL because it's reliable and powerful. During development (when the author is fixing or testing things), **SQLite** is sufficient — it's lighter and doesn't need a server. |
| **Frontend (visible part)** | Jinja2 templates, HTML/CSS/JS | When the app prepares a response, it wraps it in **HTML** (web page), styles it with **CSS** (colors, fonts, layout), and brings it to life with **JavaScript** (buttons, popups). **Jinja2** templates work like document templates — the app just fills in the data (teacher name, reservation list, etc.). |
| **Authentication (login)** | cookies with bcrypt | When you log in, the app stores a **cookie** in your browser — a small piece of data that identifies you on your next click. Passwords are encrypted with **bcrypt** (a mathematical grinder that turns your password into an irreversible code — even if someone steals the database, they can't read the passwords). |
| **Email** | SMTP via Arnes (mail.arnes.si) | When the app sends notifications (e.g., "Your assessment has been cancelled."), it uses the Arnes mail server — the same way you'd send an email from your school account. |
| **Orchestration (coordination)** | Kubernetes — specifically **k3s** | Imagine a container with your application living in a virtual world. **Kubernetes** (k3s) is the conductor that keeps all these containers working in sync: if one crashes, it starts a new one; if too many visitors show up, it distributes them across multiple containers. **k3s** is the lightweight version of Kubernetes, designed specifically for smaller systems like this one. |
| **Storage (disk)** | **Longhorn** | **Longhorn** is distributed block storage — in plain English: a smart virtual hard drive. Data is stored on **both** computers simultaneously, so if one crashes or shuts down, the other still has everything. No data loss, no panic. |
| **Network address** | **MetalLB** | **MetalLB** ensures the app has a **fixed network address**. Just like the school library is always in the same room, the app always has the same IP address — even if servers are swapped or relocated. Teachers always open the same address, and the app is there. |

---

## Application-wide variables — `.env`

The `.env` file stores all important configuration data. Think of it as the app's
**control panel** — if you want to change anything (e.g., add a new room, change
the email sending time, increase the number of tablets), you do it here. No need
to dig through code.

```bash
# App settings
APP_HOST=0.0.0.0
APP_PORT=port on which the app runs

DATABASE_URL=database connection URL (postgresql)

# Email settings
MAIL_USERNAME=short mail identifier (username)
MAIL_PASSWORD=*** mail password
MAIL_SERVER=mail.arnes.si
MAIL_PORT=587
MAIL_FROM=address from which the app sends messages
BACKUP_EMAIL=email that receives the daily database backup
STANJE_MAIL=email that receives the daily cluster status report

# App config
TABLICE_MAX=maximum number of tablets (currently 28)
SCHEDULE={"period number":"time interval of the period"}
RAZREDI=list of all classes at the school
PROSTORI=list of all reservable rooms

# Session timeout (teacher)
INACTIVITY_TIMEOUT_MINUTES=minutes of inactivity before teacher is auto-logged out
# Session timeout (admin/management)
INACTIVITY_TIMEOUT_ADMIN_MINUTES=minutes of inactivity before management/admin is auto-logged out
```

---

## Features — what can the app do?

### 📌 Room Reservations

The application supports reserving four types of rooms/items:

| Room | Description | Rule |
|------|-------------|------|
| **Tablets** | 28 portable tablets | Multiple teachers can share them in the same period — each gets their own slice |
| **Computer room** | Classroom with computers | **One** reservation per period — first come, first served |
| **Ship**  | Special tool for practical lessons | **One** reservation per period |
| **Home economics classroom** | Classroom for home economics | **One** reservation per period |

Reservations are displayed in a clear calendar view. Every teacher can see what's
free, what's taken, and who took it. No sticky notes, no asking around.

### 📝 Assessment Scheduling

Teachers enter a date and class, and the app **automatically checks all the rules**
— violations simply can't happen.

**Rules enforced by the system:**

- **Max 3 assessments per week** — regardless of type
- **Max 2 regular (non-retake) assessments per week** — the lav
- **No 3 consecutive days** — no class may take a test three days in a row
- **Automatic rule checking for grades 1–7** — because of mixed-group scheduling,
  this is considerably harder to do for grades 8 and 9

If a teacher tries to schedule an assessment that would violate the rules, the app
**won't allow it**. It shows a warning and explains why the date isn't available.
No more "I didn't know you already had a test."

### 🚫 Blocked Dates

Management or admin can mark any days as **blocked** — these are days when
assessments are **not allowed** (sports day, field trip, cultural day, etc.).

When management blocks a period:

1. **The system automatically deletes** all existing assessments that fall within
   that period
2. **It sends email notifications** to all affected teachers — clearly stating
   which assessment was cancelled
3. The period shows up in the calendar as **purple** (blocked) for those classes
   that are affected at that time

No more need for the principal to send memos asking teachers to manually delete
dates. The app does it all.

### ⚙️ Admin Panel

**Admin only.** This is where users are managed:

- **Adding** new users (new teachers, new management)
- **Editing** existing users (name, role, email change)
- **Deleting** users (when they leave the school)
- **Deactivation** (temporarily disable access without deleting data)

The admin panel is straightforward and transparent — no hidden menus or complicated
settings.

---

## User Roles — who can do what?

The school has three types of users. Each has their own permissions — similar to
how students, teachers, and the principal all have different keys to different
cabinets.

| Function | Teacher | Management | Admin |
|----------|:-------:|:-----------:|:-----:|
| **Room reservations** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Delete own reservation** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Delete others' reservations** | ❌ No | ✅ Yes | ✅ Yes |
| **Schedule assessment** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Manage blocked dates** | ❌ No | ✅ Yes | ✅ Yes |
| **Serial reservatopm** | ❌ No | ✅ Yes | ✅ Yes |
| **Admin panel (users)** | ❌ No | ❌ No | ✅ Yes |

**Teacher** — can reserve rooms, schedule assessments, and delete only their own
entries. Cannot interfere with others' work.

**Management** (principal, deputy) — can do everything a teacher can, **plus**
delete others' reservations (when something urgently needs rescheduling), mark
blocked dates, and perform serial (batch) reservations. The only things they
cannot do: manage users or access the Audit log (history of all events in the app).

**Admin** — the highest access level. Can do absolutely everything, including
adding and deleting users. Typically one or two people at the school (the IT
coordinator, the system administrator).

---

## Why is everything so simple?

The author of the application is aware that he won't be at the school forever.
That's why every development decision followed three principles:

1. **Simplicity** — if something can be done in a simple way, there's no reason to
   make it complicated
2. **Maintainability** — the application must work even when the author is no
   longer around
3. **Transparency** — anyone who can open a `.env` file and read documentation
   should understand how things work

That's why the technologies were chosen thoughtfully and the documentation is
written in as accessible a language as possible. If something isn't clear, ask
the administrator — and if even they don't know, at least you'll have a clear
idea of where to look.

---

> **Author:** Matej Čušin  
