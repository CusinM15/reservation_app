"""Database backup script.
Runs as a Kubernetes CronJob to dump the PostgreSQL database and email the backup.

Usage:
  python -m scripts.db_backup
"""

import sys, os, subprocess, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.routers.blocked_dates import _send_email

BACKUP_EMAIL = settings.BACKUP_EMAIL
DB_URL = settings.DATABASE_URL


def run():
    if "postgresql" not in DB_URL:
        print("Skipping backup: not a PostgreSQL database")
        return

    # Parse DATABASE_URL for pg_dump
    # Format: postgresql://user:password@host:port/database
    parts = DB_URL.replace("postgresql://", "").split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    username = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else ""
    host = host_port[0]
    port = host_port[1] if len(host_port) > 1 else "5432"
    database = host_db[1] if len(host_db) > 1 else "sola"

    timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_filename = f"sola-backup-{timestamp}.sql"
    backup_path = f"/tmp/{backup_filename}"

    # Set PGPASSWORD for pg_dump
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    try:
        # Dump database
        result = subprocess.run(
            ["pg_dump", "-h", host, "-p", port, "-U", username, "-d", database, "-F", "p"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            error_msg = f"pg_dump failed: {result.stderr[:500]}"
            print(error_msg)
            _send_email(
                to_email=BACKUP_EMAIL,
                subject="⚠️ Backup napaka - Šolski App",
                body=f"Prišlo je do napake pri izdelavi varnostne kopije baze:\n\n{error_msg}",
            )
            return

        # Save to file
        with open(backup_path, "w") as f:
            f.write(result.stdout)

        file_size = os.path.getsize(backup_path)
        size_mb = file_size / (1024 * 1024)

        # Send backup as email attachment (if small enough) or just notification
        if file_size < 25 * 1024 * 1024:  # 25MB limit
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders
            import smtplib, ssl

            msg = MIMEMultipart()
            msg["Subject"] = f"✅ Varnostna kopija baze - {timestamp}"
            msg["From"] = settings.MAIL_FROM
            msg["To"] = BACKUP_EMAIL

            body_text = MIMEText(
                f"Varnostna kopija baze Šolski App.\n\n"
                f"Datum: {timestamp}\n"
                f"Velikost: {size_mb:.2f} MB\n\n"
                f"Baza: {database}\n"
            )
            msg.attach(body_text)

            with open(backup_path, "rb") as f:
                attachment = MIMEBase("application", "octet-stream")
                attachment.set_payload(f.read())
                encoders.encode_base64(attachment)
                attachment.add_header(
                    "Content-Disposition",
                    f"attachment; filename={backup_filename}",
                )
                msg.attach(attachment)

            context = ssl.create_default_context()
            with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=30) as s:
                s.starttls(context=context)
                s.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                s.send_message(msg)

            print(f"Backup {backup_filename} ({size_mb:.2f} MB) sent to {BACKUP_EMAIL}")
        else:
            # Too large for email, just send notification
            _send_email(
                to_email=BACKUP_EMAIL,
                subject=f"✅ Varnostna kopija baze - {timestamp}",
                body=f"Varnostna kopija je pripravljena.\n\n"
                     f"Velikost: {size_mb:.2f} MB\n"
                     f"Lokacija: {backup_path}\n\n"
                     f"Datoteka je prevelika za email, dostopna je na strežniku.",
            )
            print(f"Backup {backup_filename} ({size_mb:.2f} MB) saved to {backup_path}")

        # Clean up old backups (keep last 7)
        import glob
        old_backups = sorted(glob.glob("/tmp/sola-backup-*.sql"))
        while len(old_backups) > 7:
            os.remove(old_backups.pop(0))

    except Exception as e:
        error_msg = f"Backup failed: {type(e).__name__}: {str(e)[:500]}"
        print(error_msg)
        _send_email(
            to_email=BACKUP_EMAIL,
            subject="⚠️ Backup napaka - Šolski App",
            body=error_msg,
        )


if __name__ == "__main__":
    run()
