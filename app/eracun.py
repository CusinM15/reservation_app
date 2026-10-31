# ─────────────────────────────────────────────────────────────────────────
# app/eracun.py — Generiranje in pošiljanje e-računa (elektronskega računa)
#
# Namen: Šolski admin (ali glavni admin) na strani /narocnina klikne »Naroči
# račun«, aplikacija pa naredi e-račun (e-SLOG 2.0 / UBL XML + PDF povzetek)
# za letno naročnino in ga pošlje po e-pošti.
#
# Standard: e-SLOG 2.0 Račun (Center e-Poslovja Slovenije, epos.si).
# Dokumentacija in sheme so javne/brezplačne. XML je zgrajen po UBL/e-SLOG
# strukturi (AccountingSupplierParty / AccountingCustomerParty / obračun
# DDV / PaymentMeans z IBAN in sklicem).
#
# Faza 1: XML pošljemo brez kvalificiranega podpisa — dovolj za e-račun po
# e-pošti (šola ga lahko uvozi v svoj računovodski program ali ročno uporabi
# PDF). Kvalificiran podpis (QES) + oddaja na nacionalno platformo = faza 2.
# Podpis (ime podpisnika) je v tej fazi le tekstovno polje, shranjeno skupaj
# z izdajateljem in videno v XML + PDF.
#
# Ta modul je BREZ odvisnosti od DB — vse vhodne podatke dobi v slovarju
# `invoice`, zato ga lahko testiramo samostojno.
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import ssl
import smtplib
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from xml.sax.saxutils import escape

# Stopnja DDV (slovenska splošna oznaka 2026).
DDV_RATE_PCT = 22.0


# ── SI sklic (slovenska referenca plačila, ISO 7064 Mod 97) ─────────────
# Sestavi validno slovensko referenco »SIbb-####-###« iz zaporedne številke.
# Preverbni števki se izračunata tako, da je celotno število deljivo z 97
# (pogoj: (base*100 + check) mod 97 == 1) — po konvenciji UPN/e-račun.
def si_sklic(base: int) -> str:
    base = int(base)
    check = (98 - (base * 100 % 97)) % 97
    if check == 0:
        check = 97
    # Veljavna slovenska referenca: številka + kontrolni števki (celotno
    # število deljivo z 97 → (base*100+check) % 97 == 1), predpona "SI".
    return f"SI{base}{check:02d}"


# ── Pomožniki za XML ────────────────────────────────────────────────────
def _money(value: float) -> str:
    """Večina e-SLOG primerov uporabi decimalno piko v vrednosti (2 mesti)."""
    return f"{float(value):.2f}"


def _amount_spec(name: str, value: float) -> str:
    """cbc element s tekstovno vrednostjo."""
    return f"<cbc:{name}>{escape(_money(value))}</cbc:{name}>"


