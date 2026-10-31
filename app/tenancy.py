# ─────────────────────────────────────────────────────────────────────────
# app/tenancy.py — Večšolska (multi-tenant) osnova
#
# Namen: Aplikacijo pripravi na več šol (tenantov). Vsebuje:
#   1. Preslikavo URL-aliasov v šolo (npr. /ocenjevanje_ostcj → /ocenjevanje).
#   2. SchoolConfig — nastavitve šole iz baze z fallbackom na .env.
#   3. Pomožne funkcije za določitev »obsega podatkov« (data scope) pri
#      posameznem zahtevku — katera šola se sme brati/pisati.
#   4. Bootstrap: privzeta šola (ostcj), glavni admin, migracija obstoječih
#      podatkov na privzeto šolo.
#
# Zakaj ločen modul? Ker je večšolska logika prečna (uporabljajo jo routerji,
# middleware in startup). Če bi jo razpršili po routerjih, bi vsak router
# moral ponovno izumiti ista pravila izolacije.
#
# POMEMBNO (varnost): obseg podatkov za šolskega uporabnika je VEDNO
# user.school_id iz baze — NIKOLI iz piškotka/URL-ja. URL-alias lahko samo
# zoži pogled glavnemu adminu; za navadne uporabnike je trdna meja.
# ─────────────────────────────────────────────────────────────────────────

import json
import re
import threading
import time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.security import get_current_user_id

# ── Vloge ──────────────────────────────────────────────────────────────
# main_admin = glavni admin (mi) — vidi vse šole, upravlja šole.
# admin      = ŠOLSKI admin (skrbnik posamezne šole) — vidi samo svojo šolo.
MAIN_ADMIN_ROLE = "main_admin"
SCHOOL_ADMIN_ROLE = "admin"
SCHOOL_SCOPED_ROLES = ("admin", "vodstvo", "teacher")

# ── Vrste aliasov ──────────────────────────────────────────────────────
# Alias je prvi segment poti (npr. "ocenjevanje_ostcj"). Kind pove, v katero
# kanonično pot se prevede: /<kind>/... → /ocenjevanje/...
ALIAS_KINDS = {
    "rezervacije": "/rezervacije",
    "ocenjevanje": "/ocenjevanje",
    # Digitalni zaslon (nadomeščanja): vsaka šola dobi svojo kratko pot
    # /nadomescanja_<slug>, ki se prevede v /zasloni te šole.
    "nadomescanja": "/zasloni",
    # Govorilne ure: vsaka šola dobi svojo kratko pot /govorilne_<slug>,
    # ki se prevede v /govorilne te šole (javna prijavna stran staršev).
    "govorilne": "/govorilne",
}

# Regex prepozna alias v prvem segmentu poti: <kind>_<slug>
_ALIAS_RE = re.compile(r"^(rezervacije|ocenjevanje|nadomescanja|govorilne)_([A-Za-z0-9][A-Za-z0-9_-]*)$")

# ── Ključi nastavitev po šoli ──────────────────────────────────────────
# Ista imena kot v .env, da je preslikava 1:1 in da lahko School Admin
# kasneje ureja vrednosti, ki so bile prej v ConfigMap/Secret.
SCHOOL_SETTING_KEYS = [
    "MAIL_USERNAME",
    "MAIL_PASSWORD",
    "MAIL_SERVER",
    "MAIL_PORT",
    "MAIL_FROM",
    "BACKUP_EMAIL",
    "STANJE_MAIL",
    "ADMIN_EMAIL",
    # Jezik vmesnika (napisi gumbov/oken) — "sl" ali "en". Izbira šole; vpliva
    # na vse napise, ki jih aplikacija bere iz tabele ui_strings (glej app/i18n.py).
    "UI_LANGUAGE",
    "TABLICE_MAX",
    "SCHEDULE",
    # Imenovane številske spremenljivke šole (JSON: ime → celo število), npr.
    # {"Število tablic": 28, "Število računalnikov": 30}. Ločen objekt — tako
    # lahko šola doda poljubno število (ne le omejitve tablic). Nadomešča
    # skalarni TABLICE_MAX, ki ostaja le še kot zgodovinska rezerva.
    "STEVILA",
    "RAZREDI",
    # Razredi, označeni kot »izbirni predmet« (IP/NIP): vejica-ločen seznam
    # imen iz RAZREDI. V koledarju ocenjevanj se njihova ocenjevanja izpišejo
    # v zeleni znački zraven razredov 6.–9.; kljukico nastavi šolski admin
    # v Nastavitvah (vsaka vrstica razreda).
    "RAZREDI_IP",
    "PROSTORI",
    # Prostori, ki delujejo KOT TABLICE: v njih lahko več učiteljev hkrati
    # rezervira, vsak navede količino, skupna vsota na uro pa ne sme preseči
    # kapacitete. Zdaj se shranjuje kot objekt prostor → ime številske
    # spremenljivke (glej STEVILA), npr. {"tablice": "Število tablic"}.
    "PROSTORI_STEVILO",
    # Zgodovinski seznam prostorov »kot Tablice« (brez vezave na ime
    # spremenljivke). Bere se le, kadar PROSTORI_STEVILO še ni nastavljen.
    "PROSTORI_QTY",
    # Popoldanski urnik (JSON ura → opis, npr. 15:00–21:00) in seznam
    # prostorov, ki uporabljajo TA urnik (vejica-ločeno). Če je prostor v
    # PROSTORI_POPOLDAN, se v UI prikažejo popoldanski termini.
    "POPOLDAN_SCHEDULE",
    "PROSTORI_POPOLDAN",
    # Prostori, ki so VIDNI in rezervabilni samo za vodstvo/admin (glavni
    # admin jih vidi vedno). Navadni učitelji zanje sploh ne vedo.
    # Vejica-ločeno (kot PROSTORI_POPOLDAN).
    "PROSTORI_VODSTVO",
    "INACTIVITY_TIMEOUT_MINUTES",
    "INACTIVITY_TIMEOUT_ADMIN_MINUTES",
    "RESET_TOKEN_EXPIRATION_MINUTES",
    # Pravila ocenjevanja (nastavljiva po šoli)
    "ASSESSMENT_MAX_PER_WEEK",
    "ASSESSMENT_MAX_PER_DAY",
    "ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE",
    "ASSESSMENT_MAX_CONSECUTIVE_DAYS",
    # Naročnina: datum veljavnosti (ISO, npr. 2026-10-25) in samodejno mesečno
    # plačilo (NAROCNINA_AVTO). Nastavita se ob potrjenem plačilu oziroma v
    # obrazcu naročnine — šolski admin jih ne ureja prek seznama polj, zato ju
    # ni v SCHOOL_SETTING_FIELDS.
    "NAROCNINA_DO",
    "NAROCNINA_AVTO",
    # Digitalni zaslon (nadomeščanja + obvestila) — nastavi šolski admin
    "ZASLON_URL",
    "ZASLON_POKAZI_NADOMESCANJA",
    "ZASLON_CAS_OBVESTILA",
    "ZASLON_MIN_CAS_TABELE",
    "ZASLON_HITROST_DRSENJA",
    # Casovni pas ure na zaslonu (npr. Europe/Ljubljana).
    "ZASLON_TIME_ZONE",
    # Osveži vse zaslone: sprememba vrednosti pošlje vsem napravam ukaz za reload.
    "ZASLON_OSVEZI_AT",
    # Aktivna obvestila zaslona: JSON seznam imen datotek v vec_obvestil/,
    # ki se prikazujejo PO VRSTI (v navedenem vrstnem redu), ne naključno.
    "ZASLON_OBVESTILA",
    # Tekstovna obvestila zaslona: JSON seznam besedil (največ 5), ki jih
    # šolski admin doda v UI. Vrtijo se skupaj s slikovnimi obvestili.
    "ZASLON_OBVESTILA_TEKST",
    # Govorilne ure: ali so za to šolo sploh omogočene (vklop/izklop
    # v Nastavitvah šole). Privzeto omogočene (obstoječe šole se ne izklopijo).
    "GOVORILNE_OMOGOCENE",
]


# Privzeto ime številske spremenljivke za kapaciteto prostorov »kot Tablice«.
# Uporabi se pri prehodu s starega skalarnega TABLICE_MAX.
DEFAULT_NUMBERS_NAME = "Število tablic"

# ── Privzete nastavitve za NOVO šolo (jezikovno občutljive) ─────────────
# Nova šola dobi majhen, univerzalen nabor prostorov (admin ostalo doda v
# Nastavitvah šole) in imena v jeziku vmesnika, izbranem ob ustvarjanju.
# Pomembno: če se jezik šole POZNEJE spremeni, se imena prostorov NE
# spremenijo — spremenijo se le napisi gumbov/oken (tabela ui_strings).
DEFAULT_NEW_SCHOOL_ROOMS = {
    "sl": ["Računalnica", "Tablice"],
    "en": ["Computer room", "Tablets"],
}
DEFAULT_NEW_SCHOOL_QTY_ROOM = {"sl": "Tablice", "en": "Tablets"}
DEFAULT_NEW_SCHOOL_NUMBER_NAME = {"sl": "Število tablic", "en": "Number of tablets"}
DEFAULT_TABLICE_COUNT = 25


