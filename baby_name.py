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
import random

from cosmic_logic import abjad_kabir, _reduce_full, STATUS_TEXT, INCOME_TEXT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "persian_names_boy.json"), encoding="utf-8") as f:
    BOY_NAMES = json.load(f)
with open(os.path.join(BASE_DIR, "persian_names_girl.json"), encoding="utf-8") as f:
    GIRL_NAMES = json.load(f)

STATUS_OPTIONS = [("1", "نزولی"), ("2", "صعودی"), ("3", "راکد")]
INCOME_OPTIONS = [("1", "پرنوسان"), ("2", "متوسط رو به بالا"), ("0", "پایدار")]


def _harmony_score(name: str, family_name: str) -> float:
    """
    امتیاز تقریبی «هم‌آوایی و شیکی» اسم فرزند در کنار نام خانوادگی.
    هرچی امتیاز بالاتر، هماهنگی صوتی بهتر (heuristic ساده، نه علم زبان‌شناسی دقیق).
    """
    score = 0.0

    # جریمه: حرف اول اسم و فامیل یکی باشه (حس تکراری/اسم کوچیک شبیه فامیلی)
    if name[0] == family_name[0]:
        score -= 2.0

    # جریمه: حرف آخر اسم با حرف اول فامیل برخورد ناجور صوتی بده (تکرار پشت‌سرهم یک صامت)
    if name[-1] == family_name[0]:
        score -= 1.5

    # پاداش: هماهنگی طول اسم و فامیل (نه خیلی کوتاه در برابر فامیل بلند، نه برعکس)
    length_diff = abs(len(name) - len(family_name))
    score += max(0.0, 2.0 - length_diff * 0.4)

    # جریمه‌ی خفیف برای اسم‌های خیلی کوتاه (۲ حرفی) که معمولاً کنار فامیل بلند شیک نیستن
    if len(name) <= 2:
        score -= 1.0

    return score


def _name_pool(gender: str) -> list:
    return BOY_NAMES if gender == "boy" else GIRL_NAMES


def evaluate_name(name_entry: dict, family_name: str, mother_name: str) -> dict:
    name = name_entry["name"]
    kabir_name = abjad_kabir(name)
    a_val = kabir_name + abjad_kabir(mother_name)
    b_val = abjad_kabir(family_name) + kabir_name
    status_key = str(a_val % 4)
    income_key = str(b_val % 3)
    baten = _reduce_full(kabir_name)
    return {
        "name": name,
        "meaning": name_entry.get("meaning", ""),
        "status_key": status_key,
        "status_text": STATUS_TEXT[status_key],
        "income_key": income_key,
        "income_text": INCOME_TEXT[income_key],
        "baten": baten,
    }


def get_all_matches(gender: str, family_name: str, mother_name: str,
                     desired_status: str | None, desired_income: str | None) -> dict:
    """
    تمام اسم‌های مطابق (بدون برش) را برمی‌گرداند:
    {"top3": [...سه‌تای هم‌آواترین...], "rest": [...بقیه، بر اساس هماهنگی مرتب‌شده...], "total": N}
    """
    matches = []
    for name_entry in _name_pool(gender):
        info = evaluate_name(name_entry, family_name, mother_name)
        status_ok = (desired_status is None) or (info["status_key"] == desired_status)
        income_ok = (desired_income is None) or (info["income_key"] == desired_income)
        if status_ok and income_ok:
            info["harmony"] = _harmony_score(info["name"], family_name)
            matches.append(info)

    total = len(matches)
    if total == 0:
        return {"top3": [], "rest": [], "total": 0}

    ranked = sorted(matches, key=lambda x: x["harmony"], reverse=True)
    return {"top3": ranked[:3], "rest": ranked[3:], "total": total}


def format_page(gender: str, result: dict, page: int = 0, page_size: int = 10) -> dict:
    """
    خروجی: {"text": متن قابل ارسال, "has_more": آیا صفحه‌ی بعدی هست}
    page=0 شامل سه‌تای برتر + ۱۰ تای اول از بقیه است؛ صفحه‌های بعدی فقط ۱۰تا ۱۰تا از rest.
    """
    gender_label = "پسر" if gender == "boy" else "دختر"
    if result["total"] == 0:
        return {
            "text": (
                "❌ با این ترکیب دقیق، اسمی توی فهرست فعلی پیدا نشد.\n"
                "می‌تونی یکی از فیلترها (پایگاه یا درآمد) رو «فرقی نداره» بذاری تا گزینه‌های بیشتری ببینی."
            ),
            "has_more": False,
        }

    rest = result["rest"]
    start = page * page_size
    end = start + page_size
    chunk = rest[start:end]
    has_more = end < len(rest)

    lines = []
    if page == 0:
        lines.append(f"👶 *پیشنهاد اسم {gender_label}* (از {result['total']} گزینه‌ی مطابق)\n")
        lines.append("✨ *سه گزینه‌ی برتر (هم‌آواترین با فامیلی):*")
        for r in result["top3"]:
            lines.append(f"• *{r['name']}* — {r['meaning']}")
        if chunk:
            lines.append("\n📋 *گزینه‌های بیشتر:*")
    else:
        lines.append(f"📋 *ادامه‌ی گزینه‌ها (صفحه {page + 1}):*")

    for r in chunk:
        lines.append(f"• *{r['name']}* — {r['meaning']}")

    return {"text": "\n".join(lines), "has_more": has_more}
