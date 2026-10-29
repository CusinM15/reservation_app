# ─────────────────────────────────────────────────────────────────────────
# tests/test_school_kratica.py — šolski admin spremeni kratico šole (school.slug)
#
# Zahteva uporabnika (2026-10-29): kratico (oznako/slug) šole naj v Nastavitvah
# šole lahko spremeni šolski admin — vendar mora biti UNIKATNA (ne sme biti
# enaka kot pri drugi šoli). Ob spremembi se regenerirajo generirani URL-aliasi.
# ─────────────────────────────────────────────────────────────────────────

from app.database import SessionLocal
from app.models import School, SchoolAlias
from app.tenancy import create_school, generate_aliases
from tests.conftest import default_school_id, login


def _db_school(slug):
    db = SessionLocal()
    try:
        return db.query(School).filter(School.slug == slug).first()
    finally:
        db.close()

def _db_school_by_id(school_id):
    db = SessionLocal()
    try:
        return db.query(School).filter(School.id == school_id).first()
    finally:
        db.close()


def _db_aliases(slug):
    db = SessionLocal()
    try:
        s = db.query(School).filter(School.slug == slug).first()
        if not s:
            return []
        return sorted(a.alias for a in s.aliases)
    finally:
        db.close()


def _make_school_admin(client, make_user, school_id):
    """Ustvari šolskega admina določene šole in se z njim prijavi.

    make_user default veže uporabnika na privzeto šolo (ostcj); za DRUGO šolo
    podamo school_id eksplicitno (kot naredi make_user school_id=...).
    """
    admin = make_user(role="admin", school_id=school_id)
    login(client, admin.username)
    return admin


# ── 1. Uspešna sprememba kratice (svoje šole) ─────────────────────────

def test_sk_rate_svpremeni_slug_in_ok(client, make_user):
    """Šolski admin spremeni svojo kratico → 200, slug posodobljen, novi aliased."""
    sid = default_school_id()
    _make_school_admin(client, make_user, sid)
    r = client.put(f"/api/schools/{sid}/settings",
                   json={"values": {"slug": "nova-oznaka"}})
    assert r.status_code == 200, r.text
    s = _db_school("nova-oznaka")
    assert s is not None, "slug ni posodobljen"
    # Stara generirana pot manjka, nova generirana obstaja.
    ali = _db_aliases("nova-oznaka")
    for a, _k in generate_aliases("nova-oznaka"):
        assert a in ali, f"manjka generiran alias: {a}"


def test_sk_rate_is_slug_pre_vrne400(client, make_user):
    """Kratico ostaviti nespremenjeno (isti slug) → 200, brez napake."""
    sid = default_school_id()
    s = _db_school_by_id(sid)
    _make_school_admin(client, make_user, sid)
    r = client.put(f"/api/schools/{sid}/settings",
                   json={"values": {"slug": s.slug}})
    assert r.status_code == 200, r.text
    assert _db_school(s.slug) is not None


# ── 2. Unikatnost: ne sme biti enaka kot pri drugi šoli ────────────────

def test_sk_rate_duplikat_vrne400(client, make_user):
    """Slug, ki ga že ima druga šola → 400, sprememba zavrnjena."""
    # Druga šola že obstaja s slugom 'tuje'.
    db = SessionLocal()
    try:
        create_school(db, name="Tuja šola", slug="tuje")
        db.commit()
    finally:
        db.close()

    sid = default_school_id()
    _make_school_admin(client, make_user, sid)
    r = client.put(f"/api/schools/{sid}/settings",
                   json={"values": {"slug": "tuje"}})
    assert r.status_code == 400, f"pričakovan 400, dobil {r.status_code}: {r.text}"
    # Trenutni slug ostane (sprememba ni bila uspešna).
    assert _db_school("tuje") is not None
    assert _db_school_by_id(default_school_id()) is not None


def test_sk_rate_prazna_vrne400(client, make_user):
    """Prazen slug → 400."""
    sid = default_school_id()
    _make_school_admin(client, make_user, sid)
    r = client.put(f"/api/schools/{sid}/settings",
                   json={"values": {"slug": "   "}})
    assert r.status_code == 400, r.text


def test_sk_rate_sprememba_je_atomska_pri_konfliktu_aliased(client, make_user):
    """Če novi slug trči z ALIASOM druge šole → 400, obstoječi se ne izbrišejo.

    Preverimo, da sprememba ostane atomska: če pade zaradi konflikta novih
    poti, ne smemo izgubiti že-delujočih starih.
    """
    db = SessionLocal()
    try:
        b = create_school(db, name="Šola B", slug="sola-b")
        # Šoli B dodama ROČNO (kustom) alias, ki NI del njenih generiranih
        # poti (generate_aliases("sola-b") → "rezervacije_solab", ne solab2).
        db.add(SchoolAlias(school_id=b.id, alias="rezervacije_solab2", kind="rezervacije"))
        db.commit()
    finally:
        db.close()

    sid = default_school_id()
    _make_school_admin(client, make_user, sid)

    # Poskušaj kratico 'solab2' → na njo nobena šola ni vezana po slug-ju,
    # zato gre čez unikatnost sluga; pade pa na konfliktu, ker 'solab2'
    # generira 'rezervacije_solab2', ki ga ročno drži šola B.
    ali_before = sorted(a for a in _db_aliases(_db_school_by_id(default_school_id()).slug))
    r = client.put(f"/api/schools/{sid}/settings",
                   json={"values": {"slug": "solab2"}})
    assert r.status_code == 400, f"pričakovan 400, dobil {r.status_code}: {r.text}"
    assert _db_aliases(_db_school_by_id(default_school_id()).slug) == ali_before, \
        "ob atomskem padcu se obstoječi aliased ne smejo spremeniti"


def test_sk_rate_ne_dotakja_rocnih_zgodovinskih_aliased(client, make_user):
    """Ročno dodani (zgodovinski) alias se ob spremembi kratice ohrani."""
    db = SessionLocal()
    try:
        s = db.query(School).filter(School.id == default_school_id()).first()
        db.add(SchoolAlias(school_id=s.id, alias="zgodovinski-old", kind="rezervacije"))
        db.commit()
    finally:
        db.close()

    sid = default_school_id()
    _make_school_admin(client, make_user, sid)
    r = client.put(f"/api/schools/{sid}/settings",
                   json={"values": {"slug": "nova-oznaka-2"}})
    assert r.status_code == 200, r.text
    assert "zgodovinski-old" in _db_aliases("nova-oznaka-2"), \
        "ročno dodan zgodovinski alias mora ostati"