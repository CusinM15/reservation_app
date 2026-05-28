#!/usr/bin/env python3
"""
import_teachers.py
==================

Uvozi vse učitelje z javne strani OŠ Toneta Čufarja
(https://www.tonecufar.si/o-soli/zaposleni/) v Šolski App.

Pravila:
  - username = email
  - geslo se generira: 7 znakov, vsebuje >=1 malo, >=1 veliko, >=1 številko
    (skladno z validate_password_strength v app/config.py — min 5 znakov,
    7 znakov da malce več varnosti, kot je zahteval naročnik).
  - vloga (role):
        VODSTVO            -> "vodstvo"
        vsi ostali tabi    -> "teacher"
        (administracija/tehnično lahko preskočiš s --skip-non-teaching)
  - če uporabnik z istim username že obstaja, ga PRESKOČI (server vrne
    redirect z ?error=Uporabnik%20že%20obstaja, kar ujamemo).

Uporaba:
    pip install requests beautifulsoup4 lxml
    python3 import_teachers.py \\
        --base-url https://ostc.si/solski-app \\
        --admin-user admin \\
        --admin-pass 'admin123' \\
        --out gesla_ucitelji.csv

    # Dry-run (samo izpis, brez ustvarjanja):
    python3 import_teachers.py --dry-run

    # Vključi tudi administracijo in tehnično osebje:
    python3 import_teachers.py --include-all

Output:
    CSV s kolonami: email, ime, priimek, vloga, geslo, status
"""
from __future__ import annotations

import argparse
import csv
import random
import re
import string
import sys
from dataclasses import dataclass, field
from typing import Iterable

import requests
from bs4 import BeautifulSoup

SCRAPE_URL = "https://www.tonecufar.si/o-soli/zaposleni/"

# Mapping naslovov tabov -> vloga v naši aplikaciji.
ROLE_MAP = {
    "VODSTVO": "vodstvo",
    "ADMINISTRACIJA": "teacher",          # uvozimo kot teacher; lahko preskočimo s flagom
    "STROKOVNE SLUŽBE": "teacher",
    "TEHNIČNO OSEBJE": "teacher",
    "RAZREDNA STOPNJA": "teacher",
    "PREDMETNA STOPNJA": "teacher",
    "JUTRANJE VARSTVO IN PODALJŠANO BIVANJE": "teacher",
}

# Tabi, ki se preskočijo če uporabnik ne podaš --include-all
NON_TEACHING_TABS = {"ADMINISTRACIJA", "TEHNIČNO OSEBJE", "KABINETI"}

EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+\.[A-Za-z]{2,}")


@dataclass
class Teacher:
    email: str
    first_name: str = ""
    last_name: str = ""
    role: str = "teacher"
    source_tab: str = ""
    password: str = ""
    status: str = ""  # "created", "exists", "error: ...", "dry-run"


# ── Geslo ─────────────────────────────────────────────────────────────

def generate_password(length: int = 7) -> str:
    """7 znakov, garantirano >=1 mala, >=1 velika, >=1 številka.
    Izognemo se zamenljivim znakom (0/O, 1/l/I) za enostavnejši izgovor."""
    lower = "abcdefghijkmnpqrstuvwxyz"   # brez l
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # brez I, O
    digit = "23456789"                    # brez 0, 1
    if length < 3:
        raise ValueError("Geslo mora biti dolgo vsaj 3 znake")
    chars = [
        random.choice(lower),
        random.choice(upper),
        random.choice(digit),
    ]
    pool = lower + upper + digit
    chars += [random.choice(pool) for _ in range(length - 3)]
    random.shuffle(chars)
    return "".join(chars)


# ── Scraping ──────────────────────────────────────────────────────────

def scrape_employees(html: str) -> list[Teacher]:
    """Vsaka tabela na strani je en tab. Naslove tabov najdemo v gumbu/labelu."""
    soup = BeautifulSoup(html, "lxml")
    teachers: list[Teacher] = []

    # Pristop: stran ima 8 tabel; vrstni red tabel odgovarja vrstnemu redu tabov
    # (ki ga vrne JS na frontu). Poiščemo vse tabele in vse "tab title" gumbe.
    tab_titles: list[str] = []
    for el in soup.select('[role="tab"], .elementor-tab-title, .e-n-tab-title'):
        t = el.get_text(strip=True)
        if t and t not in tab_titles:
            tab_titles.append(t)

    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("Na strani ni nobene tabele — verjetno se je struktura spremenila.")

    # Če najdemo manj tabov kot tabel, uporabimo placeholder
    while len(tab_titles) < len(tables):
        tab_titles.append(f"TAB_{len(tab_titles)+1}")

    for table, tab_name in zip(tables, tab_titles):
        # Stolpci so: Telefon | Funkcija | Email | Ime in priimek
        rows = table.find_all("tr")
        for tr in rows:
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            email = next((EMAIL_RE.search(c).group(0).lower() for c in cells if EMAIL_RE.search(c)), None)
            if not email:
                continue
            # Ime in priimek je običajno zadnji stolpec (column-4)
            name_cell = cells[-1] if cells[-1] and "@" not in cells[-1] else ""
            first_name, last_name = "", ""
            if name_cell:
                parts = name_cell.split()
                if len(parts) >= 2:
                    first_name = parts[0]
                    last_name = " ".join(parts[1:])
                else:
                    first_name = name_cell

            role = ROLE_MAP.get(tab_name.upper(), "teacher")
            teachers.append(Teacher(
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                source_tab=tab_name,
            ))

    # Deduplikacija po emailu (isti človek lahko nastopa v več tabih → obdrži prvi vnos = po prioriteti tabov)
    seen: dict[str, Teacher] = {}
    for t in teachers:
        if t.email not in seen:
            seen[t.email] = t
        else:
            # Če je drugje označen kot vodstvo, prepiši vlogo gor
            if t.role == "vodstvo" and seen[t.email].role != "vodstvo":
                seen[t.email].role = "vodstvo"
                seen[t.email].source_tab = t.source_tab
    return list(seen.values())


