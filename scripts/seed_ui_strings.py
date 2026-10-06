#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────
# scripts/seed_ui_strings.py — napolni tabelo ui_strings (SL/EN)
#
# Namen: v bazo zapiše napise gumbov in pogovornih oken v SLOVENŠČINI in
# ANGLEŠČINI. Aplikacija jih bere po ključu (glej app/i18n.py, {{ t('kljuc') }}),
# admin šole pa v Nastavitvah šole izbere jezik (UI_LANGUAGE).
#
# Uporaba:
#   python -m scripts.seed_ui_strings            # doda manjkajoče, posodobi obstoječe
#   python -m scripts.seed_ui_strings --dry-run  # samo pokaže, kaj bi naredil
#
# Vrstice se UJEMAJO po ključu: obstoječe posodobimo, nove dodamo. Ročno
# spremenjenih vrstic v bazi NE prepišemo, če dodamo --keep-manual.
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal          # noqa: E402
from app.i18n import invalidate_cache          # noqa: E402
from app.models import UIString                # noqa: E402

# (ključ, kontekst/opis, slovenščina, angleščina)
STRINGS: list[tuple[str, str, str, str]] = [
    # ── Splošni gumbi ──────────────────────────────────────────────────
    ("btn_shrani", "splošno", "Shrani", "Save"),
    ("btn_preklici", "splošno", "Prekliči", "Cancel"),
    ("btn_izbrisi", "splošno", "Izbriši", "Delete"),
    ("btn_dodaj", "splošno", "Dodaj", "Add"),
    ("btn_uredi", "splošno", "Uredi", "Edit"),
    ("btn_nazaj", "splošno", "Nazaj", "Back"),
    ("btn_osvezi", "splošno", "Osveži", "Refresh"),
    ("btn_zapri", "splošno", "Zapri", "Close"),
    ("btn_potrdi", "splošno", "Potrdi", "Confirm"),
    ("btn_zavrni", "splošno", "Zavrni", "Reject"),
    # ── Prijava / odjava ──────────────────────────────────────────────
    ("btn_prijava", "prijava", "Prijava", "Log in"),
    ("btn_odjava", "meni", "Odjava", "Log out"),
    ("link_pozabljeno_geslo", "prijava", "Pozabljeno geslo?", "Forgot password?"),
    ("link_spremeni_geslo", "meni", "Spremeni geslo", "Change password"),
    ("link_nova_sola", "prijava", "Nova šola", "New school"),
    ("btn_ustvari_solo", "registracija", "Ustvari šolo", "Create school"),
    # ── Rezervacije ───────────────────────────────────────────────────
    ("btn_nova_rezervacija", "rezervacije", "Nova rezervacija", "New reservation"),
    ("popup_rezervacija_naslov", "rezervacije", "Nova rezervacija", "New reservation"),
    ("label_prostor", "rezervacije", "Prostor", "Room"),
    ("label_datum", "rezervacije", "Datum", "Date"),
    ("label_ura", "rezervacije", "Ura", "Period"),
    ("label_kolicina", "rezervacije", "Količina", "Quantity"),
    ("label_rezervacija", "rezervacije", "Rezervacija", "Reservation"),
    # ── Serije (vodstvo/admin) ────────────────────────────────────────
    ("btn_tedenska_serija", "rezervacije", "Tedenska serija", "Weekly series"),
    ("btn_celodnevna_serija", "rezervacije", "Celodnevna serija", "Full-day series"),
    ("label_ime_rezervacije", "rezervacije", "Ime rezervacije", "Reservation name"),
    ("label_od_datuma", "splošno", "Od datuma", "From date"),
    ("label_do_datuma", "splošno", "Do datuma", "To date"),
    # ── Ocenjevanja ───────────────────────────────────────────────────
    ("btn_novo_ocenjevanje", "ocenjevanja", "Novo ocenjevanje", "New assessment"),
    ("popup_ocenjevanje_naslov", "ocenjevanja", "Novo ocenjevanje", "New assessment"),
    ("label_razred", "splošno", "Razred", "Class"),
    ("label_ponavljanje", "ocenjevanja", "Ponavljanje", "Retake"),
    ("label_ocenjevanje", "ocenjevanja", "Ocenjevanje", "Assessment"),
    ("legenda_obicajno", "ocenjevanja", "Običajno ocenjevanje", "Regular assessment"),
    ("legenda_ponavljanje", "ocenjevanja", "Ponavljanje", "Retake"),
    ("legenda_dan_dejavnosti", "ocenjevanja", "Dan dejavnosti", "Activity day"),
    # ── Dnevi dejavnosti ──────────────────────────────────────────────
    ("dejavnost", "koledar", "Dejavnost", "Activity"),
    ("popup_dejavnosti_naslov", "dejavnosti", "Dejavnosti", "Activities"),
    ("label_celoten_dan", "dejavnosti", "Celoten dan", "Full day"),
    ("label_ni_celoten_dan", "dejavnosti", "Ne traja cel dan", "Not a full day"),
    ("label_stevilo", "dejavnosti", "Število", "Number"),
    ("label_opomba", "splošno", "Opomba", "Note"),
    ("label_vodja", "dejavnosti", "Vodja", "Leader"),
    ("label_cena", "dejavnosti", "Cena (€)", "Price (€)"),
    ("btn_dodaj_dogodek", "dejavnosti", "Dodaj dogodek / tedensko rezervacijo", "Add event / weekly reservation"),
    # ── Koledar ───────────────────────────────────────────────────────
    ("cal_prejsnji_mesec", "koledar", "‹ Prejšnji mesec", "‹ Previous month"),
    ("cal_naslednji_mesec", "koledar", "Naslednji mesec ›", "Next month ›"),
    # ── Uporabniki ────────────────────────────────────────────────────
    ("users_naslov", "uporabniki", "Uporabniki", "Users"),
    ("users_aktiviraj", "uporabniki", "Aktiviraj", "Activate"),
    ("users_deaktiviraj", "uporabniki", "Deaktiviraj", "Deactivate"),
    ("users_uvoz_csv", "uporabniki", "Uvoz CSV", "Import CSV"),
    # ── Naročnina ─────────────────────────────────────────────────────
    ("narocnina_naslov", "naročnina", "Naročnina šole", "School subscription"),
    ("btn_sporoci_placilo", "naročnina", "Sporoči plačilo", "Report payment"),
    ("btn_placaj_paypal", "naročnina", "Plačaj prek PayPala", "Pay with PayPal"),
    ("btn_podaljsaj", "naročnina", "Podaljšaj", "Extend"),
    ("label_veljavno_do", "naročnina", "Veljavno do", "Valid until"),
    # ── Varnostne kopije ──────────────────────────────────────────────
    ("backup_naredi", "nastavitve", "Naredi backup", "Make backup"),
    ("backup_obnovi", "nastavitve", "Obnova iz varnostne kopije", "Restore from backup"),
    # ── Navodila / dokumentacija ──────────────────────────────────────
    ("doc_ucitelji", "navodila", "Učitelji", "Teachers"),
    ("doc_vodstvo", "navodila", "Vodstvo", "Management"),
    ("doc_admin", "navodila", "Admin", "Admin"),
    ("doc_prenesi_pdf", "navodila", "Prenesi PDF", "Download PDF"),
    # ── Splošna sporočila / okna ──────────────────────────────────────
    ("msg_potrditev_brisanja", "pogovorno okno", "Ali res želite izbrisati? Tega ni mogoče razveljaviti.",
     "Are you sure you want to delete? This cannot be undone."),
    ("msg_shranjeno", "sporočila", "Shranjeno.", "Saved."),
    ("msg_napaka", "sporočila", "Napaka.", "Error."),
    ("msg_ni_podatkov", "sporočila", "Ni podatkov.", "No data."),
    ("msg_nimam_dostopa", "sporočila", "Za to dejanje nimate pravic.", "You do not have permission for this action."),
]


