# -*- coding: utf-8 -*-
"""
«مناجات» — از مناجات‌نامه‌ی خواجه عبدالله انصاری (قرن ۵ هجری، مالکیت عمومی).
برخلاف فال حافظ، اینجا محدودیت «یک‌بار در روز» وجود نداره — هر بار که کاربر
بخواد، یه مناجات کاملاً تصادفی جدید نشون داده می‌شه.
"""
import json
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "munajat_data.json"), encoding="utf-8") as f:
    _ITEMS = json.load(f)


def get_random_munajat() -> dict:
    return random.choice(_ITEMS)


def format_munajat(item: dict) -> str:
    return (
        "🕊 *مناجات*\n\n"
        f"_{item['text']}_\n\n"
        "— خواجه عبدالله انصاری"
    )