def default_new_school_settings(ui_language: str) -> dict:
    """Privzete nastavitve za NOVO šolo, prilagojene jeziku vmesnika.

    Razlika od ``env_default_settings()``: prostori so majhen, univerzalen
    nabor (Računalnica, Tablice / Computer room, Tablets), število tablic je
    privzeto 25, imena prostorov in številske spremenljivke pa so v jeziku
    šole. Ostalo (razredi, urnik, timeouti, pravila ocenjevanja) ostane iz
    .env, kot doslej. Trenutne (obstoječe) šole se s tem NE spremenijo.
    """
    lang = ui_language if ui_language in ("sl", "en") else "sl"
    values = env_default_settings()
    num_name = DEFAULT_NEW_SCHOOL_NUMBER_NAME[lang]
    qty_room = DEFAULT_NEW_SCHOOL_QTY_ROOM[lang]
    values["PROSTORI"] = ",".join(DEFAULT_NEW_SCHOOL_ROOMS[lang])
    values["PROSTORI_STEVILO"] = json.dumps({qty_room: num_name}, ensure_ascii=False)
    values["STEVILA"] = json.dumps({num_name: DEFAULT_TABLICE_COUNT}, ensure_ascii=False)
    values["TABLICE_MAX"] = str(DEFAULT_TABLICE_COUNT)
    return values

# Opis polj za UI (oznaka + tip vnosa). Vrstni red = vrstni red v obrazcu.
SCHOOL_SETTING_FIELDS = [
    {"key": "RAZREDI", "label": "Razredi (vejica-ločeno)", "type": "csv"},
    {"key": "PROSTORI", "label": "Prostori (vejica-ločeno)", "type": "csv"},
    {"key": "SCHEDULE", "label": "Urnik (JSON: ura → opis)", "type": "json"},
    # Števila: imenovane številske spremenljivke (npr. »Število tablic«).
    {"key": "STEVILA", "label": "Števila (JSON: ime → vrednost)", "type": "json"},
    {"key": "PROSTORI_STEVILO", "label": "Prostori — vezava na število (JSON)", "type": "json"},
    {"key": "UI_LANGUAGE", "label": "Jezik vmesnika (slovenščina / angleščina)", "type": "lang"},
    {"key": "INACTIVITY_TIMEOUT_MINUTES", "label": "Timeout neaktivnosti — učitelji (min)", "type": "int"},
    {"key": "INACTIVITY_TIMEOUT_ADMIN_MINUTES", "label": "Timeout neaktivnosti — admin/vodstvo (min)", "type": "int"},
    {"key": "MAIL_SERVER", "label": "SMTP strežnik", "type": "text"},
    {"key": "MAIL_PORT", "label": "SMTP vrata", "type": "int"},
    {"key": "MAIL_USERNAME", "label": "SMTP uporabniško ime", "type": "text"},
    {"key": "MAIL_PASSWORD", "label": "SMTP geslo", "type": "password"},
    {"key": "MAIL_FROM", "label": "Naslov pošiljatelja (From)", "type": "text"},
    {"key": "BACKUP_EMAIL", "label": "E-pošta za varnostne kopije", "type": "text"},
    {"key": "ADMIN_EMAIL", "label": "E-pošta šolskega admina", "type": "text"},
    {"key": "ASSESSMENT_MAX_PER_WEEK", "label": "Ocenjevanja: največ na teden", "type": "int"},
    {"key": "ASSESSMENT_MAX_PER_DAY", "label": "Ocenjevanja: največ na dan", "type": "int"},
    {"key": "ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE", "label": "Ocenjevanja: največ na teden (z ponavljanjem)", "type": "int"},
    {"key": "ASSESSMENT_MAX_CONSECUTIVE_DAYS", "label": "Ocenjevanja: največ zaporednih dni", "type": "int"},
    # ── Digitalni zaslon ─────────────────────────────────────────
    {"key": "ZASLON_URL", "label": "Zaslon — eAsistent URL nadomeščanj", "type": "text"},
    {"key": "ZASLON_POKAZI_NADOMESCANJA", "label": "Zaslon — prikaži nadomeščanja", "type": "bool"},
    {"key": "ZASLON_CAS_OBVESTILA", "label": "Zaslon — sekund: vidna slika/obvestilo", "type": "int"},
    {"key": "ZASLON_MIN_CAS_TABELE", "label": "Zaslon — sekund: minimalni čas tabele", "type": "int"},
    {"key": "ZASLON_HITROST_DRSENJA", "label": "Zaslon — hitrost drsenja tabele", "type": "float"},
    {"key": "ZASLON_TIME_ZONE", "label": "Zaslon — časovni pas ure (npr. Europe/Ljubljana)", "type": "text"},
    {"key": "ZASLON_OBVESTILA", "label": "Zaslon — aktivna obvestila (JSON seznam)", "type": "json"},
    {"key": "ZASLON_OBVESTILA_TEKST", "label": "Zaslon — tekstovna obvestila (JSON seznam, največ 5)", "type": "json"},
    # Govorilne ure (modul): ali so za šolo omogočene.
    {"key": "GOVORILNE_OMOGOCENE", "label": "Govorilne ure — so omogočene", "type": "bool"},
]


# Privzete vrednosti pravil ocenjevanja — MORAJOpreslikati obstoječe
# vedenje aplikacije (max 2 običajni/teden, max 1/dan, 3 z ponavljanjem,
# prepoved 3 zaporednih dni).
ASSESSMENT_RULE_DEFAULTS = {
    "ASSESSMENT_MAX_PER_WEEK": 2,
    "ASSESSMENT_MAX_PER_DAY": 1,
    "ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE": 3,
    "ASSESSMENT_MAX_CONSECUTIVE_DAYS": 2,
}


# ═══════════════════════════════════════════════════════════════════════
# Slug / aliasi
# ═══════════════════════════════════════════════════════════════════════

def slugify(value: str) -> str:
    """Naredi URL-varen slug iz imena šole.

    Primer: "OŠ Toneta Čufarja Jesenice" → "os-toneta-cufarja-jesenice".
    Šumniki se transliterirajo (č→c, š→s, ž→z), ker v URL-jih ne želimo
    percent-encodinga.
    """
    mapping = {"č": "c", "ć": "c", "š": "s", "ž": "z", "đ": "d"}
    text = (value or "").strip().lower()
    for src, dst in mapping.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "sola"


def generate_aliases(slug: str) -> list[tuple[str, str]]:
    """Iz sluga šole generiraj privzete URL-aliasse.

    Vrne seznam parov (alias, kind): npr. za slug "ostcj" →
    [("rezervacije_ostcj", "rezervacije"), ("ocenjevanje_ostcj", "ocenjevanje"),
     ("nadomescanja_ostcj", "nadomescanja"), ("govorilne_ostcj", "govorilne"),
     ("ostcj", "nadomescanja")].

    Zadnji par je GOLI slug (brez predpone) — skrajšana pot za digitalni zaslon
    te šole (npr. /ostcj → /zasloni / nadomeščanja). Vsaka šola ima svoj goli
    slug, zato ni konflikta.

    Zakaj tako? Ko kasneje ustvarimo novo šolo, dobimo ustrezne poti brez
    ročnega vpisovanja. Zgodovinski aliasi (npr. "rezervacije_ostc") se
    dodajo ločeno kot podatki.
    """
    base = re.sub(r"[^a-z0-9]", "", (slug or "").lower())
    if not base:
        base = "sola"
    pairs = [(f"{kind}_{base}", kind) for kind in ALIAS_KINDS.keys()]
    # Goli slug = zaslon te šole (/nadomeščanja). Prevede se na /zasloni.
    pairs.append((base, "nadomescanja"))
    return pairs


def default_school_admin_username(slug: str) -> str:
    """Privzeto uporabniško ime ŠOLSKEGA admina: admin_<oznaka>.

    Zakaj ne kar "admin"? Ker je admin vezan na šolo — pri več šolah bi imelo
    golo ime "admin" več pomenov. Primer: slug "ostcj" → "admin_ostcj".
    Novo ime se uporabi ob ustvarjanju šole; obstoječe "admin" se ob zagonu
    enkratno preimenuje (geslo ostane nespremenjeno).
    """
    base = re.sub(r"[^a-z0-9]", "", (slug or "").lower())
    if not base:
        base = "sola"
    return f"admin_{base}"


# Besede, ki pri inicialkah ne nosijo pomena (jih preskočimo).
_INICIALKE_STOPWORDS = {
    "in", "ter", "za", "na", "ob", "do", "od", "po", "z", "s", "k", "v", "pri", "pod",
}

# Črke s strešicami → osnovne, da je uporabniško ime lažje vtipkati.
_TRANSLIT_INICIALK = str.maketrans({"č": "c", "š": "s", "ž": "z", "ć": "c", "đ": "d"})

