# ─────────────────────────────────────────────────────────────────────────
# app/template_override.py — univerzalni urejevalnik predlog (strani appa)
#
# Glavni admin lahko prek editorja na /navodila preglasši HTML predlogo poljubne
# strani (npr. login.html, registracija.html). Override se shrani v bazo
# (AppSetting "TEMPLATE_OVERRIDE:<ime>") in vsak naslednji prikaz strani vrne
# njegovo verzijo — brez ponovne gradnje. Backend .py logike ne urejamo.
#
# Ta modul:
#  - Jinja2 loader (OverrideLoader), ki najprej vrača DB override,
#    sicer pade na vgrajeno datoteko (prek FileSystemLoader).
#  - predpomnilnik override-ov (TTL) + registracija jinja okoliščin, da se ob
#    shranjevanju počisti template-cache (sprememba vidna takoj).
#  - zgodovina verzij (backup) za vračanje prejšnje različice.
# ─────────────────────────────────────────────────────────────────────────

import json
import threading
import time

from jinja2.loaders import BaseLoader, ChoiceLoader, FileSystemLoader
from jinja2.exceptions import TemplateNotFound

OVERRIDE_PREFIX = "TEMPLATE_OVERRIDE:"
HISTORY_PREFIX = "TEMPLATE_HISTORY:"

_CACHE: dict[str, tuple[str | None, float]] = {}
_CACHE_TTL = 30.0
_LOCK = threading.Lock()
_ENVS: list = []          # jinja Environment instance (za invalidation cache-a)
_HISTORY_MAX = 8

_TEMPLATES_DIR: str | None = None


def _db_factory():
    from app.database import SessionLocal
    return SessionLocal


def set_templates_dir(directory: str) -> None:
    global _TEMPLATES_DIR
    _TEMPLATES_DIR = directory


def override_key(name: str) -> str:
    return OVERRIDE_PREFIX + name


def history_key(name: str) -> str:
    return HISTORY_PREFIX + name


def register_env(env) -> None:
    """Zapomni si jinja okolje, da lahko ob shranjevanju počistimo template-cache."""
    with _LOCK:
        _ENVS.append(env)


def invalidate(name: str | None = None) -> None:
    """Počisti predpomnilnik override-ov in jinja template-cache (sprememba takoj)."""
    with _LOCK:
        if name is None:
            _CACHE.clear()
        else:
            _CACHE.pop(name, None)
        envs = list(_ENVS)
    for env in envs:
        try:
            env.cache.clear()
        except Exception:
            pass


def get_override_cached(name: str) -> str | None:
    """Vrni DB override predloge (s TTL predpomnilnikom) ali None."""
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(name)
        if hit and now - hit[1] < _CACHE_TTL:
            return hit[0]

    val: str | None = None
    db = _db_factory()()
    try:
        from app.models import AppSetting
        row = db.query(AppSetting).filter(AppSetting.key == override_key(name)).first()
        if row is not None and row.value:
            val = row.value
    except Exception:
        val = None
    finally:
        db.close()

    with _LOCK:
        _CACHE[name] = (val, time.time())
    return val


def save_override(db, name: str, content: str) -> None:
    """Shrani override; prejšnjo vrednost shrani v zgodovino (backup)."""
    from app.models import AppSetting

    row = db.query(AppSetting).filter(AppSetting.key == override_key(name)).first()
    old_value = row.value if row is not None else None
    if old_value is not None and old_value != content:
        _push_history(db, name, old_value)

    if row is None:
        db.add(AppSetting(key=override_key(name), value=content))
    else:
        row.value = content
    db.commit()
    invalidate(name)


def _push_history(db, name: str, content: str) -> None:
    from app.models import AppSetting
    hrow = db.query(AppSetting).filter(AppSetting.key == history_key(name)).first()
    hist = []
    if hrow is not None and hrow.value:
        try:
            hist = json.loads(hrow.value)
            if not isinstance(hist, list):
                hist = []
        except Exception:
            hist = []
    hist.append(content)
    hist = hist[-_HISTORY_MAX:]
    if hrow is None:
        db.add(AppSetting(key=history_key(name), value=json.dumps(hist)))
    else:
        hrow.value = json.dumps(hist)


def list_history(db, name: str) -> list[str]:
    from app.models import AppSetting
    hrow = db.query(AppSetting).filter(AppSetting.key == history_key(name)).first()
    if hrow is None or not hrow.value:
        return []
    try:
        v = json.loads(hrow.value)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def revert_override(db, name: str) -> str | None:
    """Obnovi zadnjo prejšnjo verzijo iz zgodovine. Vrne obnovljeno vsebino ali None."""
    from app.models import AppSetting
    hrow = db.query(AppSetting).filter(AppSetting.key == history_key(name)).first()
    if hrow is None or not hrow.value:
        return None
    try:
        hist = json.loads(hrow.value)
        if not isinstance(hist, list) or not hist:
            return None
    except Exception:
        return None

    prev = hist.pop()
    if hist:
        hrow.value = json.dumps(hist)
    else:
        db.delete(hrow)

    row = db.query(AppSetting).filter(AppSetting.key == override_key(name)).first()
    if row is not None:
        if prev:
            row.value = prev
        else:
            db.delete(row)
    elif prev:
        db.add(AppSetting(key=override_key(name), value=prev))
    db.commit()
    invalidate(name)
    return prev


def clear_override(db, name: str) -> None:
    """Ponastavi na vgrajeno predlogo (pobriše override, zgodovino ohrani)."""
    from app.models import AppSetting
    db.query(AppSetting).filter(AppSetting.key == override_key(name)).delete()
    db.commit()
    invalidate(name)


def read_override(db, name: str) -> str | None:
    from app.models import AppSetting
    row = db.query(AppSetting).filter(AppSetting.key == override_key(name)).first()
    return row.value if row is not None else None


def read_builtin(name: str) -> str | None:
    """Prebere vgrajeno predlogo z diska (za editor)."""
    if _TEMPLATES_DIR is None:
        return None
    import os
    p = os.path.join(_TEMPLATES_DIR, name)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read()


class OverrideLoader(BaseLoader):
    """Jinja loader: najprej DB override, sicer pade na vgrajeno datoteko."""

    def __init__(self, directory: str):
        self.directory = directory

    def get_source(self, environment, template):
        content = get_override_cached(template)
        if content is None:
            raise TemplateNotFound(template)
        return content, template, True


def install(tpl, directory: str):
    """Vgradi override-loader v jinja okolje Jinja2Templates instance."""
    tpl.env.loader = ChoiceLoader([
        OverrideLoader(directory),
        tpl.env.loader if tpl.env.loader is not None else FileSystemLoader(directory),
    ])
    register_env(tpl.env)
    return tpl