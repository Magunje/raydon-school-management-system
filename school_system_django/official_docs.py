import base64
import io
import os
from decimal import Decimal, InvalidOperation

from django.conf import settings as django_settings
from django.urls import NoReverseMatch, reverse


NAVY = "#071f4d"
GOLD = "#c18a13"
BORDER = "#9db2d0"
LIGHT_BLUE = "#edf5ff"
INK = "#081b3f"


def money_decimal(value):
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def money_text(value):
    return f"USD {float(money_decimal(value)):,.2f}"


ONES = [
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
SCALES = ["", "Thousand", "Million", "Billion"]


def _under_thousand_to_words(number):
    number = int(number)
    parts = []
    if number >= 100:
        parts.append(f"{ONES[number // 100]} Hundred")
        number %= 100
    if number >= 20:
        parts.append(TENS[number // 10])
        number %= 10
    if 0 < number < 20:
        parts.append(ONES[number])
    return " ".join(parts)


def amount_in_words(value, currency="United States Dollars"):
    amount = money_decimal(value)
    whole = int(amount)
    cents = int((amount - Decimal(whole)) * 100)
    if whole == 0:
        words = "Zero"
    else:
        groups = []
        scale_index = 0
        number = whole
        while number > 0:
            number, chunk = divmod(number, 1000)
            if chunk:
                chunk_words = _under_thousand_to_words(chunk)
                scale = SCALES[scale_index] if scale_index < len(SCALES) else ""
                groups.append(f"{chunk_words} {scale}".strip())
            scale_index += 1
        words = " ".join(reversed(groups))
    if cents:
        return f"{words} {currency} and {cents:02d} Cents Only"
    return f"{words} {currency} Only"


def official_logo_path(settings):
    custom_logo = settings.get("school_logo") if settings else None
    candidates = []
    if custom_logo:
        candidates.append(os.path.join(django_settings.BASE_DIR, "static", custom_logo))
        candidates.append(os.path.join(django_settings.BASE_DIR, custom_logo))
    candidates.append(os.path.join(django_settings.BASE_DIR, "static", "img", "raydon-system-logo.png"))
    for path in candidates:
        if path and os.path.exists(path) and not path.lower().endswith(".svg"):
            return path
        if path and path.lower().endswith(".svg"):
            png_path = path.rsplit(".", 1)[0] + ".png"
            if os.path.exists(png_path):
                return png_path
    return None


def school_website(settings):
    site = (settings or {}).get("school_website") or "www.raydonschool.ac.zw"
    return site.replace("https://", "").replace("http://", "").strip("/")


def school_contact_line(settings):
    pieces = []
    if (settings or {}).get("school_phone"):
        pieces.append(settings.get("school_phone"))
    if (settings or {}).get("school_email"):
        pieces.append(settings.get("school_email"))
    site = school_website(settings)
    if site:
        pieces.append(site)
    return "  |  ".join(pieces)


def build_absolute_or_default(request, route_name, args, fallback_path):
    if request:
        try:
            path = reverse(route_name, args=args)
            return request.build_absolute_uri(path)
        except NoReverseMatch:
            return request.build_absolute_uri(fallback_path)
    return fallback_path


def result_verify_url(request, result_id):
    return build_absolute_or_default(request, "results_verify", [result_id], f"/results/verify/{result_id}")


def receipt_verify_url(request, receipt_no):
    return build_absolute_or_default(request, "receipt_by_number", [receipt_no], f"/receipt/{receipt_no}")


def qr_png_bytes(value):
    import qrcode

    qr = qrcode.QRCode(version=1, box_size=5, border=1)
    qr.add_data(value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def qr_data_uri(value):
    try:
        data = base64.b64encode(qr_png_bytes(value)).decode("ascii")
        return f"data:image/png;base64,{data}"
    except Exception:
        return ""


def qr_flowable(value, size_mm=28):
    from reportlab.lib.units import mm
    from reportlab.platypus import Image

    try:
        buffer = io.BytesIO(qr_png_bytes(value))
        return Image(buffer, width=size_mm * mm, height=size_mm * mm)
    except Exception:
        return None


def published_date_time(value):
    text = str(value or "").strip()
    if not text:
        return "-", "-"
    if "T" in text:
        date_part, time_part = text.split("T", 1)
    elif " " in text:
        date_part, time_part = text.split(" ", 1)
    else:
        return text[:10], "-"
    return date_part[:10], time_part[:5]


def receipt_status(balance):
    bal = money_decimal(balance)
    if bal < 0:
        return "CREDIT"
    if bal == 0:
        return "PAID"
    return "BALANCE DUE"


def create_reportlab_stamp(school_name, date_str, time_str, term_str=None, year_str=None, status_str="PAYMENT VERIFIED", stamp_color="#0f2f57"):
    import math
    from reportlab.graphics.shapes import Drawing, Circle, String, Group
    from reportlab.lib import colors

    d = Drawing(90, 90)
    
    # Outer circle
    d.add(Circle(45, 45, 42, strokeColor=colors.HexColor(stamp_color), strokeWidth=1.8, fillColor=None))
    # Inner circle (dashed)
    d.add(Circle(45, 45, 36, strokeColor=colors.HexColor(stamp_color), strokeWidth=0.8, fillColor=None, strokeDashArray=[2.5, 1.5]))
    
    # Group for rotation
    g = Group()
    g.translate(45, 45)
    g.rotate(-8) # Distressed rotated stamp look!
    
    # Status center text
    status_text = status_str.upper()
    g.add(String(0, 3, status_text, fontName="Helvetica-Bold", fontSize=8, textAnchor="middle", fillColor=colors.HexColor(stamp_color)))
    
    # Date / Time
    g.add(String(0, -5, date_str, fontName="Helvetica-Bold", fontSize=5.5, textAnchor="middle", fillColor=colors.HexColor(stamp_color)))
    g.add(String(0, -11, time_str, fontName="Helvetica-Bold", fontSize=5.5, textAnchor="middle", fillColor=colors.HexColor(stamp_color)))
    
    # Term/Year if provided
    if term_str and year_str:
        g.add(String(0, -17, f"{term_str.upper()} {year_str}", fontName="Helvetica-Bold", fontSize=4.5, textAnchor="middle", fillColor=colors.HexColor(stamp_color)))

    # Top curved text
    top_text = school_name[:32].upper()
    num_chars = len(top_text)
    start_angle = 155
    end_angle = 25
    angle_range = start_angle - end_angle
    for i, char in enumerate(top_text):
        angle = start_angle - (i * angle_range / max(num_chars - 1, 1))
        rad = math.radians(angle)
        x = 30 * math.cos(rad)
        y = 30 * math.sin(rad)
        char_g = Group()
        char_g.translate(x, y)
        char_g.rotate(angle - 90)
        char_g.add(String(0, 0, char, fontName="Helvetica-Bold", fontSize=4.5, textAnchor="middle", fillColor=colors.HexColor(stamp_color)))
        g.add(char_g)

    # Bottom curved text
    bottom_text = "★ OFFICIAL SEAL ★"
    num_chars_b = len(bottom_text)
    start_angle_b = -155
    end_angle_b = -25
    angle_range_b = end_angle_b - start_angle_b
    for i, char in enumerate(bottom_text):
        angle = start_angle_b + (i * angle_range_b / max(num_chars_b - 1, 1))
        rad = math.radians(angle)
        x = 30 * math.cos(rad)
        y = 30 * math.sin(rad)
        char_g = Group()
        char_g.translate(x, y)
        char_g.rotate(angle + 90)
        char_g.add(String(0, 0, char, fontName="Helvetica-Bold", fontSize=4.5, textAnchor="middle", fillColor=colors.HexColor(stamp_color)))
        g.add(char_g)

    d.add(g)
    return d