# Testni naslovi za novo šolo (dokler jih admin ne uredi v Nastavitvah šole).
TEST_EMAIL_PLACEHOLDER = "test@example.invalid"
# Psevdo SMTP podatki za novo šolo — nova šola NE sme podedovati pravih SMTP
# poverilnic naše šole (npr. Toneta Čufarja), sicer bi pošiljala pošto z našim
# računom. Admin jih zamenja v Nastavitvah šole.
TEST_MAIL_USERNAME = "test@example.invalid"
TEST_MAIL_PASSWORD = "testno-geslo"


def school_admin_username_from_initials(name: str) -> str:
    """Uporabniško ime admina iz INICIALK imena šole.

    Primer: »Osnovna šola Toneta Čufarja Jesenice« → `admin_ost`.
    Zakaj inicialke? Uporabniško ime je kratko in prepoznavno, šoli pa se ga ni
    treba izmišljati — ob registraciji ga določimo samodejno. Uporabimo največ
    TRI inicialke, da ostane ime kratko in lahko za vtipkanje. Če inicialk ne
    moremo sestaviti (prekratko ime), vrnemo prazen niz in klicatelj uporabi
    oznako šole.
    """
    besede = re.findall(r"[A-Za-zČŠŽčšžĆćĐđ]+", name or "")
    crke: list[str] = []
    for beseda in besede:
        if beseda.lower() in _INICIALKE_STOPWORDS:
            continue
        crke.append(beseda[0].lower().translate(_TRANSLIT_INICIALK))
    osnova = re.sub(r"[^a-z0-9]", "", "".join(crke))
    if len(osnova) < 2:
        return ""
    # Največ 3 inicialke (zahteva uporabnika 2026-09-29): uporabniško ime
    # admina naj bo krajše, npr. admin_ost namesto admin_ostcj.
    return f"admin_{osnova[:3]}"


def apply_test_email_settings(db: Session, school_id: int) -> None:
    """Novi šoli zapiši TESTNE vrednosti e-pošte.

    Zakaj? Ob ustvarjanju šole se nastavitve napolnijo iz .env — tam so povezane
    z NAŠO šolo (naslov pošiljatelja, obvestila, varnostne kopije) IN tudi SMTP
    uporabniško ime/geslo. Nova šola zato dobi začasne testne/psevdo vrednosti,
    ki jih admin zamenja v Nastavitvah šole (glej stran Navodila za nastavitev).
    """
    for key in ("MAIL_FROM", "BACKUP_EMAIL", "ADMIN_EMAIL", "MAIL_USERNAME"):
        set_school_setting(db, school_id, key, TEST_EMAIL_PLACEHOLDER)
    # SMTP geslo: psevdo vrednost — nova šola NE sme pošiljati z našim računom.
    set_school_setting(db, school_id, "MAIL_PASSWORD", TEST_MAIL_PASSWORD)


def parse_alias_path(path: str) -> tuple[str | None, str | None]:
    """Razbij pot na (alias, kanonična pot).

    /ocenjevanje_ostcj/dejavnosti → ("ocenjevanje_ostcj", "/ocenjevanje/dejavnosti")
    /rezervacije_ostc             → ("rezervacije_ostc", "/rezervacije")
    /rezervacije                  → (None, None)   # že kanonično

    Vrne (None, None), če prvi segment ni alias — takrat poti ne spreminjamo.
    """
    if not path or not path.startswith("/"):
        return None, None
    trimmed = path.lstrip("/")
    if not trimmed:
        return None, None
    parts = trimmed.split("/", 1)
    first = parts[0]
    # Preostanek poti normaliziramo: odstranimo morebitne zaključne poševnice.
    # Zakaj? Brez tega se "/rezervacije_ostc/" prevede v "/rezervacije/", kar
    # Starlette preusmeri (307) na "/rezervacije" — pri tem pa se izgubi
    # kontekst šole (state), zato je uporabnik videl podatke druge šole.
    rest = ("/" + parts[1]).rstrip("/") if len(parts) > 1 else ""
    m = _ALIAS_RE.match(first)
    if not m:
        return None, None
    kind = m.group(1)
    prefix = ALIAS_KINDS.get(kind)
    if not prefix:
        return None, None
    return first, f"{prefix}{rest}"


# ── Predpomnilnik aliasov ──────────────────────────────────────────────
# Alias prevedemo na school_id pred vsakim zahtevkom. Ker se aliasi
# spreminjajo zelo redko, uporabimo kratek TTL predpomnilnik (manj
# poizvedb v bazo), ki ga ob spremembi počistimo.
_ALIAS_CACHE: dict[str, tuple[int | None, float]] = {}
_ALIAS_KIND_CACHE: dict[str, str | None] = {}
_ALIAS_CACHE_TTL = 30.0
_ALIAS_CACHE_LOCK = threading.Lock()


def invalidate_alias_cache() -> None:
    """Počisti predpomnilnik aliasov (kliči ob spremembi/ustvarjanju šole)."""
    with _ALIAS_CACHE_LOCK:
        _ALIAS_CACHE.clear()
        _ALIAS_KIND_CACHE.clear()


def lookup_alias_kind(alias: str) -> str | None:
    """Vrni 'kind' registriranega aliasa ali None.

    Ključno za GOLI slug (npr. "ostcj"), kjer vrste ni mogoče izpeljati iz
    imena (za razliko od "nadomescanja_ostcj"). Prebere ustrezen
    SchoolAlias.kind; ni na voljo -> None. Predpomnjeno kot lookup_alias_school_id.
    """
    with _ALIAS_CACHE_LOCK:
        if alias in _ALIAS_KIND_CACHE:
            return _ALIAS_KIND_CACHE[alias]

    from app.database import SessionLocal
    from app.models import SchoolAlias

    kind = None
    db = SessionLocal()
    try:
        row = db.query(SchoolAlias).filter(SchoolAlias.alias == alias).first()
        kind = row.kind if row else None
    except Exception:
        return None
    finally:
        db.close()

    with _ALIAS_CACHE_LOCK:
        _ALIAS_KIND_CACHE[alias] = kind
    return kind


def resolve_alias_path(path: str) -> tuple[str | None, str | None]:
    """Kot parse_alias_path, a razreši tudi GOLI slug šole (npr. /ostcj → /zasloni).

    Zaporedje:
      1. Standardni <kind>_<slug> alias (parse_alias_path).
      2. Goli slug (en sam segment brez poševnice), če je registriran kot
         šolski alias z vrsto, ki kaže na /zasloni.

    Vrne (None, None), če nič od tega ni veljavno — poti ne spreminjamo.
    """
    alias, canonical = parse_alias_path(path)
    if alias and canonical:
        return alias, canonical

    if not path or not path.startswith("/"):
        return None, None
    trimmed = path.lstrip("/")
    if not trimmed or "/" in trimmed:
        return None, None
    first = trimmed
    kind = lookup_alias_kind(first)
    prefix = ALIAS_KINDS.get(kind) if kind else None
    if not prefix:
        return None, None
    return first, prefix


def lookup_alias_school_id(alias: str) -> int | None:
    """Vrni school_id za alias (iz predpomnilnika ali baze).

    Vrne None, če alias ne obstaja — takrat middleware poti NE prevede
    (in uporabnik dobi 404 namesto tujih podatkov).
    """
    now = time.time()
    with _ALIAS_CACHE_LOCK:
        cached = _ALIAS_CACHE.get(alias)
        if cached and now - cached[1] < _ALIAS_CACHE_TTL:
            return cached[0]

    from app.database import SessionLocal
    from app.models import SchoolAlias

    school_id = None
    db = SessionLocal()
    try:
        row = db.query(SchoolAlias).filter(SchoolAlias.alias == alias).first()
        school_id = row.school_id if row else None
    except Exception:
        return None
    finally:
        db.close()

    with _ALIAS_CACHE_LOCK:
        _ALIAS_CACHE[alias] = (school_id, now)
    return school_id


# ═══════════════════════════════════════════════════════════════════════
# SchoolConfig — nastavitve posamezne šole (baza + fallback na .env)
# ═══════════════════════════════════════════════════════════════════════

