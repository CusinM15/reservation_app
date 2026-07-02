# ─────────────────────────────────────────────────────────────────────────
# app/audit.py — Beleženje dogodkov v audit log
#
# Namen: Preprosta funkcija za zapis dogodka v audit_log tabelo.
# Kliče se po vseh pomembnih akcijah (ustvarjanje, brisanje, spreminjanje).
#
# Zakaj samostojen modul namesto inline v routerjih?
# Da je logika za beleženje centralizirana in jo lahko spremenimo na
# enem mestu (npr. dodamo async logging ali pošiljanje v zunanji sistem).
#
# Razlika med to funkcijo in log_audit v database.py:
# Ta verzija samostojno kliče db.commit(), medtem ko tista v database.py
# samo doda zapis v sejo (commit je prepuščen klicatelju).
# Ta verzija je novejša in bolj robustna — commit zagotovi, da se zapis
# shrani tudi, če kasnejši commit v klicatelju spodleti.
# ─────────────────────────────────────────────────────────────────────────

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_audit(
    db: Session,
    user_id: int | None,
    username: str | None,
    action: str,
    details: str | None = None,
):
    """Zapiši dogodek v audit log.
    
    Args:
        db: SQLAlchemy seja (mora biti aktivna).
        user_id: ID uporabnika, ki je izvedel akcijo.
        username: Uporabniško ime (shranimo ga ločeno za primer, ko
                 uporabnika kasneje izbrišemo — audit log ostane čitljiv).
        action: Akcija (npr. 'create_rezervacija', 'delete_user').
        details: Poljubni podrobnosti v besedilni obliki.
    
    Pomembno: Ta funkcija kliče db.commit() sama, kar pomeni, da deluje
    tudi, če je klicana po že zaključeni transakciji. To je uporabno v
    primerih, ko želimo beležiti tudi neuspele poskuse.
    """
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        details=details,
        timestamp=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()  # commit samostojno — deluje tudi če je klican po drugem commit
