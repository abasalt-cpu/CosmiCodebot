# -*- coding: utf-8 -*-
"""
منطق محاسباتی «عدد کیهانی» — استخراج‌شده از فایل اکسل Cosmic_Code-2026-1.xlsm

این ماژول ۵ عدد اصلی گزارش را حساب می‌کند:
  1) عدد سرنوشت   (Sarnevesht) - از تاریخ تولد شمسی
  2) عدد تقدیر    (Taghdir)    - از تاریخ تولد میلادی (معادل شمسی)
  3) ارتعاش تاریخ تولد (Erteash) - کاهش‌یافته تا یک رقم (بدون عدد استاد)
  4) وضعیت درآمد و معیشت (Daramad - بخش اول) - از حروف ابجد نام+نام‌خانوادگی
  5) پایگاه اجتماعی (Daramad - بخش دوم) - از حروف ابجد نام+نام مادر

⚠️ نکته مهم برای صاحب فایل:
فایل اکسل اصلی شامل چند فرمول شکسته (#REF!) و زنجیره‌ی محاسباتی بسیار پیچیده
(بیش از ۱۸۰ فرمول به‌هم‌مرتبط در هر شیت) بود. بخش‌های اصلی (سرنوشت، تقدیر،
ارتعاش، ابجد، درآمد/پایگاه) دقیقاً طبق فرمول‌ها و برچسب‌های خود فایل پیاده‌سازی
شده‌اند. اگر بعد از تست، خروجی با فایل اکسل روی چند نمونه تاریخ/اسم تفاوت داشت،
بگو تا با هم دقیق‌تر تطبیق بدیم.
"""
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "tables.json"), encoding="utf-8") as f:
    TABLES = json.load(f)

SARNEVESHT = TABLES["sarnevesht"]   # keys: "1".."9","11","22"
TAGHDIR = TABLES["taghdir"]         # keys: "1".."9","11","22"
ERTEASH = TABLES["erteash"]         # keys: "1".."9"
# این دو جدول عیناً از سطرهای شیت «Daramad» در فایل اکسل خوانده شده‌اند
# (چون هر دو جدول در فایل اصلی کلیدهای عددی مشترکی دارند، جدا نگه داشته می‌شوند)
DARAMAD_INCOME = {                  # باقی‌مانده‌ی (ابجدِ فامیل + نام) بر ۳
    "1": "حادثه آفرین",
    "2": "کم درآمد",
    "3": "عرفانی",
    "4": "اشرافی",
    "0": "اشرافی",
}
DARAMAD_STATUS = {                  # باقی‌مانده‌ی (ابجدِ نام مادر + نام) بر ۴
    "1": "نزولی",
    "2": "صعودی",
    "3": "راکد",
    "0": "راکد",
}

# جدول حروف ابجد کبیر (استخراج‌شده از شیت Abjad، شامل ۴ حرف اضافه‌ی فارسی)
ABJAD = {
    "ا": 1, "آ": 1, "ب": 2, "پ": 4000, "ج": 3, "چ": 3000, "د": 4,
    "ه": 5, "ة": 5, "و": 6, "ز": 7, "ژ": 5000, "ح": 8, "ط": 9,
    "ی": 10, "ي": 10, "ک": 20, "گ": 2000, "ل": 30, "م": 40, "ن": 50,
    "س": 60, "ع": 70, "ف": 80, "ص": 90, "ق": 100, "ر": 200, "ش": 300,
    "ت": 400, "ث": 500, "خ": 600, "ذ": 700, "ض": 800, "ظ": 900, "غ": 1000,
}


def _digit_sum(n: int) -> int:
    return sum(int(d) for d in str(abs(n)))


def reduce_keep_master(n: int) -> int:
    """کاهش عدد تا یک رقم، با نگه‌داشتن اعداد استاد ۱۱ و ۲۲."""
    n = abs(int(n))
    while n > 9 and n not in (11, 22):
        n = _digit_sum(n)
    return n


