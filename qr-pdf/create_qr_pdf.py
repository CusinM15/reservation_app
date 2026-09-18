from io import BytesIO

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


URL = "https://ostc-app.org"
OUTPUT_FILE = "qr_koda_z_naslovi.pdf"


def create_qr_code(url):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )

    qr.add_data(url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")

    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)

    return ImageReader(image_buffer)


def create_pdf():
    page_width, page_height = A4
    pdf = canvas.Canvas(OUTPUT_FILE, pagesize=A4)

    pdf.setTitle(
        "Rezervacije, napoved ocenjevanja in dnevi dejavnosti"
    )

    # Glavni naslov
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 70,
        "Aplikacija",
    )

    # Ena QR-koda na sredini
    qr_image = create_qr_code(URL)
    qr_size = 220

    pdf.drawImage(
        qr_image,
        (page_width - qr_size) / 2,
        page_height - 350,
        width=qr_size,
        height=qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )

    # Večji URL
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 390,
        URL,
    )

    # Trije naslovi
    titles = [
        "Rezervacije",
        "Napoved ocenjevanja",
        "Dnevi dejavnosti",
    ]

    pdf.setFont("Helvetica-Bold", 16)

    y_position = page_height - 455

    for title in titles:
        pdf.drawCentredString(
            page_width / 2,
            y_position,
            title,
        )
        y_position -= 38

    # Kratko navodilo
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(
        page_width / 2,
        70,
        "Skenirajte QR-kodo ali uporabite prikazano spletno povezavo.",
    )

    pdf.save()

    print(f"PDF created successfully: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_pdf()
