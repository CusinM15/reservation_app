# Šolski App - Task Brief

## Critical Instructions
- If you are unsure about any requirement, STOP and ask instead of guessing.
- Do NOT invent APIs, endpoints, or authentication mechanisms.
- Do NOT simulate or fake integrations.
- Do NOT mention or reference NextCloud anywhere in the code.

## Context
- Standalone FastAPI app, completely independent
- Has its own login system and its own database
- Access via: http://ostonecufar.local (school) — do NOT use or expose raw IPs
- App runs as a Docker container with its own docker-compose.yml
- New dedicated Git repository (do not mix with any other project)

## Code Modification Rules
- Only modify files that are necessary for the current phase
- Do NOT refactor unrelated code
- Do NOT rename existing files unless absolutely required
- Keep changes minimal and focused

---

## Configuration & Environment

All configuration lives in ONE place: `app/config.py` (loads from `.env`).
No value may be hardcoded anywhere else — always import from `settings`.

### .env variables:

```env
# App
APP_HOST=0.0.0.0
APP_PORT=8001
SECRET_KEY=change-this-to-a-random-secret

# Database
DB_PATH=./data/sola.db

# Tablice capacity
TABLICE_MAX=28

# School schedule (JSON string, hour index -> start-end)
SCHEDULE={"0":"07:30-08:15","1":"08:20-09:05","2":"09:15-10:00","3":"10:20-11:05","4":"11:10-11:55","5":"12:00-12:45","6":"12:50-13:35","7":"14:00-14:45"}

# Classes (comma-separated)
RAZREDI=1.a,1.b,1.c,1.č,2.a,2.b,2.c,2.č,3.a,3.b,3.c,3.č,4.a,4.b,4.c,4.č,5.a,5.b,5.c,5.č,6.a,6.b,6.c,6.č,7.a,7.b,7.c,8.a,8.b,8.c,8.č,8.1,8.2,8.3,8.4,8.5,9.a,9.b,9.c,9.1,9.2,9.3,9.4,9.5

# Spaces available for reservation
PROSTORI=tablice,racunalnica,ladja
```

### config.py pattern:
```python
import os, json
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", 8001))
    SECRET_KEY = os.getenv("SECRET_KEY")
    DB_PATH = os.getenv("DB_PATH", "./data/sola.db")
    TABLICE_MAX = int(os.getenv("TABLICE_MAX", 28))
    SCHEDULE = json.loads(os.getenv("SCHEDULE", "{}"))
    RAZREDI = os.getenv("RAZREDI", "").split(",")
    PROSTORI = os.getenv("PROSTORI", "").split(",")

settings = Settings()
```

Frontend (HTML/JS) must fetch RAZREDI, PROSTORI and SCHEDULE from API endpoints — never hardcode them in templates.

---

## Authentication

- Custom login system (no external auth)
- Passwords hashed with bcrypt (passlib)
- Session via signed cookie (itsdangerous or starlette SessionMiddleware)
- If not authenticated → redirect to /login
- Two roles: `admin`, `teacher`
- Admin can create/edit/deactivate teacher accounts

### Bulk import (Word documents):
- Script: `scripts/import_users.py`
- Accepts a folder path as argument
- Reads .docx files, extracts: username (AAI login), optionally password
- If password missing in document → generates random password, prints to stdout
- Creates user in DB with hashed password
- Idempotent: if user already exists → skip and log warning
- Implement in Phase 4

---

## Features

### 1. Rezervacije (Reservations)

Teachers reserve school spaces for a specific date + school hour.

**Spaces:**
- `tablice` — tablets (capacity: TABLICE_MAX from .env)
- `racunalnica` — computer room (1 reservation per hour max)
- `ladja` — school space (1 reservation per hour max)

**Tablice rules:**
- Multiple reservations per hour allowed
- Sum of all reserved tablets in one hour must not exceed TABLICE_MAX
- Teacher specifies how many tablets they need (qty field)

**Računalnica / Ladja rules:**
- Max 1 reservation per hour per space
- If slot taken → return Slovenian error

**Reservation fields:**
- date, hour (0–7), prostor, razred, teacher_id, qty (tablice only)

### 2. Ocenjevanje (Assessment Scheduling)

Teachers schedule assessment dates per class.

**Business Rules (STRICT):**
- Max 2 assessments per class per week (Mon–Fri)
- The 2 assessments in the same week MUST NOT be on the same day
- Exception — "ponavljanje" (revision assessment):
  - Allows up to 3 assessments in one week
  - Each on a different day
  - Must NOT be on 3 consecutive days in a row
- Ponavljanje shown in different color in calendar UI

---

## Language
- UI: Slovenian (labels, buttons, errors, messages)
- Code: English (variables, functions, comments, docstrings)

---

## Technical Requirements
- FastAPI backend
- SQLite + SQLAlchemy ORM
- Frontend: HTML/JS/CSS served by FastAPI (no React, no separate frontend)
- Reverse-proxy friendly (X-Forwarded-For, X-Forwarded-Proto)
- Docker Compose with .env support

