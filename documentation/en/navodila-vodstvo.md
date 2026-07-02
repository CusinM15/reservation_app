---

# 👑 Instructions for School Management

> Intended for the **principal and assistant principals**.  
> Management has more power than teachers — you can delete other people's reservations,
> manage blocked dates, and oversee assessments. 
>
> ⚡ **Quick start:** Go to the app, log in with your school account and
> use the menu at the top. Anything not mentioned below works the same as for teachers.

---

## 📅 Reservations

Management has **two additional reservation types** that teachers don't have.

### Weekly Series

> **Idea:** Like a recurring calendar event — set it once, it applies for multiple weeks.

Instead of manually entering the same reservation for 10 Mondays in a row, set up a series and the system takes care of everything.

| Field | Description |
|---|---|
| Room | Which room to reserve |
| Period | Period number (0 = before first period, 1–7 = regular periods) |
| Day of week | 0 = Monday, 1 = Tuesday … 6 = Sunday |
| From date | First day of the series |
| To date | Last day of the series |
| Number of tablets | Only for tablet reservations |

### Full-day Series

Reserves the entire day (all periods) for multiple consecutive days.

| Field | Description |
|---|---|
| Room | Which room to reserve |
| From date | Start date |
| To date | End date |
| Number of tablets | Only for tablets |
| Periods | If empty → reserves all periods 0–7. You can list specific ones: `1 3 5` |

### 🔥 Deleting reservations

| Role | Can delete |
|---|---|
| Teacher | Only their own reservations |
| **Management** | **Their own + other people's** reservations |

**Management has more power — you can delete other people's reservations. With this comes responsibility.** Before deleting a teacher's reservation, consider whether they might just need it rescheduled.

---

## 📝 Assessments

### Blocked Dates

> When you mark a day as blocked, all existing assessments for that day are automatically deleted
> and teachers receive an email — **the system handles the notifications**.

Use this for:
- Sports days
- Excursions
- Cultural days
- Technical days
- Other school events when classes (and assessments) don't take place

| Field | Description |
|---|---|
| Class | Select one or more (hold **Ctrl** for multiple) |
| From date | First blocked day |
| To date | Last blocked day |

**What happens when you save:**

1. The system **automatically deletes** all existing assessments for the selected classes in this period
2. **Affected teachers automatically receive an email notification**
3. Everything is logged in the audit log

You don't need to announce anything separately — the system notifies on your behalf.

### Email Notifications

The system **automatically sends email notifications** whenever management:

| Action | Who gets the email | Why? |
|---|---|---|
| ✅ Marks a date as **blocked** | All teachers of affected classes | They need to know no assessments that day |
| ✅ Creates a **series reservation** | Teachers with conflicting reservations | They're notified their reservation was moved/cancelled |

> **⚠️ Important:** If you just click `✕` (delete) an individual reservation, **no one gets notified**. For automatic notifications, always use **series reservations** or **blocked dates** — the system notifies all affected teachers automatically.

**ELI5:** Series reservations and blocked dates are like a public announcement on the bulletin board — everyone sees it and everyone is informed. Deleting an individual reservation is like quietly erasing something from the board — no one knows why it disappeared.

---

## 📋 Audit Log — Change History

![Audit log overview — filter, table, search by action](../diagrams/audit-log-zgodovina.png)

The audit log provides an **overview of all important changes in the system** — who did what and when.

**What is logged:**

| Action | Description |
|---|---|
| `create_rezervacija` | One-time reservation created |
| `delete_rezervacija` | Reservation deleted |
| `create_series` | Weekly/full-day series created |
| `delete_series` | Entire series deleted |
| `create_ocenjevanje` | Assessment scheduled |
| `delete_ocenjevanje` | Assessment deleted |
| `create_blocked_dates` | Blocked dates added |
| `delete_blocked_date` | Blocked date removed |

**Admin** is only on who can see it, go under **Admin panel** - **Dnevni dogodki**

---

## 📥 **Exporting Data to CSV**

> **What is this?** Export data to CSV (Excel-friendly format) — an easy way to transfer data from the app to your computer and open it in Excel, Google Sheets, or similar programs.

### What can you export?

| Export type | Where to click | What data |
|---|---|---|
| **Room reservations** | 📥 Export reservations (in the menu) | Date, period, room, class, teacher |
| **Assessments** | 📥 Export assessments (in the menu) | Date, class, assessment type, teacher |

### How to do it?

1. In the top menu click **📥 Export reservations** or **📥 Export assessments**
2. Choose the **date range** (default: last month):
   - **From date** — start of the range
   - **To date** — end of the range
3. For reservations, you can also select a **room** (or leave "All rooms")
4. Click **📥 Download CSV**

> 💡 **ELI5:** Like borrowing a book from the library and making a copy of the pages that interest you. CSV is a universal language that all office programs understand.

### What to do with the CSV file?

- Open it in **Excel** (File → Open)
- Open it in **Google Sheets** (File → Import)
- Import it into **any data analysis tool**

> **Tip:** CSV uses semicolons (`;`) as delimiters. Excel (Slovenian locale) recognizes this automatically. If data appears in a single column, choose **semicolon delimiter** during import.

---

## 🛡️ Admin Panel — ADMIN ONLY

> ⛔ **Management does not have access to this section.** This is just for information about what your administrator does.

### Manual User Entry

**Recommended only during the school year** — when a new teacher joins mid-year and needs to be added on the spot.

At the beginning of the school year, it's better to:
1. Delete all users
2. Re-import them using the script (see below)

### Importing Employees via Script

The script **automatically reads the employee list from the school website** — no manual entry, no Excel tables, no copying.

**Where does it get the data?**
The script goes to `https://www.tonecufar.si/o-soli/zaposleni/` and
automatically reads all employee tables — management, teachers,
administration, technical staff. All you need to know is that
**data comes directly from the school website**.

**(Don't worry — the script only reads, it doesn't change anything on the website.)**

```bash
cd /home/admin/reservation_app
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Dry run (no actual changes) — shows who would be imported:
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
| Editing | Click "Edit". Leave password blank to keep it unchanged |
| Deactivation / Activation | Disable or re-enable a user's access |
| Deleting | Permanently delete a user (admin with ID=1 is protected) |
| Change password | Admin can change any user's password at any time |

---

## 🎯 Role Recommendations

> Correct role assignment prevents problems and misuse.

| Role | Who should have it | Permissions |
|---|---|---|
| **Admin** | System administrator only | Everything — admin panel, users, settings |
| **Management** | Principal, assistant principals | Series reservations, delete others, blocked dates |
| **Teacher** | All teaching staff | Basic reservations and assessments |

**In one sentence:** Admin takes care of the system, management takes care of the schedule, teachers take care of teaching.

> **Author:** Matej Čušin  
> **School:** OŠ Toneta Čufarja, Jesenice
