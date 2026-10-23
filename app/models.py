# ─────────────────────────────────────────────────────────────────────────
# app/models.py — SQLAlchemy modeli (tabelne definicije)
#
# Namen: Definira vse tabele v bazi: uporabniki, rezervacije, ocenjevanja,
# zasedeni datumi in audit log.
#
# Zakaj ločeni modeli? Vsak model predstavlja svojo domeno v šolskem
# informacijskem sistemu. Relacije so preproste (ForeignKey na users),
# brez kompleksnih več-povezav.
# ─────────────────────────────────────────────────────────────────────────

from datetime import date, datetime

from sqlalchemy import Boolean, Column, Integer, String, Date, DateTime, Text, ForeignKey, Float, Enum as SAEnum, BigInteger, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum

from app.database import Base


# ── Šola (tenant) ─────────────────────────────────────────────────────
# Vsaka šola je ločen tenant: ima svoje uporabnike, rezervacije,
# ocenjevanja, dneve dejavnosti in svoje nastavitve. Podatki se filtrirajo
# po school_id — šolski uporabniki vidijo izključno svojo šolo.
#
# slug: kratka oznaka (npr. "ostcj"), iz katere se generirajo URL-aliasi.
class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    aliases = relationship("SchoolAlias", back_populates="school", cascade="all, delete-orphan")
    settings = relationship("SchoolSetting", back_populates="school", cascade="all, delete-orphan")


# ── URL-alias šole ────────────────────────────────────────────────────
# Alias je prvi segment poti, vezan na šolo. Primeri:
#   /ocenjevanje_ostcj          → /ocenjevanje
#   /rezervacije_ostc           → /rezervacije
#   /ocenjevanje_ostcj/dejavnosti → /ocenjevanje/dejavnosti
# kind ("ocenjevanje" | "rezervacije") pove, v katero kanonično pot se
# alias prevede. Novi šoli se aliasi generirajo iz sluga (glej tenancy.py).
class SchoolAlias(Base):
    __tablename__ = "school_aliases"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    alias = Column(String, unique=True, nullable=False, index=True)
    kind = Column(String, nullable=False, index=True)

    school = relationship("School", back_populates="aliases")


# ── Nastavitve šole (prej v .env) ─────────────────────────────────────
# Ključ/vrednost par na šolo. Vrednosti so shranjene kot besedilo, ker
# imajo različne tipe (int, CSV, JSON). Tip se interpretira v
# app/tenancy.SchoolConfig. Šolski admin jih kasneje ureja v UI.
class SchoolSetting(Base):
    __tablename__ = "school_settings"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    key = Column(String, nullable=False, index=True)
    value = Column(Text, nullable=True, default="")

    __table_args__ = (
        UniqueConstraint("school_id", "key", name="uq_school_settings_school_key"),
    )

    school = relationship("School", back_populates="settings")


# ── Vloge uporabnikov ─────────────────────────────────────────────────
# Definiramo vloge z naraščajočimi pravicami:
# - teacher:      lahko ustvarja in briše lastne rezervacije in ocenjevanja
# - vodstvo:      enako kot teacher + upravlja zasedene datume, serijske rezervacije
# - admin:        ŠOLSKI admin — polne pravice v svoji šoli (uporabniki,
#                 nastavitve šole, audit log). Vidi SAMO svojo šolo.
# - main_admin:   GLAVNI admin (mi) — vidi in upravlja vse šole, ustvarja
#                 nove šole. Nima school_id (globalni račun).
class RoleEnum(str, enum.Enum):
    main_admin = "main_admin"
    admin = "admin"
    vodstvo = "vodstvo"
    teacher = "teacher"


# ── Uporabnik ─────────────────────────────────────────────────────────
# Vsak uporabnik ima unikatno uporabniško ime (username) in email.
# Password_hash hrani bcrypt hash (nikoli čistega gesla).
# Reset_token je začasen — uporablja se za ponastavitev gesla.
# is_active omogoča deaktivacijo brez brisanja (ohranimo zgodovino).
#
# school_id: kateri šoli uporabnik pripada. NULL = globalni račun
# (glavni admin), ki ni vezan na nobeno šolo.
# Unikatnost username/email je ZNOTRAJ šole (ne globalno) — dve šoli
# lahko imata vsaka svojega "jnovak". Zato ni več unique=True na stolpcih,
# ampak sestavljeni unikatni indeks (glej migracijo v database.py).
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    username = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True, index=True)
    first_name = Column(String, nullable=False, default="")
    last_name = Column(String, nullable=False, default="")
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum(RoleEnum), default=RoleEnum.teacher, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    reset_token = Column(String, nullable=True, default=None, index=True)

    # Relacije: uporabnik ima lahko več rezervacij in ocenjevanj
    reservations = relationship("Reservation", back_populates="teacher")
    assessments = relationship("Assessment", back_populates="teacher")


