# tests/test_dpa.py — DPA: podpis v aplikaciji (šola + ponudnik samodejno)
#
# Zahteva uporabnika 2026-11-06: šolski admin izpolni podatke (sekcija DPA v
# nastavitvah), klikne »Podpiši« → dokument se podpiše z OBEMA stranema:
# šola (admin) + ponudnik (samodejno, podatki iz ERACUN_IZDAJATELJ_*).
from app.app_settings import set_app_setting
from app.database import SessionLocal
from app.dpa import get_agreement, provider_complete, provider_data, reset_dpa, sign_dpa
from app.models import School
from app.tenancy import set_school_setting
from tests.conftest import TEST_PASSWORD, default_school_id, login


def _pripravi_dpa_podatke(db, sid):
    set_app_setting(db, "ERACUN_IZDAJATELJ_NAZIV", "Test ponudnik s.p.")
    set_app_setting(db, "ERACUN_IZDAJATELJ_NASLOV", "Trg 1, 1000 Ljubljana")
    set_app_setting(db, "ERACUN_IZDAJATELJ_DAVCMA", "12345678")
    set_app_setting(db, "ERACUN_IZDAJATELJ_MATICNA", "99999999")
    set_app_setting(db, "ERACUN_IZDAJATELJ_EMAIL", "reservation.app@proton.me")
    set_school_setting(db, sid, "DPA_NASLOV", "Šolska ulica 5")
    set_school_setting(db, sid, "DPA_DAVCNA", "87654321")
    set_school_setting(db, sid, "DPA_MATICNA", "11112222")
    set_school_setting(db, sid, "DPA_ZASTOPNIK", "Test Admin")
    set_school_setting(db, sid, "DPA_FUNKCIJA", "ravnateljica")
    db.commit()


def test_dpa_provider_data_iz_eracun_nastavitev(client):
    db = SessionLocal()
    try:
        set_app_setting(db, "ERACUN_IZDAJATELJ_NAZIV", "Test ponudnik s.p.")
        set_app_setting(db, "ERACUN_IZDAJATELJ_NASLOV", "Trg 1")
        db.commit()
        p = provider_data(db)
        assert p["naziv"] == "Test ponudnik s.p."
        assert p["davcna"] == ""
        assert provider_complete(p)
        assert provider_complete({"naziv": "", "naslov": ""}) is False
    finally:
        db.close()


def test_dpa_sign_ustvari_podpisan_pdf(client, make_user):
    db = SessionLocal()
    try:
        sid = default_school_id()
        school = db.query(School).filter(School.id == sid).first()
        _pripravi_dpa_podatke(db, sid)
        admin = make_user(role="admin")

        a = sign_dpa(db, school, admin)
        assert a.pdf and len(a.pdf) > 1000
        assert a.pdf[:4] == b"%PDF"
        assert len(a.sha256) == 64
        assert a.signed_by_user_id == admin.id
        assert get_agreement(db, sid) is not None

        # ponovni podpis nadomesti obstoječi
        a2 = sign_dpa(db, school, admin)
        assert a2.id == a.id
        assert get_agreement(db, sid).sha256 == a2.sha256

        assert reset_dpa(db, sid) is True
        assert get_agreement(db, sid) is None
        assert reset_dpa(db, sid) is False
    finally:
        db.close()


def test_dpa_sign_brez_podatkov_sole_napaka(client, make_user):
    db = SessionLocal()
    try:
        sid = default_school_id()
        school = db.query(School).filter(School.id == sid).first()
        set_app_setting(db, "ERACUN_IZDAJATELJ_NAZIV", "Test ponudnik s.p.")
        set_app_setting(db, "ERACUN_IZDAJATELJ_NASLOV", "Trg 1")
        db.commit()
        admin = make_user(role="admin")
        try:
            sign_dpa(db, school, admin)
            raise AssertionError("pričakovana ValueError napaka")
        except ValueError:
            pass
    finally:
        db.close()


def test_dpa_api_potok(client, make_user):
    db = SessionLocal()
    try:
        sid = default_school_id()
        _pripravi_dpa_podatke(db, sid)
        admin = make_user(role="admin")
        username = admin.username
    finally:
        db.close()

    login(client, username)
    r = client.post("/settings/dpa/sign")
    assert r.status_code == 200, r.text
    assert r.json().get("sha256")

    r2 = client.get("/settings/dpa/pdf")
    assert r2.status_code == 200
    assert r2.headers.get("content-type", "").startswith("application/pdf")
    assert r2.content[:4] == b"%PDF"

    r3 = client.post("/settings/dpa/reset")
    assert r3.status_code == 200
    assert r3.json().get("ok") is True

    r4 = client.get("/settings/dpa/pdf")
    assert r4.status_code == 404




def _vk_zahtevo_dpa() -> None:
    from app.app_settings import set_app_setting
    db = SessionLocal()
    try:
        set_app_setting(db, "REQUIRE_DPA", "1")
        db.commit()
    finally:
        db.close()


