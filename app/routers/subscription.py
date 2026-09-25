# ─────────────────────────────────────────────────────────────────────────
# app/routers/subscription.py — naročnine: status, nakup, potrditev plačila
#
# Namen: šola vidi stanje svoje naročnine in kupi nov mesec; glavni admin
# potrjuje prejeta plačila (naročnina se podaljša za en mesec) in ureja
# nastavitve prodaje (cena, PayPal povezava).
#
# Varnost: podatkov o kartici tu NI — plačilo poteka na PayPalovi strani,
# v bazi je le evidenca (znesek, sklic, opomba, kdo je potrdil).
# ─────────────────────────────────────────────────────────────────────────

from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.app_settings import save_selling_config, selling_config
from app.audit import log_audit
from app.database import get_db
from app.models import Payment, School
from app.routers.schools import _manageable_school
from app.subscriptions import extend_subscription, subscription_state
from app.tenancy import get_request_user, is_main_admin

router = APIRouter(tags=["narocnina"])
templates = Jinja2Templates(directory="app/templates")


def _require_main_admin(db: Session, request: Request):
    """Samo glavni admin sme potrjevati plačila in urejati prodajo."""
    user = get_request_user(request, db)
    if user is None or not is_main_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Plačila in nastavitve prodaje lahko ureja le glavni admin.",
        )
    return user


