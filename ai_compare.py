# -*- coding: utf-8 -*-
"""
تحلیل همخونی دو نفر با استفاده از Claude API.

⚠️ نیازمندی مهم:
این قابلیت به یه کلید API جدا از Anthropic نیاز داره (متغیر محیطی ANTHROPIC_API_KEY) —
این غیر از توکن ربات تلگرامه و هزینه‌ی جداگانه‌ای داره (بر اساس مصرف، طبق تعرفه‌ی
console.anthropic.com). از این آدرس یه کلید بساز:
    https://console.anthropic.com/settings/keys

بدون این کلید، ربات هنوز کار می‌کنه ولی فقط مقایسه‌ی عددی رو نشون می‌ده و
تحلیل کیفی («ترکیبتون خوبه یا بده») رو نمی‌سازه.
"""
import os

from anthropic import Anthropic

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("AI_MODEL", "claude-sonnet-5")

_client = Anthropic(api_key=API_KEY, timeout=25.0, max_retries=1) if API_KEY else None


def ai_available() -> bool:
    return _client is not None


def _profile_summary(name: str, data: dict) -> str:
    return (
        f"نام: {name}\n"
        f"عدد سرنوشت: {data['destiny_num']}\n"
        f"عدد تقدیر: {data['fate_num']}\n"
        f"ارتعاش تاریخ تولد: {data['vibration_num']}\n"
        f"عدد باطن: {data['baten_num']}\n"
        f"کد کیهانی: {data['cosmic_code']}"
    )


def compare_two_people(name1: str, data1: dict, name2: str, data2: dict) -> str:
    """با فراخوانی Claude API، یه تحلیل همخونی فارسی برمی‌گردونه."""
    if not _client:
        raise RuntimeError("ANTHROPIC_API_KEY تنظیم نشده است.")

    prompt = f"""بر اساس اعداد عددشناسی (نومرولوژی) زیر برای دو نفر، یک تحلیل کوتاه و صمیمی
به زبان فارسی بنویس که شامل این بخش‌ها باشه:

۱. اشتراکات: کجاها این دو نفر عدد/ویژگی مشترک دارن؟
۲. نقاط مکمل: کجاها می‌تونن مکمل هم باشن (نقطه‌ضعف یکی، نقطه‌قوت اون یکی)؟
۳. جمع‌بندی: به‌طور کلی ترکیبشون (دوستی/همکاری/رابطه) چقدر هماهنگه؟ یه امتیاز کلی (مثلاً از ۱۰) بده.
۴. یک توصیه‌ی عملی کوتاه برای بهتر شدن رابطه‌شون.

لحن باید دوستانه، غیرقطعی (چون این یک سیستم سرگرمی/فرهنگی است نه علم دقیق) و
حداکثر ۲۵۰ کلمه باشه. از تیتر برای هر بخش استفاده کن.

--- نفر اول ---
{_profile_summary(name1, data1)}

--- نفر دوم ---
{_profile_summary(name2, data2)}
"""

    response = _client.messages.create(
        model=MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip() or "پاسخی دریافت نشد."


def numeric_overlap_summary(name1: str, data1: dict, name2: str, data2: dict) -> str:
    """مقایسه‌ی عددی ساده (بدون نیاز به AI) — همیشه در دسترسه."""
    lines = [f"🔢 *مقایسه‌ی عددی {name1} و {name2}*\n"]
    fields = [
        ("عدد سرنوشت", "destiny_num"),
        ("عدد تقدیر", "fate_num"),
        ("ارتعاش تاریخ تولد", "vibration_num"),
        ("عدد باطن", "baten_num"),
    ]
    shared = 0
    for label, key in fields:
        v1, v2 = data1[key], data2[key]
        same = "✅ مشترک" if v1 == v2 else "▫️"
        if v1 == v2:
            shared += 1
        lines.append(f"{label}: {v1} / {v2}  {same}")
    lines.append(f"\nتعداد اعداد مشترک: {shared} از {len(fields)}")
    return "\n".join(lines)
