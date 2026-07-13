# -*- coding: utf-8 -*-
"""
انتخاب بهترین اسم فرزند بر اساس نام خانواده و نام مادر، با هدف رسیدن به
پایگاه اجتماعی و وضعیت درآمد دلخواه برای فرزند — دقیقاً با همون فرمول‌هایی
که برای «عدد کیهانی» استفاده می‌کنیم:

  پایگاه اجتماعی فرزند = (ابجدِ کبیرِ نام فرزند + ابجدِ کبیرِ نام مادر) mod 4
  وضعیت درآمد فرزند   = (ابجدِ کبیرِ نام‌خانوادگی + ابجدِ کبیرِ نام فرزند) mod 3

چون اسم فرزند هنوز مشخص نیست، این ماژول از بین یک فهرست اسم‌های اصیل ایرانی
می‌گرده و اسم‌هایی که به ترکیب دلخواه (پایگاه/درآمد) می‌رسن رو پیدا می‌کنه.
"""
import json
import os

from cosmic_logic import abjad_kabir, _reduce_full, STATUS_TEXT, INCOME_TEXT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "persian_names_boy.json"), encoding="utf-8") as f:
    BOY_NAMES = json.load(f)
with open(os.path.join(BASE_DIR, "persian_names_girl.json"), encoding="utf-8") as f:
    GIRL_NAMES = json.load(f)

STATUS_OPTIONS = [("1", "نزولی"), ("2", "صعودی"), ("3", "راکد")]
INCOME_OPTIONS = [("1", "پرنوسان"), ("2", "متوسط رو به بالا"), ("0", "پایدار")]


def _name_pool(gender: str) -> list:
    return BOY_NAMES if gender == "boy" else GIRL_NAMES


def evaluate_name(name: str, family_name: str, mother_name: str) -> dict:
    kabir_name = abjad_kabir(name)
    a_val = kabir_name + abjad_kabir(mother_name)
    b_val = abjad_kabir(family_name) + kabir_name
    status_key = str(a_val % 4)
    income_key = str(b_val % 3)
    baten = _reduce_full(kabir_name)
    return {
        "name": name,
        "status_key": status_key,
        "status_text": STATUS_TEXT[status_key],
        "income_key": income_key,
        "income_text": INCOME_TEXT[income_key],
        "baten": baten,
    }


def suggest_names(gender: str, family_name: str, mother_name: str,
                   desired_status: str | None, desired_income: str | None,
                   limit: int = 12) -> list:
    """
    desired_status: یکی از "1"(نزولی)/"2"(صعودی)/"3"(راکد) یا None (فرقی نداره)
    desired_income: یکی از "1"(پرنوسان)/"2"(متوسط)/"0"(پایدار) یا None (فرقی نداره)
    """
    results = []
    for name in _name_pool(gender):
        info = evaluate_name(name, family_name, mother_name)
        status_ok = (desired_status is None) or (info["status_key"] == desired_status)
        income_ok = (desired_income is None) or (info["income_key"] == desired_income)
        if status_ok and income_ok:
            results.append(info)
    return results[:limit]


def format_suggestions(gender: str, results: list) -> str:
    gender_label = "پسر" if gender == "boy" else "دختر"
    if not results:
        return (
            f"❌ با این ترکیب دقیق، اسمی توی فهرست فعلی پیدا نشد.\n"
            f"می‌تونی یکی از فیلترها (پایگاه یا درآمد) رو «فرقی نداره» بذاری تا گزینه‌های بیشتری ببینی."
        )
    lines = [f"👶 *پیشنهاد اسم {gender_label} — {len(results)} گزینه*\n"]
    for r in results:
        lines.append(
            f"• *{r['name']}* — پایگاه: {r['status_text']} | درآمد: {r['income_text'].split('،')[0]} | باطن: {r['baten']}"
        )
    return "\n".join(lines)
