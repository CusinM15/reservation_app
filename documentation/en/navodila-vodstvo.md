🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../navodila-vodstvo.md) | [🇬🇧 English](navodila-vodstvo.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# 👑 Instructions for Management

> Intended for the **principal and deputy principals**.
> Management has more power than teachers — you can delete other people's
> reservations, manage blocked dates, and oversee assessments. With great power
> comes **great responsibility**.
>
> ⚡ **Quick start:** Log in to the app with your school account and use the
> menu at the top. Everything not mentioned below works the same as for teachers.

---

## 📅 Reservations

Management has **two additional reservation types** that teachers don't have.

### Weekly Series

> **Idea:** Like a recurring event in a calendar — set it once, it repeats for multiple weeks.

Instead of manually entering the same reservation for 10 Mondays in a row, you
set up a series and the system handles the rest.

| Field | Description |
|---|---|
| Room | Which room to reserve |
| Period | Period number (0 = before first period, 1–7 = regular periods) |
| Day of week | 0 = Monday, 1 = Tuesday … 6 = Sunday |
| From date | First day of the series |
| To date | Last day of the series |
| Tablets | Number of tablets (only for tablet reservations) |

### Full-day Series

Reserves the entire day (all periods) for multiple consecutive days.

| Field | Description |
|---|---|
| Room | Which room to reserve |
| From date | Start date |
| To date | End date |
| Tablets | Number of tablets (only for tablets) |
| Periods | If empty → reserves all periods 0–7. You can specify only certain ones: `1 3 5` |

### 🔥 Deleting Reservations

| Role | Can delete |
|---|---|
| Teacher | Only their own reservations |
| **Management** | **Their own + other people's** reservations |

**Management has more power — you can delete other teachers' reservations.
With that power comes responsibility.** Before deleting a teacher's
reservation, consider whether they might just need it rescheduled.

---

## 📝 Assessments

### Blocked Dates

> When you mark a day as blocked, all assessments for that day are automatically
> deleted and affected teachers receive an email — **the system handles
> notifications**.

Use this for:
- Sports days
- Field trips / excursions
- Cultural days
- Technical days
- Other school events when classes (and assessments) are cancelled

| Field | Description |
|---|---|
| Class | Select one or more (hold **Ctrl** for multiple) |
| From date | First blocked day |
| To date | Last blocked day |

**What happens when you save:**

1. The system **automatically deletes** all existing assessments for the
   selected classes in that period
2. Affected teachers **automatically receive an email notification**
3. Everything is recorded in the audit log

No need to announce anything separately — the system notifies on your behalf.

### Email Notifications

The system **automatically sends email notifications** whenever management:

| Action | Who gets the email | Why? |
|--------|-------------------|------|
| ✅ Marks a day as **blocked** | All teachers of affected classes | So they know assessments are cancelled that day |
| ✅ Creates a **series reservation** | Teachers with conflicting reservations | They are notified their reservation was moved/cancelled |
| ✅ Deletes a **series reservation** | Teachers with conflicting reservations | Same as above |

> **⚠️ Important:** If you simply click `✕` (delete) an individual
> reservation, **nobody gets notified**. For automatic notifications, always use
> **series reservations** or **blocked dates** — the system notifies everyone
> automatically.

**ELI5:** Series reservations and blocked dates are like a public announcement
on the bulletin board — everyone sees it and everyone is informed. Deleting an
individual reservation is like quietly erasing something from the board — no
one knows why it disappeared.

---

## 📋 Audit Log — Change History

> ⚠️ **Update:** The audit log is now available to management as well.

![Audit log view — filter, table, search by action](diagrams/audit-log-zgodovina.png)

The audit log gives you a **complete overview of all important changes in the
system** — who did what and when.

**What is logged:**

| Action | Description |
|--------|------------|
| `create_rezervacija` | Single reservation created |
| `delete_rezervacija` | Reservation deleted |
| `create_series` | Weekly/full-day series created |
| `delete_series` | Entire series deleted |
| `create_ocenjevanje` | Assessment announced |
| `delete_ocenjevanje` | Assessment deleted |
| `create_blocked_dates` | Blocked dates added |
| `delete_blocked_date` | Blocked date removed |
| `create_user` | New user created |
| `update_user` | User updated |
| `delete_user` | User deleted |
| `change_password` | Password changed |

**What is NOT logged:**
- ❌ Reading data (who viewed what)
- ❌ Failed login attempts

### How does management access the audit log?

Since the audit log isn't visible in the regular menu (only admins can see it),
management can access it via a secret link with a special token:

1. **The administrator will give you a link** in the form:
   `https://{{DOMAIN}}/history?token=***`
2. **Simply paste this link into your browser** (no login required)
3. It opens **the same view as the admin sees** — a table with all changes

> 💡 **ELI5:** It's like having a special key that opens the archive door.
> This key doesn't open anything else — just the change archive. If you lose
> the key or someone steals it, ask the administrator to create a new one.

---

## 📥 **Exporting Data to CSV**

> **What is this?** Export data as CSV (Excel-friendly format) — a simple way
> to download data from the app and open it in Excel, Google Sheets, or any
> spreadsheet program.

### What can you export?

| Export type | Where to click | What data |
|---|---|---|
| **Room reservations** | 📥 Izvoz rezervacij (in the menu) | Date, period, room, class, teacher |
| **Assessments** | 📥 Izvoz ocenjevanj (in the menu) | Date, class, assessment type, teacher |

### How to do it?

1. In the top menu click **📥 Izvoz rezervacij** or **📥 Izvoz ocenjevanj**
2. Choose the **date range** (default: last month):
   - **From date** — start of the range
   - **To date** — end of the range
3. For reservations, you can also filter by **room** (or leave "All rooms")
4. Click **📥 Prenesi CSV**

> **ELI5:** Like borrowing a book from the library and making a copy of the
> pages you're interested in. CSV is the universal language that all office
> programs understand.

### What to do with the CSV?

- Open in **Excel** (File → Open)
- Open in **Google Sheets** (File → Import)
- Import into **any data analysis tool**

> **Tip:** CSV uses semicolons (`;`) as delimiters. Excel (Slovenian locale)
> recognizes this automatically. If data appears in a single column, choose
> **semicolon delimiter** during import.

---

## 🛡️ Admin Panel — ADMIN ONLY

> ⛔ **Management does NOT have access to this section.** This is just for
> your information — to understand what your administrator does.

### Manual User Entry

**Recommended only during the school year** — when a new teacher joins mid-year
and needs to be added on the spot.

At the beginning of the school year, it's better to:
1. Delete all users
2. Import them fresh with the script (see below)

### Importing Staff via Script

The script **automatically reads the employee list from the school website** —
no manual entry, no Excel files, no copy-pasting.

**Where does the data come from?**
The script goes to `https://www.tonecufar.si/o-soli/zaposleni/` and
automatically reads all employee tables — management, teachers,
administration, technical staff. All you need to know is that **the data comes
directly from the school website**.

**(Don't worry — the script only reads, it doesn't change anything on the
school website.)**

```bash
cd /home/admin/reservation_app
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Dry-run (no changes) — shows who would be imported:
python3 scripts/import_teachers.py --dry-run

# Including administration and technical staff:
python3 scripts/import_teachers.py --base-url https://ostc-app.org --include-all
```

### User Management

**Access:** In the top navigation, click **Admin panel**.

| Function | Description |
|---|---|
| Adding | Enter email, first name, last name, password, role |
| Overview | Table of all users — click a column to sort |
| Editing | Click "Edit". If you leave the password empty, it stays unchanged |
| Deactivation / Activation | Disable or re-enable a user's access |
| Deleting | Permanently delete a user (admin with ID=1 is protected) |
| Change password | Admin can change any user's password at any time |

---

## 🎯 Role Recommendations

> Proper role assignment prevents problems and misuse.

| Role | Who should have it | Permissions |
|---|---|---|
| **Admin** | System administrator only | Everything — admin panel, users, settings |
| **Management** | Principal, deputy principals | Series reservations, delete others' reservations, blocked dates |
| **Teacher** | All teaching staff | Basic reservations and assessments |

**In a nutshell:** Admin takes care of the system, management takes care of the
schedule, teachers take care of teaching.

> **Author:** Matej Čušin  
> **School:** OŠ Toneta Čufarja, Jesenice
