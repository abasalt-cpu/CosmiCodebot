# -*- coding: utf-8 -*-
"""
فال حافظ روزانه.

هر کاربر در هر روز (به وقت UTC) دقیقاً یک فال ثابت می‌گیره — یعنی اگه چند بار
توی همون روز درخواست بده، همون فال قبلی رو دوباره می‌بینه (مطابق سنت فال‌گیری:
یک فال در روز). فردا، فال جدید و متفاوتی می‌گیره.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "hafez_data.json"), encoding="utf-8") as f:
    _GHAZALS = json.load(f)


def get_daily_fal(telegram_id: int) -> dict:
    """فال ثابت امروز برای این کاربر (deterministic بر اساس آیدی + تاریخ امروز)."""
    today = datetime.now(timezone.utc).date().isoformat()
    seed_str = f"{telegram_id}-{today}"
    digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(_GHAZALS)
    return _GHAZALS[index]


def get_ghazal_by_id(ghazal_id: int) -> dict | None:
    for g in _GHAZALS:
        if g["id"] == ghazal_id:
            return g
    return None


def format_fal(ghazal: dict) -> str:
    verses_text = "\n".join(ghazal["verses"])
    return (
        "🔮 *فال امروز شما*\n\n"
        f"_{verses_text}_\n\n"
        f"📖 *تفسیر:*\n{ghazal['interpretation']}"
    )


def format_full_ghazal(ghazal: dict) -> str:
    verses_text = "\n".join(ghazal.get("full_verses", ghazal["verses"]))
    return f"📜 *غزل شماره‌ی {ghazal['id']} حافظ*\n\n_{verses_text}_"
