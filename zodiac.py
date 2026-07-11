# -*- coding: utf-8 -*-
"""
طالع‌بینی/برج روزانه — بر پایه‌ی ماه تولد شمسی.

نگاشت ساده‌شده‌ی ماه شمسی به برج غربی (فروردین≈حمل و...) که رایج‌ترین تناظر
استفاده‌شده در محتوای فارسیه. دقیق‌ترین حالت واقعی چون هر برج از حدود بیستم
یک ماه شمسی تا بیستم ماه بعد طول می‌کشه با کمی اختلاف همراهه، ولی برای یک
قابلیت سرگرمی، همین تناظر ماه‌به‌ماه رایج و کافیه.

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


def format_horoscope(jalali_month: int) -> str:
    sign = get_sign(jalali_month)
    forecast = get_daily_forecast(jalali_month)
    return (
        f"{sign['emoji']} *طالع‌بینی امروز — برج {sign['name']}*\n\n"
        f"_{sign['trait']}_\n\n"
        f"💞 *عشق و رابطه:* {forecast['love']}\n\n"
        f"💼 *کار و تلاش:* {forecast['work']}\n\n"
        f"🌿 *سلامتی:* {forecast['health']}\n\n"
        f"✨ *نکته‌ی امروز:* {forecast['tip']}\n\n"
        "_(طالع‌بینی صرفاً برای سرگرمیه، نه پیش‌گویی قطعی 🔭)_"
    )
