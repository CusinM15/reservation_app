# ─────────────────────────────────────────────────────────────────────────
# app/app_settings.py — nastavitve cele namestitve (prodaja naročnin)
#
# Namen: hrani stvari, ki ne sodijo k posamezni šoli (cena, PayPal povezava,
# ali prodaja naročnin teče). Shranjene so v tabeli app_settings (ključ → vrednost).
#
# Zakaj stikalo? Isti repozitorij teče v dveh namestitvah: v šoli (k3s) in na
# gostovanju (Railway), kjer se naročnine prodajajo. Privzeto je prodaja
# IZKLOPLJENA, zato šolska namestitev po posodobitvi deluje natanko kot prej —
# prodajo vklopiš le tam, kjer jo potrebuješ.
# ─────────────────────────────────────────────────────────────────────────

from sqlalchemy.orm import Session

import time
from datetime import date

from app.models import AppSetting

# Predpomnilnik za stikalo prodaje (glej selling_enabled).
SELLING_CACHE_TTL = 30.0
_SELLING_CACHE_VALUE: bool | None = None
_SELLING_CACHE_AT: float = 0.0

# Ključi v tabeli app_settings
KEY_SELLING = "SUBSCRIPTION_SELLING"          # "1" = prodaja vklopljena, "0" = izklopljena
KEY_PRICE = "SUBSCRIPTION_PRICE_EUR"          # cena za LETO (12 mes.) v €; 0 = brez plačila
KEY_PAYPAL = "SUBSCRIPTION_PAYPAL_URL"        # povezava do enkratnega plačila (izdelek)
KEY_PAYPAL_SUB = "SUBSCRIPTION_PAYPAL_SUB_URL"  # povezava do SAMODEJNEGA (naročniškega) plačila
KEY_NOTE = "SUBSCRIPTION_PAYMENT_NOTE"        # navodila ob plačilu (sklic, kako sporočiti)

# Plan naročnine — zaenkrat SAMO LETO (12 mes.); polletni plan odstranjen
# (zahteva uporabnika 2026-10-01). Cena letnega plana je nastavljiva prek
# SUBSCRIPTION_PRICE_EUR (na šolski namestitvi ostc-app.org je 0 €).
PLAN_ORDER = ("leto",)
PLAN_MONTHS = {"leto": 12}
PLAN_LABELS = {"leto": "leto"}
PLAN_PER_LABELS = {"leto": "na leto"}
PLAN_PRICE_KEYS = {"leto": KEY_PRICE}
PLAN_PRICE_DEFAULTS = {"leto": 50}

DEFAULT_PRICE_EUR = PLAN_PRICE_DEFAULTS["leto"]
DEFAULT_PAYPAL_URL = ""
DEFAULT_PAYPAL_SUB_URL = ""
DEFAULT_NOTE = (
    "Po plačilu prek spodnjega gumba klikni »Sporoči plačilo« in vpiši sklic "
    "oziroma kodo transakcije — naročnino bomo potrdili ter podaljšali za izbrano obdobje."
)


def get_app_setting(db: Session, key: str, default: str = "") -> str:
    """Preberi nastavitev namestitve (ali privzeto vrednost)."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None or row.value is None or row.value == "":
        return default
    return row.value


def invalidate_cache() -> None:
    """Pobriši predpomnilnik stikala prodaje.

    Kliče se ob spremembi stikala in tudi v testih (conftest.clean_db), ker se
    tabele pobrišejo, predpomnjeno stanje pa bi sicer ostalo v pomnilniku.
    """
    global _SELLING_CACHE_VALUE, _SELLING_CACHE_AT
    _SELLING_CACHE_VALUE = None
    _SELLING_CACHE_AT = 0.0


def set_app_setting(db: Session, key: str, value: str | None) -> None:
    """Shrani nastavitev namestitve (ustvari vrstico, če je še ni)."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        db.add(AppSetting(key=key, value=value or ""))
    else:
        row.value = value or ""
    if key == KEY_SELLING:
        # Stikalo se je spremenilo — predpomnilnik naj se takoj osveži.
        invalidate_cache()