def build_invoice_xml(inv: dict) -> str:
    """Zgradi e-SLOG 2.0 / UBL Račun XML iz slovarja `inv`.

    Pričakovani ključi (vsi družine, ki jih zgradi router):
      number, issue_date, due_date, currency, sklic
      net, ddv, gross, unit_net, qty
      item_name, item_desc
      issuer: {name, address, post, tax, maticna, iban, bank, email, sign}
      buyer:  {name, address, post, tax, email}
    """
    i = inv["issuer"]
    b = inv["buyer"]
    due = inv["due_date"].strftime("%Y-%m-%d") if isinstance(inv["due_date"], date) else str(inv["due_date"])
    issue = inv["issue_date"].strftime("%Y-%m-%d") if isinstance(inv["issue_date"], date) else str(inv["issue_date"])

    # Davčna številka (podjetje) — e-SLOG želi brez predpone SI v CompanyID,
    # ker nosilec pove identifikacijska shema. Odstranimo morebitni "SI".
    tax_id = str(i.get("tax", "")).replace("SI", "").strip()
    sign = str(i.get("sign", "")).strip()

    lines = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    lines.append(
        "<Invoice xmlns=\"urn:eslog:cenim\" "
        "xmlns:cac=\"urn:oasis:names:specification:ubl:schema:xsd:"
        "CommonAggregateComponents-2\" "
        "xmlns:cbc=\"urn:oasis:names:specification:ubl:schema:xsd:"
        "CommonBasicComponents-2\" "
        "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
    )
    lines.append("  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>")
    lines.append("  <cbc:CustomizationID>urn:eslog:cenim</cbc:CustomizationID>")
    lines.append(f"  <cbc:ID>{escape(str(inv['number']))}</cbc:ID>")
    lines.append(f"  <cbc:IssueDate>{issue}</cbc:IssueDate>")
    lines.append(f"  <cbc:DueDate>{due}</cbc:DueDate>")
    lines.append("  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>")
    lines.append(f"  <cbc:DocumentCurrencyCode>{escape(str(inv.get('currency', 'EUR')))}</cbc:DocumentCurrencyCode>")
    lines.append(f"  <cbc:Note>{escape(str(inv.get('item_desc', '')))}</cbc:Note>")

    # ── Podpis (tekstovno polje, fazo 2 = QES cert) ───────────────────
    if sign:
        lines.append("  <cac:Signature>")
        lines.append(f"    <cbc:ID>{escape(sign)}</cbc:ID>")
        lines.append("    <cac:SignatoryParty><cac:PartyName><cbc:Name>"
                     f"{escape(sign)}</cbc:Name></cac:PartyName></cac:SignatoryParty>")
        lines.append("  </cac:Signature>")

    # ── Izdajatelj (bratova firma / s.p.) ──────────────────────────────
    lines.append("  <cac:AccountingSupplierParty>")
    lines.append("    <cac:Party>")
    lines.append("      <cac:PartyName><cbc:Name>"
                 f"{escape(str(i.get('name', '')))}</cbc:Name></cac:PartyName>")
    lines.append("      <cac:PostalAddress>")
    lines.append("        <cbc:StreetName>"
                 f"{escape(str(i.get('address', '')))}</cbc:StreetName>")
    lines.append("        <cbc:CityName>"
                 f"{escape(str(i.get('post', '')))}</cbc:CityName>")
    lines.append("      </cac:PostalAddress>")
    lines.append("      <cac:PartyTaxScheme>"
                 "<cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>"
                 "</cac:PartyTaxScheme>")
    lines.append("      <cac:PartyLegalEntity>")
    lines.append("        <cbc:RegistrationName>"
                 f"{escape(str(i.get('name', '')))}</cbc:RegistrationName>")
    if tax_id:
        lines.append("        <cbc:CompanyID schemeID=\"VAT\">"
                     f"{escape(tax_id)}</cbc:CompanyID>")
    if i.get("maticna"):
        lines.append("        <cac:CorporateRegistrationScheme>"
                     "<cbc:ID>"
                     f"{escape(str(i.get('maticna', '')))}"
                     "</cbc:ID></cac:CorporateRegistrationScheme>")
    lines.append("      </cac:PartyLegalEntity>")
    lines.append("      <cac:Contact><cbc:ElectronicMail>"
                 f"{escape(str(i.get('email', '')))}</cbc:ElectronicMail>"
                 "</cac:Contact>")
    lines.append("    </cac:Party>")
    lines.append("  </cac:AccountingSupplierParty>")

    # ── Kupcu (šola) ──────────────────────────────────────────────────
    lines.append("  <cac:AccountingCustomerParty>")
    lines.append("    <cac:Party>")
    lines.append("      <cac:PartyName><cbc:Name>"
                 f"{escape(str(b.get('name', '')))}</cbc:Name></cac:PartyName>")
    lines.append("      <cac:PostalAddress>")
    lines.append("        <cbc:StreetName>"
                 f"{escape(str(b.get('address', '')))}</cbc:StreetName>")
    lines.append("        <cbc:CityName>"
                 f"{escape(str(b.get('post', '')))}</cbc:CityName>")
    lines.append("      </cac:PostalAddress>")
    lines.append("      <cac:PartyLegalEntity>")
    lines.append("        <cbc:RegistrationName>"
                 f"{escape(str(b.get('name', '')))}</cbc:RegistrationName>")
    if b.get("tax"):
        lines.append("        <cbc:CompanyID schemeID=\"VAT\">"
                     f"{escape(str(b.get('tax', '')).replace('SI', ''))}"
                     "</cbc:CompanyID>")
    lines.append("      </cac:PartyLegalEntity>")
    lines.append("      <cac:Contact><cbc:ElectronicMail>"
                 f"{escape(str(b.get('email', '')))}</cbc:ElectronicMail>"
                 "</cac:Contact>")
    lines.append("    </cac:Party>")
    lines.append("  </cac:AccountingCustomerParty>")

    # ── Plačilni nalog (IBAN + sklic) ─────────────────────────────────
    lines.append("  <cac:PaymentMeans>")
    lines.append("    <cbc:PaymentMeansCode>30</cbc:PaymentMeansCode>")  # 30 = bankovno nakazilo
    lines.append("    <cac:PayeeFinancialAccount>")
    lines.append("      <cbc:ID>"
                 f"{escape(str(i.get('iban', '')))}</cbc:ID>")
    lines.append("      <cac:PaymentMandate><cbc:ID>"
                 f"{escape(str(inv.get('sklic', '')))}</cbc:ID>"
                 "</cac:PaymentMandate>")
    lines.append("    </cac:PayeeFinancialAccount>")
    lines.append("  </cac:PaymentMeans>")

    # ── Davčni povzetek (DDV) ─────────────────────────────────────────
    lines.append("  <cac:TaxTotal><cbc:TaxAmount currencyID=\"EUR\">"
                 f"{_money(inv['ddv'])}</cbc:TaxAmount>")
    lines.append("    <cac:TaxSubtotal>")
    lines.append("      <cbc:TaxableAmount currencyID=\"EUR\">"
                 f"{_money(inv['net'])}</cbc:TaxableAmount>")
    lines.append("      <cbc:TaxAmount currencyID=\"EUR\">"
                 f"{_money(inv['ddv'])}</cbc:TaxAmount>")
    lines.append("      <cac:TaxCategory>")
    lines.append("        <cbc:ID>S</cbc:ID>")
    lines.append("        <cbc:Percent>"
                 f"{DDV_RATE_PCT:.0f}</cbc:Percent>")
    lines.append("        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>")
    lines.append("      </cac:TaxCategory>")
    lines.append("    </cac:TaxSubtotal>")
    lines.append("  </cac:TaxTotal>")

    # ── Σ money ───────────────────────────────────────────────────────
    lines.append("  <cac:LegalMonetaryTotal>")
    lines.append(_amount_spec("LineExtensionAmount", inv["net"]))
    lines.append(_amount_spec("TaxExclusiveAmount", inv["net"]))
    lines.append(_amount_spec("TaxInclusiveAmount", inv["gross"]))
    lines.append(_amount_spec("PayableAmount", inv["gross"]))
    lines.append("  </cac:LegalMonetaryTotal>")

    # ── Postavka ──────────────────────────────────────────────────────
    lines.append("  <cac:InvoiceLine>")
    lines.append("    <cbc:ID>1</cbc:ID>")
    lines.append("    <cbc:InvoicedQuantity unitCode=\"C62\">"
                 f"{inv.get('qty', 1)}</cbc:InvoicedQuantity>")
    lines.append(_amount_spec("LineExtensionAmount", inv["net"]))
    lines.append("    <cac:Item>")
    lines.append("      <cbc:Name>"
                 f"{escape(str(inv.get('item_name', '')))}</cbc:Name>")
    lines.append("      <cbc:Description>"
                 f"{escape(str(inv.get('item_desc', '')))}</cbc:Description>")
    lines.append("      <cac:ClassifiedTaxCategory>")
    lines.append("        <cbc:ID>S</cbc:ID>")
    lines.append("        <cbc:Percent>"
                 f"{DDV_RATE_PCT:.0f}</cbc:Percent>")
    lines.append("        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>")
    lines.append("      </cac:ClassifiedTaxCategory>")
    lines.append("    </cac:Item>")
    lines.append("    <cac:Price><cbc:PriceAmount currencyID=\"EUR\">"
                 f"{_money(inv['unit_net'])}</cbc:PriceAmount></cac:Price>")
    lines.append("  </cac:InvoiceLine>")

    lines.append("</Invoice>")
    return "\n".join(lines)


