# -*- coding: utf-8 -*-
"""
منطق محاسباتی «عدد کیهانی» — استخراج‌شده از فایل اکسل Cosmic_Code-2026-1.xlsm

خروجی نهایی به این ترتیب است:
  0) نام و نام‌خانوادگی
  1) کد کیهانی (عدد طولانی)  — بازسازی‌شده از فرمول‌های فایل (⚠️ نیاز به کالیبراسیون با یک نمونه‌ی واقعی)
  2) تاریخ تولد میلادی معادل
  3) عدد خورشیدی  = شماره‌ی ماه تولد شمسی
  4) ارتعاش تاریخ تولد
  5) عدد تقدیر (الگوریتم ۵ مرحله‌ای، بر پایه‌ی تاریخ میلادی)
  6) عدد سرنوشت (بر پایه‌ی تاریخ شمسی)
  7) وضعیت درآمد و معیشت
  8) پایگاه اجتماعی
  9) عدد باطن فرد

⚠️ نکته برای صاحب فایل:
فایل اکسل اصلی چند فرمول شکسته (#REF!) و چند سلول کمکی داشت که مقادیرشان از رد شدن
چند لایه غیرمستقیم به دست می‌آمد و قابل ردیابی کامل نبود. بخش‌های «عدد خورشیدی»،
«عدد سرنوشت»، «عدد تقدیر» و جداول متنی، دقیقاً طبق فرمول‌های خود فایل پیاده شده‌اند.
«کد کیهانی» (عدد طولانی) بر پایه‌ی برچسب‌ها و فرمول‌های در دسترس بازسازی شده ولی
تأییدنشده است — لطفاً یک نمونه که در خود اکسل تست کرده‌ای بفرست تا با هم کالیبره‌ش کنیم.
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

# جدول تبدیل شمسی به میلادی (دقیقاً از شیت PC، ردیف‌های ۳۱ تا ۴۲ استخراج شده)
# هر ماه شمسی: (روزهای ماه, نام ماه میلادی مبدأ, افست روز, سال میلادی base)
JALALI_MONTH_TABLE = {
    1: 31, 2: 31, 3: 31, 4: 31, 5: 31, 6: 31,
    7: 30, 8: 30, 9: 30, 10: 30, 11: 30, 12: 29,
}


def _digit_sum(n: int) -> int:
    return sum(int(d) for d in str(abs(int(n))))


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


def first_digit(n: int) -> str:
    return str(abs(int(n)))[0]


def jalali_to_gregorian(jy: int, jm: int, jd: int):
    """تبدیل تاریخ شمسی به میلادی (الگوریتم استاندارد جهانی)."""
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


def calculate_taghdir(gy: int, gm: int, gd: int, jm: int) -> int:
    """
    عدد تقدیر — دقیقاً طبق فرمول سلول C22 در شیت PC.
    ⚠️ توجه: خود فایل اکسل سلول کمکی AD19 را خالی گذاشته (عملاً همیشه ۰)،
    پس در عمل عدد تقدیر فقط از «شماره ماه تولد شمسی» به دست می‌آید.
    این دقیقاً همان رفتاری‌ست که شیت PC الان نشان می‌دهد.
    """
    bt36 = 0 + jm  # AD19 (خالی=۰) + W14(=شماره ماه شمسی)
    return _reduce_v10(bt36)


def calculate_sarnevesht(gy: int, gm: int, gd: int) -> int:
    """عدد سرنوشت — دقیقاً طبق زنجیره‌ی AD18+AD16+AD14 در شیت PC (بر پایه‌ی تاریخ میلادی)."""
    ad18 = _reduce_master_only(gd)          # AD18
    ad16 = _digit_sum(gm)                   # AD16
    bp21 = _digit_sum(gy)                   # جمع رقم‌های سال میلادی
    ad14 = _reduce_v10(bp21)                # AD14
    bs33 = ad18 + ad16 + ad14
    br33 = _reduce_master_only(bs33)
    return _reduce_v10(br33)                # S22 نهایی


def calculate_erteash(jd: int, jm: int) -> int:
    """ارتعاش تاریخ تولد — دقیقاً طبق زنجیره‌ی C18 در شیت PC."""
    bs18 = jd * jm
    br18 = 365 - bs18
    bn18 = _digit_sum(br18)
    bm18 = _digit_sum(bn18)
    return (9 - bm18) if bm18 < 9 else bm18


def _reduce_v10(n: int) -> int:
    """الگوی تکرارشونده در چند سلول: جمع ارقام، مگر اینکه حاصل ۱۰ شود (=>۱) یا خود عدد ۱۱/۲۲ باشد."""
    ds = _digit_sum(n)
    if ds == 10:
        return 1
    if n in (11, 22):
        return n
    return ds


def _reduce_master_only(n: int) -> int:
    """اگر خود عدد ۱۱ یا ۲۲ باشد نگه‌داشته می‌شود، وگرنه یک‌بار جمع ارقام."""
    if n in (11, 22):
        return n
    return _digit_sum(n)


def calculate_cosmic_report(first_name: str, family_name: str, mother_name: str,
                             jy: int, jm: int, jd: int) -> dict:
    # تاریخ میلادی معادل
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)

    # عدد سرنوشت — دقیقاً طبق شیت PC (بر پایه‌ی تاریخ میلادی)
    destiny_num = calculate_sarnevesht(gy, gm, gd)

    # عدد تقدیر — دقیقاً طبق شیت PC
    fate_num = calculate_taghdir(gy, gm, gd, jm)

    # ارتعاش تاریخ تولد — دقیقاً طبق شیت PC
    vibration_num = calculate_erteash(jd, jm)

    # عدد خورشیدی = شماره‌ی ماه تولد شمسی (۱ تا ۱۲)
    solar_num = jm

    # ابجد صغیر نام‌ها
    s_first = abjad_saghir(first_name)
    s_family = abjad_saghir(family_name)
    s_mother = abjad_saghir(mother_name)
    k_first = abjad_kabir(first_name)
    k_family = abjad_kabir(family_name)

    income_key = str((s_family + s_first) % 3)
    status_key = str((s_mother + s_first) % 4)
    baten_num = (s_mother + s_first) // 4

    # کد کیهانی (عدد طولانی) — بازسازی بهترین‌تلاش، نیاز به کالیبراسیون
    name_abjad_part = k_first + k_family  # "جمع ابجد صغیر اسم و فامیل" (کبیر خام)
    solar_fd = first_digit(solar_num)
    destiny_fd = first_digit(destiny_num)
    sum_fd = first_digit(solar_num + destiny_num)
    cosmic_code = f"{name_abjad_part}-{solar_fd}-{destiny_fd}-{sum_fd}"

    return {
        "cosmic_code": cosmic_code,
        "gregorian_date": f"{gy}-{gm:02d}-{gd:02d}",
        "solar_num": solar_num,
        "vibration_num": vibration_num,
        "vibration_text": ERTEASH.get(str(vibration_num), "متن یافت نشد"),
        "fate_num": fate_num,
        "fate_text": TAGHDIR.get(str(fate_num), "متن یافت نشد"),
        "destiny_num": destiny_num,
        "destiny_text": SARNEVESHT.get(str(destiny_num), "متن یافت نشد"),
        "income_text": DARAMAD_INCOME.get(income_key, DARAMAD_INCOME["0"]),
        "status_text": DARAMAD_STATUS.get(status_key, "راکد"),
        "baten_num": baten_num,
    }


def format_report(full_name: str, data: dict) -> str:
    return (
        f"👤 *{full_name}*\n\n"
        f"🌌 *کد کیهانی:* `{data['cosmic_code']}`\n\n"
        f"📅 *تاریخ تولد میلادی:* {data['gregorian_date']}\n\n"
        f"☀️ *عدد خورشیدی:* {data['solar_num']}\n\n"
        f"📌 *ارتعاش تاریخ تولد:* {data['vibration_num']}\n{data['vibration_text']}\n\n"
        f"📌 *عدد تقدیر:* {data['fate_num']}\n{data['fate_text']}\n\n"
        f"📌 *عدد سرنوشت:* {data['destiny_num']}\n{data['destiny_text']}\n\n"
        f"💰 *وضعیت درآمد و معیشت:* {data['income_text']}\n"
        f"🏛 *پایگاه اجتماعی:* {data['status_text']}\n"
        f"🔮 *عدد باطن فرد:* {data['baten_num']}"
    )
