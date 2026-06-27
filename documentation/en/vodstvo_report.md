[🇸🇮 Slovenščina](../vodstvo_report.md) | [🇬🇧 English](vodstvo_report.md)

---

# 🏢 **Management/Admin Guide — ostc-app**

> This document covers UI-based management only.

---

## Reservations

### Weekly series

| Field | Description |
|---|---|
| Room | Room to reserve |
| Hour | 0–7 (0 = before first period) |
| Day of week | 0–6 (0 = Monday, 6 = Sunday) |
| From date | Series start date |
| To date | Series end date |
| Tablets count | Tablets only – set quantity so others can borrow remaining ones |

### Full-day series

| Field | Description |
|---|---|
| Room | Room to reserve |
| From date | Series start date |
| To date | Series end date |
| Tablets count | Tablets only |
| Hour | Leave empty to reserve all hours (0–7). Specify individual hours separated by spaces (e.g. `1 3 5`) |

## Exams

### Blocked dates

| Field | Description |
|---|---|
| Class | Select one or more classes (hold **Ctrl** to select multiple) |
| From date | Blocked start date |
| To date | Blocked end date |

Blocked dates appear purple on the calendar.

### Email notifications

When management cancels a reservation or exam, the app automatically sends an email notification to the teacher who created it.

## Admin panel (admin only)

> This section is only accessible to the administrator.

### Manual user entry

Available at the top of the admin panel. Recommended during the school year for new teachers.

At the start of each school year, it's recommended to delete all users and re-import them using the script:

```bash
cd /home/admin_os/ostc-app_deli
python3 scripts/import_teachers.py --base-url https://ostc-app.org
```

### User search and management

Search by email, first name, or last name. Each result has three buttons:

**Edit:** Fix name/email errors, change role (Teacher/Management/Admin).

> **Recommendation:** The `Admin` role should only be assigned to the system administrator.