def env_default_settings() -> dict:
    """Privzete vrednosti nastavitev iz .env (uporabljene kot fallback).

    Te vrednosti so izhodišče: ob ustvarjanju šole jih preslikamo v tabelo
    school_settings, tako da jih lahko Šolski admin kasneje ureja v UI.
    """
    return {
        "MAIL_USERNAME": settings.MAIL_USERNAME,
        "MAIL_PASSWORD": settings.MAIL_PASSWORD,
        "MAIL_SERVER": settings.MAIL_SERVER,
        "MAIL_PORT": str(settings.MAIL_PORT),
        "MAIL_FROM": settings.MAIL_FROM,
        "BACKUP_EMAIL": settings.BACKUP_EMAIL,
        "STANJE_MAIL": settings.STANJE_MAIL,
        "ADMIN_EMAIL": settings.ADMIN_EMAIL,
        "TABLICE_MAX": str(settings.TABLICE_MAX),
        "SCHEDULE": json.dumps(settings.SCHEDULE, ensure_ascii=False),
        "POPOLDAN_SCHEDULE": json.dumps(settings.POPOLDAN_SCHEDULE, ensure_ascii=False),
        "PROSTORI_POPOLDAN": "",
        "PROSTORI_VODSTVO": "",
        "RAZREDI": ",".join(settings.RAZREDI),
        # Izbirni predmet (IP/NIP): privzeto noben razred; šola označi sama.
        "RAZREDI_IP": "",
        "PROSTORI": ",".join(settings.PROSTORI),
        "INACTIVITY_TIMEOUT_MINUTES": str(settings.INACTIVITY_TIMEOUT_MINUTES),
        "INACTIVITY_TIMEOUT_ADMIN_MINUTES": str(settings.INACTIVITY_TIMEOUT_ADMIN_MINUTES),
        "RESET_TOKEN_EXPIRATION_MINUTES": str(settings.RESET_TOKEN_EXPIRATION_MINUTES),
        "ASSESSMENT_MAX_PER_WEEK": str(ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_PER_WEEK"]),
        "ASSESSMENT_MAX_PER_DAY": str(ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_PER_DAY"]),
        "ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE": str(ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE"]),
        "ASSESSMENT_MAX_CONSECUTIVE_DAYS": str(ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_CONSECUTIVE_DAYS"]),
        # Digitalni zaslon
        "ZASLON_URL": "https://urniki.easistent.com/nadomescanja/d960638bb866d19b58f4e2de616db8eb56e73cfe",
        "ZASLON_POKAZI_NADOMESCANJA": "true",
        "ZASLON_CAS_OBVESTILA": "5",
        "ZASLON_MIN_CAS_TABELE": "2",
        "ZASLON_HITROST_DRSENJA": "1.2",
        "ZASLON_TIME_ZONE": "Europe/Ljubljana",
        "ZASLON_OSVEZI_AT": "",
        # Prazno → uporabijo se VSA obvestila iz vec_obvestil/ po vrsti.
        "ZASLON_OBVESTILA": "",
        "ZASLON_OBVESTILA_TEKST": "[]",
        # Govorilne ure privzeto omogočene (obstoječe šole se ne izklopijo).
        "GOVORILNE_OMOGOCENE": "true",
    }



class SchoolConfig:
    """Nastavitve ene šole.

    Bere vrednosti iz slovarja (tabela school_settings) in za manjkajoče
    ključe uporabi vrednosti iz .env — zato aplikacija deluje tudi, če v
    bazi ni (še) nič. ``school=None`` pomeni »brez šole« (globalni pogled);
    takrat se uporabijo izključno .env vrednosti, kar ohranja dosedanje
    vedenje za eno šolo.
    """

    def __init__(self, school=None, values: dict | None = None):
        self.school = school
        self._values = dict(values or {})
        self._env = env_default_settings()

    # ── Interni pomočniki ────────────────────────────────────────────
    def _raw(self, key: str):
        """Vrednost iz baze; prazen niz šteje kot »ni nastavljeno«."""
        value = self._values.get(key)
        if value is None or str(value).strip() == "":
            return None
        return str(value)

    def get_str(self, key: str, fallback: str = "") -> str:
        raw = self._raw(key)
        if raw is not None:
            return raw
        return self._env.get(key, fallback)

    def get_int(self, key: str, fallback: int) -> int:
        raw = self._raw(key)
        if raw is None:
            raw = self._env.get(key)
        try:
            return int(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return int(fallback)

    def get_list(self, key: str, fallback: list[str]) -> list[str]:
        raw = self._raw(key)
        if raw is None:
            raw = self._env.get(key)
        if raw is None:
            return list(fallback)
        return [x.strip() for x in str(raw).split(",") if x.strip()]

    def get_dict(self, key: str, fallback: dict) -> dict:
        raw = self._raw(key)
        if raw is None:
            raw = self._env.get(key)
        if raw is None:
            return dict(fallback)
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else dict(fallback)
        except (TypeError, ValueError):
            return dict(fallback)

    @property
    def school_id(self) -> int | None:
        return self.school.id if self.school else None

    # ── Seznami in urnik ─────────────────────────────────────────────
    @property
    def RAZREDI(self) -> list[str]:
        return self.get_list("RAZREDI", settings.RAZREDI)

    @property
    def RAZREDI_IP(self) -> set[str]:
        """Razredi, označeni kot »izbirni predmet« (IP/NIP)."""
        return set(self.get_list("RAZREDI_IP", []))

    @property
    def PROSTORI(self) -> list[str]:
        return self.get_list("PROSTORI", settings.PROSTORI)

    @property
    def STEVILA(self) -> dict:
        """Imenovane številske spremenljivke šole (ime → celo število).

        Shranjeno kot JSON objekt, npr. {"Število tablic": 28, "Število
        računalnikov": 30}. Ločen objekt omogoča, da šola doda poljubno
        število (ne le omejitve tablic) in da se prostori nanje vežejo
        (PROSTORI_STEVILO).

        Če v bazi ni zapisa, se vrne privzetek iz starega skalarnega
        TABLICE_MAX — tako je vedenje obstoječih šol nespremenjeno.
        """
        raw = self._raw("STEVILA")
        if raw is not None:
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                return self._normalize_numbers(parsed)
        return {DEFAULT_NUMBERS_NAME: self.TABLICE_MAX}

    @staticmethod
    def _normalize_numbers(values: dict) -> dict:
        """Obdrži samo vnose z imenom in celoštevilsko vrednostjo."""
        out: dict[str, int] = {}
        for key, value in values.items():
            name = str(key).strip()
            if not name:
                continue
            try:
                out[name] = int(value)
            except (TypeError, ValueError):
                continue
        return out

    @property
    def PROSTORI_STEVILO(self) -> dict:
        """Vezava prostor → ime številske spremenljivke (odgovarja STEVILA).

        Objekt, npr. {"tablice": "Število tablic", "racunalnica": "Število
        računalnikov"}. Prostor v tem objektu deluje »kot Tablice«: več
        učiteljev lahko rezervira hkrati, vsak navede količino, skupna vsota
        na uro pa je omejena z vrednostjo pripisane spremenljivke.

        Če PROSTORI_STEVILO ni nastavljen, se prebere zgodovinski seznam
        PROSTORI_QTY in vsak prostor veže na privzeto ime (»Število tablic«).
        """
        raw = self._raw("PROSTORI_STEVILO")
        if raw is not None:
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                out: dict[str, str] = {}
                for room, name in parsed.items():
                    room = str(room).strip()
                    if room:
                        out[room] = str(name).strip() if name is not None else ""
                return out
        # Nazajzdružljivost: star seznam prostorov brez imena spremenljivke.
        return {p: DEFAULT_NUMBERS_NAME for p in self._legacy_qty_rooms()}

    def _legacy_qty_rooms(self) -> list[str]:
        """Preberi staro nastavitev PROSTORI_QTY (seznam ali vejica-ločeno)."""
        raw = self._raw("PROSTORI_QTY")
        if raw is None:
            raw = self._env.get("PROSTORI_QTY", "tablice")
        if raw is None:
            return ["tablice"]
        text = str(raw).strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except (TypeError, ValueError):
                pass
        return [x.strip() for x in text.split(",") if x.strip()]

    @property
    def PROSTORI_QTY(self) -> list[str]:
        """Prostori, ki delujejo kot Tablice (imenovan seznam, za nazaj).

        Vrne imena prostorov iz PROSTORI_STEVILO. Ohranjeno zaradi združljivosti
        (API /api/prostori-qty, obstoječa koda in testi).
        """
        return list(self.PROSTORI_STEVILO.keys())

    def ima_kolicino(self, prostor: str) -> bool:
        """Ali prostor deluje kot Tablice (več uporabnikov, količina, omejitev).

        Zakaj predikat? Ker je bilo prej povsod trdo zapisano 'tablice'; zdaj se
        pravilo bere iz nastavitev šole, zato lahko šola doda npr. 'tablice2'.
        """
        return bool(prostor) and prostor in self.PROSTORI_STEVILO

    def kapaciteta(self, prostor: str) -> int:
        """Največja dovoljena skupna količina za prostor v eni uri.

        Bere vrednost pripisane številske spremenljivke (STEVILA); če prostor
        ni vezan ali spremenljivka ne obstaja, pade nazaj na TABLICE_MAX.
        """
        name = self.PROSTORI_STEVILO.get(prostor)
        stevila = self.STEVILA
        if name and name in stevila:
            return int(stevila[name])
        return self.TABLICE_MAX

    @property
    def SCHEDULE(self) -> dict:
        return self.get_dict("SCHEDULE", settings.SCHEDULE)

    @property
    def POPOLDAN_SCHEDULE(self) -> dict:
        """Popoldanski urnik (ura → opis), privzeto termini 15:00–21:00."""
        return self.get_dict("POPOLDAN_SCHEDULE", settings.POPOLDAN_SCHEDULE)

    @property
    def PROSTORI_POPOLDAN(self) -> list[str]:
        """Prostori, ki uporabljajo POPOLDANSKI urnik (ne šolskega dopoldanskega)."""
        return self.get_list("PROSTORI_POPOLDAN", [])

    def je_popoldan(self, prostor: str | None) -> bool:
        """Ali prostor uporablja popoldanski urnik."""
        return bool(prostor) and str(prostor) in self.PROSTORI_POPOLDAN

    @property
    def PROSTORI_VODSTVO(self) -> list[str]:
        """Prostori, ki so vidni in rezervabilni samo za vodstvo/admin.

        Navadni učitelji teh prostorov sploh ne vidijo (in jih ne morejo
        rezervirati); glavni admin jih vidi vedno.
        """
        return self.get_list("PROSTORI_VODSTVO", [])

    def je_vodstvo_prostor(self, prostor: str | None) -> bool:
        """Ali je prostor omejen le na vodstvo/admin."""
        return bool(prostor) and str(prostor) in self.PROSTORI_VODSTVO

    def schedule_for(self, prostor: str | None) -> dict:
        """Urnik (ura → opis) za dani prostor.

        Če je prostor označen kot popoldanski (PROSTORI_POPOLDAN) in ima šola
        popoldanski urnik, vrne tega; sicer vrne šolski (dopoldanski) urnik.
        """
        if prostor and self.je_popoldan(prostor):
            sched = self.POPOLDAN_SCHEDULE
            if sched:
                return sched
        return self.SCHEDULE

    def max_hour(self, prostor: str | None = None) -> int:
        """Najvišja dovoljena ura za prostor.

        Popoldanski prostori: največji ključ POPOLDAN_SCHEDULE (npr. 5 = 20:00–21:00).
        Ostali: največji ključ šolskega urnika, a vsaj 7 (ohrani obstoječe vedenje).
        """
        if self.je_popoldan(prostor) and self.POPOLDAN_SCHEDULE:
            sched = self.POPOLDAN_SCHEDULE
            top = 0
        else:
            sched = self.SCHEDULE
            top = 7
        for key in (sched or {}).keys():
            try:
                top = max(top, int(str(key).strip()))
            except (TypeError, ValueError):
                continue
        return top

    # ── Kapaciteta in timeouti ───────────────────────────────────────
    @property
    def TABLICE_MAX(self) -> int:
        return self.get_int("TABLICE_MAX", settings.TABLICE_MAX)

    @property
    def INACTIVITY_TIMEOUT_MINUTES(self) -> int:
        return self.get_int("INACTIVITY_TIMEOUT_MINUTES", settings.INACTIVITY_TIMEOUT_MINUTES)

    @property
    def INACTIVITY_TIMEOUT_ADMIN_MINUTES(self) -> int:
        return self.get_int("INACTIVITY_TIMEOUT_ADMIN_MINUTES", settings.INACTIVITY_TIMEOUT_ADMIN_MINUTES)

    @property
    def RESET_TOKEN_EXPIRATION_MINUTES(self) -> int:
        return self.get_int("RESET_TOKEN_EXPIRATION_MINUTES", settings.RESET_TOKEN_EXPIRATION_MINUTES)

    # ── E-pošta ──────────────────────────────────────────────────────
    @property
    def MAIL_FROM(self) -> str:
        return self.get_str("MAIL_FROM", settings.MAIL_FROM)

    @property
    def MAIL_USERNAME(self) -> str:
        return self.get_str("MAIL_USERNAME", settings.MAIL_USERNAME)

    @property
    def MAIL_PASSWORD(self) -> str:
        return self.get_str("MAIL_PASSWORD", settings.MAIL_PASSWORD)

    @property
    def MAIL_SERVER(self) -> str:
        return self.get_str("MAIL_SERVER", settings.MAIL_SERVER)

    @property
    def MAIL_PORT(self) -> int:
        return self.get_int("MAIL_PORT", settings.MAIL_PORT)

    @property
    def BACKUP_EMAIL(self) -> str:
        return self.get_str("BACKUP_EMAIL", settings.BACKUP_EMAIL)

    @property
    def STANJE_MAIL(self) -> str:
        return self.get_str("STANJE_MAIL", settings.STANJE_MAIL)

    @property
    def ADMIN_EMAIL(self) -> str:
        return self.get_str("ADMIN_EMAIL", settings.ADMIN_EMAIL)

    # ── Pravila ocenjevanja (nastavljiva po šoli) ────────────────────
    @property
    def ASSESSMENT_MAX_PER_WEEK(self) -> int:
        return self.get_int("ASSESSMENT_MAX_PER_WEEK", ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_PER_WEEK"])

    @property
    def ASSESSMENT_MAX_PER_DAY(self) -> int:
        return self.get_int("ASSESSMENT_MAX_PER_DAY", ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_PER_DAY"])

    @property
    def ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE(self) -> int:
        return self.get_int(
            "ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE",
            ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE"],
        )

    @property
    def ASSESSMENT_MAX_CONSECUTIVE_DAYS(self) -> int:
        return self.get_int(
            "ASSESSMENT_MAX_CONSECUTIVE_DAYS",
            ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_CONSECUTIVE_DAYS"],
        )

    def effective_values(self) -> dict:
        """Vse ključe z dejansko veljavno vrednostjo (baza ali .env)."""
        return {key: self.get_str(key, self._env.get(key, "")) for key in SCHOOL_SETTING_KEYS}


# ═══════════════════════════════════════════════════════════════════════
# Branje/pisanje nastavitev v bazi
# ═══════════════════════════════════════════════════════════════════════

def get_school_settings_map(db: Session, school_id: int | None) -> dict:
    """Preberi vse nastavitve šole kot slovar key → value."""
    if school_id is None:
        return {}
    from app.models import SchoolSetting
    rows = db.query(SchoolSetting).filter(SchoolSetting.school_id == school_id).all()
    return {r.key: r.value for r in rows}


def get_school_config(db: Session, school_id: int | None) -> SchoolConfig:
    """Vrni SchoolConfig za šolo (ali globalnega, če school_id ni podan)."""
    if school_id is None:
        return SchoolConfig(None, {})
    from app.models import School
    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        return SchoolConfig(None, {})
    return SchoolConfig(school, get_school_settings_map(db, school_id))


def set_school_setting(db: Session, school_id: int, key: str, value: str | None) -> None:
    """Nastavi (ali posodobi) eno nastavitev šole."""
    from app.models import SchoolSetting
    if key not in SCHOOL_SETTING_KEYS:
        raise ValueError(f"Neznana nastavitev: {key}")
    row = db.query(SchoolSetting).filter(
        SchoolSetting.school_id == school_id, SchoolSetting.key == key
    ).first()
    text = "" if value is None else str(value)
    if row is None:
        db.add(SchoolSetting(school_id=school_id, key=key, value=text))
    else:
        row.value = text


def seed_school_settings(db: Session, school_id: int, defaults: dict | None = None) -> int:
    """Napolni nastavitve šole iz privzetih vrednosti — samo manjkajoče ključe.

    Zakaj samo manjkajoče? Da ob vsakem zagonu ne povozimo vrednosti, ki
    jih je Šolski admin že uredil v UI.

    ``defaults`` privzeto iz .env (obstoječe/privzete šole); ob ustvarjanju
    NOVE šole klicatelj poda jezikovno občutljive privzetke
    (``default_new_school_settings``).
    """
    from app.models import SchoolSetting
    existing = {r.key for r in db.query(SchoolSetting).filter(SchoolSetting.school_id == school_id).all()}
    defaults = env_default_settings() if defaults is None else defaults
    added = 0
    for key, value in defaults.items():
        if key not in existing:
            db.add(SchoolSetting(school_id=school_id, key=key, value=value))
            added += 1
    return added


# ═══════════════════════════════════════════════════════════════════════
# Šole
# ═══════════════════════════════════════════════════════════════════════

def create_school(
    db: Session,
    name: str,
    slug: str | None = None,
    aliases: list[str] | None = None,
    extra_aliases: list[str] | None = None,
    ui_language: str = "sl",
) -> "object":
    """Ustvari novo šolo z aliasi in privzetimi nastavitvami.

    Args:
        name: Polno ime šole (npr. "OŠ Toneta Čufarja Jesenice").
        slug: Kratka oznaka (npr. "ostcj"). Če ni podana, se naredi iz imena.
        aliases: Eksplicitni seznam aliasov (npr. ["rezervacije_xyz"]).
        extra_aliases: Dodatni (zgodovinski) aliasi poleg generiranih.

    Vrne School. Dvigne ValueError, če slug/alias že obstaja.
    """
    from app.models import School, SchoolAlias

    slug = (slug or slugify(name)).strip().lower()
    if db.query(School).filter(School.slug == slug).first():
        raise ValueError(f"Šola s slugom '{slug}' že obstaja.")

    school = School(slug=slug, name=name.strip(), is_active=True)
    db.add(school)
    db.flush()

    pairs: list[tuple[str, str]] = []
    if aliases:
        for alias in aliases:
            parsed_kind = _alias_kind_for(alias)
            if parsed_kind:
                pairs.append((alias, parsed_kind))
    else:
        pairs.extend(generate_aliases(slug))
    for alias in (extra_aliases or []):
        parsed_kind = _alias_kind_for(alias)
        if parsed_kind:
            pairs.append((alias, parsed_kind))

    seen: set[str] = set()
    for alias, kind in pairs:
        if alias in seen:
            continue
        seen.add(alias)
        if db.query(SchoolAlias).filter(SchoolAlias.alias == alias).first():
            raise ValueError(f"Alias '{alias}' je že zaseden.")
        db.add(SchoolAlias(school_id=school.id, alias=alias, kind=kind))

    seed_school_settings(db, school.id, default_new_school_settings(ui_language))
    # Jezik vmesnika nove šole = jezik registracijske povezave
    # (»Nova šola« → sl, »New school« → en).
    if ui_language in ("sl", "en"):
        set_school_setting(db, school.id, "UI_LANGUAGE", ui_language)
    db.commit()
    db.refresh(school)
    invalidate_alias_cache()
    return school


def add_school_alias(db: Session, school_id: int, alias: str) -> "object":
    """Dodaj alias šoli (npr. dodatna pot za isto šolo)."""
    from app.models import SchoolAlias
    alias = (alias or "").strip().strip("/")
    kind = _alias_kind_for(alias)
    if not kind:
        raise ValueError(
            "Alias mora imeti obliko 'rezervacije_<oznaka>' ali 'ocenjevanje_<oznaka>'."
        )
    if db.query(SchoolAlias).filter(SchoolAlias.alias == alias).first():
        raise ValueError(f"Alias '{alias}' je že zaseden.")
    row = SchoolAlias(school_id=school_id, alias=alias, kind=kind)
    db.add(row)
    db.commit()
    db.refresh(row)
    invalidate_alias_cache()
    return row


def remove_school_alias(db: Session, school_id: int, alias: str) -> None:
    """Odstrani alias šole (npr. podvojen/zgodovinski alias)."""
    from app.models import SchoolAlias
    alias = (alias or "").strip().strip("/")
    row = db.query(SchoolAlias).filter(
        SchoolAlias.school_id == school_id, SchoolAlias.alias == alias
    ).first()
    if row is None:
        raise ValueError(f"Alias '{alias}' ne obstaja pri tej šoli.")
    db.delete(row)
    db.commit()
    invalidate_alias_cache()


def _alias_kind_for(alias: str) -> str | None:
    """Vrni vrsto ('rezervacije'/'ocenjevanje') iz imena aliasa."""
    match = _ALIAS_RE.match((alias or "").strip())
    return match.group(1) if match else None


def delete_school_data(db: Session, school) -> dict:
    """Izbriše VSE podatke ene šole in šolo samo (samo glavni admin).

    Vrstni red je pomemben zaradi tujih ključev:
      1. podatki, ki kažejo na uporabnike/šolo (rezervacije, ocenjevanja,
         blokade, dejavnosti),
      2. dnevnik dogodkov TE šole,
      3. uporabniki in njihove nastavitve/aliasi,
      4. šola.
    Dnevnik dogodkov, ki šoli ne pripada (school_id je NULL), se NE briše —
    tam se user_id na brisane uporabnike samo počisti (username ostane
    zapisan), da ne pade tuji ključ in da zgodovina ostane berljiva.

    Vrne slovar {tabela: število izbrisanih vrstic}.
    """
    from app.models import (
        ActivityDay, Assessment, AuditLog, BlockedDate, Reservation,
        SchoolAlias, SchoolSetting, User,
    )
    from sqlalchemy import select

    sid = int(school.id)
    counts: dict[str, int] = {}

    for model, name in (
        (Reservation, "reservations"),
        (Assessment, "assessments"),
        (BlockedDate, "blocked_dates"),
        (ActivityDay, "activity_days"),
    ):
        counts[name] = db.query(model).filter(model.school_id == sid).delete(
            synchronize_session=False
        ) or 0

    counts["audit_log"] = db.query(AuditLog).filter(AuditLog.school_id == sid).delete(
        synchronize_session=False
    ) or 0

    # Dnevnik z school_id = NULL, ki kaže na uporabnike te šole: sklopi vez
    # (username ostane), da brisanje uporabnikov ne pade na tujem ključu.
    user_ids = select(User.id).where(User.school_id == sid)
    db.query(AuditLog).filter(AuditLog.user_id.in_(user_ids)).update(
        {"user_id": None}, synchronize_session=False
    )

    counts["users"] = db.query(User).filter(User.school_id == sid).delete(
        synchronize_session=False
    ) or 0
    counts["school_settings"] = db.query(SchoolSetting).filter(
        SchoolSetting.school_id == sid
    ).delete(synchronize_session=False) or 0
    counts["school_aliases"] = db.query(SchoolAlias).filter(
        SchoolAlias.school_id == sid
    ).delete(synchronize_session=False) or 0

    db.delete(school)
    db.flush()
    invalidate_alias_cache()
    return counts


def primary_admin(db: Session, school_id: int):
    """Glavni (primarni) admin račun šole — najstarejši, tj. najnižji id.

    Zakaj samo eden? V bazi velja UNIQUE (school_id, email), zato istega naslova
    ne moreta imeti dva uporabnika iste šole. Naslov iz nastavitve ADMIN_EMAIL
    zato nosi natanko ta račun (v ostcj je to admin_ostcj); morebitni dodatni
    admin računi ostanejo brez e-pošte.
    """
    from app.models import RoleEnum, User

    return db.query(User).filter(
        User.school_id == school_id,
        User.role == RoleEnum.admin.value,
    ).order_by(User.id).first()


def sync_admin_user_email(db: Session, school_id: int, email: str | None) -> tuple[list[str], str | None]:
    """Uskladi e-pošto GLAVNEGA ADMIN računa šole z nastavitvijo ADMIN_EMAIL.

    Pravilo (zahteva uporabnika 2026-09-23): šolski admin (npr. admin_ostcj) mora
    imeti VEDNO tisto e-pošto, ki je določena v nastavitvi ADMIN_EMAIL — in je
    drugače ni mogoče spremeniti, le prek nastavitev šole.

    Zakaj tako? E-pošta admina je naslov, kamor gredo sistemska sporočila
    (obvestila, ponastavitev gesla). Če bi se nastavitev in uporabniški račun
    razšla, bi pošta šla na en naslov, ponastavitev gesla pa na drugega.

    Podatkovna omejitev: UNIQUE (school_id, email) — zato istega naslova ne
    moreta imeti dva uporabnika. Če naslov že uporablja NEKI DRUGI uporabnik
    (npr. ločen račun vodstva z istim AAI naslovom), ga ne moremo prepisati;
    vrnemo konflikt, da klicatelj uporabniku POVE, kaj naj uredi (prej je to
    povzročilo neuspešno shranjevanje brez razlage).

    Vrne (spremembe, konflikt):
      * spremembe — opisi, npr. ["admin_ostcj: a@b → c@d"]
      * konflikt — besedilo napake ali None
    """
    from app.models import User

    email = (email or "").strip() or None
    admin = primary_admin(db, school_id)
    if admin is None:
        return [], None

    if email:
        holder = db.query(User).filter(
            User.school_id == school_id,
            User.email == email,
        ).first()
        if holder is not None and holder.id != admin.id:
            return [], (
                f"naslov {email} že uporablja uporabnik »{holder.username}« "
                f"(e-pošta mora biti prosta, ker je v bazi unikatna znotraj šole)"
            )

    if (admin.email or None) != email:
        return [f"{admin.username}: {admin.email or '-'} → {email or '-'}"], None
    return [], None


def apply_admin_email(db: Session, school_id: int, email: str | None) -> bool:
    """Zapiši e-pošto v glavni admin račun šole. Vrne True, če je bila sprememba."""
    admin = primary_admin(db, school_id)
    if admin is None:
        return False
    new_value = (email or "").strip() or None
    if (admin.email or None) != new_value:
        admin.email = new_value
        return True
    return False


def admin_email_for_user(db: Session, user) -> str | None:
    """Kateri naslov naj nosi TA admin račun.

    Naslov iz nastavitve ADMIN_EMAIL nosi le GLAVNI (najstarejši) admin račun
    šole — ker velja UNIQUE (school_id, email), ga drugi admin računi ne morejo
    imeti. Zato:
      * glavni admin → naslov iz nastavitev (ali None, če ga zaseda drug račun),
      * drugi admin računi → None.
    """
    from app.models import User

    primary = primary_admin(db, user.school_id)
    if primary is None or primary.id != user.id:
        return None
    desired = (get_school_config(db, user.school_id).ADMIN_EMAIL or "").strip() or None
    if not desired:
        return None
    if (user.email or None) == desired:
        return desired
    holder = db.query(User).filter(
        User.school_id == user.school_id,
        User.email == desired,
        User.id != user.id,
    ).first()
    return None if holder is not None else desired


def admin_email_for_new_user(db: Session, school_id: int) -> str | None:
    """Naslov iz nastavitve ADMIN_EMAIL, če je prost — sicer None.

    Uporabimo ga pri USTVARJANJU/UVOZU admin računa. Če naslov že uporablja
    drug uporabnik te šole (UNIQUE school_id+email), nov račun dobi None
    (brez e-pošte), namesto da bi shranjevanje padlo.
    """
    from app.models import User

    email = (get_school_config(db, school_id).ADMIN_EMAIL or "").strip() or None
    if not email:
        return None
    holder = db.query(User).filter(
        User.school_id == school_id, User.email == email
    ).first()
    return None if holder is not None else email


def aliases_by_kind(db: Session, school_id: int) -> dict[str, str]:
    """Vrni {'rezervacije': 'rezervacije_st', 'ocenjevanje': 'ocenjevanje_st'}.

    Uporabi se za ohranjanje poti šole pri prehajanju med zavihki: kdor vstopi
    prek poti šole, mora na njej tudi ostati.
    """
    from app.models import SchoolAlias
    result: dict[str, str] = {}
    rows = db.query(SchoolAlias).filter(SchoolAlias.school_id == school_id).all()
    for row in rows:
        kind = row.kind or _alias_kind_for(row.alias)
        if kind and kind not in result:
            # Prva (najstarejša) zmaga — to je privzeta, generirana pot.
            result[kind] = row.alias
    return result


def nav_paths(db: Session, request, school_id: int | None = None) -> dict[str, str]:
    """Poti za glavne zavihke, odvisno od tega, kako je uporabnik vstopil.

    Če je zahtevek prišel prek poti šole (npr. /rezervacije_st), ostanejo poti
    na poti te šole — klik na »Ocenjevanje« mora voditi na /ocenjevanje_st in ne
    na /ocenjevanje, sicer se oznaka šole v naslovu izgubi.

    Če je uporabnik vstopil po kanonični poti, ostanejo kanonične poti
    (vedenje se ne spremeni).
    """
    canonical = {kind: path for kind, path in ALIAS_KINDS.items()}
    alias = getattr(getattr(request, "state", None), "school_alias", None)
    if not alias or school_id is None:
        return canonical
    mapping = aliases_by_kind(db, school_id)
    return {
        kind: (f"/{mapping[kind]}" if mapping.get(kind) else path)
        for kind, path in canonical.items()
    }


def ensure_default_school(db: Session) -> "object":
    """Poskrbi, da privzeta šola (ostcj) obstaja — skupaj z aliasi.

    Idempotentno: če šola že obstaja, ne naredi nič (razen dopolni
    manjkajoče nastavitve).
    """
    from app.models import School

    slug = settings.DEFAULT_SCHOOL_SLUG
    school = db.query(School).filter(School.slug == slug).first()
    if school is None:
        school = School(slug=slug, name=settings.SCHOOL_NAME, is_active=True)
        db.add(school)
        db.flush()
        # Aliasi: generirani iz sluga + morebitni dodatni (zgodovinski) iz .env.
        alias_map: dict[str, str] = dict(generate_aliases(slug))
        for extra in settings.DEFAULT_SCHOOL_ALIASES:
            kind = _alias_kind_for(extra)
            if kind:
                alias_map[extra] = kind
        from app.models import SchoolAlias
        for alias, kind in alias_map.items():
            if not db.query(SchoolAlias).filter(SchoolAlias.alias == alias).first():
                db.add(SchoolAlias(school_id=school.id, alias=alias, kind=kind))
        db.commit()
        db.refresh(school)
        invalidate_alias_cache()

    # Backfill: za VSE obstoječe šole dopolni manjkajoče generirane aliase
    # (npr. ko naknadno dodamo novo vrsto 'nadomescanja', obstoječe šole
    # samodejno dobijo svojo kratko /nadomescanja_<slug> pot).
    from app.models import School as _SchoolRow, SchoolAlias as _SAAlias
    _aliases_changed = False
    for _sch in db.query(_SchoolRow).all():
        for _alias, _kind in dict(generate_aliases(_sch.slug)).items():
            if not db.query(_SAAlias).filter(_SAAlias.alias == _alias).first():
                db.add(_SAAlias(school_id=_sch.id, alias=_alias, kind=_kind))
                _aliases_changed = True
    if _aliases_changed:
        invalidate_alias_cache()

    seed_school_settings(db, school.id)
    db.commit()
    return school


# ═══════════════════════════════════════════════════════════════════════
# Določitev obsega podatkov pri zahtevku
# ═══════════════════════════════════════════════════════════════════════

def get_request_user(request, db: Session):
    """Vrni prijavljenega uporabnika (ali None, če ni prijavljen)."""
    from app.models import User
    user_id = get_current_user_id(request)
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id)).first()


def role_value(user) -> str:
    """Vrni vlogo uporabnika kot niz: "admin", "vodstvo", "teacher", "main_admin".

    Zakaj ne preprosto str(user.role)? Ker je RoleEnum definiran kot
    (str, enum.Enum), zato str(RoleEnum.admin) vrne "RoleEnum.admin" in ne
    "admin". Ta pomočnik vrne pravo vrednost, ki jo primerjamo z konstantami.
    """
    role = getattr(user, "role", None)
    if role is None:
        return ""
    return getattr(role, "value", None) or str(role)


def is_main_admin(user) -> bool:
    """Ali je uporabnik glavni admin (vidi vse šole)?"""
    if user is None:
        return False
    return role_value(user) == MAIN_ADMIN_ROLE


def is_school_admin(user) -> bool:
    """Ali je uporabnik šolski admin (skrbnik svoje šole)?"""
    if user is None:
        return False
    return role_value(user) == SCHOOL_ADMIN_ROLE


def user_may_see_prostor(user, prostor, config) -> bool:
    """Ali uporabnik lahko vidi (in rezervira) prostor?

    Prostori iz PROSTORI_VODSTVO so vidni samo šolskemu adminu, vodstvu in
    glavnemu adminu; navadni učitelji (in neprijavljeni) zanje sploh ne
    vedo. Neprivilegiran uporabnik dobi False tudi za neznane prostore.
    """
    if config is None or not config.je_vodstvo_prostor(prostor):
        return True
    return role_value(user) in (SCHOOL_ADMIN_ROLE, "vodstvo", MAIN_ADMIN_ROLE)


def vidni_prostori(config, user) -> list[str]:
    """Prostori šole, ki so vidni danemu uporabniku (filtrira PROSTORI_VODSTVO)."""
    return [p for p in config.PROSTORI if user_may_see_prostor(user, p, config)]


def request_school_id(request) -> int | None:
    """Šola, določena iz URL-aliasa (nastavi jo middleware)."""
    state = getattr(request, "state", None)
    value = getattr(state, "school_id", None) if state is not None else None
    if value is None:
        # Fallback: glavni admin si lahko šolo izbere s piškotkom school_ctx.
        raw = request.cookies.get("school_ctx")
        if raw and str(raw).isdigit():
            return int(raw)
    return value


def resolve_school_context(request, db: Session):
    """Vrni (school_id, school) — kontekst trenutnega zahtevka.

    Vrstni red:
      1. Šola prijavljenega uporabnika (trdna meja za šolske vloge).
      2. URL-alias / piškotek school_ctx (samo glavni admin).
    """
    from app.models import School

    user = get_request_user(request, db)
    if user is not None and user.school_id:
        # Obseg šolske vloge je vedno njena šola. Če piškotek/alias kaže na
        # DRUGO šolo, zahteve ne izvedemo (varnost: tuja šola ni dostopna), a
        # dodamo navodilo — takšno stanje nastane, ko v istem brskalniku ostane
        # seja uporabnika druge šole (glej tudi registracijo, ki piškotek
        # nastavi, in odjavo, ki ga pobriše).
        ctx = request_school_id(request)
        if ctx is not None and ctx != user.school_id:
            raise HTTPException(
                status_code=403,
                detail=("Nimate dostopa do podatkov te šole. Vaša seja je iz "
                        "druge šole — odjavite se in se prijavite znova."),
            )
        school = db.query(School).filter(School.id == user.school_id).first()
        return user.school_id, school

    ctx = request_school_id(request)
    if ctx is not None:
        school = db.query(School).filter(School.id == ctx).first()
        if school is not None:
            return school.id, school
    return None, None


def data_school_id(request, db: Session) -> int | None:
    """Obseg branja: school_id ali None (= vse šole; samo glavni admin).

    Za šolske uporabnike vrne njihovo šolo. Za glavnega admina vrne
    izbrano šolo (alias/piškotek) ali None, kar pomeni »vse šole«.
    """
    user = get_request_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    if is_main_admin(user):
        return request_school_id(request)
    if not user.school_id:
        # Šolski uporabnik brez šole (legacy) — omejimo na privzeto šolo,
        # da ne vidi podatkov drugih šol.
        return _default_school_id(db)
    # Obseg branja je vedno šola uporabnika; navedba druge šole (alias ali
    # zastarel piškotek) se zavrne z navodilom, kako naprej.
    ctx = request_school_id(request)
    if ctx is not None and ctx != user.school_id:
        raise HTTPException(
            status_code=403,
            detail=("Nimate dostopa do podatkov te šole. Vaša seja je iz druge "
                    "šole — odjavite se in se prijavite znova."),
        )
    return user.school_id


def write_school_id(request, db: Session) -> int:
    """Šola, v katero se zapisuje. Nikoli ne vrne None.

    Za šolske uporabnike: njihova šola. Za glavnega admina: izbrana šola
    (alias/piškotek) — brez izbire je pisanje zavrnjeno, ker ne vemo, kam
    naj zapis pripada.
    """
    user = get_request_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    if user.school_id:
        # Pisanje gre v šolo uporabnika; navedba druge šole se zavrne.
        ctx = request_school_id(request)
        if ctx is not None and ctx != user.school_id:
            raise HTTPException(
                status_code=403,
                detail=("Nimate dostopa do podatkov te šole. Vaša seja je iz "
                        "druge šole — odjavite se in se prijavite znova."),
            )
        return user.school_id
    if is_main_admin(user):
        ctx = request_school_id(request)
        if ctx is not None:
            return ctx
        raise HTTPException(
            status_code=400,
            detail=(
                "Glavni admin mora izbrati šolo v spustnem seznamu »Šola« na vrhu "
                "strani (ali odpreti pot šole, npr. /rezervacije_<oznaka>)."
            ),
        )
    default_id = _default_school_id(db)
    if default_id is None:
        raise HTTPException(status_code=400, detail="Nobena šola še ne obstaja.")
    return default_id


def config_for_request(request, db: Session) -> SchoolConfig:
    """SchoolConfig za trenutni zahtevek (nastavitve šole + fallback na .env)."""
    school_id, school = resolve_school_context(request, db)
    if school is None:
        return SchoolConfig(None, {})
    return SchoolConfig(school, get_school_settings_map(db, school_id))


def default_config() -> SchoolConfig:
    """Konfiguracija brez šole (samo .env) — za kontekste brez zahtevka."""
    return SchoolConfig(None, {})


def _default_school_id(db: Session) -> int | None:
    from app.models import School
    school = db.query(School).filter(School.slug == settings.DEFAULT_SCHOOL_SLUG).first()
    return school.id if school else None


def scope(query, model, school_id: int | None):
    """Dodaj filter school_id na poizvedbo (None = brez filtra = vse šole)."""
    if school_id is None:
        return query
    return query.filter(model.school_id == school_id)


# ═══════════════════════════════════════════════════════════════════════
# Iskanje uporabnika pri prijavi
# ═══════════════════════════════════════════════════════════════════════

def find_user_for_login(db: Session, request, identifier: str, *, active_only: bool = True):
    """Poišči uporabnika po username ALI email za prijavo.

    Pravila:
      - Najprej TOČNO ujemanje (nespremenjeno dosedanje vedenje).
      - Če ni zadetka, tolerantno ujemanje: brez velikih/malih črk in brez
        odvečnih presledkov. Zakaj? E-pošta je po standardu neobčutljiva na
        velikost črk, uporabniki pa pogosto vtipkajo drugačno velikost ali
        prilepijo presledek — takrat prijava ne sme pasti z »napačno geslo«.
      - Če je zahtevek vezan na šolo (URL-alias), se išče znotraj te šole
        (+ glavni admin, ki nima šole).
      - Sicer se išče globalno. Če se najde več različnih uporabnikov
        (enako ime v več šolah), prijava ni mogoča brez konteksta šole —
        dvigne se 400 z jasnim sporočilom.
    """
    from sqlalchemy import func
    from app.models import User

    ident = (identifier or "").strip()
    # Za prijavo upoštevamo SAMO pot šole (URL-alias), ne piškotka school_ctx:
    # piškotek hrani le, katero šolo gleda prejšnji uporabnik, zato je ob
    # zastareli vrednosti (npr. po registraciji nove šole) prijava iz druge šole
    # ne bi bila mogoča (uporabnik se ne bi našel).
    _state = getattr(request, "state", None)
    school_id = getattr(_state, "school_id", None) if _state is not None else None

    def _base():
        query = db.query(User)
        if active_only:
            query = query.filter(User.is_active == True)  # noqa: E712
        if school_id is not None:
            query = query.filter((User.school_id == school_id) | (User.school_id.is_(None)))
        return query

    matches = _base().filter((User.username == ident) | (User.email == ident)).all()
    if not matches:
        low = ident.lower()
        matches = _base().filter(
            (func.lower(User.username) == low) | (func.lower(User.email) == low)
        ).all()

    if len(matches) > 1:
        # Preferiraj glavnega admina, če je med zadetki (globalni račun).
        main_admins = [u for u in matches if role_value(u) == MAIN_ADMIN_ROLE]
        if len(main_admins) == 1:
            return main_admins[0]
        raise HTTPException(
            status_code=400,
            detail="Uporabniško ime obstaja v več šolah. Odprite povezavo svoje šole.",
        )
    return matches[0] if matches else None


# ═══════════════════════════════════════════════════════════════════════
# Bootstrap
# ═══════════════════════════════════════════════════════════════════════

def bootstrap_tenancy(db: Session) -> "object":
    """Ob zagonu: privzeta šola, glavni admin, priklop obstoječih podatkov.

    Idempotentno — varno za vsak zagon aplikacije.
    """
    from app.models import School, User, RoleEnum
    from app.audit import log_audit
    # Uvoz na ZAČETKU funkcije: prej je bil le znotraj veje za glavnega admina,
    # zato je ob obstoječem glavnem adminu (in manjkajočem šolskem) spodaj
    # vrglo UnboundLocalError »CryptContext«.
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    school = ensure_default_school(db)

    # 1) Glavni admin (mi) — globalni račun brez šole.
    main_admin = db.query(User).filter(User.username == settings.MAIN_ADMIN_USERNAME).first()
    if main_admin is None:
        main_admin = User(
            username=settings.MAIN_ADMIN_USERNAME,
            email=settings.MAIN_ADMIN_EMAIL or None,
            first_name="Glavni",
            last_name="Admin",
            password_hash=pwd_context.hash(settings.MAIN_ADMIN_PASSWORD),
            role=MAIN_ADMIN_ROLE,
            is_active=True,
            school_id=None,
        )
        db.add(main_admin)
        db.commit()

    # 2) Šolski admin privzete šole.
    #    Uporabniško ime je VEZANO NA ŠOLO: admin_<oznaka> (npr. "admin_ostcj"),
    #    ker golo ime "admin" pri več šolah ni več smiselno (v vsaki šoli je
    #    svoj admin). Če je v bazi še staro ime "admin", ga preimenujemo —
    #    geslo in vse ostalo ostane nedotaknjeno.
    admin_username = default_school_admin_username(school.slug)
    school_admin = db.query(User).filter(
        User.school_id == school.id, User.role == RoleEnum.admin
    ).order_by(User.id).first()
    if school_admin is None:
        # Zgodovinsko ime "admin" (nastalo pred večšolsko prenovo).
        school_admin = db.query(User).filter(User.username == "admin").first()

    if school_admin is None:
        school_admin = User(
            username=admin_username,
            email=settings.ADMIN_EMAIL or None,
            first_name="Admin",
            last_name="OŠ",
            password_hash=pwd_context.hash("admin123"),
            role=SCHOOL_ADMIN_ROLE,
            is_active=True,
            school_id=school.id,
        )
        db.add(school_admin)
        db.commit()
    else:
        changed = False
        if school_admin.school_id is None:
            school_admin.school_id = school.id
            changed = True
        # Preimenovanje generičnega "admin" → "admin_<oznaka>" (enkratno).
        if school_admin.username == "admin" and admin_username != "admin":
            taken = db.query(User).filter(
                User.school_id == school.id, User.username == admin_username
            ).first()
            if taken is None:
                old_name = school_admin.username
                school_admin.username = admin_username
                changed = True
                log_audit(
                    db, user_id=school_admin.id, username=admin_username,
                    action="rename_school_admin",
                    details=f"'{old_name}' → '{admin_username}' (šolski admin vezan na šolo {school.slug})",
                    school_id=school.id,
                )
        if changed:
            db.commit()

    # 3) Migracija obstoječih podatkov na privzeto šolo (samo NULL vrednosti).
    backfill_school_id(db, school)

    return school


def backfill_school_id(db: Session, school) -> dict:
    """Pripiši obstoječe zapise (school_id IS NULL) privzeti šoli.

    Zakaj: pred večšolsko prenovo tabela ni imela school_id. Brez tega
    koraka bi bili stari podatki za šolske uporabnike nevidni.
    Glavni admin ima school_id NULL namerno in je izvzet.
    """
    from sqlalchemy import text as sql_text

    counts = {}
    tables = ["reservations", "assessments", "blocked_dates", "activity_days", "audit_log"]
    for table in tables:
        result = db.execute(
            sql_text(f"UPDATE {table} SET school_id = :sid WHERE school_id IS NULL"),
            {"sid": school.id},
        )
        counts[table] = result.rowcount or 0

    result = db.execute(
        sql_text(
            "UPDATE users SET school_id = :sid "
            "WHERE school_id IS NULL AND role <> :main_role"
        ),
        {"sid": school.id, "main_role": MAIN_ADMIN_ROLE},
    )
    counts["users"] = result.rowcount or 0
    db.commit()
    return counts
