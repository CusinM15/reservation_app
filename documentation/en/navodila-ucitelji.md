
---

> 👋 **Hello, colleagues!**
>
> This app lets you reserve rooms (e.g. computer lab and tablets) and schedule written tests. This guide is short and to the point — the examples will help you figure everything out in no time. 😊

---

# 👩‍🏫 Teacher Instructions

---

## 1. How to access the app?

Go to your school's app address. To get a password, click **Forgot password?** and enter your **school email address**. You will shortly receive an email from your school's sender address:

```text
From:    School <sender@guest.arnes.si>
Subject: Password reset

Hello!

To set a new password, click the link below:
   https://<app-address>/auth/reset-password?token=...

The link is valid for a limited time.
If you didn't request it, simply ignore this message.
```

If the email doesn't arrive, let the administrator know — they will check if your email address is correctly entered in the database (your message should include your correct email address).

---

## 2. Setting up your password

Click the link in the email and set a new password.

Your password must have:
- ✅ At least **5 characters**
- ✅ At least **one lowercase letter**
- ✅ At least **one UPPERCASE letter**
- ✅ At least **one number**

> 💡 **Example:** `Sola2025` — easy to remember, secure enough.

---

## 3. Logging in

Once you've set your password, log in:

| Field | Enter |
|---|---|
| **Username** | Your school email address |
| **Password** | The password you just set |

```text
Login

  Username:  [ your.name@guest.arnes.si ]
  Password:  [ ******** ]  (eye = show/hide)

  [ Log in ]
  Forgot password?  ·  New school
```

> 🛡️ If login doesn't work, try resetting your password a few times first. Only contact the administrator if the issue persists.

> 💡 The menu also has a **Change password** button (see section 7).

---

## 4. Reservations

Which rooms you can reserve depends on **your school's settings**. There are two types:

| Room type | How it works |
|---|---|
| **Exclusive room** | Only **one** reservation per slot (e.g. computer lab) |
| **Room with multiple units** | Multiple teachers can reserve **at the same time** — each states a quantity, and the total per hour is limited by the room's capacity (e.g. tablets) |

```text
"Reservations" page

  [ New reservation ]              week: 14 Sep – 18 Sep 2026

  Room          Mon    Tue    Wed    Thu    Fri
  -------------------------------------------------------
  Computer lab   +      +      +      +      +
  Tablets      2/28     +      +      +      +
  ...
  (Each room and period has a + button; for rooms with multiple
   units the remaining count is shown, e.g. 2/28.)
```

You can make reservations in **2 ways**:

**Method 1 — click the `+` button in the table:**
The date is automatically set to the one you clicked on (you can also change it manually).

**Method 2 — click the `New reservation` button:**
Fill in all the details in the window that opens.

```text
"New reservation" window

  Room:      [ dropdown ]
  Date:      [ 14 Sep 2026 ]
  Period:    [ 3rd period ]
  Quantity:  [ 5 ]        <- only for a room with multiple units

  [ Save ]   [ Cancel ]
```

In this window, select the **Room** from the dropdown menu; the periods follow your school's timetable. For a room with multiple units you also enter the **quantity** — each shows how many units are still available (format `x/N`).

> ⚠️ **Note:** If a room with multiple units is already partially reserved for a slot, you cannot use the `+` button — use the **New reservation** button instead.

**Deleting a reservation:**
Management can delete **any** reservation, while teachers can only delete **their own**. Management also has 2 additional ways to create reservations. If you already have a reservation for that slot, it will be cancelled (except for rooms with multiple units, as long as the total isn't exceeded).

```text
Reservations overview (weekly calendar)

  Mon    Tue    Wed    Thu    Fri
  [R]    [R]     —     [T]     —
  R = your reservation      T = partially occupied room with multiple units
```

---

## 5. Assessments

You can schedule assessments in **2 ways**:

**Method 1 — click the `+` button in the calendar:**
In the assessment calendar, every weekday has a **`+`** button (*Add assessment*) in the bottom-right corner of its cell. Clicking it creates a new assessment — a window opens with the **date already filled in** (you can change the class and date). The `+` button also appears when that day already has an assessment or an activity day.

**Method 2 — click the `New assessment` button:**
Select the class and date manually.

```text
"New assessment" window

  Class:    [ 3. a ]
  Date:     [ 14 Sep 2026 ]
  Retake:   [ ]   (tick when correcting a grade / for PIP)

  [ Save ]   [ Cancel ]
```

**Rules automatically checked by the system (for grades 1 through 7):**

| Rule | Description |
|---|---|
| 📊 **Max 1 test per day** | No class can take more than one test on the same day |
| ✏️ **Max 2 regular tests per week** | Retakes don't count toward this limit |
| 🗓️ **Max 3 assessments total per week** | Including retakes |
| 🔄 **Retakes allow a 3rd test** | But three consecutive days with tests are not allowed |

```text
Assessment calendar (month)

  Mon            Tue            Wed
  ─────────────────────────────────────────────
  14             15             16
  [Assessment]                  Activity: 3. a
  +              +              +

  Legend:  blue  = regular assessment
           red   = retake
           green = IP/NIP/ID
           purple = activity day
           + = add assessment
```

> ℹ️ For **grades 8 and 9** (group-class labels combining letters and numbers, where the numbers represent groups), the system does not check these rules automatically. Teachers must ensure the rules are followed based on which students are in which group and class.

The window also has a **Retake** checkbox — when checked, the rules change slightly (a 3rd test per week becomes allowed).

---

## 6. Activity days

Management can mark certain dates as **activity days** (e.g. sports day). If you already had an assessment scheduled for that day, you will receive an automatic email notification.

### 🟣 The purple "Activities:" field in the calendar

In the calendar, on a day when any of your classes has an activity, there is a
**purple "Activities:" field**. Clicking it opens a list of all that day's
activities:

```text
Activities — 14 Sep 2026

  Class   Activity
  ─────────────────────────────────────────────
  3. a    Sports day              [ Full day ]
  3. b    Science day             [ Not a full day ]
```

In the list, each activity shows its **class** and a tag:

| Tag | Meaning |
|---|---|
| 🟣 **Full day** | The activity lasts **all day** — on that day assessments for that class are **not possible**. If you had any scheduled, they were deleted and you were notified. |
| 🟢 **Not a full day** | A **shorter** activity — assessments on that day are **still possible**. |

> 💡 This way you can see at a glance which day is "closed" for tests (full-day
> activity) and when you can still schedule a test (shorter activity).

The assessment page also has a **filter dropdown**:
Select a specific class or — for grades 8 and 9 — an entire cohort. Filters help you see which days are still available for testing.

> 💡 **Note:** After selecting a filter, click the **Refresh** button to see the updated data.

---

## 7. Changing your password

1. In the menu, click **Change password**
2. Enter your **current password**
3. Enter your **new password** (follow the rules above)
4. Confirm your new password
5. Click **Change password**

> Forgot your password? On the login page click **Forgot password?**, enter your email address and follow the instructions in the email.

---

## 8. Accessing these instructions inside the app

On the right side of the **app** there is a **`Učitelji`** (Teachers) button. When you hover over it with your mouse, these instructions open in a small window that you can scroll through with your mouse. At the bottom of the window there is also a **Download PDF** button, which lets you download the instructions to your computer.

```text
Right side of the app

  [ Učitelji ]   <- hovering opens a preview of these instructions
  [ Vodstvo ]      (visible to management and admin only)
  [ Admin ]        (visible to admin only)

  At the bottom of the window:  [ Download PDF ]
```

---

> 🫶 **I hope this app helps make your work easier. All the best!**
>
> **Author:** Matej Čušin
