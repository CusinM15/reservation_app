🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../aplikacija-rezervacije.md) | [🇬🇧 English](aplikacija-rezervacije.md)

---

# 📱 Reservation and Assessment Scheduling Application

## Purpose

The application was developed for OŠ Toneta Čufarja Jesenice. The main purpose is that the school needs a network diagram for scheduling assessments. In addition, it also enables room reservations (computer room, ship, tablets, home economics classroom).

Since the author does not plan to stay at the school for long, the application is made as simple as possible — even for people who are not computer-savvy.

**Server:** Ubuntu Server on old computers (too weak for Windows 11), giving them new useful value.

---

## Technologies

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Database | PostgreSQL (production) / SQLite (development) |
| Frontend | Jinja2 templates, HTML/CSS/JS |
| Authentication | cookie-based session with bcrypt hash |
| Email | SMTP via Arnes (mail.arnes.si) |
| Orchestration | Kubernetes (k3s) |
| Storage | Longhorn (distributed block storage) |
| LoadBalancer | MetalLB |

---

## Application-wide variables — .env

```bash
# App settings
APP_HOST=0.0.0.0
APP_PORT=port on which the app runs

DATABASE_URL=postgresql url

# Email settings
MAIL_USERNAME=short mail name
MAIL_PASSWORD=*** mail password
MAIL_SERVER=mail.arnes.si
MAIL_PORT=587
MAIL_FROM=mail from which the application sends messages
BACKUP_EMAIL=mail that receives the daily database backup
STANJE_MAIL=mail that receives the daily cluster status report

# App config
TABLICE_MAX=total number of tablets
SCHEDULE={"period number":"time interval of the period"}
RAZREDI=list of classes
PROSTORI=list of rooms

# Session timeout (teacher)
INACTIVITY_TIMEOUT_MINUTES=after how long a teacher is logged out due to inactivity
# Session timeout (admin/management)
INACTIVITY_TIMEOUT_ADMIN_MINUTES=after how long management/admin is logged out
```

---

## Features

### Room Reservations

- **Tablets** — 28 units, can be shared by multiple teachers in the same period
- **Computer room** — one reservation per period
- **Ship** (washing boat) — one reservation per period
- **Home economics classroom** — one reservation per period

### Assessments

Scheduling written assessments with limits:
- Max 3 assessments per week
- Max 2 regular (non-retake) per week
- 3 consecutive days not allowed
- Automatic rule checking for grades 1–7

### Blocked Dates

Management/admin marks days as blocked (sports day, excursion...). The system:
- Automatically deletes existing assessments in that period
- Sends email notifications to affected teachers

### Admin Panel

User management — adding, editing, deleting, deactivation.

---

## User Roles

| Function | Teacher | Management | Admin |
|---|---|---|---|
| Room reservations | ✅ | ✅ | ✅ |
| Delete own reservation | ✅ | ✅ | ✅ |
| Delete others' reservations | ❌ | ✅ | ✅ |
| Schedule assessment | ✅ | ✅ | ✅ |
| Manage blocked dates | ❌ | ✅ | ✅ |
| Admin panel (users) | ❌ | ❌ | ✅ |
