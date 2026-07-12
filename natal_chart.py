# -*- coding: utf-8 -*-
"""
زایچه‌ی تقریبی (Natal Chart) — محاسبه‌ی واقعی نجومی موقعیت خورشید، ماه و طالع
(نه فال، بلکه فرمول‌های استاندارد اخترشناسی با دقت پایین/متوسط، معروف به
"Low-precision formulas" کتاب Jean Meeus - Astronomical Algorithms).

⚠️ محدودیت‌های این نسخه (صادقانه):
- دقت موقعیت خورشید: حدود ۰.۰۱ درجه (عملاً بی‌نقص برای تعیین برج).
- دقت موقعیت ماه: حدود ۱-۲ درجه (برای تعیین برج ماه کافیه، چون هر برج ۳۰ درجه‌ست).
- طالع (Ascendant) به ساعت و مکان دقیق تولد خیلی حساسه؛ هر ۴ دقیقه خطای ساعت
  تولد، ~۱ درجه خطا در طالع ایجاد می‌کنه.
- فرض شده ایران همیشه UTC+3:30 بوده (ساعت تابستانی از سال ۱۴۰۱ حذف شده).
  برای تاریخ‌های قبل‌تر که ساعت تابستانی وجود داشت، ممکنه طالع کمی خطا داشته باشه.
- این یک زایچه‌ی کامل با خانه‌ها و سیارات دیگه نیست؛ فقط خورشید+ماه+طالعه.
"""
import math
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "iran_cities.json"), encoding="utf-8") as f:
    CITIES = json.load(f)
with open(os.path.join(BASE_DIR, "natal_interpretations.json"), encoding="utf-8") as f:
    _INTERPRETATIONS = json.load(f)

IRAN_UTC_OFFSET = 3.5  # ساعت (بدون تغییر فصلی، از ۱۴۰۱ به بعد)

SIGN_NAMES = [
    "حمل", "ثور", "جوزا", "سرطان", "اسد", "سنبله",
    "میزان", "عقرب", "قوس", "جدی", "دلو", "حوت",
]


