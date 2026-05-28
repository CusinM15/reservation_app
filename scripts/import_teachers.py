#!/usr/bin/env python3
"""
import_teachers.py
==================

Uvozi vse učitelje z javne strani OŠ Toneta Čufarja
(https://www.tonecufar.si/o-soli/zaposleni/) v Šolski App.

Gesla se NE shranjujejo lokalno. Učitelji si geslo nastavijo
sami preko 'Pozabljeno geslo' na login strani.

Pravila:
  - username = email
  - geslo se generira začasno samo za klic API-ja (nikoli na disk)
  - vloga (role):
        VODSTVO            -> "vodstvo"
        vsi ostali tabi    -> "teacher"
  - če uporabnik že obstaja, se preskoči

Uporaba:
    pip install requests beautifulsoup4 lxml
    python3 import_teachers.py \\
        --base-url https://ostc.si/solski-app

    # Dry-run (samo izpis, brez ustvarjanja):
    python3 import_teachers.py --dry-run

    # Vključi tudi administracijo in tehnično osebje:
    python3 import_teachers.py --include-all
"""
from __future__ import annotations

import argparse
import random
import re
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
NON_TEACHING_TABS = set()  # privzeto vključimo vse

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
    """Vsaka tabela na strani je en tab. Naslove tabov najdemo v gumbu/labelu Divi theme."""
    soup = BeautifulSoup(html, "lxml")
    teachers: list[Teacher] = []

    # Divi theme: tab titles so v <li class="et_pb_tab_N"><a>...</a></li>
    tab_titles: list[str] = []
    for li in soup.select('li[class*="et_pb_tab_"]'):
        a = li.find('a')
        if a:
            t = a.get_text(strip=True)
            if t:
                tab_titles.append(t)

    # Fallback: poskusi standardne tab selektorje (Elementor/Divi)
    if not tab_titles:
        for el in soup.select('[role="tab"], .elementor-tab-title, .e-n-tab-title, .et_pb_tab_control a'):
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
        # Stolpci so različni glede na tab — poiščemo email in ime po logiki
        rows = table.find_all("tr")
        for tr in rows:
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            
            # Poišči celico z emailom
            email = None
            email_idx = None
            for idx, c in enumerate(cells):
                m = EMAIL_RE.search(c)
                if m:
                    email = m.group(0).lower()
                    email_idx = idx
                    break
            
            if not email:
                continue
            
            # Preskoči generične šolske email naslove (ne osebe)
            if email in ("os-tone.cufar@guest.arnes.si",):
                continue
            
            # Ime je celica poleg emaila — najprej preveri za emailom (VODSTVO/ADMIN),
            # nato pred emailom (RAZREDNA/PREDMETNA/STROKOVNE)
            name = ""
            if email_idx is not None:
                for candidate_idx in [email_idx + 1, email_idx - 1]:
                    if 0 <= candidate_idx < len(cells):
                        val = cells[candidate_idx]
                        if val and "@" not in val and not re.match(r'^[\d\s/\-]+$', val):
                            # Ne sme biti očiten naziv/funkcija/predmet
                            func_keywords = [
                                'ravnatelj', 'tajništvo', 'tajnica', 'računovodstvo', 'računalnikar',
                                'pedagog', 'psiholog', 'socialni', 'knjižničar', 'vodja', 'hišnik',
                                'kuhinja', 'jedilnica', 'organizator', 'materialno',
                                'razred', 'predmet', 'angleščina', 'matematika',
                                'slovenščina', 'zgodovina', 'geografija', 'fizika', 'kemija', 'biologija',
                                'športna', 'likovna', 'tehnika', 'gospodinjstvo', 'družba', 'naravoslovje',
                                'jutranje varstvo', 'podaljšano bivanje',
                            ]
                            if not any(kw in val.lower() for kw in func_keywords):
                                name = val
                                break
            
            # Če imena nismo našli poleg emaila, vzemi zadnjo celico (fallback za VODSTVO/ADMIN brez naziva)
            if not name:
                last = cells[-1]
                if last and "@" not in last and not re.match(r'^[\d\s/\-]+$', last):
                    name = last
            
            if not name:
                # Brez imena — preskoči
                continue

            # Razdeli na ime in priimek
            first_name, last_name = "", ""
            if name:
                parts = name.split()
                first_name = parts[0]
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

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

def login(session: requests.Session, base_url: str, username: str, password: str, verify: bool = True) -> None:
    """Prijavi se kot admin. Naš /auth/login je form-based in nastavi cookie user_id."""
    url = base_url.rstrip("/") + "/auth/login"
    r = session.post(url, data={"username": username, "password": password}, allow_redirects=False, verify=verify)
    if r.status_code not in (302, 303):
        raise RuntimeError(f"Login spodletel: HTTP {r.status_code} — {r.text[:200]}")
    if "user_id" not in session.cookies:
        # Mogoče Set-Cookie pride na drugem hostu (proxy) — preveri response
        cookies = r.headers.get("set-cookie", "")
        if "user_id" not in cookies:
            raise RuntimeError("Login: cookie user_id ni bil nastavljen. Preveri credentiale.")


def create_user(session: requests.Session, base_url: str, t: Teacher, verify: bool = True) -> str:
    """Vrni 'created' / 'exists' / 'error: ...'. Uporabi začasno geslo."""
    url = base_url.rstrip("/") + "/auth/admin/users"
    data = {
        "username": t.email,        # username = email, kot je zahtevano
        "email": t.email,
        "first_name": t.first_name,
        "last_name": t.last_name,
        "password": t.password,     # začasno geslo, nikoli shranjeno na disk
        "role": t.role,
    }
    r = session.post(url, data=data, allow_redirects=False, verify=verify)
    if r.status_code == 403:
        return "error: nimate admin pravic"
    if r.status_code not in (302, 303):
        return f"error: HTTP {r.status_code}"
    loc = r.headers.get("location", "")
    if "error=" in loc:
        from urllib.parse import unquote
        err = unquote(loc.split("error=", 1)[1])
        if "že obstaja" in err or "ze obstaja" in err.lower():
            return "exists"
        return f"error: {err}"
    return "created"


