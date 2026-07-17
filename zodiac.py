# -*- coding: utf-8 -*-
"""
طالع‌بینی/برج روزانه — بر پایه‌ی ماه تولد شمسی.

نگاشت ساده‌شده‌ی ماه شمسی به برج غربی (فروردین≈حمل و...) که رایج‌ترین تناظر
استفاده‌شده در محتوای فارسیه.

مثل فال حافظ، پیش‌بینی هر برج در هر روز ثابته (تا فردا)، نه کاملاً تصادفی هر بار.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "zodiac_data.json"), encoding="utf-8") as f:
    _SIGNS = json.load(f)
with open(os.path.join(BASE_DIR, "zodiac_forecasts.json"), encoding="utf-8") as f:
    _FORECASTS = json.load(f)

# جدول سازگاری بر پایه‌ی عنصر (قاعده‌ی کلاسیک آسترولوژی)
_ELEMENT_COMPAT = {
    ("آتش", "آتش"): (9, "دو نفر پرانرژی که هم‌دیگه رو کاملاً درک می‌کنن، ولی ممکنه رقابت هم پیش بیاد."),
    ("آتش", "هوا"): (9, "ترکیب کلاسیک و بسیار سازگار — هوا آتش رو شعله‌ورتر می‌کنه."),
    ("هوا", "آتش"): (9, "ترکیب کلاسیک و بسیار سازگار — هوا آتش رو شعله‌ورتر می‌کنه."),
    ("خاک", "آب"): (9, "ترکیب کلاسیک و بسیار سازگار — آب به خاک حاصلخیزی می‌ده."),
    ("آب", "خاک"): (9, "ترکیب کلاسیک و بسیار سازگار — آب به خاک حاصلخیزی می‌ده."),
    ("خاک", "خاک"): (8, "دو نفر عملگرا و باثبات، رابطه‌ای مطمئن ولی نیازمند کمی هیجان بیشتر."),
    ("آب", "آب"): (8, "همخونی احساسی عمیق، ولی مراقب غرق‌شدن در حساسیت‌های مشترک باشید."),
    ("هوا", "هوا"): (7, "ارتباط ذهنی عالی و گفت‌وگوهای جذاب، ولی نیاز به پایه‌ی عملی‌تر داره."),
    ("آتش", "خاک"): (5, "یکی سریع و پرشور، اون‌یکی آروم و محتاط — با صبر می‌تونه جواب بده."),
    ("خاک", "آتش"): (5, "یکی سریع و پرشور، اون‌یکی آروم و محتاط — با صبر می‌تونه جواب بده."),
    ("آتش", "آب"): (5, "احساسات آب می‌تونه شعله‌ی آتش رو خاموش یا کنترل کنه — نیاز به درک متقابل."),
    ("آب", "آتش"): (5, "احساسات آب می‌تونه شعله‌ی آتش رو خاموش یا کنترل کنه — نیاز به درک متقابل."),
    ("هوا", "خاک"): (5, "هوا دنبال تغییره، خاک دنبال ثبات — تفاوت دیدگاه نیاز به تفاهم داره."),
    ("خاک", "هوا"): (5, "هوا دنبال تغییره، خاک دنبال ثبات — تفاوت دیدگاه نیاز به تفاهم داره."),
    ("هوا", "آب"): (6, "هوا منطقی‌ست و آب احساسی — می‌تونن مکمل خوبی برای هم باشن اگه بفهمن زبان هم رو."),
    ("آب", "هوا"): (6, "هوا منطقی‌ست و آب احساسی — می‌تونن مکمل خوبی برای هم باشن اگه بفهمن زبان هم رو."),
}


def get_sign(jalali_month: int) -> dict:
    """برج متناظر با ماه تولد شمسی (۱ تا ۱۲)."""
    return _SIGNS[str(jalali_month)]


def get_daily_forecast(jalali_month: int) -> dict:
    """پیش‌بینی امروز برای این برج (ثابت در طول روز، متفاوت روز به روز)."""
    today = datetime.now(timezone.utc).date().isoformat()
    seed_str = f"{jalali_month}-{today}"
    digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(_FORECASTS)
    return _FORECASTS[index]


def get_daily_lucky_color(jalali_month: int) -> str:
    """رنگ خوش‌یمن امروز از بین رنگ‌های مرتبط با این برج (ثابت در طول روز)."""
    sign = get_sign(jalali_month)
    today = datetime.now(timezone.utc).date().isoformat()
    seed_str = f"color-{jalali_month}-{today}"
    digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(sign["colors"])
    return sign["colors"][index]


def format_horoscope(jalali_month: int) -> str:
    sign = get_sign(jalali_month)
    forecast = get_daily_forecast(jalali_month)
    color = get_daily_lucky_color(jalali_month)
    extra = ""
    if sign.get("strengths"):
        extra = (
            f"\n💪 *نقاط قوت:* {sign['strengths']}\n"
            f"⚠️ *نقاط ضعف:* {sign['weaknesses']}\n"
            f"✅ *عامل مثبت:* {sign['positive_factor']}\n"
            f"❌ *عامل منفی:* {sign['negative_factor']}\n"
            f"🔑 *کلید شادی:* {sign['happiness_key']}\n"
            f"🌱 *درس معنوی:* {sign['spiritual_lesson']}\n"
        )
    return (
        f"{sign['emoji']} *طالع‌بینی امروز — برج {sign['name']}*\n\n"
        f"_{sign['trait']}_\n\n"
        f"🔥 *عنصر:* {sign['element']} — 🪐 *سیاره‌ی حاکم:* {sign['ruling_planet']}\n"
        f"💎 *سنگ برج:* {sign['stone']} — 🎨 *رنگ خوش‌یمن امروز:* {color}\n"
        f"{extra}\n"
        f"💞 *عشق و رابطه:* {forecast['love']}\n\n"
        f"💼 *کار و تلاش:* {forecast['work']}\n\n"
        f"🌿 *سلامتی:* {forecast['health']}\n\n"
        f"✨ *نکته‌ی امروز:* {forecast['tip']}\n\n"
        "_(طالع‌بینی صرفاً برای سرگرمیه، نه پیش‌گویی قطعی 🔭)_"
    )


def compatibility(month1: int, month2: int) -> str:
    """هم‌خونی دو برج بر پایه‌ی عنصر (آتش/خاک/هوا/آب)."""
    s1, s2 = get_sign(month1), get_sign(month2)
    e1, e2 = s1["element"], s2["element"]
    score, desc = _ELEMENT_COMPAT.get((e1, e2), (6, "ترکیبی متعادل با فراز و نشیب‌های معمول."))
    return (
        f"💫 *هم‌خونی {s1['emoji']} {s1['name']} و {s2['emoji']} {s2['name']}*\n\n"
        f"عنصر {s1['name']}: {e1} | عنصر {s2['name']}: {e2}\n\n"
        f"امتیاز هم‌خونی: {score}/۱۰\n\n"
        f"{desc}\n\n"
        "_(این تحلیل بر پایه‌ی عنصر برج آفتابیه، نه زایچه‌ی کامل — صرفاً برای سرگرمیه.)_"
    )