def sign_from_longitude(lon: float) -> str:
    lon = lon % 360
    index = int(lon // 30)
    return SIGN_NAMES[index]


def julian_day(gy: int, gm: int, gd: int, hour: float) -> float:
    """محاسبه‌ی روز ژولینی (UT) طبق فرمول استاندارد Meeus."""
    if gm <= 2:
        gy -= 1
        gm += 12
    a = gy // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (gy + 4716)) + int(30.6001 * (gm + 1)) + gd + hour / 24.0 + b - 1524.5
    return jd


def _norm360(x: float) -> float:
    x = x % 360
    return x + 360 if x < 0 else x


def solar_longitude(jd: float) -> float:
    """طول دایره‌البروجی خورشید (درجه) — فرمول کم‌دقت Meeus، خطا ~۰.۰۱ درجه."""
    t = (jd - 2451545.0) / 36525.0
    l0 = _norm360(280.46646 + 36000.76983 * t + 0.0003032 * t * t)
    m = _norm360(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    m_rad = math.radians(m)
    c = (
        (1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m_rad)
        + (0.019993 - 0.000101 * t) * math.sin(2 * m_rad)
        + 0.000289 * math.sin(3 * m_rad)
    )
    true_lon = l0 + c
    return _norm360(true_lon)


def lunar_longitude(jd: float) -> float:
    """طول دایره‌البروجی ماه (درجه) — نسخه‌ی خلاصه‌شده‌ی نظریه‌ی ماه Meeus (چند جمله‌ی اصلی)."""
    t = (jd - 2451545.0) / 36525.0
    lp = _norm360(218.3164477 + 481267.88123421 * t)  # طول متوسط ماه
    d = _norm360(297.8501921 + 445267.1114034 * t)    # دورگه (Elongation)
    m = _norm360(357.5291092 + 35999.0502909 * t)     # آنومالی خورشید
    mp = _norm360(134.9633964 + 477198.8675055 * t)   # آنومالی ماه
    f = _norm360(93.2720950 + 483202.0175233 * t)     # آرگومان عرض

    d, m, mp, f = map(math.radians, (d, m, mp, f))

    # مهم‌ترین جمله‌های تناوبی برای طول ماه (درجه)
    dl = 0.0
    dl += 6.288774 * math.sin(mp)
    dl += 1.274027 * math.sin(2 * d - mp)
    dl += 0.658314 * math.sin(2 * d)
    dl += 0.213618 * math.sin(2 * mp)
    dl -= 0.185116 * math.sin(m)
    dl -= 0.114332 * math.sin(2 * f)
    dl += 0.058793 * math.sin(2 * d - 2 * mp)
    dl += 0.057066 * math.sin(2 * d - m - mp)
    dl += 0.053322 * math.sin(2 * d + mp)
    dl += 0.045758 * math.sin(2 * d - m)
    dl -= 0.040923 * math.sin(m - mp)
    dl -= 0.034720 * math.sin(d)
    dl -= 0.030383 * math.sin(m + mp)

    true_lon = lp + dl
    return _norm360(true_lon)


def obliquity_of_ecliptic(jd: float) -> float:
    t = (jd - 2451545.0) / 36525.0
    return 23.439291 - 0.0130042 * t


def gmst_degrees(jd: float) -> float:
    """میانگین زمان نجومی گرینویچ (درجه)."""
    t = (jd - 2451545.0) / 36525.0
    gmst = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * t * t
        - (t ** 3) / 38710000.0
    )
    return _norm360(gmst)


def ascendant(jd_ut: float, latitude: float, longitude_east: float) -> float:
    """محاسبه‌ی طالع (درجه‌ی دایره‌البروجی که در افق شرقی طلوع می‌کنه)."""
    gmst = gmst_degrees(jd_ut)
    lst = _norm360(gmst + longitude_east)  # زمان نجومی محلی
    eps = math.radians(obliquity_of_ecliptic(jd_ut))
    lat = math.radians(latitude)
    lst_rad = math.radians(lst)

    y = -math.cos(lst_rad)
    x = math.sin(eps) * math.tan(lat) + math.cos(eps) * math.sin(lst_rad)
    asc = math.degrees(math.atan2(y, x))
    return _norm360(asc)


def calculate_natal(gy: int, gm: int, gd: int, hour: int, minute: int, city_key: str) -> dict:
    city = CITIES[city_key]
    local_hour = hour + minute / 60.0
    utc_hour = local_hour - IRAN_UTC_OFFSET
    jd = julian_day(gy, gm, gd, utc_hour)

    sun_lon = solar_longitude(jd)
    moon_lon = lunar_longitude(jd)
    asc_lon = ascendant(jd, city["lat"], city["lon"])

    return {
        "sun_sign": sign_from_longitude(sun_lon),
        "sun_lon": sun_lon,
        "moon_sign": sign_from_longitude(moon_lon),
        "moon_lon": moon_lon,
        "asc_sign": sign_from_longitude(asc_lon),
        "asc_lon": asc_lon,
        "city": city["display_name"],
    }


def format_natal(result: dict) -> str:
    sun_text = _INTERPRETATIONS["sun"][result["sun_sign"]]
    moon_text = _INTERPRETATIONS["moon"][result["moon_sign"]]
    asc_text = _INTERPRETATIONS["asc"][result["asc_sign"]]
    return (
        "🌌 *زایچه‌ی تقریبی شما*\n\n"
        f"☀️ *برج خورشید (آفتاب): {result['sun_sign']}*\n{sun_text}\n\n"
        f"🌙 *برج ماه: {result['moon_sign']}*\n{moon_text}\n\n"
        f"⬆️ *طالع (صعودی): {result['asc_sign']}*\n{asc_text}\n\n"
        f"📍 محل تولد: {result['city']}"
    )