# ── Klic v naš API ────────────────────────────────────────────────────

def login(session: requests.Session, base_url: str, username: str, password: str) -> None:
    """Prijavi se kot admin. Naš /auth/login je form-based in nastavi cookie user_id."""
    url = base_url.rstrip("/") + "/auth/login"
    r = session.post(url, data={"username": username, "password": password}, allow_redirects=False)
    if r.status_code not in (302, 303):
        raise RuntimeError(f"Login spodletel: HTTP {r.status_code} — {r.text[:200]}")
    if "user_id" not in session.cookies:
        # Mogoče Set-Cookie pride na drugem hostu (proxy) — preveri response
        cookies = r.headers.get("set-cookie", "")
        if "user_id" not in cookies:
            raise RuntimeError("Login: cookie user_id ni bil nastavljen. Preveri credentiale.")


def create_user(session: requests.Session, base_url: str, t: Teacher) -> str:
    """Vrni 'created' / 'exists' / 'error: ...'."""
    url = base_url.rstrip("/") + "/auth/admin/users"
    data = {
        "username": t.email,        # username = email, kot je zahtevano
        "email": t.email,
        "first_name": t.first_name,
        "last_name": t.last_name,
        "password": t.password,
        "role": t.role,
    }
    r = session.post(url, data=data, allow_redirects=False)
    if r.status_code == 403:
        return "error: nimate admin pravic"
    if r.status_code not in (302, 303):
        return f"error: HTTP {r.status_code}"
    loc = r.headers.get("location", "")
    if "error=" in loc:
        # urldecode
        from urllib.parse import unquote
        err = unquote(loc.split("error=", 1)[1])
        if "že obstaja" in err or "ze obstaja" in err.lower():
            return "exists"
        return f"error: {err}"
    return "created"


# ── Main ──────────────────────────────────────────────────────────────

def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default="http://193.2.171.200:8002",
                   help="Base URL aplikacije (privzeto: http://193.2.171.200:8002)")
    p.add_argument("--admin-user", default="admin")
    p.add_argument("--admin-pass", default="admin123")
    p.add_argument("--source", default=SCRAPE_URL, help="URL za scrape (privzeto tonecufar.si)")
    p.add_argument("--out", default="gesla_ucitelji.csv", help="Izhodni CSV z gesli")
    p.add_argument("--include-all", action="store_true",
                   help="Vključi tudi administracijo in tehnično osebje (privzeto preskočeno)")
    p.add_argument("--dry-run", action="store_true", help="Samo izpiši, ne kliči API-ja")
    p.add_argument("--password-length", type=int, default=7)
    p.add_argument("--seed", type=int, default=None, help="Random seed za reproducibilna gesla")
    args = p.parse_args(list(argv) if argv is not None else None)

    if args.seed is not None:
        random.seed(args.seed)

    print(f"[1/4] Scraping {args.source}", file=sys.stderr)
    r = requests.get(args.source, timeout=20, headers={"User-Agent": "SolskiApp/1.0"})
    r.raise_for_status()
    teachers = scrape_employees(r.text)
    print(f"      → najdenih {len(teachers)} ljudi (vključno z neučnim osebjem)", file=sys.stderr)

    if not args.include_all:
        before = len(teachers)
        teachers = [t for t in teachers if t.source_tab.upper() not in NON_TEACHING_TABS]
        print(f"      → preskočenih {before - len(teachers)} ne-učnih (administracija, tehnično)",
              file=sys.stderr)

    # Generiraj gesla vsem
    for t in teachers:
        t.password = generate_password(args.password_length)

    if args.dry_run:
        print("[DRY-RUN] Ne kličem API-ja. Spodaj seznam, ki bi se uvozil:", file=sys.stderr)
        for t in teachers:
            print(f"  {t.role:8s}  {t.email:50s}  {t.first_name} {t.last_name}  (geslo: {t.password})")
        # vseeno zapiši CSV
        _write_csv(args.out, teachers)
        print(f"\nGesla zapisana v: {args.out}", file=sys.stderr)
        return 0

    print(f"[2/4] Prijava kot admin '{args.admin_user}' na {args.base_url}", file=sys.stderr)
    session = requests.Session()
    login(session, args.base_url, args.admin_user, args.admin_pass)

    print(f"[3/4] Ustvarjam {len(teachers)} uporabnikov ...", file=sys.stderr)
    for i, t in enumerate(teachers, 1):
        t.status = create_user(session, args.base_url, t)
        marker = {"created": "✓", "exists": "·"}.get(t.status, "✗")
        print(f"  [{i:3d}/{len(teachers)}] {marker} {t.email}  [{t.status}]", file=sys.stderr)

    print(f"[4/4] Pišem CSV: {args.out}", file=sys.stderr)
    _write_csv(args.out, teachers)

    created = sum(1 for t in teachers if t.status == "created")
    exists = sum(1 for t in teachers if t.status == "exists")
    errors = sum(1 for t in teachers if t.status.startswith("error"))
    print(f"\nPovzetek: {created} ustvarjenih, {exists} že obstaja, {errors} napak.", file=sys.stderr)
    return 0 if errors == 0 else 1


def _write_csv(path: str, teachers: list[Teacher]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["email", "ime", "priimek", "vloga", "geslo", "tab", "status"])
        for t in teachers:
            w.writerow([t.email, t.first_name, t.last_name, t.role, t.password, t.source_tab, t.status])


if __name__ == "__main__":
    sys.exit(main())
