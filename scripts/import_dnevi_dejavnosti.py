#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────
# scripts/import_dnevi_dejavnosti.py — uvoz dni dejavnosti iz Excel predloge
#
# Prebere ~/reservation_app/dnevi_dejavnosti_v_evrih.xlsx (listi po razredih)
# in vnese v Šolski App:
#   1. Dneve dejavnosti (BlockedDate) za vsak razred/oddelek z datumom
#      -> POST /api/blocked-dates (preskoči vikende, idempotentno)
#   2. Rezervacije prostorov, kjer je v vrstici X (stolpci Računalnica,
#      Tablice, Ladja, Gospodinjska učilnica) za ure 1–5 (0–4)
#      -> POST /api/rezervacije/series/full-day
#
# Pravila obsega (razredi v oklepaju za datumom):
#   - "(2. a, 2. b)"  -> samo ta oddelka
#   - brez oklepaja   -> vsi črkovni oddelki razreda iz RAZREDI
#     (8. in 9. razred: številski oddelki 8.1–8.6 / 9.1–9.5 se IGNORIRAJO)
#   - "9. 2. 2027 ali 10. 2. 2027" -> oba datuma
#   - "(rezervna datuma: ...)" -> samo primarni datum
#   - "februar" / "tekom leta"  -> brez datuma -> preskočeno
#
# PRIVZETO je DRY-RUN (samo načrt). Za dejanski vnos: --commit
#
# Uporaba:
#   python3 scripts/import_dnevi_dejavnosti.py                     # načrt
#   python3 scripts/import_dnevi_dejavnosti.py --commit            # vnos
#   python3 scripts/import_dnevi_dejavnosti.py --commit \
#       --base-url https://ostc-app.org --admin-user admin --admin-pass "***"
#   python3 scripts/import_dnevi_dejavnosti.py --hours 0-6 --tablice-qty 28
#
# Zahteve: pip install requests openpyxl
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XLSX = ROOT / "dnevi_dejavnosti_v_evrih.xlsx"

# Stolpci prostorov v Excelu (F, G, H, I) -> ključi v appu
ROOM_COLS = {6: "racunalnica", 7: "tablice", 8: "ladja", 9: "gospodinjska-ucilnica"}

BAND_RE = re.compile(r"^(PREGLED DEJAVNOSTI|KULTURNI DNEVI|NARAVOSLOVNI DNEVI|TEHNIŠKI DNEVI|ŠPORTNI DNEVI)")
CLS_LIST_RE = re.compile(r"^\d{1,2}\. [a-zč](, \d{1,2}\. [a-zč])*$")
# "22. 12. 2026", "14. 9. 2026 - 16. 9. 2026", "(2. a, 2. b)" za datumom
DATE_RE = re.compile(
    r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})"
    r"(?:\s*-\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4}))?"
    r"\s*(?:\(([^)]*)\))?"
)
REZERVNA_RE = re.compile(r"\(rezervna[^)]*\)", re.IGNORECASE)
LETTER_ODDELEK_RE = re.compile(r"^\d+\.[a-zč]$")
NUMERIC_ODDELEK_RE = re.compile(r"^\d+\.[0-9]+$")


def norm_oddelek(s: str) -> str:
    """'2. a' -> '2.a' (format appa)."""
    return re.sub(r"\s+", "", s.strip())


def load_razredi(cli_value: str | None) -> list[str]:
    """RAZREDI: --razredi > env > ../.env > znana produkcijska vrednost."""
    if cli_value:
        return [r for r in cli_value.split(",") if r]
    env = None
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("RAZREDI="):
                env = line.split("=", 1)[1]
                break
    if env:
        return [r for r in env.split(",") if r]
    return ["1.a", "1.b", "1.c", "2.a", "2.b", "2.c", "2.č",
            "3.a", "3.b", "3.c", "3.č", "4.a", "4.b", "4.c", "4.č",
            "5.a", "5.b", "5.c", "5.č", "6.a", "6.b", "6.c", "6.č",
            "7.a", "7.b", "7.c", "7.č", "8.a", "8.b", "8.c",
            "9.a", "9.b", "9.c"]


