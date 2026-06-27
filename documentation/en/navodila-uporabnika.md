🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../navodila-uporabnika.md) | [🇬🇧 English](navodila-uporabnika.md)

---

# 📖 User Manual

## Login

1. Open the application website: [https://ostc-app.org](https://ostc-app.org)
2. Enter your **AAI username** (or email) and **password**
3. After login, your name and role are displayed in the top right corner
4. Click **Logout** to sign out
5. After 1 hour of inactivity, the application automatically logs you out

### Forgot Password

Click **"Forgot password?"** on the login page, enter your work email, and follow the link in the message you receive.

### Password Rules

- At least **5 characters** long
- At least **one lowercase letter** (a–z)
- At least **one uppercase letter** (A–Ž)
- At least **one digit** (0–9)

---

## User Roles

| Function | Teacher | Management | Admin |
|---|---|---|---|
| Room reservations | ✅ | ✅ | ✅ |
| Delete own reservation | ✅ | ✅ | ✅ |
| Delete others' reservations | ❌ | ✅ | ✅ |
| Schedule assessment | ✅ | ✅ | ✅ |
| Delete own assessment | ✅ | ✅ | ✅ |
| Delete others' assessment | ❌ | ✅ | ✅ |
| Manage blocked dates | ❌ | ✅ | ✅ |
| Admin panel (users) | ❌ | ❌ | ✅ |

---

## Room Reservations

### Rooms

- **Tablets** – didactic tablets (capacity: 28 units)
- **Computer room** – computer classroom (only one teacher per period)
- **Ship** – classroom (only one teacher per period)
- **Home economics classroom** – (only one teacher per period)

### How to Reserve

1. Open the **Reservations** tab (default view)
2. Select the **start of the week** (default is the current week)
3. Click **Refresh**
4. Select the desired room by clicking the tab
5. The weekly overview shows a table: rows are periods (0–7), columns are days (Mon–Fri)
   - **Green "Available"** – the period is free
   - **Occupied period** – shows the person's name
6. Reserve in two ways:
   - Click **+** in the desired cell (quick reservation)
   - Click **+ New reservation** at the top
7. For **Tablets**, also enter the **number of tablets**
8. Click **Save**

### How to Delete a Reservation

- Click the red **✕** button next to the reservation
- **Teacher**: you can only delete your own reservations
- **Management / Admin**: you can also delete others'

### Limits

| Room | Limit |
|---|---|
| **Tablets** | Maximum 28 total per period |
| **Computer room** | Only one reservation per period |
| **Ship** | Only one reservation per period |
| **Home economics classroom** | Only one reservation per period |

---

## Assessments

### How to Schedule an Assessment

1. Open the **Assessment** tab
2. In the **Class** dropdown menu, select the class
3. Click **Refresh**
4. On the calendar, click **+** on the desired day
5. Fill out the form and click **Save**

### How to Delete an Assessment

- Click **✕** next to the assessment on the calendar
- **Teacher**: you can only delete your own
- **Management / Admin**: you can also delete others'

### Rules and Limits

| Rule | Description |
|---|---|
| Maximum 3 assessments per week | Max 3 per week |
| Maximum 2 regular per week | Retakes do not count toward this limit |
| Same day not allowed | You cannot have two on the same day |
| 3 consecutive days not allowed | Must not be on 3 consecutive days |

### Calendar Legend

- **🔵 Regular assessment** – blue badge
- **🔄 Retake** – red badge
- **🟣 Blocked date** – purple badge

---

## Blocked Dates

**Who can manage:** Management and Admin.

When a class has an activity (sports day, excursion...), management can mark these dates as "blocked". This prevents teachers from scheduling assessments on that day.

### How to Add Blocked Dates

1. Open the **Assessment** tab
2. Click **🚫 Blocked dates**
3. Select the class(es)
4. Enter a date FROM and TO
5. Click **Add blocked dates**

### How to Remove a Blocked Date

In the "Blocked dates" window, a list of blocks is displayed at the bottom. Click **✕** next to the one you want to remove.

---

## User Management (admin only)

**Access:** In the top navigation, the admin sees the **Admin panel** button.

### Functions

- **Adding users** – enter email, first name, last name, password, role
- **User overview** – table with all users
- **Editing** – click "Edit", change data
- **Deactivation / Activation** – disable or enable access
- **Deleting** – permanently delete a user (admin with ID=1 cannot be deleted)
- **Change password** – admin can change a user's password

---

## Changing Your Password

### When You Still Know Your Password

1. In the top navigation, click **Change password**
2. Enter your current password and the new password twice
3. Click **Change password**

### If You Forgot Your Password

1. On the login page, click **"Forgot password?"**
2. Enter your work email
3. Follow the link in the email you receive

---

## Technical Details

- **Automatic logout:** After 1 hour of inactivity (30 minutes for admin/management)
- **Concurrent access:** The system prevents double reservations (race condition detection)
- **Email notifications:** Sent via Arnes SMTP server
