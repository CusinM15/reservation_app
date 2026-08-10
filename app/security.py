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


def sign_user_id(user_id: int) -> str:
    """Podpiši user_id v varen cookie string."""
    return _serializer.dumps(str(user_id))


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