def resolve_oddelki(grade: str, classes_raw: str | None, razredi: list[str]) -> tuple[list[str], str]:
    """Vrni (oddelki, opis_obsega). classes_raw: '2. a, 2. b' ali None."""
    if classes_raw:
        classes_raw = classes_raw.strip()
        if not CLS_LIST_RE.match(classes_raw):
            return [], f"(oklepaj ni seznam oddelkov: '{classes_raw}' — velja za vse oddelke razreda)"
        oddelki = [norm_oddelek(c) for c in classes_raw.split(",")]
        # številski oddelki (8.1, 9.2 ...) se ignorirajo
        oddelki = [o for o in oddelki if LETTER_ODDELEK_RE.match(o)]
        valid = [o for o in oddelki if o in razredi]
        missing = [o for o in oddelki if o not in razredi]
        if missing and valid:
            print(f"      ⚠️ oddelki niso v RAZREDI, izpuščeni: {', '.join(missing)}")
        if missing and not valid:
            return [], f"(oddelki niso v RAZREDI appa: {', '.join(missing)})"
        return valid, ", ".join(valid)
    # brez oklepaja -> vsi ČRKOVNI oddelki razreda (številski za 8./9. se ignorirajo)
    oddelki = [r for r in razredi
               if r.startswith(f"{grade}.") and LETTER_ODDELEK_RE.match(r)]
    return oddelki, f"vsi oddelki {grade}. razreda ({len(oddelki)})"


def parse_termin(termin: str) -> list[dict]:
    """Vrni seznam {date_from, date_to, classes} — razširjeno (vsak datum s svojim oklepajem)."""
    if not termin or not termin.strip():
        return []
    t = REZERVNA_RE.sub("", termin)  # samo primarni datum; rezervni se ignorirajo
    out = []
    for m in DATE_RE.finditer(t):
        d1, mo1, y1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        date_from = date(y1, mo1, d1)
        if m.group(4):
            d2, mo2, y2 = int(m.group(4)), int(m.group(5)), int(m.group(6))
            date_to = date(y2, mo2, d2)
        else:
            date_to = date_from
        classes = m.group(7).strip() if m.group(7) else None
        out.append({"date_from": date_from, "date_to": date_to, "classes": classes})
    return out


def expand_workdays(d_from: date, d_to: date) -> list[date]:
    """Vsi delavniki v obsegu (vključno)."""
    days, d = [], d_from
    while d <= d_to:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def parse_hours(spec: str) -> list[int]:
    """'0-4' ali '0,1,2,3,4' -> [0,1,2,3,4]. Ure so 0-indeksirane (0 = 1. ura)."""
    hours = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            hours.extend(range(int(a), int(b) + 1))
        elif part:
            hours.append(int(part))
    return sorted(set(hours))


def split_ranges(days: list[date]) -> list[tuple[date, date]]:
    """Sosednje dneve združi v obsege (za full-day klic); presledke razdeli.
    Npr. [14.6, 18.6] -> [(14.6,14.6), (18.6,18.6)]; [18.5,19.5,20.5] -> [(18.5,20.5)]."""
    if not days:
        return []
    runs, start, prev = [], days[0], days[0]
    for d in days[1:]:
        if d == prev + timedelta(days=1):
            prev = d
        else:
            runs.append((start, prev))
            start = prev = d
    runs.append((start, prev))
    return runs


# ── Branje Excela ─────────────────────────────────────────────────────

def read_plan(xlsx_path: Path, razredi: list[str], today: date) -> tuple[list[dict], list[str]]:
    from openpyxl import load_workbook  # počasen import — samo ob zagonu

    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    activities = []
    warnings: list[str] = []

    for ws in wb.worksheets:
        if ws.title == "Navodila":
            continue
        m = re.match(r"(\d+)\. razred", ws.title)
        if not m:
            warnings.append(f"List '{ws.title}': ni razred — preskočen")
            continue
        grade = m.group(1)
        category = None
        for row in ws.iter_rows(min_row=1, values_only=True):
            a = str(row[0]).strip() if row[0] is not None else ""
            if not a:
                continue
            if BAND_RE.match(a):
                cm = re.match(r"^(KULTURNI|NARAVOSLOVNI|TEHNIŠKI|ŠPORTNI) DNEVI", a)
                if cm:
                    category = cm.group(1)
                continue
            if a == "DEJAVNOST":
                continue
            termin = str(row[1]).strip() if row[1] is not None else ""
            rooms = [ROOM_COLS[i] for i in ROOM_COLS
                     if row[i - 1] is not None and str(row[i - 1]).strip().upper() == "X"]
            activities.append({
                "grade": grade,
                "category": category,
                "dejavnost": a,
                "termin": termin,
                "rooms": rooms,
            })
    wb.close()
    return activities, warnings


# ── Gradnja načrta ────────────────────────────────────────────────────

