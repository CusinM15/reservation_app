# ─────────────────────────────────────────────────────────────────────────
# app/i18n.py — napisi vmesnika iz baze (večjezičnost SL/EN)
#
# Namen: vsi napisi na gumbih in v pogovornih oknih so shranjeni v tabeli
# `ui_strings` (stolpca `sl` in `en`). Aplikacija napis prebere po stabilnem
# ključu (npr. »btn_shrani«) in ga prikaže v jeziku, ki ga je izbrala šola
# (nastavitev UI_LANGUAGE, privzeto slovenščina).
#
# Kako se uporablja v predlogi:
#     {{ t('btn_shrani', 'Shrani') }}
# Drugi argument je privzeto (fallback) besedilo, če ključa v bazi ni.
#
# Jezik in napise za TRENUTNO zahtevo nastavi middleware (set_request_language);
# t() jih prebere iz contextvarov, zato predlogam ni treba ničesar posredovati.
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import time
from contextvars import ContextVar

from sqlalchemy.orm import Session

from app.models import UIString

LANG_SL = "sl"
LANG_EN = "en"
SUPPORTED_LANGS = (LANG_SL, LANG_EN)

# Ključ v nastavitvah šole (school_settings), ki hrani izbrani jezik vmesnika.
KEY_LANG = "UI_LANGUAGE"

_LANG: ContextVar[str] = ContextVar("ui_lang", default=LANG_SL)
_STRINGS: ContextVar[dict] = ContextVar("ui_strings", default={})

# Predpomnilnik vseh napisov (tabela je majhna; beremo jo največ vsakih 30 s).
_CACHE_TTL = 30.0
_CACHE: dict = {"at": 0.0, "data": {}}


def normalize_lang(value) -> str:
    """Vrni 'sl' ali 'en'; neveljavno/neznano → 'sl' (slovenščina)."""
    v = str(value or "").strip().lower()[:2]
    return v if v in SUPPORTED_LANGS else LANG_SL


def invalidate_cache() -> None:
    """Pobriši predpomnilnik napisov (ob spremembi v bazi/testih)."""
    _CACHE["at"] = 0.0
    _CACHE["data"] = {}


def load_strings(db: Session) -> dict[str, dict]:
    """Preberi VSE napise: {ključ: {'sl': ..., 'en': ...}}."""
    out: dict[str, dict] = {}
    for row in db.query(UIString).all():
        out[row.key] = {"sl": row.sl or "", "en": row.en or ""}
    return out


def all_strings(db: Session) -> dict[str, dict]:
    """Kot load_strings, a s 30-sekundnim predpomnilnikom."""
    now = time.monotonic()
    if _CACHE["data"] and (now - _CACHE["at"]) < _CACHE_TTL:
        return _CACHE["data"]
    data = load_strings(db)
    _CACHE["data"] = data
    _CACHE["at"] = now
    return data


def set_request_language(db: Session | None, lang) -> None:
    """Nastavi jezik in naloži napise za TRENUTNO zahtevo (kliče middleware)."""
    _LANG.set(normalize_lang(lang))
    if db is None:
        _STRINGS.set({})
        return
    try:
        _STRINGS.set(all_strings(db))
    except Exception:
        # Če baze še ni / tabele ni, ne smemo podreti zahteve.
        _STRINGS.set({})


def current_lang() -> str:
    """Trenutno izbrani jezik ('sl' ali 'en')."""
    return _LANG.get()


def t(key: str, default: str = "") -> str:
    """Napis iz baze v trenutnem jeziku; če ga ni, vrni `default`."""
    item = _STRINGS.get().get(key)
    if not item:
        return default
    return item.get(_LANG.get()) or item.get(LANG_SL) or default
