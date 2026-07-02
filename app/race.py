# ─────────────────────────────────────────────────────────────────────────
# app/race.py — Preprečevanje race condition pri sočasnih rezervacijah
#
# Namen: Ko dva uporabnika hkrati rezervirata isti termin, oba dobita
# napako (ne le drugi). To preprečuje scenarij, kjer oba mislita, da
# sta rezervirala termin, v resnici pa je uspel samo eden.
#
# Zakaj ne zadošča transakcijska izolacija baze?
# Ker želimo uporabniku povedati, kdo drug je rezerviral termin v istem
# trenutku. Transakcija bi vrnila napako, vendar brez informacije o
# sočasnem uporabniku.
#
# Kako deluje?
# 1. register_intent() — vsak uporabnik pred rezervacijo registrira
#    svoj namen (uid + ime) s časovnim žigom.
# 2. get_lock() — per-resource zaklepanje (mutex za vsak termin).
# 3. check_and_raise() — znotraj lock-a preverimo, ali je v zadnji
#    sekundi več kot en uporabnik poskušal rezervirati isti termin.
#    Če da, oba dobita napako. Prvi detektor nastavi flag.
# 4. cleanup() — po uspešni rezervaciji počistimo intent tracking.
#
# RACE_WINDOW_SEC = 1.0 — časovno okno za detekcijo race conditiona.
# CLEANUP_AFTER_SEC = 2.0 — po 2 sekundah pozabimo stare intente.
# ─────────────────────────────────────────────────────────────────────────

import threading
import time

# Per-resource locks with timestamps: resource_key -> (Lock, creation_time)
_locks = {}
_locks_lock = threading.Lock()

# Intent tracking: resource_key -> [{"uid": int, "name": str, "ts": float}, ...]
_race_attempts = {}
_race_lock = threading.Lock()

RACE_WINDOW_SEC = 1.0
CLEANUP_AFTER_SEC = 2.0


def get_lock(resource_key: str) -> threading.Lock:
    """Pridobi ali ustvari per-resource lock za ključ (npr. 'rezervacija:tablice:2024-01-01:3').
    
    Stare lock-e (starejše od 60s) počistimo, da ne puščamo pomnilnika.
    """
    with _locks_lock:
        now = time.time()
        # Clean up old locks (older than 60s)
        for k in list(_locks.keys()):
            if now - _locks[k][1] > 60:
                del _locks[k]

        if resource_key not in _locks:
            _locks[resource_key] = (threading.Lock(), now)
        return _locks[resource_key][0]


def register_intent(resource_key: str, user_id: int, user_name: str):
    """Registriraj namen rezervacije (kliči PRED pridobitvijo lock-a).
    
    Zakaj pred lock-om? Ker želimo zajeti čimprejšnji časovni žig.
    Če bi registrirali znotraj lock-a, bi drugi uporabnik že čakal
    na lock in bi bil time stamp prepozen.
    
    Stare intente (starejše od CLEANUP_AFTER_SEC) sproti čistimo.
    """
    with _race_lock:
        now = time.time()
        # Clean stale entries
        for k in list(_race_attempts.keys()):
            if not k.endswith(":race") and isinstance(_race_attempts[k], list):
                _race_attempts[k] = [
                    i for i in _race_attempts[k] if now - i["ts"] < CLEANUP_AFTER_SEC
                ]
                if not _race_attempts[k]:
                    del _race_attempts[k]

        if resource_key not in _race_attempts:
            _race_attempts[resource_key] = []
        _race_attempts[resource_key].append(
            {"uid": user_id, "name": user_name, "ts": now}
        )


def check_and_raise(resource_key: str, current_user_id: int) -> str | None:
    """Preveri race condition. Kliči ZNOTRAJ per-resource lock-a.
    
    Logika:
    1. Preveri, ali obstaja race flag (prvi detektor ga je nastavil).
       Če da — tudi trenutni uporabnik je del race-a in mora spodleteti.
    2. Če ni flag-a, preveri recent intente (zadnja 1 sekunda).
       Če sta dva različna uporabnika — race detected!
       Prvi detektor nastavi flag, da tudi drugi ve, da je v race-u.
    
    Returns:
        Ime drugega uporabnika, če je prišlo do race-a (oba spodletita).
        None, če race-a ni (ali če smo mi prvi detektor in bomo
        uspeli — naslednji bo videl flag in spodletel).
    """
    with _race_lock:
        now = time.time()
        race_flag_key = resource_key + ":race"

        # Check if a previous lock holder already detected a race
        if race_flag_key in _race_attempts:
            other_name = _race_attempts[race_flag_key]
            # This request is part of the race - fail too
            _cleanup_resource(resource_key)
            return other_name

        # Check current intents for race
        intents = _race_attempts.get(resource_key, [])
        recent = [i for i in intents if now - i["ts"] < RACE_WINDOW_SEC]
        unique_uids = set(i["uid"] for i in recent)

        if len(unique_uids) >= 2:
            # Race detected! Set flag so the next lock holder also fails
            other_entry = next(
                (i for i in recent if i["uid"] != current_user_id), None
            )
            other_name = other_entry["name"] if other_entry else "neznan uporabnik"
            _race_attempts[race_flag_key] = other_name
            _cleanup_intents(resource_key)
            return other_name

        # No race
        return None


def cleanup(resource_key: str):
    """Počisti vse tracking podatke za resource po uspešni operaciji."""
    with _race_lock:
        _cleanup_resource(resource_key)


def _cleanup_resource(key: str):
    """Odstrani vse ključe, ki se začnejo z 'key' (vključno s flag ključi)."""
    for k in list(_race_attempts.keys()):
        if k == key or k.startswith(key + ":"):
            del _race_attempts[k]


def _cleanup_intents(key: str):
    """Odstrani samo intent list, pusti flag ključe."""
    _race_attempts.pop(key, None)
