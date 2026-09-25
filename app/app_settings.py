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

from app.models import AppSetting

# Predpomnilnik za stikalo prodaje (glej selling_enabled).
SELLING_CACHE_TTL = 30.0
_SELLING_CACHE_VALUE: bool | None = None
_SELLING_CACHE_AT: float = 0.0

# Ključi v tabeli app_settings
KEY_SELLING = "SUBSCRIPTION_SELLING"          # "1" = prodaja vklopljena, "0" = izklopljena
KEY_PRICE = "SUBSCRIPTION_PRICE_EUR"          # cena v evrih (celo število)
KEY_PAYPAL = "SUBSCRIPTION_PAYPAL_URL"        # povezava do PayPal plačila (izdelek/načrt)
KEY_NOTE = "SUBSCRIPTION_PAYMENT_NOTE"        # navodila ob plačilu (sklic, kako sporočiti)

DEFAULT_PRICE_EUR = 30
DEFAULT_PAYPAL_URL = ""
DEFAULT_NOTE = (
    "Po plačilu prek spodnjega gumba klikni »Sporoči plačilo« in vpiši sklic "
    "oziroma kodo transakcije — naročnino bomo potrdili ter podaljšali za en mesec."
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


def price_eur(db: Session) -> int:
    """Cena mesečne naročnine v evrih."""
    raw = get_app_setting(db, KEY_PRICE, str(DEFAULT_PRICE_EUR))
    try:
        value = int(float(str(raw).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return DEFAULT_PRICE_EUR
    return value if value > 0 else DEFAULT_PRICE_EUR


def paypal_url(db: Session) -> str:
    """Povezava do plačila (PayPal izdelek/načrt). Prazno = še ni nastavljeno."""
    return get_app_setting(db, KEY_PAYPAL, DEFAULT_PAYPAL_URL)


def payment_note(db: Session) -> str:
    """Navodila, ki jih šola vidi ob nakupu."""
    return get_app_setting(db, KEY_NOTE, DEFAULT_NOTE)


def selling_config(db: Session) -> dict:
    """Vse za prodajo naročnin na enem mestu (za predloge in preverjanja)."""
    return {
        "enabled": selling_enabled(db),
        "price_eur": price_eur(db),
        "paypal_url": paypal_url(db),
        "note": payment_note(db),
    }


def save_selling_config(
    db: Session,
    *,
    enabled: bool,
    price: str | int | None,
    paypal: str | None,
    note: str | None,
) -> None:
    """Shrani nastavitve prodaje (kliče glavni admin)."""
    set_app_setting(db, KEY_SELLING, "1" if enabled else "0")
    set_app_setting(db, KEY_PRICE, str(price or DEFAULT_PRICE_EUR).strip())
    set_app_setting(db, KEY_PAYPAL, (paypal or "").strip())
    set_app_setting(db, KEY_NOTE, (note or "").strip())
