
---

> 🛠️ **For the school administrator (system keeper) only.**
> Management and teachers do not see this document.
>
> The administrator takes care of **school settings, users, email, the
> subscription and backups**. For everyday work (reservations, assessments) see
> the *Management Guide* and *Teacher Instructions*.

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
| 🗓️ **Activity days** | **Activity entry** page (tab *Assessment and activity days*, <code>/dejavnosti</code>) or the **calendar** |
| 📋 **Change log (audit log)** | Top menu → **📋 Audit log** |

> 💡 **Tip:** Almost all administrator settings live in one place — **School
> settings**. Changes apply immediately after saving.

---

## 2. Users

A user's username is **their school email address**. Passwords are **never
displayed** — every user sets their own via the **Forgot password?** button on
the login page.

### Manual user entry

Recommended **only during the school year** (when a new teacher arrives mid-year
and needs to be added on the spot). At the start of the school year it is better
to use an import (see below).

### Import from a CSV file

On the **Users** page choose a CSV file and click **📥 Import CSV**. A header row
is optional; the default order is
`username, email, first name, last name, role, password`. You may omit the
password — the app invents one and **does not show it**. Existing usernames are
skipped.

### Import staff with a script

The script **reads the staff list straight from the school website** — no manual
entry, no Excel tables. It reads every staff table (management, teachers,
administration, technical staff). The script only **reads**; it changes nothing on
the website.

```bash
cd /home/admin/reservation_app
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Dry run (no actual changes) — shows who would be imported:
python3 scripts/import_teachers.py --dry-run

# Including administration and technical staff:
python3 scripts/import_teachers.py --base-url https://ostc-app.org --include-all
```

### Managing users

**Access:** In the top navigation click **Admin panel**.

| Function | Description |
|---|---|
| Add | Enter email, first name, last name, password, role |
| Overview | Table of all users (click a column to sort) |
| Edit | »Edit« — if you leave the password blank, it stays unchanged |
| Deactivate / Activate | Disable or re-enable a user's access |
| Delete | Permanently deletes the user (the main admin, ID=1, is protected) |
| Change password | Admin can change any user's password at any time |

---

## 3. School settings

On the **⚙️ School settings** page you edit everything that determines how the
app behaves for your school. Click **Save settings** after every change.

| Section | What you edit |
|---|---|
| **Classes** | List of classes. One class per row; add with **＋ Add class** |
| **Numbers** | Named numeric variables (e.g. `Number of tablets = 28`) |
| **Rooms** | Rooms available for reservation. The **»number«** checkbox links a room to a numeric variable — several teachers may share such a room at once (each states a quantity) |
| **Schedule** | Lesson times (e.g. `07:30-08:15`) |
| **Assessment rules** | Max assessments per week / day / with repetition / consecutive days |
| **Email (SMTP)** | Admin address, sender address (From), backup address, SMTP server, username and password |

### Classes = groups from grade 1 to 9

In the **Classes** field enter all of the school's classes (groups) — **from
grade 1 to grade 9**. One class per row, e.g. `1. a`, `1. b`, `2. a`, … `9. č`.
They are used in reservations, assessments and **activity days**, so they must be
entered exactly the way the school uses them.

> ℹ️ For **grades 8 and 9**, *group-class notation* is often used (e.g. `8. a` and
> `8. 1`), where the number means the group. Enter them as they apply to you — the
> app treats them as separate classes.

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

## 7. Activity days — what they are and how they work

An **activity day** is a day when a class cannot write assessments and (usually)
has no lessons — e.g. sports day, culture day, science day, technical day, a trip
or a school event.

Activities are managed on the **Activity entry** page (link in the tab
*Assessment and activity days*, path `/dejavnosti`). They are edited by
**management or admin**; teachers see the page read-only. Each class (generation
1–9) has its own tab.

### How to add one

1. Open a class (tab **1.–9.**) and click **＋ [type] DAY** (e.g. **＋ SPORTS DAY**)
   or **＋ Add event / weekly reservation**.
2. Enter the activity **title** and, optionally, a **sub-activity**.
3. Tick **»Full day«** if the activity lasts the whole day (see below).
4. In the **Dates** section enter the date (**From**) and choose the **classes**
   (individual classes, e.g. `3. a`, `3. b` — or **All classes of the generation**).
5. Optionally choose **rooms** (e.g. the gym) and a **leader**, then save.

### Multi-day activity (e.g. a trip over several days)

1. In the **Dates** section click **＋ Add date**.
2. Enter **From** (the first day).
3. Tick **»Multi-day«** and enter the **last day** in the **To** field.
4. Save — the activity applies to **every consecutive day in that range** (for the
   selected classes). Each day is blocked for assessments and (with selected
   rooms) reserves periods 1–5.

> 💡 You can also add **several separate dates** for the same activity — click
> **＋ Add date** as many times as you need.

### How it affects things

| Setting | What it means |
|---|---|
| **»Full day« (ticked)** | The day is **blocked for assessments** for the selected classes — existing assessments on that day are deleted and affected teachers receive an email. If rooms are selected, **periods 1–5 are reserved** in those rooms. The day shows in the calendar (purple **Activities:** field). |
| **»Full day« (not ticked)** | A shorter activity: assessments are **not** blocked and the day does not show as a block in the calendar. Suitable when the activity lasts only part of the day. |
| **Manual block in the calendar** | To block a day **without** a record in activities, mark it in the **calendar** on the main page (activity-days button: choose classes and range). Such a block has no record in activities — the calendar shows it as »manually blocked«. |
| **Editing / deleting** | When you edit or delete an activity, the app automatically removes the old blocks and reservations for that record and creates the new ones — the calendar always reflects the current state. |

> ⚠️ If you delete a single reservation with `✕` (in reservations), **nobody gets
> a notification**. For automatic notifications, use activity days.

---

## 8. Audit log (change log)

**📋 Audit log** gives an overview of **all important changes in the system** —
who did what and when. Useful for traceability and troubleshooting.

| Action | Description |
|--------|------|
| `create_rezervacija` / `delete_rezervacija` | Reservation created / deleted |
| `create_series` / `delete_series` | Series created / deleted |
| `create_ocenjevanje` / `delete_ocenjevanje` | Assessment announced / deleted |
| `create_blocked_dates` / `delete_blocked_date` | Activity days added / removed |
| `create_user` / `update_user` / `delete_user` | User changes |
| `change_password` | Password change |
| `save_selling_settings` | Sales settings change |

---

## 9. Role recommendations

| Role | Who should have it | Permissions |
|---|---|---|
| **Admin** | The system administrator only | Everything — admin panel, users, settings, subscription, backups |
| **Management** | Headteacher, assistants | Series reservations, deleting others' reservations, activity days |
| **Teacher** | All teaching staff | Basic reservations and assessments |

**In one word:** the admin runs the system, management runs the timetable,
teachers run the lessons.

> Correct role assignment prevents problems and abuse.

---

> 🛠️ **Note:** There are no real passwords or email addresses in this guide —
> replace all examples with your own. Passwords are never displayed in the app.
>
> **Author:** Matej Čušin
