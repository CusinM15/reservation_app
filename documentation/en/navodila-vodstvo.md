

# 👑 Instructions for School Management

> Intended for the **principal and assistant principals**.  
> Management has more power than teachers — you can delete other people's reservations,
> manage activity days, and oversee assessments. With this comes **responsibility**.
>
> ⚡ **Quick start:** Log in with your school account. **Most of your work is done on the
> "Activity entry" page (`/dejavnosti`)** — there you set up activity days and weekly series.
> Anything not mentioned below works the same as for teachers.

---

## 📝 Activity days and series — the "Activity entry" page

This is **the main page for your work**. Reach it via the tab **"Assessment and activity days"**
or directly at **`/dejavnosti`**. It is edited by management and the admin; teachers see it
read-only.

There you set up:
- **activity days** (sports day, culture day, science day, technical day, other),
- **weekly series** (regular weekly reservations, e.g. an elective every Monday),
- **multi-day activities** (e.g. a trip over several days).

### Classes (groups) from grade 1 to 9

Activities are organised **by class (generation) from grade 1 to grade 9** — each class has its own
tab (plus an **IP/POUK** tab for special groups). In every date row you choose which **classes
(groups)** the activity applies to: individual classes (e.g. `3. a`, `3. b`) or
**"All classes of the generation"**.

> ℹ️ For **grades 8 and 9**, group-class notation is often used (e.g. `8. a` and `8. 1`), where the
> number means the group.

### How to add an activity (steps)

1. Open a **class tab** (e.g. grade 3).
2. Click the button for the activity type — **"＋ SPORTS DAY"**, **"＋ CULTURE DAY"**,
   **"＋ SCIENCE DAY"**, **"＋ TECHNICAL DAY"** or **"＋ OTHER"** — or
   **"＋ Add event / weekly reservation"**.
3. Fill in the fields (see the table below).
4. Click **💾 Save**. The activity appears immediately in the list and in the calendar.

### Form fields

| Field | Meaning |
|---|---|
| **Section** | Type of day (CULTURE / SCIENCE / TECHNICAL / SPORTS / OTHER) |
| **Main title** | Activity name (e.g. "Sports day"); if left empty, the section name is used |
| **Sub-activity** | Optional — e.g. "Oblak 365", "Powerpoint" (several sub-activities under the same day) |
| **Full day** | Whether the activity lasts all day (see below) |
| **Weekly repetition** | For regular weekly reservations (a series) |
| **Date not yet determined** | If you don't know the date yet — enter only the estimated period (e.g. "October–November") |
| **Dates** | From (+ **Multi-day** → **To**), choice of classes or "All classes of the generation" |
| **Rooms** | Which rooms are reserved (e.g. gym, computer lab) |
| **Price (€)** | Optional (e.g. an estimated cost) |
| **Leader** | Optional (who leads the activity) |
| **Note** | Optional |

### Multi-day activity (e.g. a trip over several days)

1. In the **Dates** section click **＋ Add date**.
2. Enter **From** (the first day).
3. Tick **»Multi-day«** and enter the **last day** in the **To** field.
4. Save — the activity applies to **every consecutive day in that range**; each day is blocked
   for assessments and (with selected rooms) reserves periods 1–5.

> 💡 You can also add **several separate dates** for the same activity — click **＋ Add date**
> as many times as you need (each with its own classes).

### Full day or shorter activity

- **»Full day«** (ticked): the day is **blocked for assessments**, existing ones are deleted
  (teachers get an email); with selected rooms, **periods 1–5 are reserved**.
- **Not ticked**: a **shorter** activity — assessments are **not** blocked and the day does not
  show as a block in the calendar.

### Weekly repetition (series)

Tick **»Weekly repetition«** to repeat the activity/reservation every week on the same day within
the chosen range (e.g. every Monday, 1st period, in the computer lab). Handy for regular electives
or other standing reservations.

### What happens when you save

1. The system **automatically deletes** all existing assessments for the selected classes in this period.
2. **Affected teachers automatically receive an email notification.**
3. With selected rooms, **periods 1–5 are reserved**.
4. Everything is logged in the audit log.

You don't need to announce anything separately — the system notifies on your behalf.

> 🟣 **Manual block in the calendar:** to block a day **without** a record in activities, mark it in
> the **calendar** on the main page (activity-days button — choose classes and range). Such a block
> has no record in activities (the calendar shows "manually blocked").

---

## 📅 Reservations

Besides activities on the **`/dejavnosti`** page, you can manage individual reservations in the
calendar on the main page (just like teachers), but with extra rights:

| Role | Can delete |
|---|---|
| Teacher | Only their own reservations |
| **Management** | **Their own + other people's** reservations |

| Button | What it does |
|---|---|
| **`+`** in a calendar cell | Quickly creates a reservation for that date |
| **New reservation** | Opens the reservation window (room, date, period, quantity) |
| **✕** on a reservation | Deletes the reservation (yours, or — as management — someone else's) |
| **Refresh** | Reloads the displayed data |

**Management has more power — you can delete other people's reservations. With this comes
responsibility.** Before deleting a teacher's reservation, think it over.

### Email notifications

The system **automatically sends email notifications** whenever management:

| Action | Who gets the email | Why? |
|--------|--------------------|------|
| Marks a date as an **activity day** | All teachers whose assessment was deleted | So they know they must find another date |
| Creates a **weekly series** | Teachers with conflicting reservations | They're notified their reservation was moved/cancelled |
| Deletes a **series** | Teachers with conflicting reservations | Same as above |

> ⚠️ **Important:** If you just click `✕` (delete) an individual reservation, **no one gets
> notified**. For automatic notifications, use **activity days** or **series** — the system
> notifies all affected teachers automatically.

**ELI5:** Activity days and series are like a public announcement on the bulletin board — everyone
sees it and everyone is informed. Deleting an individual reservation with `✕` is like quietly
erasing something from the board — no one knows why it disappeared.

---

## 📥 Exporting Data to CSV

> **What is this?** Export to CSV (Excel-friendly format) — transfer data from the app to your
> computer and open it in Excel, Google Sheets, or similar programs.

| Export type | Where to click | What data |
|---|---|---|
| **Room reservations** | 📥 Export reservations (in the menu) | Date, period, room, class, teacher |
| **Assessments** | 📥 Export assessments (in the menu) | Date, class, assessment type, teacher |

1. In the top menu click **📥 Export reservations** or **📥 Export assessments**.
2. Choose the **date range** (default: last month): **From date** and **To date**.
3. For reservations, you can also select a **room** (or leave "All rooms").
4. Click **📥 Download CSV**.

> **Tip:** CSV uses semicolons (`;`) as delimiters. Excel (Slovenian locale) recognizes this
> automatically. If data appears in a single column, choose **semicolon delimiter** during import.

---

## 🎯 Role Recommendations

> Correct role assignment prevents problems and misuse.

| Role | Who should have it | Permissions |
|---|---|---|
| **Management** | Principal, assistant principals | Series reservations, deleting others' reservations, activity days |
| **Teacher** | All teaching staff | Basic reservations and assessments |

**In one sentence:** management takes care of the timetable and activity days, teachers take care
of teaching.

---

> **Author:** Matej Čušin