def update_user(session: requests.Session, base_url: str, t: Teacher, user_id: int, verify: bool = True) -> str:
    """Posodobi ime in priimek obstoječega uporabnika."""
    data = {
        "username": t.email,
        "email": t.email,
        "first_name": t.first_name,
        "last_name": t.last_name,
        "role": t.role,
        "new_password": "",
    }
    r = session.post(
        base_url.rstrip("/") + f"/auth/admin/users/{user_id}/update",
        data=data,
        allow_redirects=False,
        verify=verify,
    )
    if r.status_code in (302, 303):
        return "updated"
    return f"error: HTTP {r.status_code}"


def list_users(session: requests.Session, base_url: str, verify: bool = True) -> dict[str, int]:
    """Vrni {email: id} za vse uporabnike iz admin strani."""
    r = session.get(base_url.rstrip("/") + "/auth/admin/users", verify=verify)
    if r.status_code != 200:
        return {}
    soup = BeautifulSoup(r.text, "lxml")
    result = {}
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) >= 4:
            # Stolpci: username, email, role, akcije
            email_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            email = EMAIL_RE.search(email_cell)
            if email:
                email = email.group(0).lower()
            if not email:
                continue
            # Poišči ID iz deactivate linka
            deactivate_link = tr.find("a", href=lambda h: h and "/deactivate" in h)
            if deactivate_link:
                import re as _re
                m = _re.search(r"/auth/admin/users/(\d+)/deactivate", deactivate_link.get("href", ""))
                if m:
                    result[email] = int(m.group(1))
    return result


# ── Main ──────────────────────────────────────────────────────────────

def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default="http://193.2.171.200:8002",
                   help="Base URL aplikacije (privzeto: http://193.2.171.200:8002)")
    p.add_argument("--admin-user", default="admin")
    p.add_argument("--admin-pass", default="admin123")
    p.add_argument("--source", default=SCRAPE_URL, help="URL za scrape (privzeto tonecufar.si)")
    p.add_argument("--include-all", action="store_true",
                   help="Vključi tudi administracijo in tehnično osebje (privzeto preskočeno)")
    p.add_argument("--dry-run", action="store_true", help="Samo izpiši, ne kliči API-ja")
    p.add_argument("--password-length", type=int, default=7)
    p.add_argument("--seed", type=int, default=None, help="Random seed za reproducibilnost")
    p.add_argument("--no-verify-ssl", action="store_true",
                   help="Izklopi SSL verification (če cert ni za ostc.si ampak za interno IP)")
    args = p.parse_args(list(argv) if argv is not None else None)

    if args.seed is not None:
        random.seed(args.seed)

    # SSL verify
    verify_ssl = not args.no_verify_ssl

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

    # Generiraj začasna gesla samo v spominu — nikoli na disk
    for t in teachers:
        t.password = generate_password(args.password_length)

    if args.dry_run:
        print("[DRY-RUN] Ne kličem API-ja. Seznam za uvoz:", file=sys.stderr)
        for t in teachers:
            print(f"  {t.role:8s}  {t.email:50s}  {t.first_name} {t.last_name}", file=sys.stderr)
        print(f"\nSkupaj: {len(teachers)} oseb", file=sys.stderr)
        return 0

    print(f"[2/4] Prijava kot admin '{args.admin_user}' na {args.base_url}", file=sys.stderr)
    session = requests.Session()
    login(session, args.base_url, args.admin_user, args.admin_pass, verify=verify_ssl)

    # Pridobi zemljevid email → user_id za posodabljanje obstoječih
    user_map = list_users(session, args.base_url, verify=verify_ssl)
    print(f"      → najdenih {len(user_map)} obstoječih uporabnikov", file=sys.stderr)

    print(f"[3/4] Ustvarjam/posodabljam {len(teachers)} uporabnikov ...", file=sys.stderr)
    updated = 0
    for i, t in enumerate(teachers, 1):
        t.status = create_user(session, args.base_url, t, verify=verify_ssl)
        marker = {"created": "✓", "exists": "·"}.get(t.status, "✗")
        if t.status == "exists" and t.email in user_map:
            # Posodobi ime in priimek
            t.status = update_user(session, args.base_url, t, user_map[t.email], verify=verify_ssl)
            if t.status == "updated":
                updated += 1
                marker = "↻"
            else:
                marker = "✗"
        print(f"  [{i:3d}/{len(teachers)}] {marker} {t.email:50s} {t.first_name} {t.last_name}  [{t.status}]", file=sys.stderr)

    created = sum(1 for t in teachers if t.status == "created")
    exists = sum(1 for t in teachers if t.status == "exists")
    update_count = sum(1 for t in teachers if t.status == "updated")
    errors = sum(1 for t in teachers if t.status.startswith("error"))
    print(f"\nPovzetek: {created} ustvarjenih, {update_count} posodobljenih, {exists} že obstaja (nespremenjenih), {errors} napak.", file=sys.stderr)
    print(f"Gesla NISO shranjena lokalno.", file=sys.stderr)
    print(f"Učitelji naj kliknejo 'Pozabljeno geslo' na login strani za nastavitev gesla.", file=sys.stderr)
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
