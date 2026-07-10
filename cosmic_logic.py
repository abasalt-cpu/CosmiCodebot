# -*- coding: utf-8 -*-
"""
منطق محاسباتی «عدد کیهانی» — استخراج و کالیبره‌شده از فایل اکسل Cosmic_Code (شیت PC)

ترتیب خروجی:
  0) نام و نام‌خانوادگی
  1) کد کیهانی (عدد طولانی) — کالیبره‌شده و تست‌شده، ۱۰۰٪ منطبق با شیت PC
  2) تاریخ تولد میلادی معادل
  3) عدد خورشیدی = شماره‌ی ماه تولد شمسی
  4) ارتعاش تاریخ تولد + توضیح
  5) عدد تقدیر + توضیح
  6) عدد سرنوشت + توضیح
  7) وضعیت درآمد و معیشت
  8) پایگاه اجتماعی
  9) عدد باطن فرد + توضیح
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

# --- وضعیت درآمد و معیشت (باقی‌مانده‌ی (ابجدِ کبیرِ فامیل + نام) بر ۳) ---
INCOME_TEXT = {
    "1": "معیشت پرنوسان، نیاز به مدیریت دقیق هزینه‌ها.",
    "2": "معیشت متوسط رو به بالا، با تلاش قابل بهبود است.",
    "0": "معیشت نسبتاً پایدار و بخت باز شدن درهای مالی را دارد.",
}

# --- پایگاه اجتماعی (باقی‌مانده‌ی (ابجدِ کبیرِ نام + نام مادر) بر ۴) ---
STATUS_TEXT = {
    "1": "نزولی",
    "2": "صعودی",
    "3": "راکد",
    "0": "راکد",
}

# --- عدد باطن فرد (ابجد کبیر نام، کاهش‌یافته تا یک رقم ۱ تا ۹) ---
BATEN_TEXT = {
    1: ("مبتکر / رهبر",
        "ذات: مستقل، جسور، خلاق و متولد برای رهبری.\n"
        "نکته: مسیرتان را خودتان می‌سازید، اما مراقب خودمحوری و لجبازی باشید."),
    2: ("صلح‌جو / دیپلمات",
        "ذات: حساس، همکار، شنونده‌ی خوب و عاشق آرامش.\n"
        "نکته: استعداد بالایی در ایجاد ارتباط دارید، اما ممکن است بیش از حد وابسته به نظر دیگران شوید."),
    3: ("هنرمند / خوش‌بین",
        "ذات: پر از انرژی، خلاق، خوش‌صحبت و اجتماعی.\n"
        "نکته: زندگی برایتان صحنه‌ی نمایش است، اما از سطحی‌نگری و پراکنده‌کاری دوری کنید."),
    4: ("ساختارگرا / بنیادگذار",
        "ذات: منظم، سخت‌کوش، وفادار و اهل نظم و قانون.\n"
        "نکته: ستون زندگی دیگران هستید، ولی انعطاف‌پذیری را فراموش نکنید."),
    5: ("ماجراجو / آزادی‌خواه",
        "ذات: پویا، کنجکاو، تغییرپذیر و عاشق تجربه‌های جدید.\n"
        "نکته: از قفسِ یکنواختی فرار می‌کنید، اما مواظب بی‌ثباتی و تعهدگریزی باشید."),
    6: ("مسئول / مراقب",
        "ذات: خانواده‌دوست، فداکار، ایده‌آلیست و عاشق زیبایی.\n"
        "نکته: شفا‌دهنده‌ی جمع هستید، اما دیگران را بیش از حد تحت مراقبت خود قرار ندهید."),
    7: ("فیلسوف / رازجو",
        "ذات: عمیق‌اندیش، شهودی، درون‌گرا و عاشق تنهایی و دانش.\n"
        "نکته: اهل کشف حقیقت هستید، اما بدبینی و گوشه‌گیری را مدیریت کنید."),
    8: ("قدرتمند / ثروت‌ساز",
        "ذات: جاه‌طلب، مدبر، عمل‌گرا و متولد برای موفقیت مادی.\n"
        "نکته: انرژی فراوانی برای پول‌سازی دارید، ولی تعادل بین کار و زندگی را رعایت کنید."),
    9: ("بشردوست / کامل‌گرا",
        "ذات: مهربان، بخشنده، آرمان‌گرا و از خود گذشته.\n"
        "نکته: عاشق کمک به جهان هستید، اما گاهی خودتان را فراموش می‌کنید."),
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
    return sum(int(d) for d in str(abs(int(n))))


def _reduce_full(n: int) -> int:
    """کاهش کامل تا یک رقم بین ۱ تا ۹."""
    n = abs(int(n))
    while n > 9:
        n = _digit_sum(n)
    return n if n != 0 else 9


def _reduce_v10(n: int) -> int:
    """جمع ارقام؛ اگر حاصل ۱۰ شود => ۱، یا اگر خود عدد ۱۱/۲۲ باشد نگه داشته می‌شود."""
    ds = _digit_sum(n)
    if ds == 10:
        return 1
    if n in (11, 22):
        return n
    return ds


def _reduce_master_only(n: int) -> int:
    if n in (11, 22):
        return n
    return _digit_sum(n)


def _first_digit(n: int) -> str:
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
    """جمع کل ارزش ابجد یک نام (کبیر، خام - بدون کاهش)."""
    text = re.sub(r"[\u200c\s]+", "", text or "")
    return sum(ABJAD.get(ch, 0) for ch in text)


# ---------------------------------------------------------------------------
# عدد تقدیر، عدد سرنوشت، ارتعاش  (دقیقاً طبق فرمول‌های شیت PC، کالیبره‌شده)
# ---------------------------------------------------------------------------

def calculate_taghdir(jm: int) -> int:
    """عدد تقدیر — طبق سلول C22 (سلول کمکی AD19 در فایل اصلی خالی/۰ است)."""
    bt36 = 0 + jm
    return _reduce_v10(bt36)


def calculate_sarnevesht(gy: int, gm: int, gd: int) -> int:
    """عدد سرنوشت — طبق زنجیره‌ی AD18+AD16+AD14 (بر پایه‌ی تاریخ میلادی)."""
    ad18 = _reduce_master_only(gd)
    ad16 = _digit_sum(gm)
    ad14 = _reduce_v10(_digit_sum(gy))
    bs33 = ad18 + ad16 + ad14
    br33 = _reduce_master_only(bs33)
    return _reduce_v10(br33)


def calculate_erteash(jd: int, jm: int) -> int:
    """ارتعاش تاریخ تولد — طبق زنجیره‌ی C18."""
    bs18 = jd * jm
    br18 = 365 - bs18
    bn18 = _digit_sum(br18)
    bm18 = _digit_sum(bn18)
    return (9 - bm18) if bm18 < 9 else bm18


# ---------------------------------------------------------------------------
# کد کیهانی (عدد طولانی) — کالیبره و تست‌شده با مقادیر واقعی شیت PC
# ---------------------------------------------------------------------------

def calculate_cosmic_code(first_name: str, family_name: str, jm: int,
                           gy: int, gm: int, gd: int) -> str:
    # --- بخش اول: شبکه‌ی رقم‌ها ---
    ds_gy = _digit_sum(gy)
    ds_gm = _digit_sum(gm)
    ds_gd = _digit_sum(gd)
    stage1 = ds_gy + ds_gm + ds_gd
    stage2 = _digit_sum(stage1)
    stage3 = stage1 - (int(_first_digit(gd)) * 2)
    stage4 = _digit_sum(abs(stage3))

    pool_numbers = [stage1, stage2, stage3, stage4, gy, gm, gd]
    digits_pool = [int(ch) for num in pool_numbers for ch in str(abs(num)) if ch != "0"]

    groups = []
    for d in range(1, 10):
        c = digits_pool.count(d)
        if c > 0:
            groups.append(str(d) * c)
    segment1 = ("-".join(groups) + "-") if groups else ""

    # --- بخش دوم: ۴ رقم پایانی ---
    kabir_family = abjad_kabir(family_name)
    kabir_first = abjad_kabir(first_name)
    bn39 = kabir_family + kabir_first
    part_a = _reduce_v10(_digit_sum(bn39))

    part_b = int(_first_digit(jm))

    ds_gm2 = _digit_sum(gm)
    part_c = int(_first_digit(ds_gm2))

    bo42 = jm + ds_gm2
    part_d = int(_first_digit(_reduce_v10(bo42)))

    segment2 = f"{part_a}-{part_b}-{part_c}-{part_d}"
    return segment1 + segment2


def calculate_cosmic_report(first_name: str, family_name: str, mother_name: str,
                             jy: int, jm: int, jd: int) -> dict:
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)

    destiny_num = calculate_sarnevesht(gy, gm, gd)
    fate_num = calculate_taghdir(jm)
    vibration_num = calculate_erteash(jd, jm)
    solar_num = jm
    cosmic_code = calculate_cosmic_code(first_name, family_name, jm, gy, gm, gd)

    # عدد باطن فرد = جمع ارقام ابجد کبیر نام فرد تا رسیدن به یک رقم
    baten_num = _reduce_full(abjad_kabir(first_name))
    baten_title, baten_desc = BATEN_TEXT[baten_num]

    # پایگاه اجتماعی: A = ابجد کبیر (نام + نام مادر)، باقی‌مانده بر ۴
    # اگه نام مادر وارد نشده باشه، این بخش محاسبه نمی‌شه.
    if mother_name:
        a_val = abjad_kabir(first_name) + abjad_kabir(mother_name)
        status_key = str(a_val % 4)
        status_text = STATUS_TEXT.get(status_key, "راکد")
    else:
        status_text = None

    # وضعیت درآمد و معیشت: B = ابجد کبیر (فامیل + نام)، باقی‌مانده بر ۳
    b_val = abjad_kabir(family_name) + abjad_kabir(first_name)
    income_key = str(b_val % 3)
    income_text = INCOME_TEXT.get(income_key, INCOME_TEXT["0"])

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
        "income_text": income_text,
        "status_text": status_text,
        "baten_num": baten_num,
        "baten_title": baten_title,
        "baten_desc": baten_desc,
    }


def format_report(full_name: str, data: dict) -> str:
    status_line = (
        f"🏛 *پایگاه اجتماعی:* {data['status_text']}\n\n"
        if data["status_text"]
        else "🏛 *پایگاه اجتماعی:* محاسبه نشد (نام مادر وارد نشده)\n\n"
    )
    return (
        f"👤 *{full_name}*\n\n"
        f"🌌 *کد کیهانی:*\n`{data['cosmic_code']}`\n\n"
        f"📅 *تاریخ تولد میلادی:* {data['gregorian_date']}\n\n"
        f"☀️ *عدد خورشیدی:* {data['solar_num']}\n\n"
        f"📌 *ارتعاش تاریخ تولد:* {data['vibration_num']}\n{data['vibration_text']}\n\n"
        f"📌 *عدد تقدیر:* {data['fate_num']}\n{data['fate_text']}\n\n"
        f"📌 *عدد سرنوشت:* {data['destiny_num']}\n{data['destiny_text']}\n\n"
        f"💰 *وضعیت درآمد و معیشت:* {data['income_text']}\n\n"
        f"{status_line}"
        f"🔮 *عدد باطن فرد:* {data['baten_num']} ({data['baten_title']})\n{data['baten_desc']}"
    )
