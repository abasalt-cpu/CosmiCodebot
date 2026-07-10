# -*- coding: utf-8 -*-
"""
ذخیره‌سازی پروفایل کاربران ربات «عدد کیهانی» با SQLite.

⚠️ نکته‌ی مهم درباره‌ی هاستینگ:
اگه ربات روی Railway (یا هر سرویسی با فایل‌سیستم موقت/ephemeral) اجرا می‌شه،
فایل دیتابیس با هر دیپلوی جدید ممکنه پاک بشه، مگر یک "Volume" دائمی به سرویس وصل کنی
(در Railway: Settings -> Volumes -> New Volume -> مسیر /data را مقداردهی کن و
مسیر DB_PATH پایین رو هم به /data/cosmic_bot.db تغییر بده).
روی یک VPS معمولی، فایل دیتابیس به‌طور طبیعی روی دیسک می‌مونه و مشکلی نیست.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "cosmic_bot.db"))


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                telegram_username TEXT,
                first_name TEXT NOT NULL,
                family_name TEXT NOT NULL,
                mother_name TEXT,
                jalali_year INTEGER NOT NULL,
                jalali_month INTEGER NOT NULL,
                jalali_day INTEGER NOT NULL,
                gregorian_date TEXT,
                cosmic_code TEXT,
                destiny_num INTEGER,
                fate_num INTEGER,
                vibration_num INTEGER,
                baten_num INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_submissions_telegram_id ON submissions(telegram_id)"
        )


def save_submission(telegram_id: int, telegram_username: str, first_name: str,
                     family_name: str, mother_name: str, jy: int, jm: int, jd: int,
                     report: dict) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO submissions (
                telegram_id, telegram_username, first_name, family_name, mother_name,
                jalali_year, jalali_month, jalali_day, gregorian_date, cosmic_code,
                destiny_num, fate_num, vibration_num, baten_num, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id, telegram_username, first_name, family_name, mother_name,
                jy, jm, jd, report["gregorian_date"], report["cosmic_code"],
                report["destiny_num"], report["fate_num"], report["vibration_num"],
                report["baten_num"], datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_stats() -> dict:
    with _connect() as conn:
        total_submissions = conn.execute("SELECT COUNT(*) c FROM submissions").fetchone()["c"]
        unique_users = conn.execute("SELECT COUNT(DISTINCT telegram_id) c FROM submissions").fetchone()["c"]
        latest = conn.execute(
            "SELECT first_name, family_name, created_at FROM submissions ORDER BY id DESC LIMIT 5"
        ).fetchall()
    return {
        "total_submissions": total_submissions,
        "unique_users": unique_users,
        "latest": [dict(r) for r in latest],
    }


def count_today(telegram_id: int) -> int:
    """تعداد درخواست‌هایی که این کاربر امروز (UTC) ثبت کرده."""
    today = datetime.now(timezone.utc).date().isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM submissions WHERE telegram_id = ? AND substr(created_at,1,10) = ?",
            (telegram_id, today),
        ).fetchone()
    return row["c"]


def get_user_history(telegram_id: int, limit: int = 5) -> list:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT first_name, family_name, cosmic_code, destiny_num, fate_num,
                   vibration_num, baten_num, created_at
            FROM submissions
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (telegram_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]
