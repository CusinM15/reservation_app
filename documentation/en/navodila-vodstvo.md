🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../navodila-vodstvo.md) | [🇬🇧 English](navodila-vodstvo.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# 👑 Instructions for Management and Administrators

> This document covers managing the application via the browser — intended for management (additional functions) and admin.

---

## Reservations

Management has additional options for creating reservations.

### Weekly Series

Allows reserving the same time slot for multiple consecutive days.

| Field | Description |
|---|---|
| Room | The room you want to reserve |
| Period | Value 0–7 (0 = before first period) |
| Day of week | Value 0–6 (0 = Monday) |
| From date | Start date of the series |
| To date | End date of the series |
| Number of tablets | Only for tablets |

### Full-day Series

Allows reserving an entire day (all periods) for multiple days.

| Field | Description |
|---|---|
| Room | The room you want to reserve |
| From date | Start date of the series |
| To date | End date of the series |
| Number of tablets | Only for tablets |
| Period | If empty, all periods 0–7. You can list: `1 3 5` |

### Deleting

Management can delete **other people's** reservations as well (teachers can only delete their own).

---

## Assessments

### Blocked Dates

Management can mark days as "blocked" (sports day, excursion...).

| Field | Description |
|---|---|
| Class | Select one or more (hold Ctrl for multiple) |
| From date | Start date |
| To date | End date |

When you add blocked dates:
1. The system automatically deletes all existing assessments for that class in that period
2. Sends email notifications to affected teachers

### Email Notifications

When management cancels a reservation or assessment, the application automatically sends an email notification to the teacher.

---

## 📥 **Exporting data to CSV**

> **What is this?** CSV export — download data from the app as a file you can open in Excel, Google Sheets, or any spreadsheet program.

### What can you export?

| Export type | How to access | What data |
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

> **Tip:** CSV uses semicolons (`;`) as delimiters. Excel (Slovenian locale) recognizes this automatically. If data appears in a single column, choose **semicolon delimiter** during import.

### What to do with the CSV?

- Open in **Excel** (File → Open)
- Open in **Google Sheets** (File → Import)
- Import into **any data analysis tool**

## Admin Panel (admin only)

> Accessible only to the administrator — management does not have access to it.

### Manual User Entry

Recommended **only during the school year** when a new teacher joins.

At the beginning of the school year, I recommend:
1. Delete all users
2. Import them anew with the script

### Importing Teachers via Script

The script reads the employee list from the school website.

```bash
cd /home/admin/ostc-app_deli
python3 scripts/import_teachers.py --base-url https://ostc-app.org

# Dry-run (no changes):
python3 scripts/import_teachers.py --dry-run

# Including administration/technical staff:
python3 scripts/import_teachers.py --base-url https://ostc-app.org --include-all
```

### User Management

**Access:** In the top navigation, click **Admin panel**.

Functions:
- **Adding** — enter email, first name, last name, password, role
- **Overview** — table with all users (sort by clicking a column)
- **Editing** — click "Edit", change data. If you leave the password empty, it stays unchanged
- **Deactivation / Activation** — disable a user's access
- **Deleting** — permanently delete a user (admin with ID=1 cannot be deleted)
- **Change password** — admin can change a user's password

### Recommendations

- The **Admin** role should be assigned exclusively to the administrator
- The **Management** role for the principal, assistant principals, and counselors
- The **Teacher** role for all teaching staff