# ── Rezervacija ───────────────────────────────────────────────────────
# Rezervacija pomeni, da učitelj zasede določen prostor v določeni uri
# na določen datum.
#
# Prostori so: tablice, računalnica, ladja, gospodinjstvo.
# Za 'tablice' je obvezno polje qty (število tablic), ker lahko več
# učiteljev sočasno uporablja tablice (do TABLICE_MAX).
# Za ostale prostore je prostor ekskluziven — samo en učitelj na uro.
#
# series_id: Če je nastavljen, pomeni, da rezervacija pripada seriji
# (tedenska ponovitev ali celodnevni dogodek). NULL = enkratna rezervacija.
# Serijske rezervacije lahko ustvarja samo admin/vodstvo.
class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    prostor = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    hour = Column(Integer, nullable=False)  # 0–7
    razred = Column(String, nullable=True, default="")
    qty = Column(Integer, nullable=True)  # only for tablice

    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    teacher = relationship("User", back_populates="reservations")

    # Identifier of a recurring/full-day series. NULL = enkratna rezervacija.
    # Vsi zapisi iste serije (npr. "vsak četrtek predura računalnica" ali
    # "naravoslovni dan: vse ure istega dne") delijo isti series_id.
    series_id = Column(String, nullable=True, index=True)

    # Ime serijske rezervacije (npr. "Naravoslovni dan — 5. a"). Če je
    # prazno/NULL, se v koledarju prikaže privzeto "Dogodek". Enkratne
    # rezervacije nimajo imena — prikazujejo ime učitelja (teacher_name).
    name = Column(String, nullable=True)


# ── Ocenjevanje ───────────────────────────────────────────────────────
# Ocenjevanje pomeni, da učitelj napoveduje ocenjevanje za določen
# razred na določen datum. Omejitve:
# - Max 3 ocenjevanja na teden na razred (katerakoli vrsta)
# - Max 2 običajni (ne ponavljanje) na teden
# - Največ 1 ocenjevanje na dan na razred
# - Prepoved 3 zaporednih dni
#
# ponavljanje: Če je True, je ocenjevanje tipa "ponavljanje" (snov iz
# prejšnjih ur) in ima drugačne omejitve kot običajno ocenjevanje.
class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    razred = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    ponavljanje = Column(Boolean, default=False, nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    teacher = relationship("User", back_populates="assessments")


# ── Zasedeni datumi ───────────────────────────────────────────────────
# Vodstvo/admin lahko označi določene datume kot "zasedene" za določen
# razred. To pomeni, da na ta dan ni možno napovedati ocenjevanja.
# Če ocenjevanje že obstaja, se ob blokiranju samodejno izbriše.
class BlockedDate(Base):
    __tablename__ = "blocked_dates"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    razred = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by = relationship("User")


# ── Audit log ─────────────────────────────────────────────────────────
# Beleži vse pomembne dogodke v aplikaciji: ustvarjanje/brisanje
# rezervacij, ocenjevanj, uporabnikov, sprememba gesel itd.
# ID je BigInteger, ker lahko audit log v letu dni zraste precej.
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User")


# ── Dnevi dejavnosti (UI "Vnos dejavnosti") ──────────────────────────
# Nova tabela za vizualni vnos vseh daljših dejavnosti (kulturni,
# naravoslovni, tehniški, športni dnevi) po razredih, s pregledom in
# CRUD po vrsticah. Stran je namenjena vodstvu/adminu; učitelji jo
# ne vidijo (vendar posledice — blokirani datumi, rezervacije,
# preklini ocenjevanj — so vidne vsem).
#
# Dnevi dejavnosti (activity_days) — vnosi po razredih
# polni VEČ vrstic za isti grade iz enega lista — zato ni unikatne omejitve
# na (grade, section, title).
#
# Sync: ob shranjevanju z izpolnjenim datumom, full_day in prostori router
# ustvari BlockedDate (za izbrane razrede/datum) in serijske rezervacije
# (ure 1–5) ter pošlje učiteljem email za preklicana ocenjevanja —
# enaka logika kot obstoječi blocked_dates / series.
class ActivityDay(Base):
    __tablename__ = "activity_days"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    grade = Column(String, nullable=False, index=True)  # "1".."9", "ip" (IP/POUK), "pouk"
    section = Column(String, nullable=False, index=True)  # KULTURNI/NARAVOSLOVNI/TEHNIŠKI/ŠPORTNI
    title = Column(String, nullable=False, default="")  # glavni naslov; če prazen → "{section} {grade}. razred"
    subtitle = Column(String, nullable=True, default="")  # "pod dejavnost" (npr. "Oblak 365, Powerpoint")
    full_day = Column(Boolean, default=False, nullable=False)  # Celoten dan (rezervira ure 1–5 + blokira dan)
    recurring = Column(Boolean, default=False, nullable=False)  # tedensko ponavljanje (za nedeterminiran termin)
    date_from = Column(Date, nullable=True)  # točen začetek; None = "ni še določen"
    date_to = Column(Date, nullable=True)    # konec; None = en dan
    date_undetermined = Column(Boolean, default=False, nullable=False)  # checkpoint "datum ni še določen"
    date_text = Column(String, nullable=True, default="")  # npr. "oktober–november"
    all_classes = Column(Boolean, default=False, nullable=False)  # "vsi" razredi generacije
    classes = Column(Text, nullable=True, default="")  # vejica-ločen seznam izbranih črkovnih oddelkov
    prostori = Column(Text, nullable=True, default="")  # vejica-ločeni prostori
    cena = Column(String, nullable=True, default="")  # besedilo (lahko "3", "225,00 EVR" ipd.)
    vodja = Column(String, nullable=True, default="")
    opomba = Column(Text, nullable=True, default="")
    parent_title = Column(String, nullable=True, default="", index=True)  # glavni naslov skupine (npr. "TEHNIŠKI DAN"), če so to poddejavnosti
    source = Column(String, nullable=False, default="manual", index=True)  # interni izvor: "xlsx" = sekcijski vnos, "manual" = ročni
    termini = Column(JSONB, nullable=True, default=list)  # seznam [{date, classes}] — več datumov (po razredih) pod eno dejavnost

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = relationship("User")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ── Nastavitve cele namestitve ────────────────────────────────────────
# Zakaj ločeno od school_settings? Nekatere nastavitve niso vezane na šolo,
# ampak na celo namestitev — npr. ali se naročnine sploh prodajajo, po kaki
# ceni in na katero PayPal povezavo. Velja: ključ → vrednost (besedilo).
class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True, default="")