@router.get("/narocnina", response_class=HTMLResponse)
def narocnina_page(
    request: Request,
    school_id: int | None = None,
    info: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Stanje naročnine + nakup za izbrano šolo (šolski ali glavni admin)."""
    # Učitelja sem preusmeri middleware, ko naročnina poteče — takrat naj vidi
    # le obvestilo (kupuje lahko samo administrator šole), ne pa napake 403.
    view_only = False
    try:
        school = _manageable_school(db, request, school_id)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
        user0 = get_request_user(request, db)
        school = db.query(School).filter(School.id == (user0.school_id if user0 else None)).first()
        if school is None:
            raise
        view_only = True

    user = get_request_user(request, db)

    payments = (
        db.query(Payment)
        .filter(Payment.school_id == school.id)
        .order_by(Payment.reported_at.desc())
        .limit(10)
        .all()
    )

    # Glavni admin vidi tudi vsa nerešena plačila po vseh šolah.
    pending: list[dict] = []
    if is_main_admin(user):
        rows = (
            db.query(Payment, School)
            .join(School, Payment.school_id == School.id)
            .filter(Payment.status == "pending")
            .order_by(Payment.reported_at)
            .all()
        )
        pending = [
            {
                "id": p.id,
                "school_name": s.name,
                "school_id": s.id,
                "amount_eur": p.amount_eur,
                "reference": p.reference,
                "note": p.note,
                "reported_at": p.reported_at,
            }
            for p, s in rows
        ]

    return templates.TemplateResponse(
        "narocnina.html",
        {
            "request": request,
            "school": school,
            "state": subscription_state(db, school.id),
            "cfg": selling_config(db),
            "payments": payments,
            "pending": pending,
            "is_main_admin": is_main_admin(user),
            "view_only": view_only,
            "user": user,
            "info": info,
            "error": error,
            "danes": datetime.now(),
        },
    )


@router.post("/narocnina/sporoci-placilo")
def report_payment(
    request: Request,
    reference: str = Form(""),
    note: str = Form(""),
    school_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Šola sporoči, da je plačala — glavni admin nato potrdi in podaljša."""
    school = _manageable_school(db, request, school_id)
    user = get_request_user(request, db)
    cfg = selling_config(db)

    db.add(Payment(
        school_id=school.id,
        amount_eur=cfg["price_eur"],
        months=1,
        reference=(reference or "").strip(),
        note=(note or "").strip(),
        status="pending",
        reported_by_id=user.id if user else None,
    ))
    db.commit()
    log_audit(
        db, user.id if user else None, user.username if user else "?",
        "report_payment",
        f"school_id={school.id}, znesek={cfg['price_eur']} EUR, sklic={reference}",
        school_id=school.id,
    )
    return RedirectResponse(
        url=f"/narocnina?school_id={school.id}&info=Plačilo je zabeleženo. "
            "Ko bo nakazilo prejeto, bo naročnina podaljšana za en mesec.",
        status_code=303,
    )


@router.post("/narocnina/potrdi/{payment_id}")
def confirm_payment(
    payment_id: int,
    request: Request,
    school_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Glavni admin potrdi prejeto plačilo → naročnina +1 mesec."""
    user = _require_main_admin(db, request)
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Plačilo ne obstaja.")

    until = extend_subscription(db, payment.school_id, payment.months or 1)
    payment.status = "confirmed"
    payment.valid_until = until
    payment.confirmed_at = datetime.utcnow()
    payment.confirmed_by = user.username
    db.commit()
    log_audit(
        db, user.id, user.username, "confirm_payment",
        f"payment_id={payment.id}, school_id={payment.school_id}, "
        f"znesek={payment.amount_eur} EUR, veljavnost do {until.isoformat()}",
        school_id=payment.school_id,
    )
    return RedirectResponse(
        url=f"/narocnina?school_id={payment.school_id}&info="
            f"Plačilo potrjeno — naročnina velja do {until.day}. {until.month}. {until.year}.",
        status_code=303,
    )


@router.post("/narocnina/zavrni/{payment_id}")
def reject_payment(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Glavni admin zavrne sporočeno plačilo (npr. nakazilo ni prispelo)."""
    user = _require_main_admin(db, request)
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Plačilo ne obstaja.")
    payment.status = "rejected"
    payment.confirmed_at = datetime.utcnow()
    payment.confirmed_by = user.username
    db.commit()
    log_audit(
        db, user.id, user.username, "reject_payment",
        f"payment_id={payment.id}, school_id={payment.school_id}",
        school_id=payment.school_id,
    )
    return RedirectResponse(
        url=f"/narocnina?school_id={payment.school_id}&info=Plačilo je označeno kot neprejeto.",
        status_code=303,
    )


@router.post("/narocnina/podaljsaj")
def grant_months(
    request: Request,
    months: int = Form(1),
    school_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Glavni admin podaljša naročnino brez plačila (npr. za svojo šolo)."""
    user = _require_main_admin(db, request)
    school = _manageable_school(db, request, school_id)
    until = extend_subscription(db, school.id, months or 1)
    db.commit()
    log_audit(
        db, user.id, user.username, "grant_subscription",
        f"school_id={school.id}, mesecev={months}, veljavnost do {until.isoformat()}",
        school_id=school.id,
    )
    return RedirectResponse(
        url=f"/narocnina?school_id={school.id}&info="
            f"Naročnina podaljšana do {until.day}. {until.month}. {until.year}.",
        status_code=303,
    )


@router.post("/narocnina/nastavitve")
def save_settings(
    request: Request,
    selling: str = Form("0"),
    price_eur: str = Form("30"),
    paypal_url: str = Form(""),
    payment_note: str = Form(""),
    db: Session = Depends(get_db),
):
    """Glavni admin shrani nastavitve prodaje (cena, PayPal povezava, navodila)."""
    user = _require_main_admin(db, request)
    save_selling_config(
        db,
        enabled=(str(selling) == "1"),
        price=price_eur,
        paypal=paypal_url,
        note=payment_note,
    )
    db.commit()
    log_audit(
        db, user.id, user.username, "save_selling_settings",
        f"prodaja={'vklopljena' if str(selling) == '1' else 'izklopljena'}, "
        f"cena={price_eur} EUR, paypal={'nastavljen' if paypal_url else 'prazen'}",
        school_id=None,
    )
    return RedirectResponse(
        url="/narocnina?info=Nastavitve prodaje so shranjene.", status_code=303
    )
