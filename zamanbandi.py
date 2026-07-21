# -*- coding: utf-8 -*-
"""
«به زمان‌بندی خدا اعتماد کن» — دقیقاً مثل فال حافظ: هر کاربر روزی یک پیام
ثابت می‌گیره، بدون تکرار تا وقتی کل مجموعه تموم بشه؛ بعدش دوباره شافل می‌شه.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "zamanbandi_data.json"), encoding="utf-8") as f:
    _ITEMS = json.load(f)


def get_daily_zamanbandi(telegram_id: int) -> dict:
    """پیام ثابت امروز برای این کاربر (deterministic بر اساس آیدی + تاریخ امروز)."""
    today = datetime.now(timezone.utc).date().isoformat()
    seed_str = f"zamanbandi-{telegram_id}-{today}"
    digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(_ITEMS)
    return _ITEMS[index]


def format_zamanbandi(item: dict) -> str:
    return f"⏳ *به زمان‌بندی خدا اعتماد کن*\n\n_{item['quote']}_"