def build_actions(activities, razredi, today, hours, tablice_qty):
    """Vrni (block_plan, reserve_plan, skipped, conflicts).
    block_plan: {date: set(oddelki)}
    reserve_plan: [{prostor, date_from, date_to, qty, name, label}]
    """
    block_plan: dict[date, set[str]] = {}
    reserve_plan: list[dict] = []
    skipped: list[str] = []
    conflicts: list[str] = []
    reserve_keys: dict[tuple[str, date, date], str] = {}  # (prostor, od, do) -> label

    for act in activities:
        specs = parse_termin(act["termin"])
        if not specs:
            skipped.append(f"{act['grade']}. razred | {act['dejavnost'][:45]} | termin: {act['termin'][:40] or '(prazen)'}")
            continue
        label = f"{act['grade']}. razred | {act['dejavnost'][:45]} | termin: {act['termin'][:45]}"
        all_days: set[date] = set()
        scope_oddelki: set[str] = set()
        for spec in specs:
            oddelki, scope_desc = resolve_oddelki(act["grade"], spec["classes"], razredi)
            if not oddelki:
                skipped.append(f"{label} | {scope_desc} — ta termin preskočen")
                continue
            scope_oddelki.update(oddelki)
            days = expand_workdays(spec["date_from"], spec["date_to"])
            past = [d for d in days if d < today]
            for d in past:
                skipped.append(f"{label} | datum v preteklosti: {d} — preskočen")
            for d in days:
                if d >= today:
                    block_plan.setdefault(d, set()).update(oddelki)
                    all_days.add(d)
        # rezervacije prostorov — vsak neprekinjen niz dni je svoj full-day klic
        for prostor in act["rooms"]:
            days = sorted(all_days)
            if not days:
                skipped.append(f"{label} | prostor {prostor}: ni datumov — preskočen")
                continue
            scope = ", ".join(sorted(scope_oddelki)) if scope_oddelki else f"vsi oddelki {act['grade']}. razreda"
            for d_from, d_to in split_ranges(days):
                key = (prostor, d_from, d_to)
                name = f"{act['dejavnost'][:42]} ({scope})"
                conflict = None
                for (p, df, dt), lbl in reserve_keys.items():
                    if p == prostor and not (d_to < df or d_from > dt):
                        conflict = lbl
                        break
                if conflict:
                    conflicts.append(f"{label} | {prostor}: ŽE rezerviran za {conflict} — preskočen (prepreči preklic)")
                    continue
                reserve_keys[key] = label
                reserve_plan.append({
                    "prostor": prostor,
                    "date_from": d_from,
                    "date_to": d_to,
                    "qty": tablice_qty if prostor == "tablice" else None,
                    "name": name,
                    "label": label,
                    "hours": hours,
                })
    return block_plan, reserve_plan, skipped, conflicts


# ── Izvedba preko API-ja ──────────────────────────────────────────────

def api_login(base_url, username, password):
    import requests
    s = requests.Session()
    r = s.post(base_url.rstrip("/") + "/auth/login",
               data={"username": username, "password": password},
               allow_redirects=False, timeout=30)
    if r.status_code not in (302, 303):
        raise RuntimeError(f"Prijava spodletela: HTTP {r.status_code} — {r.text[:200]}")
    return s