# ── Plačila naročnine ─────────────────────────────────────────────────
# Zakaj ločena tabela? Naročnina se prodaja po mesecih (30 €/mesec), zato
# potrebujemo evidenco: kdaj je šola sporočila plačilo in kdaj ga je glavni
# admin potrdil. PODATKOV O KARTICI tu NI in jih nikoli ne shranjujemo —
# plačilo poteka na PayPalovi strani, tu je le evidenca (znesek, sklic,
# opomba, kdo je potrdil).
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    amount_eur = Column(Integer, nullable=False, default=0)      # znesek v evrih (30)
    months = Column(Integer, nullable=False, default=1)          # koliko mesecev pokriva
    reference = Column(String, nullable=True, default="")        # sklic / naziv plačnika
    note = Column(Text, nullable=True, default="")               # sporočilo šole
    # pending = šola je sporočila plačilo, čaka potrditev
    # confirmed = glavni admin potrdil (naročnina podaljšana)
    # rejected = plačilo ni bilo prejeto / ni veljavno
    status = Column(String, nullable=False, default="pending", index=True)
    valid_until = Column(Date, nullable=True)                    # do kdaj je podaljšano (ob potrditvi)
    reported_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reported_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by = Column(String, nullable=True, default="")     # uporabniško ime potrjevalca


# ── Napisi vmesnika (večjezičnost SL/EN) ──────────────────────────────
# Zakaj tabela? Vsi napisi na gumbih in v pogovornih oknih naj bodo na enem
# mestu, v obeh jezikih, tako da jih lahko admin šole preklaplja (nastavitev
# UI_LANGUAGE). Aplikacija napis prebere iz te tabele po stabilnem ključu
# (npr. »btn_shrani«) in ga prikaže v izbranem jeziku; če prevoda ni, pade na
# slovenščino (ali na privzeto besedilo v predlogi).
class UIString(Base):
    __tablename__ = "ui_strings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, unique=True, index=True)  # stabilen ključ (npr. btn_shrani)
    context = Column(String, nullable=True, default="")            # kje se uporablja (opis/opomba)
    sl = Column(Text, nullable=True, default="")                   # slovenski napis
    en = Column(Text, nullable=True, default="")


# ── Datoteke zaslona (naložena obvestila) ──────────────────────────
# Obvestila, ki jih šolski admin naloži v UI (jpg/png/pdf → pdf postane
# jpg). Shranjena v DB — preživijo rollout in so vidna vsem replikam
# (skupna baza). Diskovna (vgrajena v sliko) se ob prvi uporabi prenesejo
# sem, da jih admin lahko tudi briše.
class ZaslonFile(Base):
    __tablename__ = "zasloni_files"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("school_id", "filename", name="uq_zasloni_files_school_file"),
    )                   # angleški napis
