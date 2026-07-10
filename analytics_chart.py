# -*- coding: utf-8 -*-
"""
رسم نمودار میله‌ای ساده‌ی «رشد کاربران روزانه» برای دستور /stats.

برخلاف image_report.py، این ماژول فقط از عدد و تاریخ لاتین (مثلاً 07-10) استفاده
می‌کنه، پس نیازی به فونت فارسی نداره و همیشه (حتی بدون فونت Vazirmatn) کار می‌کنه.
"""
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 900, 450
MARGIN = 60
BG = (24, 20, 54)
BAR = (240, 195, 90)
GRID = (70, 65, 100)
TEXT = (230, 228, 240)


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_growth_chart(growth_rows: list) -> BytesIO:
    """
    growth_rows: [{"day": "2026-07-08", "new_users": 3}, ...]
    خروجی: تصویر PNG به‌صورت BytesIO
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    font_title = _font(28)
    font_label = _font(18)
    font_value = _font(20)

    draw.text((MARGIN, 20), "Daily New Users (last 7 days)", font=font_title, fill=TEXT)

    if not growth_rows:
        draw.text((MARGIN, HEIGHT // 2), "No data yet", font=font_label, fill=TEXT)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    chart_top = 100
    chart_bottom = HEIGHT - 60
    chart_left = MARGIN
    chart_right = WIDTH - MARGIN
    chart_h = chart_bottom - chart_top

    max_val = max(r["new_users"] for r in growth_rows) or 1
    n = len(growth_rows)
    slot_w = (chart_right - chart_left) / n
    bar_w = slot_w * 0.5

    # خطوط راهنما (grid)
    for i in range(5):
        y = chart_top + chart_h * i / 4
        draw.line([(chart_left, y), (chart_right, y)], fill=GRID, width=1)
        val = round(max_val * (4 - i) / 4)
        draw.text((chart_left - 35, y - 8), str(val), font=font_label, fill=TEXT)

    for i, row in enumerate(growth_rows):
        val = row["new_users"]
        bar_h = (val / max_val) * chart_h if max_val else 0
        x0 = chart_left + i * slot_w + (slot_w - bar_w) / 2
        x1 = x0 + bar_w
        y1 = chart_bottom
        y0 = chart_bottom - bar_h
        draw.rectangle([x0, y0, x1, y1], fill=BAR)

        # مقدار بالای میله
        val_text = str(val)
        vtw = draw.textlength(val_text, font=font_value)
        draw.text((x0 + (bar_w - vtw) / 2, y0 - 26), val_text, font=font_value, fill=TEXT)

        # برچسب تاریخ (مثلاً 07-10) زیر محور
        day_label = row["day"][5:]  # "MM-DD"
        dtw = draw.textlength(day_label, font=font_label)
        draw.text((chart_left + i * slot_w + (slot_w - dtw) / 2, chart_bottom + 10),
                   day_label, font=font_label, fill=TEXT)

    draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=TEXT, width=2)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