def reduce_full(n: int) -> int:
    """کاهش کامل تا یک رقم بین ۱ تا ۹ (اعداد استاد نگه داشته نمی‌شوند)."""
    n = abs(int(n))
    while n > 9:
        n = _digit_sum(n)
    return n if n != 0 else 9


def jalali_to_gregorian(jy: int, jm: int, jd: int):
    """تبدیل تاریخ شمسی به میلادی (الگوریتم استاندارد)."""
    jy += 1595
    days = (
        -355668
        + (365 * jy)
        + ((jy // 33) * 8)
        + (((jy % 33) + 3) // 4)
        + jd
        + (((jm - 1) * 31) if jm < 7 else (((jm - 7) * 30) + 186))
    )
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    g_days_in_month = [31, 29 if (gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)) else 28,
                        31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    for i, dim in enumerate(g_days_in_month):
        if gd <= dim:
            gm = i + 1
            break
        gd -= dim
    return gy, gm, gd


def abjad_kabir(text: str) -> int:
    """جمع کل ارزش ابجد یک نام (کبیر)."""
    text = re.sub(r"[\u200c\s]+", "", text or "")
    return sum(ABJAD.get(ch, 0) for ch in text)


def abjad_saghir(text: str) -> int:
    """عدد ابجد صغیر (کاهش‌یافته تا یک رقم)."""
    return reduce_full(abjad_kabir(text))


def calculate_cosmic_report(first_name: str, family_name: str, mother_name: str,
                             jy: int, jm: int, jd: int) -> dict:
    # 1) عدد سرنوشت — از تاریخ تولد شمسی
    destiny_raw = _digit_sum(jy) + _digit_sum(jm) + _digit_sum(jd)
    destiny_num = reduce_keep_master(destiny_raw)

    # 2) عدد تقدیر — از تاریخ تولد میلادی معادل
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    fate_raw = _digit_sum(gy) + _digit_sum(gm) + _digit_sum(gd)
    fate_num = reduce_keep_master(fate_raw)

    # 3) ارتعاش تاریخ تولد — کاهش کامل بدون عدد استاد
    vibration_num = reduce_full(destiny_raw)

    # 4 و 5) ابجد صغیر نام‌ها
    s_first = abjad_saghir(first_name)
    s_family = abjad_saghir(family_name)
    s_mother = abjad_saghir(mother_name)

    income_key = str((s_family + s_first) % 3)
    status_key = str((s_mother + s_first) % 4)
    baten_num = (s_mother + s_first) // 4

    return {
        "destiny_num": destiny_num,
        "destiny_text": SARNEVESHT.get(str(destiny_num), "متن یافت نشد"),
        "fate_num": fate_num,
        "fate_text": TAGHDIR.get(str(fate_num), "متن یافت نشد"),
        "vibration_num": vibration_num,
        "vibration_text": ERTEASH.get(str(vibration_num), "متن یافت نشد"),
        "income_text": DARAMAD_INCOME.get(income_key, DARAMAD_INCOME["0"]),
        "status_text": DARAMAD_STATUS.get(status_key, "راکد"),
        "baten_num": baten_num,
        "gregorian_date": f"{gy}-{gm:02d}-{gd:02d}",
        "abjad": {"first": s_first, "family": s_family, "mother": s_mother},
    }


def format_report(name: str, data: dict) -> str:
    return (
        f"🌌 *گزارش عدد کیهانی برای {name}*\n\n"
        f"📌 *عدد سرنوشت:* {data['destiny_num']}\n{data['destiny_text']}\n\n"
        f"📌 *عدد تقدیر:* {data['fate_num']}\n{data['fate_text']}\n\n"
        f"📌 *ارتعاش تاریخ تولد:* {data['vibration_num']}\n{data['vibration_text']}\n\n"
        f"💰 *وضعیت درآمد و معیشت:* {data['income_text']}\n"
        f"🏛 *پایگاه اجتماعی:* {data['status_text']}\n"
        f"🔮 *عدد باطن فرد:* {data['baten_num']}\n\n"
        f"_(تاریخ میلادی معادل: {data['gregorian_date']})_"
    )