def _nova_brez_dpa_sola() -> int:
    """Ustvari novo solo BREZ podpisane DPA in vrne njen id."""
    import uuid
    from app.models import School
    db = SessionLocal()
    try:
        s = School(slug="t" + uuid.uuid4().hex[:8], name="Test šola brez DPA", is_active=True)
        db.add(s)
        db.commit()
        db.refresh(s)
        return s.id
    finally:
        db.close()


def test_ucitelj_ne_more_prijave_pred_podpisom_dpa(client, make_user):
    """Učitelj se ne more prijaviti, dokler šola ne podpiše DPA."""
    _vk_zahtevo_dpa()
    sid = _nova_brez_dpa_sola()
    admin = make_user(role="admin", school_id=sid)
    teacher = make_user(role="teacher", school_id=sid)
    teacher_u = teacher.username
    admin_u = admin.username

    # učitelj -> login zavrnjen z napako o DPA
    r = client.post("/auth/login", data={"username": teacher_u, "password": TEST_PASSWORD})
    assert r.status_code == 200
    assert "DPA" in r.text or "obdelavi osebnih" in r.text

    # admin -> prijava gre naprej (ima dostop, da podpiše)
    r2 = client.post("/auth/login", data={"username": admin_u, "password": TEST_PASSWORD},
                     follow_redirects=False)
    assert r2.status_code in (302, 303)


def test_ucitelj_se_prijavi_po_podpisu_dpa(client, make_user):
    """Po podpisu DPA se učitelj normalno prijavi."""
    from app.dpa import sign_dpa
    from app.models import School
    _vk_zahtevo_dpa()
    sid = _nova_brez_dpa_sola()
    school = None
    db = SessionLocal()
    try:
        school = db.query(School).filter(School.id == sid).first()
        _pripravi_dpa_podatke(db, sid)
        admin = make_user(role="admin", school_id=sid)
        teacher = make_user(role="teacher", school_id=sid)
        teacher_u = teacher.username
        admin_u = admin.username
        sign_dpa(db, school, admin)
    finally:
        db.close()

    # učitelj se zdaj prijavi (preusmeritev na aplikacijo)
    r2 = client.post("/auth/login", data={"username": teacher_u, "password": TEST_PASSWORD},
                     follow_redirects=False)
    assert r2.status_code in (302, 303)


def test_vodstvo_dostop_zaslu_podpisom_dpa(client, make_user):
    """Vodstvo ima dostop tudi pred podpisom DPA (da šolo pripravi)."""
    _vk_zahtevo_dpa()
    sid = _nova_brez_dpa_sola()
    vodstvo = make_user(role="vodstvo", school_id=sid)
    vodstvo_u = vodstvo.username
    r2 = client.post("/auth/login", data={"username": vodstvo_u, "password": TEST_PASSWORD},
                     follow_redirects=False)
    assert r2.status_code in (302, 303)


def test_vodstvo_vidi_dpa_sekcijo_nastavitev(client, make_user):
    """Vodstvo lahko odpre /settings in tam vidi (samo) DPA sekcijo."""
    vodstvo = make_user(role="vodstvo")
    login(client, vodstvo.username)
    r = client.get("/settings")
    assert r.status_code == 200, r.text
    assert 'id="dpa-section"' in r.text
    # vodstvo_mode CSS skrije ostale sekcije (Osnovno, Razredi ...) in pusti le DPA.
    assert "#dpa-section{display:block" in r.text


def test_vodstvo_lahko_izpolni_in_podpise_dpa_samo_dpa_kljuce(client, make_user):
    """Vodstvo posodobi SAMO DPA_ polja in lahko podpiše DPA (ostalo admin-only)."""
    db = SessionLocal()
    try:
        sid = default_school_id()
        _pripravi_dpa_podatke(db, sid)
    finally:
        db.close()

    vodstvo = make_user(role="vodstvo")
    login(client, vodstvo.username)

    # vodstvo: DPA_ polja se shranijo, ne-DPA (RAZREDI) se zavržejo
    r = client.put(f"/api/schools/{sid}/settings",
                   json={"values": {"DPA_ZASTOPNIK": "Vodja",
                                    "RAZREDI": "MOCK_RAZRED_A,MOCK_RAZRED_B"}})
    assert r.status_code == 200, r.text

    # vodstvo samo z ne-DPA ključi → prepovedano
    r3 = client.put(f"/api/schools/{sid}/settings", json={"values": {"RAZREDI": "x"}})
    assert r3.status_code == 403

    # RAZREDI ostanejo nedotaknjeni (preverimo s šolskim adminom)
    admin = make_user(role="admin")
    login(client, admin.username)
    r4 = client.get(f"/api/schools/{sid}/settings")
    assert r4.status_code == 200
    assert "MOCK_RAZRED" not in str(r4.json().get("values", {}).get("RAZREDI", ""))

    # vodstvo lahko podpiše DPA
    login(client, vodstvo.username)
    r5 = client.post("/settings/dpa/sign")
    assert r5.status_code == 200, r5.text
    assert r5.json().get("sha256")
