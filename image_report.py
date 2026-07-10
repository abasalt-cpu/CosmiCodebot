# -*- coding: utf-8 -*-
"""
تولید تصویر گزارش «عدد کیهانی» با Pillow.

⚠️ نیازمندی مهم که باید خودت اضافه کنی:
یک فونت فارسی (پیشنهاد: Vazirmatn) باید در پوشه‌ی fonts/ کنار همین فایل باشه:
    fonts/Vazirmatn-Regular.ttf
    fonts/Vazirmatn-Bold.ttf
می‌تونی از اینجا دانلودش کنی: https://github.com/rastikerdar/vazirmatn/releases
(فایل‌های .ttf رو از پوشه‌ی fonts داخل زیپ بردار و همینجا کپی کن.)

بدون این فونت، رندر متن فارسی درست کار نمی‌کنه (چون فونت‌های پیش‌فرض سیستم
معمولاً حروف فارسی/عربی رو پشتیبانی نمی‌کنن). اگه فونت پیدا نشه، کد به‌جای
کرش‌کردن، فقط پیام متنی معمولی رو می‌فرسته و از ارسال تصویر صرف‌نظر می‌کنه.

پکیج‌های موردنیاز (در requirements.txt اضافه شده‌اند):
    Pillow
    arabic-reshaper
    python-bidi
"""
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_REGULAR = os.path.join(BASE_DIR, "fonts", "Vazirmatn-Regular.ttf")
FONT_BOLD = os.path.join(BASE_DIR, "fonts", "Vazirmatn-Bold.ttf")

WIDTH = 1080
BG_TOP = (20, 16, 48)
BG_BOTTOM = (55, 20, 90)
GOLD = (240, 195, 90)
WHITE = (245, 245, 250)
LIGHT = (200, 195, 220)


def fonts_available() -> bool:
    return os.path.exists(FONT_REGULAR) and os.path.exists(FONT_BOLD)


def _shape(text: str) -> str:
    """آماده‌سازی متن فارسی برای رسم صحیح (اتصال حروف + راست‌به‌چپ)."""
    import arabic_reshaper
    from bidi.algorithm import get_display

    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def _vertical_gradient(width, height, top, bottom):
    base = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(base)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return base


def _wrap_text(draw, text, font, max_width):
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            if not trial:
                continue
            if draw.textlength(_shape(trial), font=font) <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if not paragraph:
            lines.append("")
    return lines


def render_report_image(full_name: str, data: dict) -> BytesIO:
    """یک تصویر PNG از گزارش می‌سازد و به‌صورت BytesIO برمی‌گرداند."""
    if not fonts_available():
        raise FileNotFoundError(
            "فونت فارسی پیدا نشد. فایل‌های Vazirmatn-Regular.ttf و "
            "Vazirmatn-Bold.ttf را در پوشه‌ی fonts/ قرار بده."
        )

    font_title = ImageFont.truetype(FONT_BOLD, 46)
    font_h2 = ImageFont.truetype(FONT_BOLD, 32)
    font_body = ImageFont.truetype(FONT_REGULAR, 26)
    font_code = ImageFont.truetype(FONT_REGULAR, 24)

    margin = 60
    content_width = WIDTH - 2 * margin

    # ابتدا با یک بوم موقت ارتفاع لازم را محاسبه می‌کنیم
    tmp_img = Image.new("RGB", (WIDTH, 100))
    tmp_draw = ImageDraw.Draw(tmp_img)

    sections = [
        ("🌌 کد کیهانی", data["cosmic_code"], font_code),
        ("📅 تاریخ میلادی", data["gregorian_date"], font_body),
        ("☀️ عدد خورشیدی", str(data["solar_num"]), font_body),
        (f"📌 ارتعاش تاریخ تولد: {data['vibration_num']}", data["vibration_text"], font_body),
        (f"📌 عدد تقدیر: {data['fate_num']}", data["fate_text"], font_body),
        (f"📌 عدد سرنوشت: {data['destiny_num']}", data["destiny_text"], font_body),
        ("💰 وضعیت درآمد و معیشت", data["income_text"], font_body),
        ("🏛 پایگاه اجتماعی", data["status_text"], font_body),
        (f"🔮 عدد باطن فرد: {data['baten_num']} ({data['baten_title']})", data["baten_desc"], font_body),
    ]

    line_h = 40
    y_cursor = 220
    wrapped_sections = []
    for heading, body, font in sections:
        body_lines = _wrap_text(tmp_draw, body, font, content_width)
        wrapped_sections.append((heading, body_lines, font))
        y_cursor += 44 + len(body_lines) * line_h + 24

    height = y_cursor + 60

    img = _vertical_gradient(WIDTH, height, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)

    # عنوان
    title = _shape(full_name)
    tw = draw.textlength(title, font=font_title)
    draw.text(((WIDTH - tw) / 2, 60), title, font=font_title, fill=GOLD)
    draw.text(((WIDTH - 260) / 2, 130), _shape("گزارش عدد کیهانی"), font=font_h2, fill=WHITE)

    y = 220
    for heading, body_lines, font in wrapped_sections:
        htext = _shape(heading)
        htw = draw.textlength(htext, font=font_h2)
        draw.text((WIDTH - margin - htw, y), htext, font=font_h2, fill=GOLD)
        y += 44
        for line in body_lines:
            ltext = _shape(line)
            ltw = draw.textlength(ltext, font=font)
            draw.text((WIDTH - margin - ltw, y), ltext, font=font, fill=LIGHT)
            y += line_h
        y += 24

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