def api_post(session, url, payload):
    import requests
    r = session.post(url, json=payload, timeout=60)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text[:200])
        except Exception:
            detail = r.text[:200]
        return None, f"HTTP {r.status_code}: {detail}"
    return r.json(), None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--xlsx", default=str(DEFAULT_XLSX), help=f"Excel datoteka (privzeto {DEFAULT_XLSX.name})")
    p.add_argument("--base-url", default="https://ostc-app.org")
    p.add_argument("--admin-user", default="admin")
    p.add_argument("--admin-pass", default="")
    p.add_argument("--razredi", default=None, help="Vejica-ločen seznam oddelkov (privzeto iz .env)")
    p.add_argument("--hours", default="0-4", help="Ure za rezervacijo prostorov, 0-indeksirano (privzeto 0-4 = 1.-5. ura)")
    p.add_argument("--tablice-qty", type=int, default=28, help="Št. tablic pri rezervaciji (privzeto 28 = TABLICE_MAX)")
    p.add_argument("--commit", action="store_true", help="Dejansko vstavi (brez tega = samo načrt/dry-run)")
    args = p.parse_args(argv)

    today = date.today()
    print(f"Danes: {today}")
    xlsx = Path(args.xlsx)
    if not xlsx.exists():
        print(f"Napaka: {xlsx} ne obstaja"); return 2

    razredi = load_razredi(args.razredi)
    print(f"RAZREDI ({len(razredi)} oddelkov): {', '.join(razredi[:12])} ...\n")

    try:
        activities, warnings = read_plan(xlsx, razredi, today)
    except ImportError:
        print("Manjka openpyxl: pip install openpyxl"); return 2

    for w in warnings:
        print("⚠️", w)

    hours = parse_hours(args.hours)
    block_plan, reserve_plan, skipped, conflicts = build_actions(
        activities, razredi, today, hours, args.tablice_qty)

    # ── Poročilo ─────────────────────────────────────────────────────
    print("=" * 70)
    print(f"{'NAČRT UVOZA — DRY-RUN' if not args.commit else 'UVOZ V TEKU'}")
    print("=" * 70)
    n_dated = 0
    for act in activities:
        specs = parse_termin(act["termin"])
        if not specs:
            continue
        n_dated += 1
        oddelki = set()
        for spec in specs:
            o, _ = resolve_oddelki(act["grade"], spec["classes"], razredi)
            oddelki.update(o)
        print(f"[{act['grade']}. razred] {act['category'] or '?'} — {act['dejavnost'][:55]}")
        print(f"    termin: {act['termin'][:70]}")
        print(f"    oddelki ({len(oddelki)}): {', '.join(sorted(oddelki)) if oddelki else '—'}")
        if act["rooms"]:
            print(f"    prostori z X: {', '.join(act['rooms'])} -> rezervacija ur {hours}")
    print()

    total_blocked = sum(len(v) for v in block_plan.values())
    print(f"Dejavnosti z datumom: {n_dated} | brez datuma (preskočene): {len(skipped)}")
    print(f"Blokade dni dejavnosti: {total_blocked} (na {len(block_plan)} datumov, {len(block_plan)} klicov)")
    print(f"Rezervacije prostorov: {len(reserve_plan)} (ure {hours}, tablice qty={args.tablice_qty})")
    if conflicts:
        print(f"\nKONFLIKTI v načrtu ({len(conflicts)}):")
        for c in conflicts:
            print("  ✗", c)
    if skipped:
        print(f"\nPreskočeno ({len(skipped)}):")
        for s in skipped:
            print("  -", s[:120])

    if not args.commit:
        print("\nDRY-RUN — nič ni bilo vstavljeno. Za dejanski vnos poženi z --commit")
        return 0

    # ── Dejanski vnos ────────────────────────────────────────────────
    if not args.admin_pass:
        print("\nNapaka: --admin-pass je obvezen ob --commit"); return 2
    print("\nPrijava ...")
    try:
        session = api_login(args.base_url, args.admin_user, args.admin_pass)
    except Exception as e:
        print(f"Napaka pri prijavi: {e}"); return 1

    print(f"\n[1/2] Dnevi dejavnosti ({len(block_plan)} datumov) ...")
    created = deleted_asm = errs = 0
    for d in sorted(block_plan):
        oddelki = sorted(block_plan[d])
        res, err = api_post(session, args.base_url.rstrip("/") + "/api/blocked-dates",
                            {"razredi": oddelki, "date_from": d.isoformat(), "date_to": d.isoformat()})
        if err or res is None:
            print(f"  ✗ {d} ({', '.join(oddelki)}): {err}")
            errs += 1
        else:
            created += res.get("created", 0)
            deleted_asm += res.get("deleted_assessments", 0)
            print(f"  ✓ {d}: {res.get('created', 0)} blokad ({', '.join(oddelki)})")
    print(f"  Skupaj: {created} blokad, {deleted_asm} pobrisanih ocenjevanj, {errs} napak")

    print(f"\n[2/2] Rezervacije prostorov ({len(reserve_plan)}) ...")
    r_created = r_removed = r_errs = 0
    for rp in reserve_plan:
        url = args.base_url.rstrip("/") + "/api/rezervacije/series/full-day"
        payload = {
            "prostor": rp["prostor"],
            "date_from": rp["date_from"].isoformat(),
            "date_to": rp["date_to"].isoformat(),
            "hours": rp["hours"],
            "name": rp["name"],
        }
        if rp["qty"] is not None:
            payload["qty"] = rp["qty"]
        res, err = api_post(session, url, payload)
        if err or res is None:
            print(f"  ✗ {rp['label'][:70]} | {rp['prostor']}: {err}")
            r_errs += 1
        else:
            r_created += res.get("created", 0)
            r_removed += res.get("removed", 0)
            print(f"  ✓ {rp['label'][:65]} | {rp['prostor']}: {res.get('created', 0)} terminov, "
                  f"{res.get('removed', 0)} preklicanih konfliktov")
    print(f"  Skupaj: {r_created} rezervacij, {r_removed} preklicanih konfliktov, {r_errs} napak")
    print("\nKONEC.")
    return 0 if (errs == 0 and r_errs == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