def seed(db, *, dry_run: bool = False, keep_manual: bool = False) -> tuple[int, int]:
    """Dodaj/posodobi napise; vrni (dodano, posodobljeno)."""
    added = updated = 0
    for key, context, sl, en in STRINGS:
        row = db.query(UIString).filter(UIString.key == key).first()
        if row is None:
            added += 1
            if not dry_run:
                db.add(UIString(key=key, context=context, sl=sl, en=en))
        else:
            changed = False
            if keep_manual:
                # Ne prepisuj ročno vnesenih vrednosti (samo dopolni prazne).
                if (not row.sl) and sl:
                    row.sl = sl; changed = True
                if (not row.en) and en:
                    row.en = en; changed = True
            else:
                if row.sl != sl:
                    row.sl = sl; changed = True
                if row.en != en:
                    row.en = en; changed = True
                if (row.context or "") != context:
                    row.context = context; changed = True
            if changed:
                updated += 1
    if not dry_run:
        db.commit()
        invalidate_cache()
    return added, updated


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="seed_ui_strings",
                                     description="Napolni tabelo ui_strings (SL/EN).")
    parser.add_argument("--dry-run", action="store_true", help="ne zapiši v bazo")
    parser.add_argument("--keep-manual", action="store_true",
                        help="ne prepiši obstoječih (samo dopolni prazne)")
    args = parser.parse_args(list(argv or []))

    db = SessionLocal()
    try:
        added, updated = seed(db, dry_run=args.dry_run, keep_manual=args.keep_manual)
    finally:
        db.close()

    glagol = "bi dodal" if args.dry_run else "dodal"
    print(f"ui_strings: {glagol} {added}, {'bi posodobil' if args.dry_run else 'posodobil'} {updated} "
          f"(skupaj v seznamu {len(STRINGS)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
