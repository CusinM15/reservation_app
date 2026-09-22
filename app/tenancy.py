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
}

# Regex prepozna alias v prvem segmentu poti: <kind>_<slug>
_ALIAS_RE = re.compile(r"^(rezervacije|ocenjevanje)_([A-Za-z0-9][A-Za-z0-9_-]*)$")

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
    "TABLICE_MAX",
    "SCHEDULE",
    "RAZREDI",
    "PROSTORI",
    "INACTIVITY_TIMEOUT_MINUTES",
    "INACTIVITY_TIMEOUT_ADMIN_MINUTES",
    "RESET_TOKEN_EXPIRATION_MINUTES",
    # Pravila ocenjevanja (nastavljiva po šoli)
    "ASSESSMENT_MAX_PER_WEEK",
    "ASSESSMENT_MAX_PER_DAY",
    "ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE",
    "ASSESSMENT_MAX_CONSECUTIVE_DAYS",
]

# Opis polj za UI (oznaka + tip vnosa). Vrstni red = vrstni red v obrazcu.
SCHOOL_SETTING_FIELDS = [
    {"key": "RAZREDI", "label": "Razredi (vejica-ločeno)", "type": "csv"},
    {"key": "PROSTORI", "label": "Prostori (vejica-ločeno)", "type": "csv"},
    {"key": "SCHEDULE", "label": "Urnik (JSON: ura → opis)", "type": "json"},
    {"key": "TABLICE_MAX", "label": "Največ tablic na uro", "type": "int"},
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
    [("rezervacije_ostcj", "rezervacije"), ("ocenjevanje_ostcj", "ocenjevanje")].

    Zakaj tako? Ko kasneje ustvarimo novo šolo, dobimo ustrezne poti brez
    ročnega vpisovanja. Zgodovinski aliasi (npr. "rezervacije_ostc") se
    dodajo ločeno kot podatki.
    """
    base = re.sub(r"[^a-z0-9]", "", (slug or "").lower())
    if not base:
        base = "sola"
    return [(f"{kind}_{base}", kind) for kind in ALIAS_KINDS.keys()]


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
_ALIAS_CACHE_TTL = 30.0
_ALIAS_CACHE_LOCK = threading.Lock()


def invalidate_alias_cache() -> None:
    """Počisti predpomnilnik aliasov (kliči ob spremembi/ustvarjanju šole)."""
    with _ALIAS_CACHE_LOCK:
        _ALIAS_CACHE.clear()


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
        "RAZREDI": ",".join(settings.RAZREDI),
        "PROSTORI": ",".join(settings.PROSTORI),
        "INACTIVITY_TIMEOUT_MINUTES": str(settings.INACTIVITY_TIMEOUT_MINUTES),
        "INACTIVITY_TIMEOUT_ADMIN_MINUTES": str(settings.INACTIVITY_TIMEOUT_ADMIN_MINUTES),
        "RESET_TOKEN_EXPIRATION_MINUTES": str(settings.RESET_TOKEN_EXPIRATION_MINUTES),
        "ASSESSMENT_MAX_PER_WEEK": str(ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_PER_WEEK"]),
        "ASSESSMENT_MAX_PER_DAY": str(ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_PER_DAY"]),
        "ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE": str(ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE"]),
        "ASSESSMENT_MAX_CONSECUTIVE_DAYS": str(ASSESSMENT_RULE_DEFAULTS["ASSESSMENT_MAX_CONSECUTIVE_DAYS"]),
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
    def PROSTORI(self) -> list[str]:
        return self.get_list("PROSTORI", settings.PROSTORI)

    @property
    def SCHEDULE(self) -> dict:
        return self.get_dict("SCHEDULE", settings.SCHEDULE)

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


def seed_school_settings(db: Session, school_id: int) -> int:
    """Napolni nastavitve šole iz .env — samo manjkajoče ključe.

    Zakaj samo manjkajoče? Da ob vsakem zagonu ne povozimo vrednosti, ki
    jih je Šolski admin že uredil v UI.
    """
    from app.models import SchoolSetting
    existing = {r.key for r in db.query(SchoolSetting).filter(SchoolSetting.school_id == school_id).all()}
    defaults = env_default_settings()
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

    seed_school_settings(db, school.id)
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
    m = _ALIAS_RE.match((alias or "").strip())
    return m.group(1) if m else None


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
        ctx = request_school_id(request)
        if ctx is not None and ctx != user.school_id:
            raise HTTPException(status_code=403, detail="Nimate dostopa do podatkov te šole.")
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
    ctx = request_school_id(request)
    if ctx is not None and ctx != user.school_id:
        raise HTTPException(status_code=403, detail="Nimate dostopa do podatkov te šole.")
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
        ctx = request_school_id(request)
        if ctx is not None and ctx != user.school_id:
            raise HTTPException(status_code=403, detail="Nimate dostopa do podatkov te šole.")
        return user.school_id
    if is_main_admin(user):
        ctx = request_school_id(request)
        if ctx is not None:
            return ctx
        raise HTTPException(
            status_code=400,
            detail="Glavni admin mora izbrati šolo (uporabite pot šole, npr. /rezervacije_<oznaka>).",
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
    school_id = request_school_id(request)

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

    school = ensure_default_school(db)

    # 1) Glavni admin (mi) — globalni račun brez šole.
    main_admin = db.query(User).filter(User.username == settings.MAIN_ADMIN_USERNAME).first()
    if main_admin is None:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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