def selling_enabled(db: Session) -> bool:
    """Ali v tej namestitvi prodajamo naročnine?

    Rezultat predpomnimo za 30 sekund: to preverjanje teče ob VSAKI zahtevi
    (glej AuthMiddleware), zato ne smemo vsakič spraševati baze. Ko glavni
    admin stikalo spremeni (set_app_setting), se predpomnilnik takoj pobriše.
    """
    global _SELLING_CACHE_VALUE, _SELLING_CACHE_AT
    now = time.monotonic()
    if _SELLING_CACHE_VALUE is not None and (now - _SELLING_CACHE_AT) < SELLING_CACHE_TTL:
        return bool(_SELLING_CACHE_VALUE)
    value = get_app_setting(db, KEY_SELLING, "0") == "1"
    _SELLING_CACHE_VALUE = value
    _SELLING_CACHE_AT = now
    return value


def _parse_price(raw, default: int) -> int:
    """Pretvori shranjeno vrednost v nenegativno celo število; neveljavno → default."""
    try:
        value = int(float(str(raw).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


def plan_price(db: Session, plan_id: str) -> int:
    """Cena LETNEGA plana v €; 0 = brez plačila."""
    plan_id = plan_id if plan_id in PLAN_MONTHS else "leto"
    key = PLAN_PRICE_KEYS[plan_id]
    return _parse_price(
        get_app_setting(db, key, str(PLAN_PRICE_DEFAULTS[plan_id])),
        PLAN_PRICE_DEFAULTS[plan_id],
    )


def plans(db: Session) -> list[dict]:
    """Seznam planov (samo leto) s ceno — za prikaz in izbiro šole."""
    return [_plan_dict(db, pid) for pid in PLAN_ORDER]


def plan_by_id(db: Session, plan_id: str) -> dict:
    """Vrni plan po oznaki (``leto``); neznano → LETNI plan (privzeti).

    Nikoli ne vrne None — klicatelj dobi vedno veljaven plan (privzeto letni).
    """
    for plan in plans(db):
        if plan["id"] == plan_id:
            return plan
    return _plan_dict(db, "leto")


def _plan_dict(db: Session, plan_id: str) -> dict:
    """Sestavi slovar enega plana (brez iskanja) — uporablja plan_by_id."""
    return {
        "id": plan_id,
        "months": PLAN_MONTHS[plan_id],
        "label": PLAN_LABELS[plan_id],
        "per_label": PLAN_PER_LABELS[plan_id],
        "price": plan_price(db, plan_id),
    }


def price_eur(db: Session) -> int:
    """Cena LETNEGA plana (12 mes.) v €; 0 = brez plačila (za nazajzdružljivost).

    Vrednost 0 je dovoljena (poskusno obdobje, lastna šola), a NE pomeni »brez
    omejitev« — naročnino je treba obnoviti za vsako obdobje, sicer aplikacija za
    šolo ne dela (glavni admin jo podaljša brez plačila).
    """
    return plan_price(db, "leto")


def is_free(db: Session) -> bool:
    """Ali so VSI plani brezplačni (cena 0)? Vpliva le na prikaz, ne na veljavnost."""
    return all(plan["price"] == 0 for plan in plans(db))


# ── Sorazmerna cena do 1. 9. ───────────────────────────────────────────
# Pravilo (zahteva uporabnika 2026-10-02): naročnina VEDNO velja do 1. 9.
# (začetek šolskega leta). Cena je zato sorazmerna preostanku do 1. 9.: polna
# letna cena × (dni do 1. 9. / 365). Primer: polna cena 12 €, začetek 1. 3. →
# ~184/365 × 12 ≈ 6 €. Obnovitev se odpre 15. 8.; začetek od 15. 8. dalje velja
# do 1. 9. NASLEDNJE leto (celo leto), sicer do 1. 9. ISTEGA leta.
SCHOOL_YEAR_END_MONTH = 9      # 1. september — konec obdobja
SCHOOL_YEAR_END_DAY = 1
RENEW_FROM_MONTH = 8           # 15. avgust — od takrat velja za celo leto naprej
RENEW_FROM_DAY = 15
DAYS_IN_YEAR = 365

# Donacija (»podpri projekt«) — PayPal povezava iz README (repo reservation_app).
DONATION_URL = "https://www.paypal.com/ncp/payment/XC7LTYXAWUQMW"


def subscription_period_end(start: date | None = None) -> date:
    """Kdaj se konča naročniško obdobje, ki se začne ob `start` — vedno 1. 9.

    Če je začetek od 15. 8. dalje → 1. 9. NASLEDNJE leto (celo šolsko leto),
    sicer 1. 9. ISTEGA leta (le preostanek tega šolskega leta).
    """
    d = start or date.today()
    if (d.month, d.day) >= (RENEW_FROM_MONTH, RENEW_FROM_DAY):
        return date(d.year + 1, SCHOOL_YEAR_END_MONTH, SCHOOL_YEAR_END_DAY)
    return date(d.year, SCHOOL_YEAR_END_MONTH, SCHOOL_YEAR_END_DAY)


def prorated_price_eur(db: Session, start: date | None = None) -> int:
    """Sorazmerna cena do 1. 9. glede na datum začetka (zaokroženo na cel €).

    Nikoli ne preseže polne letne cene (začetek v oknu 15. 8.–1. 9. bi sicer dal
    malenkost več kot celo leto).
    """
    full = price_eur(db)
    if full <= 0:
        return 0
    d = start or date.today()
    end = subscription_period_end(d)
    days = max(0, (end - d).days)
    return min(full, round(full * days / DAYS_IN_YEAR))


def paypal_url(db: Session) -> str:
    """Povezava do enkratnega plačila (PayPal izdelek). Prazno = ni nastavljeno."""
    return get_app_setting(db, KEY_PAYPAL, DEFAULT_PAYPAL_URL)


def paypal_subscription_url(db: Session) -> str:
    """Povezava do samodejnega (naročniškega) plačila — za samodejno obnavljanje."""
    return get_app_setting(db, KEY_PAYPAL_SUB, DEFAULT_PAYPAL_SUB_URL)


def payment_note(db: Session) -> str:
    """Navodila, ki jih šola vidi ob nakupu."""
    return get_app_setting(db, KEY_NOTE, DEFAULT_NOTE)


def selling_config(db: Session) -> dict:
    """Vse za prodajo naročnin na enem mestu (za predloge in preverjanja)."""
    plan_list = plans(db)
    return {
        "enabled": selling_enabled(db),
        "price_eur": price_eur(db),                 # letni plan (nazajzdružljivost)
        "free": is_free(db),
        "plans": plan_list,
        # Povzetek cen za besedila, npr. »13 € / leto«.
        "price_label": " ali ".join(f"{p['price']} € / {p['label']}" for p in plan_list),
        "paypal_url": paypal_url(db),
        "paypal_sub_url": paypal_subscription_url(db),
        "note": payment_note(db),
        # Donacija (»podpri projekt«) — prikazana, ko je app brezplačen.
        "donation_url": DONATION_URL,
        # Sorazmerna cena do 1. 9. glede na današnji datum (za prikaz).
        "prorated_price_eur": prorated_price_eur(db),
        "period_end": subscription_period_end(),
    }


def save_selling_config(
    db: Session,
    *,
    enabled: bool,
    price: str | int | None,
    paypal: str | None,
    note: str | None,
    paypal_sub: str | None = None,
) -> None:
    """Shrani nastavitve prodaje (kliče glavni admin).

    `price` je cena LETNEGA plana. Cena 0 pomeni »brez plačila« (naročnino je
    treba vseeno obnoviti za vsako obdobje); prazna/neveljavna vrednost pade na
    privzeto ceno, da se v obrazcu ne da »pokvariti« nastavitve s tipkarsko napako.
    """
    def _clean(value, default: int) -> str:
        text = str(value if value is not None else "").strip()
        if text == "":
            return str(default)
        try:
            if float(text.replace(",", ".")) < 0:
                return str(default)
        except ValueError:
            return str(default)
        return text

    set_app_setting(db, KEY_SELLING, "1" if enabled else "0")
    set_app_setting(db, KEY_PRICE, _clean(price, DEFAULT_PRICE_EUR))
    set_app_setting(db, KEY_PAYPAL, (paypal or "").strip())
    set_app_setting(db, KEY_PAYPAL_SUB, (paypal_sub or "").strip())
    set_app_setting(db, KEY_NOTE, (note or "").strip())
