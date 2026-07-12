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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                telegram_username TEXT,
                first_seen TEXT NOT NULL,
                banned INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                first_name TEXT NOT NULL,
                family_name TEXT NOT NULL,
                mother_name TEXT,
                jalali_year INTEGER NOT NULL,
                jalali_month INTEGER NOT NULL,
                jalali_day INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contacts_owner ON contacts(owner_id)"
        )


def touch_user(telegram_id: int, telegram_username: str) -> None:
    """هر بار کاربر /start می‌زنه، حضورش رو در جدول users ثبت/به‌روزرسانی می‌کنه."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_id, telegram_username, first_seen, banned)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(telegram_id) DO UPDATE SET telegram_username = excluded.telegram_username
            """,
            (telegram_id, telegram_username, datetime.now(timezone.utc).isoformat()),
        )


def is_banned(telegram_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT banned FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return bool(row["banned"]) if row else False


def ban_user(telegram_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE users SET banned = 1 WHERE telegram_id = ?", (telegram_id,)
        )
    return cur.rowcount > 0


def unban_user(telegram_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE users SET banned = 0 WHERE telegram_id = ?", (telegram_id,)
        )
    return cur.rowcount > 0


def get_all_user_ids() -> list:
    """آیدی همه‌ی کاربرانی که حداقل یک‌بار /start زدن (برای broadcast)."""
    with _connect() as conn:
        rows = conn.execute("SELECT telegram_id FROM users WHERE banned = 0").fetchall()
    return [r["telegram_id"] for r in rows]


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


def add_contact(owner_id: int, first_name: str, family_name: str, mother_name: str,
                 jy: int, jm: int, jd: int) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO contacts (owner_id, first_name, family_name, mother_name,
                                   jalali_year, jalali_month, jalali_day, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (owner_id, first_name, family_name, mother_name or "", jy, jm, jd,
             datetime.now(timezone.utc).isoformat()),
        )
    return cur.lastrowid


def get_contacts(owner_id: int) -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE owner_id = ? ORDER BY id DESC",
            (owner_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_contact(contact_id: int, owner_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM contacts WHERE id = ? AND owner_id = ?",
            (contact_id, owner_id),
        ).fetchone()
    return dict(row) if row else None


def delete_contact(contact_id: int, owner_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM contacts WHERE id = ? AND owner_id = ?",
            (contact_id, owner_id),
        )
    return cur.rowcount > 0


def get_todays_birthday_contacts(jalali_month: int, jalali_day: int) -> list:
    """همه‌ی مخاطبینِ همه‌ی کاربرها که امروز (شمسی) تولدشونه."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE jalali_month = ? AND jalali_day = ?",
            (jalali_month, jalali_day),
        ).fetchall()
    return [dict(r) for r in rows]


def get_last_submission(telegram_id: int) -> dict | None:
    """کامل‌ترین رکورد آخرین محاسبه‌ی این کاربر (برای قابلیت مقایسه‌ی دو نفر)."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT first_name, family_name, mother_name, jalali_year, jalali_month, jalali_day,
                   gregorian_date, cosmic_code, destiny_num, fate_num, vibration_num, baten_num
            FROM submissions
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()
    return dict(row) if row else None


def get_all_submissions() -> list:
    """همه‌ی رکوردها، برای خروجی CSV به ادمین (جدیدترین اول)."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT telegram_id, telegram_username, first_name, family_name, mother_name,
                   jalali_year, jalali_month, jalali_day, gregorian_date, cosmic_code,
                   destiny_num, fate_num, vibration_num, baten_num, created_at
            FROM submissions
            ORDER BY id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_daily_growth(days: int = 7) -> list:
    """تعداد کاربران جدید (اولین /start) به تفکیک روز، برای N روز اخیر."""
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT substr(first_seen,1,10) AS day, COUNT(*) AS new_users
            FROM users
            WHERE first_seen >= datetime('now', ?)
            GROUP BY day
            ORDER BY day
            """,
            (f"-{days} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def get_top_numbers() -> dict:
    """پرتکرارترین مقادیر عدد سرنوشت / تقدیر / ارتعاش بین همه‌ی کاربران."""
    with _connect() as conn:
        def _top(col):
            return conn.execute(
                f"SELECT {col} AS val, COUNT(*) AS c FROM submissions "
                f"GROUP BY {col} ORDER BY c DESC LIMIT 3"
            ).fetchall()
        destiny = [dict(r) for r in _top("destiny_num")]
        fate = [dict(r) for r in _top("fate_num")]
        vibration = [dict(r) for r in _top("vibration_num")]
        baten = [dict(r) for r in _top("baten_num")]
    return {"destiny": destiny, "fate": fate, "vibration": vibration, "baten": baten}


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
