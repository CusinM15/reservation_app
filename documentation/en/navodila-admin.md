
---

> 🛠️ **For the school administrator (system keeper) only.**
> Management and teachers do not see this document.
>
> The administrator takes care of **school settings, users, email, the
> subscription and backups**. For everyday work (reservations, assessments,
> activity days) see the *Management Guide* and *Teacher Instructions*.

---

# 🛠️ Administrator Guide — OŠ Toneta Čufarja Jesenice

---

## 1. Where things are

| What | Where |
|---|---|
| 👥 **Users** (teacher and management accounts) | Top menu → **Admin panel** (or <code>/auth/admin/users</code>) |
| ⚙️ **School settings** (classes, rooms, numbers, schedule, email) | Top menu → **⚙️ School settings** (or <code>/settings</code>) |
| 🧭 **School setup guide** (what is still to be done) | <code>/nastavitev</code> |
| 💶 **School subscription** | ⚙️ School settings → *School subscription* (or <code>/narocnina</code>) |
| 💾 **Backup and restore** | ⚙️ School settings → *Backup* / *Restore* |
| 📋 **Change log (audit log)** | Top menu → **📋 Audit log** |

> 💡 **Tip:** Almost all administrator settings live in one place — **School
> settings**. Changes apply immediately after saving.

---

## 2. Users

A user's username is **their school email address**. Passwords are **never
displayed** — every user sets their own via the **Forgot password?** button on
the login page.

### Manual editing (Admin panel)

| Function | Description |
|---|---|
| Add | Enter email, first name, last name and role |
| Overview | Table of all users (click a column to sort) |
| Edit | »Edit« — if you leave the password blank, it stays unchanged |
| Deactivate / Activate | Disable or re-enable a user's access |
| Delete | Permanently deletes the user (the main admin, ID=1, is protected) |

### Import from a CSV file

On the **Users** page choose a CSV file and click **📥 Import CSV**. A header row
is optional; the default order is
`username, email, first name, last name, role, password`. You may omit the
password — the app invents one and **does not show it**. Existing usernames are
skipped.

### Import staff with a script

The script reads the staff list straight from the school website (read-only — it
changes nothing):

```bash
cd /home/admin/reservation_app
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Dry run (no actual changes):
python3 scripts/import_teachers.py --dry-run

# Including administration and technical staff:
python3 scripts/import_teachers.py --base-url https://ostc-app.org --include-all
```

---

## 3. School settings

On the **⚙️ School settings** page you edit everything that determines how the
app behaves for your school. Click **Save settings** after every change.

| Section | What you edit |
|---|---|
| **Classes** | List of classes (e.g. `1. a`). One class per row; add with **＋ Add class** |
| **Numbers** | Named numeric variables (e.g. `Number of tablets = 28`) |
| **Rooms** | Rooms available for reservation. The **»number«** checkbox links a room to a numeric variable — several teachers may share such a room at once (each states a quantity) |
| **Schedule** | Lesson times (e.g. `07:30-08:15`) |
| **Assessment rules** | Max assessments per week / day / with repetition / consecutive days |
| **Email (SMTP)** | Admin address, sender address (From), backup address, SMTP server, username and password |

> 🔒 **The SMTP password is never displayed.** If you leave the field blank, the
> existing password is **kept**. Enter a new one only when you want to change it.

### A room with multiple units (e.g. 5 computers)

1. In the **Numbers** section add the variable `Number of computers = 5`.
2. In the **Rooms** section add a room, tick **»number«** and link it to that
   variable.
3. Now several teachers can share the same unit at once — the total per hour is
   limited by the variable. Without the checkbox the room is exclusive (one
   reservation per hour).

---

## 4. Email (SMTP)

Without correctly configured email, **notifications and password reset do not
work**.

| Setting | What it is |
|---|---|
| **ADMIN_EMAIL** | The school admin's address — receives notifications and the password-reset link |
| **MAIL_FROM** | Sender address (From). A new school gets a test address `test@example.invalid` — replace it with your own, otherwise mail cannot be delivered |
| **BACKUP_EMAIL** | Where the nightly backup should go |
| **MAIL_SERVER / MAIL_USERNAME / MAIL_PASSWORD** | SMTP server details (if the school uses Arnes, enter the Arnes details) |

---

## 5. School subscription

The school needs a **valid subscription** (even at a price of 0 € it must be
renewed regularly), otherwise teachers cannot log in — only the school
administrator can.

- In **School settings → School subscription** you see the status and validity.
- The **Buy / Extend subscription** button leads to the subscription page, where
  you choose the period, pay and **report the payment**.
- The subscription is confirmed by the app provider once the transfer is
  received.
- **Auto-renewal:** if you enable it and set up payment via PayPal, the
  subscription renews itself each period.

> 💶 Currently the **yearly** plan (12 months) is available.

---

## 6. Backup and restore

### Make a backup

In **School settings → School backup** click **📧 Make backup**. The app builds a
`.sql` copy of **this school's** data only and sends it to the **Backup email**
(BACKUP_EMAIL). In addition, an automatic copy is prepared every night.

### Restore from a backup

In **School settings → Restore from backup** upload a `.sql` file and choose what
to restore. The data of the selected group **for this school** is replaced with
the data from the copy; other schools' data stays untouched.

| Button | What it restores |
|---|---|
| 👥 Users | The school's accounts (with passwords) |
| ⚙️ Settings | Classes, rooms, schedule, numbers |
| 📋 Activities | Activity days + blocked dates |
| 📅 Reservations | Room reservations |
| 📝 Assessment | Assessments |
| ♻️ Entire school (all) | Rebuilds the whole school from the copy |

> ⚠️ Restore **replaces** the existing data of the selected group. Every restore
> is recorded in the audit log.

---

## 7. Activity days and blocked dates

These are managed **in the calendar** (the app's main page) or on the **Activity
entry** page — **not** in School settings. This is described in detail in the
*Management Guide* (section *Assessment and activity days*).

---

## 8. Audit log (change log)

**📋 Audit log** gives an overview of all important changes — who did what and
when (reservations, series, assessments, activity days, users, password changes,
sales settings …). Useful for traceability and troubleshooting.

---

## 9. Role recommendations

| Role | Who should have it | Permissions |
|---|---|---|
| **Admin** | The system administrator only | Everything — admin panel, users, settings, subscription, backups |
| **Management** | Headteacher, assistants | Series reservations, deleting others' reservations, activity days |
| **Teacher** | All teaching staff | Basic reservations and assessments |

**In one word:** the admin runs the system, management runs the timetable,
teachers run the lessons.

---

> 🛠️ **Note:** There are no real passwords or email addresses in this guide —
> replace all examples with your own. Passwords are never displayed in the app.
>
> **Author:** Matej Čušin
