# -*- coding: utf-8 -*-
"""
«به زمان‌بندی خدا اعتماد کن» — دقیقاً مثل فال حافظ: 
"""
import json
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "zamanbandi_data.json"), encoding="utf-8") as f:
    _ITEMS = json.load(f)



def get_sample_zamanbandi() -> dict:
    return random.choice(_ITEMS)


def format_zamanbandi(item: dict) -> str:
    return (
        f"{item['time']}\n\n"
        f"_{item['quote']}_\n\n"
        "📖 این جمله از کتاب «به زمان‌بندی خدا اعتماد کن» (آکیرا، ترجمه‌ی نهال سهیلی‌فر) بود.\n"
        
