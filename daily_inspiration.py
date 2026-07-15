# -*- coding: utf-8 -*-
"""
«الهام روز» — هر روز یک تک‌بیت یا مناجات، بدون تکرار تا وقتی همه‌ی مجموعه تموم بشه.

منطق عدم‌تکرار:
هر کاربر یک ترتیب تصادفی شخصی (shuffle) از همه‌ی آیتم‌ها می‌گیره که در دیتابیس
ذخیره می‌شه. هر روز (بر اساس تاریخ UTC)، یک پله جلو می‌ره. وقتی به انتهای
ترتیب رسید، دوباره shuffle می‌شه و از اول (بدون تکرار فوری آخرین آیتم) ادامه پیدا می‌کنه.
اگه همون روز دوباره درخواست بده، همون آیتم قبلی امروز رو دوباره می‌بینه (نه آیتم جدید).
"""
import json
import os
import random
from datetime import datetime, timezone

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "elham_data.json"), encoding="utf-8") as f:
    _ITEMS = json.load(f)

_ITEMS_BY_ID = {item["id"]: item for item in _ITEMS}
_ALL_IDS = [item["id"] for item in _ITEMS]


def _new_shuffled_order(avoid_first: str | None = None) -> list:
    order = _ALL_IDS.copy()
    random.shuffle(order)
    # جلوگیری از اینکه دور جدید دقیقاً با همون آیتم آخرِ دور قبلی شروع بشه
    if avoid_first and order[0] == avoid_first and len(order) > 1:
        order[0], order[1] = order[1], order[0]
    return order


def get_today_elham(telegram_id: int) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    state = database.get_elham_state(telegram_id)

    if state is None:
        order = _new_shuffled_order()
        position = 0
        database.save_elham_state(telegram_id, json.dumps(order), position, today)
    elif state["last_shown_date"] == today:
        order = json.loads(state["shuffled_order"])
        position = state["position"]
    else:
        order = json.loads(state["shuffled_order"])
        position = state["position"] + 1
        if position >= len(order):
            order = _new_shuffled_order(avoid_first=order[-1])
            position = 0
        database.save_elham_state(telegram_id, json.dumps(order), position, today)

    item_id = order[position]
    return _ITEMS_BY_ID[item_id]


def format_elham(item: dict) -> str:
    verses_text = "\n".join(item["verses"])
    poet_line = f"— {item['poet']}" if item.get("poet") else ""
    return (
        "🌅 *الهام روز*\n\n"
        f"_{verses_text}_\n"
        f"{poet_line}\n\n"
        f"📖 *تفسیر:*\n{item['interpretation']}"
    )