---

## Deployment
- Must work on TWO machines:
  1. School server (ostonecufar.local) — production
  2. Developer home machine — development
- All hosts/ports/paths from .env — never hardcoded
- Future: reverse proxy (Caddy or Nginx), possibly public domain
- No hardcoded IPs, hostnames, or machine-specific paths anywhere

---

## Debugging Rules
1. Identify root cause
2. Propose minimal fix
3. Do NOT rewrite large parts of the system
4. Preserve existing functionality

---

## Commit Strategy
- Commit after every meaningful working change
- Clear English commit messages
- Never commit .env
- Never break existing functionality

---

## Development Phases — WAIT FOR APPROVAL BETWEEN EACH PHASE

A phase is complete ONLY if:
- Code runs without errors
- Feature works as specified
- No existing functionality is broken

---

### Phase 1 — Project Structure + DB + Skeleton

Before implementing:
- Outline what you will build
- List all files you will create
- Then implement

What to build:
- Project folder structure
- config.py loading all values from .env
- SQLite DB + SQLAlchemy models: users, reservations, assessments
- Basic FastAPI app with empty routes
- docker-compose.yml + .env.example
- /health endpoint

**Output exactly:**
```
=== PHASE 1 COMPLETE - TESTING INSTRUCTIONS ===
Files created:
- [list]

Tables created:
- [list]

To start: [exact command]
App at: http://localhost:[port]
Health check: curl http://localhost:[port]/health

Awaiting confirmation for Phase 2.
=== END ===
```

---

### Phase 2 — Rezervacije Business Logic

Before implementing:
- Outline what you will build
- List files you will create or modify
- Then implement

What to build:
- POST /api/rezervacije
- GET /api/rezervacije?date=&prostor=
- DELETE /api/rezervacije/{id}
- Tablice capacity check
- Računalnica/ladja 1-per-hour check
- All validation errors in Slovenian

**Output exactly:**
```
=== PHASE 2 COMPLETE - TESTING INSTRUCTIONS ===
# Reserve tablice (15 tablets):
[exact curl]

# Exceed capacity (should fail):
[exact curl]

# Reserve računalnica:
[exact curl]

# Double-book računalnica (should fail):
[exact curl]

Awaiting confirmation for Phase 3.
=== END ===
```

---

### Phase 3 — Ocenjevanje Business Logic

Before implementing:
- Outline what you will build
- List files you will create or modify
- Then implement

What to build:
- POST /api/ocenjevanja
- GET /api/ocenjevanja?razred=&month=
- DELETE /api/ocenjevanja/{id}
- All strict business rules enforced
- Ponavljanje flag supported

**Output exactly:**
```
=== PHASE 3 COMPLETE - TESTING INSTRUCTIONS ===
# Add normal assessment:
[exact curl]

# Same day (should fail):
[exact curl]

# Add ponavljanje:
[exact curl]

# 4th in one week (should fail):
[exact curl]

Awaiting confirmation for Phase 4.
=== END ===
```

---

### Phase 4 — Login System + Bulk Import Script

Before implementing:
- Outline what you will build
- List files you will create or modify
- Then implement

What to build:
- /login page (Slovenian UI)
- bcrypt hashing, signed session cookie
- Middleware: unauthenticated → redirect to /login
- /logout
- /admin/users — admin creates/deactivates teachers
- scripts/import_users.py — reads folder of .docx files, creates users in DB

**Output exactly:**
```
=== PHASE 4 COMPLETE - TESTING INSTRUCTIONS ===
Test 1 - No session → redirect to /login:
[instruction]

Test 2 - Login with valid credentials:
[instruction]

Test 3 - Bulk import:
python scripts/import_users.py ./test_docs/
Expected: [describe output]

Awaiting confirmation for Phase 5.
=== END ===
```

---

### Phase 5 — UI (Rezervacije + Ocenjevanje)

Before implementing:
- Outline what you will build
- List files you will create or modify
- Then implement

What to build:
- Rezervacije: weekly view per prostor, shows available/taken slots, tablice shows remaining capacity
- Ocenjevanje: monthly calendar per razred, ponavljanje in different color
- All UI in Slovenian
- RAZREDI, PROSTORI, SCHEDULE loaded from API — never hardcoded in JS/HTML
- Basic mobile-friendly layout

**Output exactly:**
```
=== PHASE 5 COMPLETE - TESTING INSTRUCTIONS ===
Open: http://localhost:[port]/

What you should see:
- [describe rezervacije view]
- [describe ocenjevanje view]
- Ponavljanje shown in [color]

Awaiting confirmation for Phase 6.
=== END ===
```

---

### Phase 6 — Bugfixes & Polish

- Only after all phases confirmed
- Fix reported issues
- Slovenian error messages throughout
- Minor UI polish
