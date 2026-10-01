

# 👑 Instructions for School Management

> Intended for the **principal and assistant principals**.  
> Management has more power than teachers — you can delete other people's reservations,
> manage activity days, and oversee assessments. 
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
| Reservation name | Why you are reserving, e.g. elective subject or technical day |
| Room | Which room to reserve |
| Period | Period number (0 = before first period, 1–7 = regular periods) |
| Day of week | 0 = Monday, 1 = Tuesday … 6 = Sunday |
| From date | First day of the series |
| To date | Last day of the series |
| Number | Only for tablet reservations. If the field doesn't appear right away, switch the room and then select tablets again |

### Full-day Series

Reserves the entire day (all periods) for multiple consecutive days.

| Field | Description |
|---|---|
| Reservation name | Why you are reserving, e.g. elective subject or technical day |
| Room | Which room to reserve |
| From date | Start date |
| To date | End date |
| Number | Only for tablets |
| Periods | If empty → reserves all periods 0–7. You can list specific ones: `1 3 5` |

### 🔥 Deleting reservations

| Role | Can delete |
|---|---|
| Teacher | Only their own reservations |
| **Management** | **Their own + other people's** reservations |

**Management has more power — you can delete other people's reservations. With this comes responsibility.** Before deleting a teacher's reservation, think it over.

---

## 📝 Assessments and Activity Days

### Activity Days

> When you mark a day as an activity day, all existing assessments for that day are automatically deleted
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
| From date | First activity day |
| To date | Last activity day |

### Classes (groups) from grade 1 to 9

Activities are organised **by class (generation) from grade 1 to grade 9** — each
class has its own tab on the *Activity entry* page. In every date row you choose
which **classes (groups)** the activity applies to: individual classes
(e.g. `3. a`, `3. b`) or **"All classes of the generation"**.

> ℹ️ For **grades 8 and 9**, group-class notation is often used (e.g. `8. a` and
> `8. 1`), where the number means the group.

### Multi-day activity (e.g. a trip over several days)

1. In the **Dates** section click **＋ Add date**.
2. Enter **From** (the first day).
3. Tick **»Multi-day«** and enter the **last day** in the **To** field.
4. Save — the activity applies to **every consecutive day in that range**; each day
   is blocked for assessments and (with selected rooms) reserves periods 1–5.

> 💡 You can also add **several separate dates** for the same activity — click
> **＋ Add date** as many times as you need.

### Full day or shorter activity

- **»Full day«** (ticked): the day is blocked for assessments, existing ones are
  deleted (teachers get an email), and with selected rooms periods 1–5 are
  reserved.
- **Not ticked**: a shorter activity — assessments are **not** blocked.

Teachers also cannot schedule an assessment on a day when their class has an activity day.

**What happens when you save:**

1. The system **automatically deletes** all existing assessments for the selected classes in this period
2. **Affected teachers automatically receive an email notification**
3. Everything is logged in the audit log

You don't need to announce anything separately — the system notifies on your behalf.

### Email Notifications

The system **automatically sends email notifications** whenever management:

| Action | Who gets the email | Why? |
|---|---|---|
| ✅ Marks a date as an **activity day** | All teachers whose reservations were cancelled | So they know they must find another date |
| ✅ Creates a **series reservation** | Teachers with conflicting reservations | They're notified their reservation was moved/cancelled |
| ✅ Deletes a **series reservation** | Teachers with conflicting reservations | Same as above |

> **⚠️ Important:** If you just click `✕` (delete) an individual reservation, **no one gets notified**. For automatic notifications, always use **series reservations** or **activity days** — the system notifies all affected teachers automatically.

**ELI5:** Series reservations and activity days are like a public announcement on the bulletin board — everyone sees it and everyone is informed. Deleting an individual reservation is like quietly erasing something from the board — no one knows why it disappeared.

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

## Instructions

These instructions are used exactly the same way as the teacher instructions (described in that guide), except that management also has access to this guide — regular teachers cannot see it.

---

## 🛡️ Admin Panel — ADMIN ONLY

> ⛔ **Management does not have access to this section.** This is just for information about what your administrator does.
>
> 📄 **Detailed administrator instructions** live in a separate document,
> **"Administrator Guide"** — in the app it has its own **🛠️ Admin** button on the
> right-hand side, visible to the **admin only** (school settings, users, email,
> subscription, backups, audit log).

---

## 🎯 Role Recommendations

> Correct role assignment prevents problems and misuse.

| Role | Who should have it | Permissions |
|---|---|---|
| **Admin** | System administrator only | Everything — admin panel, users, settings |
| **Management** | Principal, assistant principals | Series reservations, delete others, activity days |
| **Teacher** | All teaching staff | Basic reservations and assessments |

**In one sentence:** Admin takes care of the system, management takes care of the schedule, teachers take care of teaching.

> **Author:** Matej Čušin  