# ── PDF povzetek (weasyprint) ────────────────────────────────────────────
def build_invoice_pdf(inv: dict) -> bytes:
    """Naredi lep PDF povzetek e-računa (weasyprint)."""
    from weasyprint import HTML as WP_HTML

    i = inv["issuer"]
    b = inv["buyer"]
    sign = str(i.get("sign", "")).strip()
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>
  body {{ font-family: DejaVu Sans, sans-serif; font-size: 12px; color: #222; margin: 24px; }}
  h1 {{ font-size: 22px; color: #1a5276; margin: 0 0 4px; }}
  .muted {{ color: #777; font-size: 11px; }}
  .grid {{ display: flex; gap: 24px; margin-top: 18px; }}
  .col {{ flex: 1; }}
  .box {{ border: 1px solid #ccc; border-radius: 6px; padding: 10px 14px; margin-top: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 14px; }}
  th, td {{ border-bottom: 1px solid #eee; padding: 6px 8px; text-align: left; }}
  th {{ background: #f4f6f7; }}
  .tot {{ font-weight: bold; }}
  .right {{ text-align: right; }}
  .promo {{ color: #333; line-height: 1.5; }}
</style></head><body>
  <h1>Račun št. {escape(str(inv['number']))}</h1>
  <div class="muted">e-račun · e-SLOG 2.0 · izdano {inv['issue_date']:%d. %m. %Y} ·
    zapadlost {inv['due_date']:%d. %m. %Y}</div>

  <div class="grid">
    <div class="col"><strong>Izdajatelj</strong><div>{escape(str(i.get('name','')))}</div>
      <div>{escape(str(i.get('address','')))}</div><div>{escape(str(i.get('post','')))}</div>
      <div>Davčna: {escape(str(i.get('tax','')) or '—')}</div>
      <div>Mat. št.: {escape(str(i.get('maticna','')) or '—')}</div></div>
    <div class="col"><strong>Kupec</strong><div>{escape(str(b.get('name','')))}</div>
      <div>{escape(str(b.get('address','')) or '—')}</div>
      <div>{escape(str(b.get('post','')) or '—')}</div></div>
  </div>

  <div class="box">
    <div>Postavka: <strong>{escape(str(inv['item_name']))}</strong> &nbsp;·&nbsp; količina {inv.get('qty',1)}</div>
    <div class="muted promo" style="margin-top:6px">{escape(str(inv['item_desc']))}</div>
  </div>

  <table>
    <tr><th>Opis</th><th class="right">Neto</th><th class="right">DDV {DDV_RATE_PCT:.0f}%</th><th class="right">Bruto</th></tr>
    <tr><td>{escape(str(inv['item_name']))}</td>
      <td class="right">{inv['net']:.2f} €</td><td class="right">{inv['ddv']:.2f} €</td>
      <td class="right">{inv['gross']:.2f} €</td></tr>
  </table>

  <table>
    <tr><td class="tot">Skupaj za plačilo</td><td class="right tot">{inv['gross']:.2f} €</td></tr>
    <tr><td>IBAN</td><td class="right">{escape(str(i.get('iban','')))}</td></tr>
    <tr><td>Referenca (sklic)</td><td class="right">{escape(str(inv['sklic']))}</td></tr>
  </table>

  <div class="muted" style="margin-top:18px">Račun je ustvarjen samodejno. Vsi zneski so v EUR in vključujejo DDV.</div>
  {f'<div style="margin-top:18px">Podpisal: <strong>{escape(sign)}</strong></div>' if sign else ''}
</body></html>"""
    return WP_HTML(string=html).write_pdf() or b""


# ── Pošiljanje po e-pošti (e-račun = XML + PDF priponki) ─────────────────
def send_e_racun_email(config, to_email: str, inv: dict,
                       xml: str, pdf: bytes) -> tuple[bool, str]:
    """Pošlji e-račun kot priponki (XML + PDF). Vrne (uspeh, sporočilo)."""
    if not to_email:
        return False, "Naslov za prejem e-računa (ADMIN_EMAIL šole) ni nastavljen."
    if not config.MAIL_PASSWORD:
        return False, "SMTP geslo ni nastavljeno — pošiljanje ni mogoče."

    base = f"eracun-{inv['number']}"
    msg = MIMEMultipart()
    msg["Subject"] = f"E-račun {inv['number']} — {inv['item_name']} ({inv['gross']:.2f} EUR)"
    msg["From"] = config.MAIL_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(
        f"Pozdravljeni,\n\n"
        f"v priponki je e-račun št. {inv['number']} za {inv['item_name']}.\n"
        f"Znesek za plačilo: {inv['gross']:.2f} EUR (vključno z DDV).\n"
        f"IBAN: {inv['issuer']['iban']}\n"
        f"Referenca (sklic): {inv['sklic']}\n"
        f"Zapadlost: {inv['due_date']:%d. %m. %Y}\n\n"
        f"Priponka .xml je e-račun po standardu e-SLOG 2.0 (za uvoz v "
        f"računovodski program), .pdf pa tiskan povzetek.\n"
        f"\nLep pozdrav,\n{inv['issuer']['name']}",
        "plain", "utf-8",
    ))

    xml_part = MIMEApplication(xml.encode("utf-8"), _subtype="xml")
    xml_part.add_header("Content-Disposition", "attachment",
                        filename=f"{base}.xml")
    msg.attach(xml_part)

    pdf_part = MIMEApplication(pdf, _subtype="pdf")
    pdf_part.add_header("Content-Disposition", "attachment",
                        filename=f"{base}.pdf")
    msg.attach(pdf_part)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT) as s:
            s.starttls(context=context)
            s.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
            s.send_message(msg)
    except Exception as exc:                      # noqa: BLE001
        return False, f"Pošiljanje ni uspelo: {exc}"
    return True, f"E-račun poslan na {to_email}."