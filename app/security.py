# ─────────────────────────────────────────────────────────────────────────
# app/security.py — Podpisovanje in preverjanje session cookieja
#
# Namen: user_id cookie je podpisan z itsdangerous (HMAC + timestamp), da
# ga ni mogoče ponarediti. Prej je bil cookie nesigniran — vsak je lahko
# nastavil user_id=1 in postal admin (auth bypass).
#
# Zakaj itsdangerous? Je že v requirements.txt (uporablja ga Flask
# ekosistem), podpira podpis + potek (max_age) in je preprost.
# ─────────────────────────────────────────────────────────────────────────

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

# Salt loči ta serializer od morebitnih drugih uporab itsdangerous v appu.
_serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="sola-auth")

# Veljavnost seje: 30 dni. Cookie je session cookie (poteče ob zaprtju
# brskalnika), ampak podpis ima še dodatno časovno omejitev.
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 dni v sekundah


def inactivity_timeout_ms(user, config=None) -> int:
    """Timeout za samodejno odjavo (ms) — admin/vodstvo strožji.
    
    config: SchoolConfig (iz baze šole) ali None (fallback na .env)."""
    from app.tenancy import role_value, MAIN_ADMIN_ROLE
    from app.models import RoleEnum
    is_privileged = user and role_value(user) in (RoleEnum.admin.value, RoleEnum.vodstvo.value, MAIN_ADMIN_ROLE)
    if config is not None:
        if is_privileged:
            return config.INACTIVITY_TIMEOUT_ADMIN_MINUTES * 60 * 1000
        return config.INACTIVITY_TIMEOUT_MINUTES * 60 * 1000
    if is_privileged:
        return settings.INACTIVITY_TIMEOUT_ADMIN_MINUTES * 60 * 1000
    return settings.INACTIVITY_TIMEOUT_MINUTES * 60 * 1000


def sign_user_id(user_id: int) -> str:
    """Podpiši user_id v varen cookie string."""
    return _serializer.dumps(str(user_id))


def session_inactivity_check(uid: int, raw_cookie: str | None, timeout_secs: float, now: float | None = None) -> str:
    """Strežniški timeout neaktivnosti (velja na VSAKI prijavljeni strani).

    user_id cookie hisdangerous podpis vsebuje ČAS izdaje. Če je posodobljen
    ob aktivnosti (rolling), je to tudi čas zadnje aktivnosti.

    Vrne: 'ok' (svež), 'refresh' (obnovi cookie — aktivnost), 'expired'.
    """
    if not raw_cookie or timeout_secs <= 0:
        return "ok"  # brez podatka / izklopljeno → ne blokiramo
    import time as _t
    now = now if now is not None else _t.time()
    try:
        payload, ts = _serializer.loads(
            raw_cookie, max_age=timeout_secs + 5, return_timestamp=True)
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return "expired"
    if str(payload) != str(uid):
        return "expired"
    # itsdangerous vrne timestamp kot aware datetime (novejše) ali float — beremo oboje.
    if isinstance(ts, (int, float)):
        _ts = float(ts)
    else:
        _ts = ts.timestamp()
    age = now - _ts
    if age > timeout_secs + 5:
        return "expired"
    if age > 60:
        return "refresh"  # aktivnost: pre-podpiši, da se okno pomakne
    return "ok"


def get_current_user_id(request) -> int | None:
    """Preberi in verificiraj user_id iz signed cookieja.

    Vrne int user_id ali None, če cookie manjka, je ponarejen ali je
    potekel. To je edino zaupanja vredno branje user_id — nikoli ne
    uporabljaj request.cookies.get("user_id") direktno!
    """
    raw = request.cookies.get("user_id")
    if not raw:
        return None
    try:
        return int(_serializer.loads(raw, max_age=SESSION_MAX_AGE))
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None
