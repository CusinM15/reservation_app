# ─────────────────────────────────────────────────────────────────────────
# scripts/ui_strings_data.py — KANONIČNI seznam napisov vmesnika (SL/EN)
#
# En vir resnice za:
#   • scripts/seed_ui_strings.py   (polnjenje tabele ui_strings v bazo)
#   • scripts/i18n_migrate.py      (prehod predlog: trdo besedilo → {{ t('kljuc') }})
#
# Vsak vnos: (ključ, kje/opis, slovenščina, angleščina)
# Pomembno: `slovenščina` mora DOBESEDNO ustrezati besedilu v predlogi (tudi
# morebitne ikone/embleme vključi), da se prehod ujame.
# ─────────────────────────────────────────────────────────────────────────

STRINGS: list[tuple[str, str, str, str]] = [
    # ── Splošni gumbi ──────────────────────────────────────────────────
    ("btn_shrani", "splošno", "Shrani", "Save"),
    ("btn_shrani_nastavitve", "nastavitve", "Shrani nastavitve", "Save settings"),
    ("btn_preklici", "splošno", "Prekliči", "Cancel"),
    ("btn_izbrisi", "splošno", "Izbriši", "Delete"),
    ("btn_dodaj", "splošno", "Dodaj", "Add"),
    ("btn_uredi", "splošno", "Uredi", "Edit"),
    ("btn_nazaj", "splošno", "Nazaj", "Back"),
    ("btn_nazaj_puscica", "splošno", "← Nazaj", "← Back"),
    ("btn_naprej", "splošno", "Naprej →", "Next →"),
    ("btn_osvezi", "splošno", "Osveži", "Refresh"),
    ("btn_zapri", "splošno", "Zapri", "Close"),
    ("btn_potrdi", "splošno", "Potrdi", "Confirm"),
    ("btn_zavrni", "splošno", "Zavrni", "Reject"),
    ("btn_izracunaj", "cene", "Izračunaj", "Calculate"),
    ("btn_ustvari_serijo", "rezervacije", "Ustvari serijo", "Create series"),
    ("btn_prenesi_csv", "splošno", "📥 Prenesi CSV", "📥 Download CSV"),
    ("btn_uvozi_csv", "splošno", "📥 Uvozi CSV", "📥 Import CSV"),
    ("btn_dnevi_dejavnosti", "meni", "🚫 Dnevi dejavnosti", "🚫 Activity days"),
    ("btn_dejavnosti", "meni", "📋 Dejavnosti", "📋 Activities"),
    # ── Prijava / odjava ──────────────────────────────────────────────
    ("btn_prijava", "prijava", "Prijava", "Log in"),
    ("btn_odjava", "meni", "Odjava", "Log out"),
    ("link_pozabljeno_geslo", "prijava", "Pozabljeno geslo?", "Forgot password?"),
    ("link_spremeni_geslo", "meni", "Spremeni geslo", "Change password"),
    ("naslov_sprememba_gesla", "prijava", "Sprememba gesla", "Change password"),
    ("link_nova_sola", "prijava", "Nova šola", "New school"),
    ("btn_ustvari_solo", "registracija", "Ustvari šolo", "Create school"),
    # ── Rezervacije ───────────────────────────────────────────────────
    ("btn_nova_rezervacija", "rezervacije", "Nova rezervacija", "New reservation"),
    ("popup_rezervacija_naslov", "rezervacije", "Nova rezervacija", "New reservation"),
    ("btn_nova_rezervacija_plus", "rezervacije", "+ Nova rezervacija", "+ New reservation"),
    ("label_prostor", "rezervacije", "Prostor", "Room"),
    ("label_datum", "rezervacije", "Datum", "Date"),
    ("label_ura", "rezervacije", "Ura", "Period"),
    ("label_kolicina", "rezervacije", "Količina", "Quantity"),
    ("label_rezervacija", "rezervacije", "Rezervacija", "Reservation"),
    ("btn_tedenska_serija", "rezervacije", "📅 Tedenska serija", "📅 Weekly series"),
    ("btn_celodnevna_serija", "rezervacije", "☀️ Celodnevna serija", "☀️ Full-day series"),
    ("label_tedenska_ponavljajoca", "rezervacije", "Tedenska ponavljajoča rezervacija", "Weekly recurring reservation"),
    ("label_celodnevna_serija_vse_ure", "rezervacije", "Celodnevna serija (vse ure)", "Full-day series (all periods)"),
    ("label_ime_rezervacije", "rezervacije", "Ime rezervacije", "Reservation name"),
    ("label_od_datuma", "splošno", "Od datuma", "From date"),
    ("label_do_datuma", "splošno", "Do datuma", "To date"),
    ("izvoz_rezervacij", "rezervacije", "📥 Izvoz rezervacij", "📥 Export reservations"),
    # ── Ocenjevanja ───────────────────────────────────────────────────
    ("btn_novo_ocenjevanje", "ocenjevanja", "Novo ocenjevanje", "New assessment"),
    ("btn_novo_ocenjevanje_plus", "ocenjevanja", "+ Novo ocenjevanje", "+ New assessment"),
    ("popup_ocenjevanje_naslov", "ocenjevanja", "Novo ocenjevanje", "New assessment"),
    ("label_razred", "splošno", "Razred", "Class"),
    ("label_ponavljanje", "ocenjevanja", "Ponavljanje", "Retake"),
    ("label_ocenjevanje", "ocenjevanja", "Ocenjevanje", "Assessment"),
    ("naslov_ocenjevanja", "ocenjevanja", "Ocenjevanja", "Assessments"),
    ("legenda_obicajno", "ocenjevanja", "Običajno ocenjevanje", "Regular assessment"),
    ("legenda_ponavljanje", "ocenjevanja", "Ponavljanje", "Retake"),
    ("legenda_dan_dejavnosti", "ocenjevanja", "Dan dejavnosti", "Activity day"),
    ("izvoz_ocenjevanj", "ocenjevanja", "📥 Izvoz ocenjevanj", "📥 Export assessments"),
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
    ("btn_dodaj_dneve_dejavnosti", "dejavnosti", "Dodaj dneve dejavnosti", "Add activity days"),
    # ── Koledar ───────────────────────────────────────────────────────
    ("cal_prejsnji_teden", "koledar", "‹ Prejšnji teden", "‹ Previous week"),
    ("cal_naslednji_teden", "koledar", "Naslednji teden ›", "Next week ›"),
    ("cal_prejsnji_mesec", "koledar", "‹ Prejšnji mesec", "‹ Previous month"),
    ("cal_naslednji_mesec", "koledar", "Naslednji mesec ›", "Next month ›"),
    # ── Uporabniki ────────────────────────────────────────────────────
    ("users_naslov", "uporabniki", "Upravljanje uporabnikov", "User management"),
    ("users_seznam", "uporabniki", "Seznam uporabnikov", "User list"),
    ("users_dodaj", "uporabniki", "Dodaj uporabnika", "Add user"),
    ("users_uvoz_csv_naslov", "uporabniki", "Uvoz uporabnikov iz CSV", "Import users from CSV"),
    ("users_aktiviraj", "uporabniki", "Aktiviraj", "Activate"),
    ("users_deaktiviraj", "uporabniki", "Deaktiviraj", "Deactivate"),
    ("users_uvoz_csv", "uporabniki", "Uvoz CSV", "Import CSV"),
    # ── Naročnina ─────────────────────────────────────────────────────
    ("narocnina_naslov", "naročnina", "Naročnina šole", "School subscription"),
    ("btn_sporoci_placilo", "naročnina", "Sporoči plačilo", "Report payment"),
    ("btn_placaj_paypal", "naročnina", "Plačaj prek PayPala", "Pay with PayPal"),
    ("btn_podaljsaj", "naročnina", "Podaljšaj", "Extend"),
    ("btn_podaljsaj_narocnino", "naročnina", "Podaljšaj naročnino", "Extend subscription"),
    ("btn_podaljsaj_brez_placila", "naročnina", "Podaljšaj brez plačila", "Extend without payment"),
    ("btn_potrdi_podaljsaj", "naročnina", "Potrdi (podaljšaj za izbrano obdobje)", "Confirm (extend for the selected period)"),
    ("narocnina_samodejno", "naročnina", "Samodejno plačilo", "Automatic payment"),
    ("narocnina_vklopi_avto", "naročnina", "Vklopi samodejno obnavljanje", "Enable automatic renewal"),
    ("narocnina_izklopi_avto", "naročnina", "Izklopi samodejno obnavljanje", "Disable automatic renewal"),
    ("narocnina_kaj_zdaj", "naročnina", "Kaj zdaj?", "What now?"),
    ("narocnina_sporocena_placila", "naročnina", "Sporočena plačila", "Reported payments"),
    ("narocnina_nastavitve_prodaje", "naročnina", "Nastavitve prodaje", "Sales settings"),
    ("narocnina_nereesena_placila", "naročnina", "Nerešena plačila (vse šole)", "Outstanding payments (all schools)"),
    ("label_veljavno_do", "naročnina", "Veljavno do", "Valid until"),
    ("narocnina_brezplacno", "naročnina", "Brezplačno (0 €)", "Free (0 €)"),
    # ── Nakup (javna stran) ───────────────────────────────────────────
    ("nakup_naslov", "nakup", "Naročnina za šolsko aplikacijo", "Subscription for the school app"),
    ("nakup_izracun_cene", "nakup", "Izračun cene", "Price calculation"),
    ("nakup_kaj_dobite", "nakup", "Kaj dobite", "What you get"),
    ("nakup_kako_kupite", "nakup", "Kako kupite", "How to buy"),
    # ── Registracija ──────────────────────────────────────────────────
    ("reg_naslov", "registracija", "Nova šola — ustvarite šolski račun", "New school — create a school account"),
    ("reg_kaj_dela", "registracija", "Kaj aplikacija dela", "What the app does"),
    ("reg_zakaj", "registracija", "Zakaj jo potrebujemo", "Why we need it"),
    ("reg_kako_poteka", "registracija", "Kako poteka", "How it works"),
    ("reg_vpisite_ime", "registracija", "Vpišite ime šole", "Enter the school name"),
    # ── Navodila / dokumentacija ──────────────────────────────────────
    ("doc_ucitelji", "navodila", "👩‍🏫 Učitelji", "👩‍🏫 Teachers"),
    ("doc_vodstvo", "navodila", "👑 Vodstvo", "👑 Management"),
    ("doc_admin", "navodila", "🛠️ Admin", "🛠️ Admin"),
    ("doc_prenesi_pdf", "navodila", "📥 Prenesi PDF", "📥 Download PDF"),
    # ── Nastavitev šole (navodila) ────────────────────────────────────
    ("nastavitev_naslov", "nastavitev", "Navodila za nastavitev šole", "School setup instructions"),
    ("nastavitev_kaj_urediti", "nastavitev", "Kaj je treba urediti", "What needs to be set up"),
    ("nastavitev_kako_po_vrsti", "nastavitev", "Kako po vrsti", "Step by step"),
    ("nastavitev_pravila_ocenjevanja", "nastavitev", "Pravila ocenjevanja (omejitve)", "Assessment rules (limits)"),
    ("nastavitev_dnevi_dejavnosti", "nastavitev", "Dnevi dejavnosti (Vnos dejavnosti)", "Activity days (Activity entry)"),
    ("nastavitev_kako_se_doda", "nastavitev", "Kako se doda", "How to add"),
    ("nastavitev_kako_vpliva", "nastavitev", "Kako vpliva", "How it affects"),
    ("nastavitev_pogosta_vprasanja", "nastavitev", "Pogosta vprašanja", "FAQ"),
    # ── Audit log ─────────────────────────────────────────────────────
    ("audit_naslov", "audit", "📋 Audit log — dnevnik sprememb", "📋 Audit log — change history"),
    # ── Varnostne kopije ──────────────────────────────────────────────
    ("backup_naredi", "nastavitve", "Naredi backup", "Make backup"),
    ("backup_obnovi", "nastavitve", "Obnova iz varnostne kopije", "Restore from backup"),
    # ── Splošna sporočila / okna ──────────────────────────────────────
    ("msg_potrditev_brisanja", "pogovorno okno", "Ali res želite izbrisati? Tega ni mogoče razveljaviti.",
     "Are you sure you want to delete? This cannot be undone."),
    ("msg_shranjeno", "sporočila", "Shranjeno.", "Saved."),
    ("msg_napaka", "sporočila", "Napaka.", "Error."),
    ("msg_ni_podatkov", "sporočila", "Ni podatkov.", "No data."),
    ("msg_nimam_dostopa", "sporočila", "Za to dejanje nimate pravic.", "You do not have permission for this action."),
]
