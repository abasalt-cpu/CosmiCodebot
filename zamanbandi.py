# -*- coding: utf-8 -*-
"""
«به زمان‌بندی خدا اعتماد کن» — نسخه‌ی محدود و تبلیغاتی.

⚠️ توجه مهم: این کتاب (نوشته‌ی آکیرا، ترجمه‌ی نهال سهیلی‌فر، نشر داهی) دارای
کپی‌رایت و در حال فروش فعاله. به همین دلیل، فقط ۳ جمله‌ی نمونه از اون اینجا
نگه داشته شده (نه کل کتاب)، همراه با معرفی و لینک خرید — به‌عنوان یه معرفی/تبلیغ
مشروع، نه جایگزینی برای خرید کتاب.
"""
import json
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "zamanbandi_data.json"), encoding="utf-8") as f:
    _ITEMS = json.load(f)

BOOK_LINK = "https://taaghche.com/book/232958/به-زمان-بندی-خدا-اعتماد-کن"


def get_sample_zamanbandi() -> dict:
    return random.choice(_ITEMS)


def format_zamanbandi(item: dict) -> str:
    return (
        f"{item['time']}\n\n"
        f"_{item['quote']}_\n\n"
        "📖 این جمله از کتاب «به زمان‌بندی خدا اعتماد کن» (آکیرا، ترجمه‌ی نهال سهیلی‌فر) بود.\n"
        f"برای خوندن کامل کتاب: {BOOK_LINK}"
    )
