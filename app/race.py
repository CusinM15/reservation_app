"""Race condition prevention for concurrent reservation/assessment creation.

Uses per-resource mutex + intent tracking to detect when two users try to
reserve/schedule the same slot within 1 second. In that case, both users
get an error with each other's name, and neither succeeds.
"""

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
    """Get or create a per-resource lock."""
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
    """Register a reservation attempt (must be called BEFORE acquiring the lock)."""
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
    """Check for race condition. Must be called INSIDE the per-resource lock.
    
    Returns the other user's name if this request should also fail due to a race,
    otherwise None (meaning no race or we were the first detector).
    
    The first detector sets a race flag. The second detector (next lock holder)
    sees the flag and also fails.
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
    """Remove all tracking data for a resource after successful operation."""
    with _race_lock:
        _cleanup_resource(resource_key)


def _cleanup_resource(key: str):
    """Remove all keys starting with 'key'."""
    for k in list(_race_attempts.keys()):
        if k == key or k.startswith(key + ":"):
            del _race_attempts[k]


def _cleanup_intents(key: str):
    """Remove just the intent list, keep flag keys."""
    _race_attempts.pop(key, None)
