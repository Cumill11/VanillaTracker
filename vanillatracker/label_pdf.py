"""
Label PDF — strona 35×25mm na etykietę.
Układ: [ QR code 20×20mm ] | [ BS-00001 obrócony +90° ]
"""
import io
import qrcode
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PAGE_W = 35 * mm
PAGE_H = 25 * mm

QR_SIZE  = 20 * mm
QR_X     = 1.0 * mm + 2.5 * mm          # 1mm margines + 2,5mm przesunięcie w prawo
QR_Y     = (PAGE_H - QR_SIZE) / 2       # wyśrodkowanie pionowe

SEPARATOR_X = QR_X + QR_SIZE + 0.8 * mm
STRIP_LEFT  = SEPARATOR_X + 1.0 * mm
STRIP_RIGHT = PAGE_W - QR_X              # prawy margines = lewy (3,5mm)
STRIP_W     = STRIP_RIGHT - STRIP_LEFT


def _make_qr(url: str) -> io.BytesIO:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _max_font_size(c, text, font, max_len, max_asc, start=16.0):
    size = start
    while size >= 5:
        c.setFont(font, size)
        w   = c.stringWidth(text, font, size)
        asc = size * 0.72 / 72 * 25.4 * mm
        if w <= max_len and asc <= max_asc:
            return size
        size -= 0.25
    return 5.0


def _draw_label(c, asset_tag: str, asset_url: str) -> None:
    qr_buf = _make_qr(asset_url)
    c.drawImage(ImageReader(qr_buf), QR_X, QR_Y,
                width=QR_SIZE, height=QR_SIZE, preserveAspectRatio=True, mask="auto")
    c.setStrokeColorRGB(0.70, 0.70, 0.70)
    c.setLineWidth(0.4)
    c.line(SEPARATOR_X, 1.0 * mm, SEPARATOR_X, PAGE_H - 1.0 * mm)

    font_name = "Helvetica-Bold"
    font_size = _max_font_size(c, asset_tag, font_name,
                               PAGE_H - 2.5 * mm, STRIP_W - 0.5 * mm)
    baseline_x = STRIP_RIGHT - 0.6 * mm
    c.saveState()
    c.translate(baseline_x, PAGE_H / 2)
    c.rotate(90)
    c.setFont(font_name, font_size)
    c.setFillColorRGB(0.05, 0.05, 0.05)
    c.drawCentredString(0, 0, asset_tag)
    c.restoreState()


def generate_labels_pdf(assets: list, base_url: str) -> io.BytesIO:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    c.setTitle("VanillaTracker — Etykiety")
    c.setAuthor("VanillaTracker")
    for i, asset in enumerate(assets):
        if i > 0:
            c.showPage()
        _draw_label(c, asset.asset_tag, f"{base_url}/assets/{asset.id}/")
    c.save()
    buf.seek(0)
    return buf
