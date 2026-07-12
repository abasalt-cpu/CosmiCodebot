# -*- coding: utf-8 -*-
"""
ربات تلگرام «عدد کیهانی»
اجرا: python3 bot.py
پیش‌نیاز: pip install -r requirements.txt

متغیرهای محیطی:
    BOT_TOKEN     (اجباری) توکن ربات از BotFather
    ADMIN_ID      (اختیاری) آیدی عددی تلگرام مدیر، برای /stats، /export، /broadcast، /ban و بکاپ روزانه
    DAILY_LIMIT   (اختیاری، پیش‌فرض ۱۰) سقف تعداد محاسبه در روز برای هر کاربر عادی (ادمین محدودیت نداره)
    DB_PATH       (اختیاری) مسیر فایل دیتابیس (برای Volume دائمی روی Railway)
"""
import asyncio
import csv
import io
import logging
import os
import re
import urllib.parse
from datetime import time as dt_time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram import (
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from cosmic_logic import calculate_cosmic_report, format_report, jalali_to_gregorian
import ai_compare
import analytics_chart
import database
import hafez_fal
import image_report
import natal_chart
import zodiac

LOG_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(LOG_DIR / "bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# --- مراحل مکالمه ---
FIRST_NAME, FAMILY_NAME, MOTHER_NAME, BIRTH_DAY, BIRTH_MONTH, BIRTH_YEAR = range(6)

# --- مراحل مکالمه‌ی «مقایسه‌ی دو نفر» ---
(
    CMP_CHOICE, CMP_P2_FIRST, CMP_P2_FAMILY, CMP_P2_MOTHER,
    CMP_P2_DAY, CMP_P2_MONTH, CMP_P2_YEAR,
) = range(100, 107)

# --- مراحل مکالمه‌ی «زایچه‌ی تقریبی» ---
NATAL_HOUR, NATAL_MINUTE, NATAL_CITY = range(200, 203)

TOKEN = os.environ.get("BOT_TOKEN", "PUT-YOUR-TOKEN-HERE")
ADMIN_ID = os.environ.get("ADMIN_ID")
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "10"))

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

MONTH_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(PERSIAN_MONTHS[i], callback_data=f"month_{i + 1}"),
            InlineKeyboardButton(PERSIAN_MONTHS[i + 1], callback_data=f"month_{i + 2}"),
        ]
        for i in range(0, 12, 2)
    ]
)


USER_COMMANDS = [
    ("start", "🌌 محاسبه‌ی جدید"),
    ("menu", "📋 منوی اصلی"),
    ("compare", "🔗 مقایسه با یک نفر دیگر"),
    ("hafez", "🔮 فال حافظ"),
    ("zodiac", "♈️ طالع‌بینی امروز"),
    ("natal", "🌌 زایچه‌ی تقریبی"),
    ("contacts", "📇 مخاطبین ذخیره‌شده"),
    ("history", "📜 تاریخچه‌ی من"),
    ("help", "ℹ️ راهنما"),
    ("cancel", "❌ لغو مکالمه"),
]

ADMIN_EXTRA_COMMANDS = [
    ("stats", "📊 آمار ربات"),
    ("export", "📋 خروجی CSV کاربران"),
    ("broadcast", "📢 ارسال پیام همگانی"),
    ("ban", "🚫 مسدودکردن کاربر"),
    ("unban", "✅ رفع مسدودی کاربر"),
]


def _is_admin(user_id: int) -> bool:
    return bool(ADMIN_ID) and str(user_id) == str(ADMIN_ID)


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f\u200e\u200f\u202a-\u202e]")
_MARKDOWN_SPECIAL_RE = re.compile(r"[*_`\[\]]")
_ALLOWED_NAME_RE = re.compile(r"^[a-zA-Zا-یآ-ی\u200c\s'\-]{1,40}$")


def sanitize_name(raw: str) -> str | None:
    """
    پاک‌سازی نام/فامیل/نام مادر:
      - حذف کاراکترهای کنترلی و جهت‌ساز نامرئی (که می‌تونن ورودی رو مخفی/دستکاری کنن)
      - حذف کاراکترهای خاص مارک‌داون (که فرمت پیام رو خراب می‌کنن)
      - محدود به حروف فارسی/انگلیسی، فاصله، خط تیره و آپاستروف؛ حداکثر ۴۰ کاراکتر
    اگه ورودی بعد از پاک‌سازی نامعتبر بود، None برمی‌گردونه.
    """
    if not raw:
        return None
    text = _CONTROL_CHARS_RE.sub("", raw).strip()
    text = _MARKDOWN_SPECIAL_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    if not text or not _ALLOWED_NAME_RE.match(text):
        return None
    return text


def _result_keyboard(data: dict, full_name: str) -> InlineKeyboardMarkup:
    share_text = (
        f"🌌 گزارش عدد کیهانی {full_name}\n"
        f"کد کیهانی: {data['cosmic_code']}\n"
        f"عدد سرنوشت: {data['destiny_num']} | عدد تقدیر: {data['fate_num']}"
    )
    share_url = "https://t.me/share/url?" + urllib.parse.urlencode({"url": "", "text": share_text})
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 محاسبه جدید", callback_data="new_calc"),
                InlineKeyboardButton("📜 تاریخچه من", callback_data="show_history"),
            ],
            [InlineKeyboardButton("💾 ذخیره به‌عنوان مخاطب", callback_data="save_contact")],
            [InlineKeyboardButton("🔗 اشتراک‌گذاری نتیجه", url=share_url)],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    target = update.callback_query.message if update.callback_query else update.message

    try:
        database.touch_user(user.id, user.username or "")
    except Exception:
        logger.exception("خطا در ثبت کاربر")

    try:
        if database.is_banned(user.id):
            await target.reply_text("⛔ دسترسی شما به این ربات مسدود شده است.")
            return ConversationHandler.END
    except Exception:
        logger.exception("خطا در بررسی وضعیت مسدودی")

    try:
        used_today = database.count_today(user.id)
    except Exception:
        logger.exception("خطا در بررسی محدودیت روزانه")
        used_today = 0

    if used_today >= DAILY_LIMIT and not _is_admin(user.id):
        await target.reply_text(
            f"⛔ شما امروز به سقف {DAILY_LIMIT} محاسبه رسیدی. فردا دوباره امتحان کن."
        )
        return ConversationHandler.END

    await target.reply_text(
        "🌌 به ربات «عدد کیهانی» خوش اومدی!\n\n"
        "برای محاسبه چند تا سوال کوچیک می‌پرسم.\n"
        "هر وقت خواستی، با /cancel می‌تونی لغو کنی.\n\n"
        "لطفاً *نام* خودت رو بفرست:",
        parse_mode="Markdown",
    )
    return FIRST_NAME


async def start_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await start(update, context)


SKIP_MOTHER_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("⏭ رد کردن (نمی‌خوام وارد کنم)", callback_data="skip_mother")]]
)


async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    clean = sanitize_name(update.message.text)
    if not clean:
        await update.message.reply_text(
            "❌ نام باید فقط شامل حروف فارسی/انگلیسی باشه (بدون عدد یا نماد خاص). دوباره بفرست:"
        )
        return FIRST_NAME
    context.user_data["first_name"] = clean
    await update.message.reply_text("نام خانوادگی؟")
    return FAMILY_NAME


async def get_family_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    clean = sanitize_name(update.message.text)
    if not clean:
        await update.message.reply_text(
            "❌ نام خانوادگی باید فقط شامل حروف فارسی/انگلیسی باشه. دوباره بفرست:"
        )
        return FAMILY_NAME
    context.user_data["family_name"] = clean
    await update.message.reply_text(
        "نام مادر؟ (جهت تعیین پایگاه اجتماعی)\n"
        "اگه نمی‌خوای وارد کنی، دکمه‌ی رد کردن رو بزن.",
        reply_markup=SKIP_MOTHER_KEYBOARD,
    )
    return MOTHER_NAME


async def get_mother_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    clean = sanitize_name(update.message.text)
    if not clean:
        await update.message.reply_text(
            "❌ نام مادر باید فقط شامل حروف فارسی/انگلیسی باشه. دوباره بفرست، "
            "یا دکمه‌ی رد کردن رو بزن.",
            reply_markup=SKIP_MOTHER_KEYBOARD,
        )
        return MOTHER_NAME
    context.user_data["mother_name"] = clean
    await update.message.reply_text("روز تولدت (شمسی) رو به عدد بفرست (مثلاً 15):")
    return BIRTH_DAY


async def skip_mother_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["mother_name"] = ""
    await query.message.reply_text(
        "باشه، رد شد (پایگاه اجتماعی برات محاسبه نمی‌شه).\n\n"
        "روز تولدت (شمسی) رو به عدد بفرست (مثلاً 15):"
    )
    return BIRTH_DAY


async def get_birth_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not (text.isdigit() and 1 <= int(text) <= 31):
        await update.message.reply_text("❌ عدد روز باید بین ۱ تا ۳۱ باشه. دوباره بفرست:")
        return BIRTH_DAY
    context.user_data["jd"] = int(text)
    await update.message.reply_text("ماه تولدت رو انتخاب کن:", reply_markup=MONTH_KEYBOARD)
    return BIRTH_MONTH


async def get_birth_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    month_num = int(query.data.split("_")[1])
    context.user_data["jm"] = month_num
    await query.message.reply_text(
        f"ماه انتخابی: {PERSIAN_MONTHS[month_num - 1]} ✅\n\nسال تولدت (شمسی) رو به عدد بفرست (مثلاً 1370):"
    )
    return BIRTH_YEAR


async def get_birth_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not (text.isdigit() and 1300 <= int(text) <= 1420):
        await update.message.reply_text("❌ سال باید بین ۱۳۰۰ تا ۱۴۲۰ باشه. دوباره بفرست:")
        return BIRTH_YEAR

    ud = context.user_data
    jy = int(text)
    jm = ud["jm"]
    jd = ud["jd"]

    data = calculate_cosmic_report(ud["first_name"], ud["family_name"], ud["mother_name"], jy, jm, jd)
    full_name = f"{ud['first_name']} {ud['family_name']}"

    # برای دکمه‌ی «ذخیره به‌عنوان مخاطب» (حتی اگه بعداً user_data بخشی پاک بشه، این کلید جداست)
    ud["last_full_profile"] = {
        "first_name": ud["first_name"], "family_name": ud["family_name"],
        "mother_name": ud["mother_name"], "jy": jy, "jm": jm, "jd": jd,
    }

    try:
        user = update.effective_user
        database.save_submission(
            telegram_id=user.id,
            telegram_username=user.username or "",
            first_name=ud["first_name"],
            family_name=ud["family_name"],
            mother_name=ud["mother_name"],
            jy=jy, jm=jm, jd=jd,
            report=data,
        )
    except Exception:
        logger.exception("خطا در ذخیره‌سازی دیتابیس")

    try:
        if image_report.fonts_available():
            buf = image_report.render_report_image(full_name, data)
            await update.message.reply_photo(photo=buf)
    except Exception:
        logger.exception("خطا در ساخت/ارسال تصویر گزارش")

    await update.message.reply_text(
        format_report(full_name, data),
        parse_mode="Markdown",
        reply_markup=_result_keyboard(data, full_name),
    )
    return ConversationHandler.END


async def save_contact_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    profile = context.user_data.get("last_full_profile")
    if not profile:
        await query.message.reply_text(
            "⚠️ اطلاعات این محاسبه دیگه در دسترس نیست (شاید ربات ری‌استارت شده). "
            "دوباره با /start محاسبه کن، بعد دکمه‌ی ذخیره رو بزن."
        )
        return
    try:
        database.add_contact(
            owner_id=update.effective_user.id,
            first_name=profile["first_name"], family_name=profile["family_name"],
            mother_name=profile["mother_name"], jy=profile["jy"], jm=profile["jm"], jd=profile["jd"],
        )
        await query.message.reply_text(
            f"✅ «{profile['first_name']} {profile['family_name']}» به مخاطبین ذخیره شد.\n"
            f"دفعه‌ی بعد توی /compare می‌تونی مستقیم انتخابش کنی."
        )
    except Exception:
        logger.exception("خطا در ذخیره‌ی مخاطب")
        await query.message.reply_text("مشکلی در ذخیره‌سازی مخاطب پیش اومد.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "لغو شد. هر وقت خواستی با /start دوباره شروع کن.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# مقایسه‌ی دو نفر
# ---------------------------------------------------------------------------

async def compare_start_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await compare_start(update, context)


async def compare_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # فقط کلیدهای مربوط به مقایسه رو پاک کن، نه کل user_data (مثلاً last_full_profile حفظ بشه)
    for key in list(context.user_data.keys()):
        if key.startswith(("p1_", "p2_", "cmp_")):
            del context.user_data[key]

    user = update.effective_user
    target = update.callback_query.message if update.callback_query else update.message

    try:
        used_today = database.count_today(user.id)
    except Exception:
        used_today = 0
    if used_today >= DAILY_LIMIT and not _is_admin(user.id):
        await target.reply_text(
            f"⛔ شما امروز به سقف {DAILY_LIMIT} محاسبه رسیدی. فردا دوباره امتحان کن."
        )
        return ConversationHandler.END

    try:
        last = database.get_last_submission(user.id)
    except Exception:
        last = None

    try:
        contacts = database.get_contacts(user.id)
    except Exception:
        contacts = []

    buttons = [[InlineKeyboardButton("👥 مقایسه‌ی دو نفر جدید", callback_data="cmp_new")]]
    if last and contacts:
        buttons.insert(
            0,
            [InlineKeyboardButton("📇 من + یکی از مخاطبینم", callback_data="cmp_contact")],
        )
    if last:
        buttons.insert(
            0,
            [InlineKeyboardButton(
                f"🔁 مقایسه با آخرین محاسبه‌ی خودم ({last['first_name']})",
                callback_data="cmp_self",
            )],
        )

    await target.reply_text(
        "🔗 *مقایسه‌ی دو نفر*\n\nچطور می‌خوای مقایسه کنی؟",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return CMP_CHOICE


async def compare_pick_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    last = database.get_last_submission(user.id)
    if not last:
        await query.message.reply_text("محاسبه‌ی قبلی‌ای پیدا نشد. با /start اول یه محاسبه انجام بده.")
        return ConversationHandler.END
    context.user_data["p1_name"] = f"{last['first_name']} {last['family_name']}"
    context.user_data["p1_data"] = last

    contacts = database.get_contacts(user.id)
    if not contacts:
        await query.message.reply_text("هنوز هیچ مخاطبی ذخیره نکردی.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(f"{c['first_name']} {c['family_name']}", callback_data=f"contact_{c['id']}")]
        for c in contacts
    ]
    await query.message.reply_text(
        "کدوم مخاطب رو می‌خوای مقایسه کنی؟", reply_markup=InlineKeyboardMarkup(buttons)
    )
    return CMP_CHOICE


async def compare_contact_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    contact_id = int(query.data.split("_")[1])
    contact = database.get_contact(contact_id, user.id)
    if not contact:
        await query.message.reply_text("این مخاطب پیدا نشد (شاید حذف شده).")
        return ConversationHandler.END

    p2_name = f"{contact['first_name']} {contact['family_name']}"
    p2_data = calculate_cosmic_report(
        contact["first_name"], contact["family_name"], contact["mother_name"] or "",
        contact["jalali_year"], contact["jalali_month"], contact["jalali_day"],
    )

    p1_name = context.user_data.get("p1_name")
    p1_data = context.user_data.get("p1_data")
    if not p1_name or not p1_data:
        await query.message.reply_text("مشکلی پیش اومد، دوباره از /compare شروع کن.")
        return ConversationHandler.END

    await _finish_compare(query.message, update, context, p1_name, p1_data, p2_name, p2_data)
    return ConversationHandler.END


async def contacts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        contacts = database.get_contacts(user.id)
    except Exception:
        logger.exception("خطا در خواندن مخاطبین")
        await update.message.reply_text("مشکلی در خواندن لیست مخاطبین پیش اومد.")
        return

    if not contacts:
        await update.message.reply_text(
            "هنوز هیچ مخاطبی نداری. بعد از هر محاسبه، دکمه‌ی «💾 ذخیره به‌عنوان مخاطب» رو بزن."
        )
        return

    buttons = [
        [InlineKeyboardButton(f"🗑 حذف {c['first_name']} {c['family_name']}", callback_data=f"delcontact_{c['id']}")]
        for c in contacts
    ]
    lines = ["📇 *مخاطبین ذخیره‌شده‌ی تو:*\n"]
    for c in contacts:
        lines.append(f"• {c['first_name']} {c['family_name']} — {c['jalali_year']}/{c['jalali_month']}/{c['jalali_day']}")
    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def delete_contact_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    contact_id = int(query.data.split("_")[1])
    ok = database.delete_contact(contact_id, update.effective_user.id)
    await query.message.reply_text("✅ حذف شد." if ok else "این مخاطب پیدا نشد.")


async def compare_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cmp_self":
        last = database.get_last_submission(update.effective_user.id)
        if not last:
            await query.message.reply_text("محاسبه‌ی قبلی‌ای پیدا نشد. با /start اول یه محاسبه انجام بده.")
            return ConversationHandler.END
        context.user_data["p1_name"] = f"{last['first_name']} {last['family_name']}"
        context.user_data["p1_data"] = last
        await query.message.reply_text("نام نفر دوم؟")
        return CMP_P2_FIRST

    await query.message.reply_text("باشه، اول اطلاعات *نفر اول* رو می‌گیرم.\n\nنام نفر اول؟", parse_mode="Markdown")
    context.user_data["cmp_stage"] = "p1"
    return CMP_P2_FIRST


async def compare_get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    clean = sanitize_name(update.message.text)
    if not clean:
        await update.message.reply_text("❌ فقط حروف فارسی/انگلیسی مجازه. دوباره بفرست:")
        return CMP_P2_FIRST
    stage = context.user_data.get("cmp_stage", "p2")
    context.user_data[f"{stage}_first_name"] = clean
    await update.message.reply_text("نام خانوادگی؟")
    return CMP_P2_FAMILY


async def compare_get_family_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    clean = sanitize_name(update.message.text)
    if not clean:
        await update.message.reply_text("❌ فقط حروف فارسی/انگلیسی مجازه. دوباره بفرست:")
        return CMP_P2_FAMILY
    stage = context.user_data.get("cmp_stage", "p2")
    context.user_data[f"{stage}_family_name"] = clean
    await update.message.reply_text(
        "نام مادر؟ (جهت تعیین پایگاه اجتماعی)",
        reply_markup=SKIP_MOTHER_KEYBOARD,
    )
    return CMP_P2_MOTHER


async def compare_get_mother_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    clean = sanitize_name(update.message.text)
    if not clean:
        await update.message.reply_text("❌ فقط حروف فارسی/انگلیسی مجازه، یا دکمه‌ی «رد کردن» رو بزن:")
        return CMP_P2_MOTHER
    stage = context.user_data.get("cmp_stage", "p2")
    context.user_data[f"{stage}_mother_name"] = clean
    await update.message.reply_text("روز تولد (شمسی) رو به عدد بفرست:")
    return CMP_P2_DAY


async def compare_skip_mother(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    stage = context.user_data.get("cmp_stage", "p2")
    context.user_data[f"{stage}_mother_name"] = None
    await update.callback_query.message.reply_text("روز تولد (شمسی) رو به عدد بفرست:")
    return CMP_P2_DAY


async def compare_get_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not (text.isdigit() and 1 <= int(text) <= 31):
        await update.message.reply_text("❌ عدد روز باید بین ۱ تا ۳۱ باشه. دوباره بفرست:")
        return CMP_P2_DAY
    stage = context.user_data.get("cmp_stage", "p2")
    context.user_data[f"{stage}_jd"] = int(text)
    await update.message.reply_text("ماه تولد رو انتخاب کن:", reply_markup=MONTH_KEYBOARD)
    return CMP_P2_MONTH


async def compare_get_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    stage = context.user_data.get("cmp_stage", "p2")
    month_num = int(query.data.split("_")[1])
    context.user_data[f"{stage}_jm"] = month_num
    await query.message.reply_text(
        f"ماه انتخابی: {PERSIAN_MONTHS[month_num - 1]} ✅\n\nسال تولد (شمسی) رو به عدد بفرست:"
    )
    return CMP_P2_YEAR


async def compare_get_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not (text.isdigit() and 1300 <= int(text) <= 1420):
        await update.message.reply_text("❌ سال باید بین ۱۳۰۰ تا ۱۴۲۰ باشه. دوباره بفرست:")
        return CMP_P2_YEAR

    ud = context.user_data
    stage = ud.get("cmp_stage", "p2")
    ud[f"{stage}_jy"] = int(text)

    report = calculate_cosmic_report(
        ud[f"{stage}_first_name"], ud[f"{stage}_family_name"],
        ud.get(f"{stage}_mother_name") or "",
        ud[f"{stage}_jy"], ud[f"{stage}_jm"], ud[f"{stage}_jd"],
    )
    full_name = f"{ud[f'{stage}_first_name']} {ud[f'{stage}_family_name']}"

    if stage == "p1":
        ud["p1_name"] = full_name
        ud["p1_data"] = report
        ud["cmp_stage"] = "p2"
        await update.message.reply_text("عالی! حالا اطلاعات *نفر دوم* رو می‌گیرم.\n\nنام نفر دوم؟", parse_mode="Markdown")
        return CMP_P2_FIRST

    # اگه به اینجا رسیدیم، یعنی نفر دوم کامل شد و نفر اول یا از قبل ست شده (cmp_self) یا p1 هست
    p1_name = ud["p1_name"]
    p1_data = ud["p1_data"]
    p2_name = full_name
    p2_data = report

    # ذخیره‌ی محاسبه‌ی نفر دوم هم در دیتابیس (اگه نفر جدید بود)
    try:
        user = update.effective_user
        database.save_submission(
            telegram_id=user.id, telegram_username=user.username or "",
            first_name=ud[f"{stage}_first_name"], family_name=ud[f"{stage}_family_name"],
            mother_name=ud.get(f"{stage}_mother_name") or "",
            jy=ud[f"{stage}_jy"], jm=ud[f"{stage}_jm"], jd=ud[f"{stage}_jd"],
            report=report,
        )
    except Exception:
        logger.exception("خطا در ذخیره‌سازی نفر دوم")

    await _finish_compare(update.message, update, context, p1_name, p1_data, p2_name, p2_data)
    return ConversationHandler.END


async def _finish_compare(target_message, update: Update, context: ContextTypes.DEFAULT_TYPE,
                           p1_name: str, p1_data: dict, p2_name: str, p2_data: dict) -> None:
    numeric_text = ai_compare.numeric_overlap_summary(p1_name, p1_data, p2_name, p2_data)
    await target_message.reply_text(numeric_text, parse_mode="Markdown")

    try:
        m1 = p1_data.get("solar_num") or p1_data.get("jalali_month")
        m2 = p2_data.get("solar_num") or p2_data.get("jalali_month")
        zodiac_text = zodiac.compatibility(m1, m2)
        await target_message.reply_text(zodiac_text, parse_mode="Markdown")
    except Exception:
        logger.exception("خطا در محاسبه‌ی هم‌خونی بروج")

    is_admin_user = _is_admin(update.effective_user.id)

    if ai_compare.ai_available():
        await target_message.reply_text("🤖 در حال تحلیل هوش مصنوعی، چند ثانیه صبر کن...")
        try:
            analysis = await asyncio.wait_for(
                asyncio.to_thread(
                    ai_compare.compare_two_people, p1_name, p1_data, p2_name, p2_data
                ),
                timeout=35,
            )
            await target_message.reply_text(f"🧠 *تحلیل همخونی*\n\n{analysis}", parse_mode="Markdown")
            return
        except Exception as e:
            logger.warning("تحلیل AI ناموفق بود (%s: %s)، از نسخه‌ی رایگان استفاده می‌شه", type(e).__name__, e)
            fallback = ai_compare.rule_based_analysis(p1_name, p1_data, p2_name, p2_data)
            footer = (
                f"\n\n_(⚠️ ادمین: تحلیل AI ناموفق بود — {type(e).__name__}: {e})_"
                if is_admin_user else
                "\n\n_(این یک تحلیل عمومی بر پایه‌ی اعداد است.)_"
            )
            await target_message.reply_text(f"🧠 *تحلیل همخونی*\n\n{fallback}{footer}", parse_mode="Markdown")
            return

    fallback = ai_compare.rule_based_analysis(p1_name, p1_data, p2_name, p2_data)
    footer = (
        "\n\n_(⚠️ ادمین: تحلیل هوش مصنوعی فعال نیست چون ANTHROPIC_API_KEY تنظیم نشده.)_"
        if is_admin_user else
        "\n\n_(این یک تحلیل عمومی بر پایه‌ی اعداد است.)_"
    )
    await target_message.reply_text(f"🧠 *تحلیل همخونی*\n\n{fallback}{footer}", parse_mode="Markdown")


async def hafez_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "🔮 *فال حافظ*\n\n"
        "چند لحظه چشم‌هاتو ببند، یه آرزو یا سوال توی دلت نگه‌دار، و بعد نیت کن...\n\n"
        "وقتی آماده بودی، دکمه رو بزن:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔮 فالم رو بگیر", callback_data="get_hafez")]]
        ),
    )


ZODIAC_MONTH_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(PERSIAN_MONTHS[i], callback_data=f"zmonth_{i + 1}"),
            InlineKeyboardButton(PERSIAN_MONTHS[i + 1], callback_data=f"zmonth_{i + 2}"),
        ]
        for i in range(0, 12, 2)
    ]
)


async def zodiac_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()

    last = None
    try:
        last = database.get_last_submission(update.effective_user.id)
    except Exception:
        pass

    if last:
        await target.reply_text(
            zodiac.format_horoscope(last["jalali_month"]), parse_mode="Markdown"
        )
    else:
        await target.reply_text(
            "ماه تولد شمسی‌ت رو انتخاب کن تا برجت رو پیدا کنم:",
            reply_markup=ZODIAC_MONTH_KEYBOARD,
        )


async def zodiac_month_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    month_num = int(query.data.split("_")[1])
    await query.message.reply_text(zodiac.format_horoscope(month_num), parse_mode="Markdown")


def _build_city_keyboard() -> InlineKeyboardMarkup:
    keys = list(natal_chart.CITIES.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = [InlineKeyboardButton(natal_chart.CITIES[keys[i]]["display_name"], callback_data=f"city_{keys[i]}")]
        if i + 1 < len(keys):
            row.append(InlineKeyboardButton(natal_chart.CITIES[keys[i + 1]]["display_name"], callback_data=f"city_{keys[i + 1]}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


CITY_KEYBOARD = _build_city_keyboard()


async def natal_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    try:
        last = database.get_last_submission(user.id)
    except Exception:
        last = None

    if not last:
        await update.message.reply_text(
            "برای محاسبه‌ی زایچه، اول باید یه‌بار عدد کیهانی‌ت رو با /start محاسبه کنی "
            "(چون از همون تاریخ تولد استفاده می‌کنیم)."
        )
        return ConversationHandler.END

    context.user_data["natal_jy"] = last["jalali_year"]
    context.user_data["natal_jm"] = last["jalali_month"]
    context.user_data["natal_jd"] = last["jalali_day"]

    await update.message.reply_text(
        "🌌 برای محاسبه‌ی زایچه‌ی تقریبی، به ساعت و محل تولدت هم نیاز دارم.\n\n"
        "ساعت تولدت چند بود؟ (فقط عدد ساعت، ۰ تا ۲۳ — اگه دقیق نمی‌دونی، تقریبی بفرست)"
    )
    return NATAL_HOUR


async def natal_get_hour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not (text.isdigit() and 0 <= int(text) <= 23):
        await update.message.reply_text("❌ ساعت باید بین ۰ تا ۲۳ باشه. دوباره بفرست:")
        return NATAL_HOUR
    context.user_data["natal_hour"] = int(text)
    await update.message.reply_text("دقیقه‌ی تولد؟ (۰ تا ۵۹، اگه نمی‌دونی بنویس 0)")
    return NATAL_MINUTE


async def natal_get_minute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not (text.isdigit() and 0 <= int(text) <= 59):
        await update.message.reply_text("❌ دقیقه باید بین ۰ تا ۵۹ باشه. دوباره بفرست:")
        return NATAL_MINUTE
    context.user_data["natal_minute"] = int(text)
    await update.message.reply_text("شهر تولدت رو انتخاب کن:", reply_markup=CITY_KEYBOARD)
    return NATAL_CITY


async def natal_get_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    city_key = query.data.split("_", 1)[1]

    ud = context.user_data
    gy, gm, gd = jalali_to_gregorian(ud["natal_jy"], ud["natal_jm"], ud["natal_jd"])

    try:
        result = natal_chart.calculate_natal(
            gy, gm, gd, ud["natal_hour"], ud["natal_minute"], city_key
        )
        await query.message.reply_text(natal_chart.format_natal(result), parse_mode="Markdown")
    except Exception:
        logger.exception("خطا در محاسبه‌ی زایچه")
        await query.message.reply_text("مشکلی در محاسبه‌ی زایچه پیش اومد.")

    return ConversationHandler.END


async def hafez_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🔮 *فال حافظ*\n\n"
        "چند لحظه چشم‌هاتو ببند، یه آرزو یا سوال توی دلت نگه‌دار، و بعد نیت کن...\n\n"
        "وقتی آماده بودی، دکمه رو بزن:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔮 فالم رو بگیر", callback_data="get_hafez")]]
        ),
    )


async def hafez_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    ghazal = hafez_fal.get_daily_fal(update.effective_user.id)
    await query.message.reply_text(hafez_fal.format_fal(ghazal), parse_mode="Markdown")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_admin = _is_admin(update.effective_user.id)

    buttons = [
        [InlineKeyboardButton("🌌 محاسبه‌ی جدید", callback_data="new_calc")],
        [InlineKeyboardButton("🔮 فال حافظ", callback_data="open_hafez")],
        [InlineKeyboardButton("♈️ طالع‌بینی امروز", callback_data="open_zodiac")],
        [InlineKeyboardButton("📜 تاریخچه‌ی من", callback_data="show_history")],
        [InlineKeyboardButton("🔗 مقایسه با یک نفر دیگر", callback_data="open_compare")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="show_help")],
    ]
    if is_admin:
        buttons.append([
            InlineKeyboardButton("📊 آمار", callback_data="admin_stats"),
            InlineKeyboardButton("📋 خروجی CSV", callback_data="admin_export"),
        ])

    title = "📋 *منوی مدیریت*" if is_admin else "📋 *منوی اصلی*"
    target = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()
    await target.reply_text(title, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))


async def help_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await help_command_impl(update.callback_query.message, update.effective_user.id)


async def stats_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    if not _is_admin(update.effective_user.id):
        return
    await _send_stats(update.callback_query.message)


async def export_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    if not _is_admin(update.effective_user.id):
        return
    await _send_export(update.callback_query.message)


async def help_command_impl(target_message, user_id: int) -> None:
    text = (
        "🌌 *راهنمای ربات عدد کیهانی*\n\n"
        "/start — شروع محاسبه‌ی جدید\n"
        "/menu — منوی اصلی (دکمه‌ای)\n"
        "/compare — مقایسه با یک نفر دیگر\n"
        "/contacts — مخاطبین ذخیره‌شده‌ی تو\n"
        "/hafez — فال حافظ روزانه\n"
        "/zodiac — طالع‌بینی امروز\n"
        "/natal — زایچه‌ی تقریبی (خورشید+ماه+طالع)\n"
        "/history — دیدن نتایج قبلی خودت\n"
        "/cancel — لغو مکالمه‌ی جاری\n"
        "/help — همین راهنما"
    )
    if _is_admin(user_id):
        text += (
            "\n\n👑 *دستورهای مدیر:*\n"
            "/stats — آمار کلی\n"
            "/export — خروجی CSV همه‌ی کاربران\n"
            "/broadcast <متن> — ارسال پیام همگانی\n"
            "/ban <آیدی> — مسدودکردن کاربر\n"
            "/unban <آیدی> — رفع مسدودی"
        )
    await target_message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await help_command_impl(update.message, update.effective_user.id)


async def _send_history(target_message, telegram_id: int) -> None:
    try:
        rows = database.get_user_history(telegram_id)
    except Exception:
        logger.exception("خطا در خواندن تاریخچه")
        await target_message.reply_text("مشکلی در خواندن تاریخچه پیش اومد.")
        return

    if not rows:
        await target_message.reply_text("هنوز هیچ محاسبه‌ای ثبت نکردی. با /start شروع کن.")
        return

    lines = ["🕓 *آخرین محاسبات تو:*\n"]
    for r in rows:
        lines.append(
            f"• {r['first_name']} {r['family_name']} — کد: `{r['cosmic_code']}` "
            f"(سرنوشت {r['destiny_num']}, تقدیر {r['fate_num']}, ارتعاش {r['vibration_num']}, باطن {r['baten_num']})\n"
            f"  {r['created_at'][:10]}"
        )
    await target_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_history(update.message, update.effective_user.id)


async def history_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await _send_history(update.callback_query.message, update.effective_user.id)


async def _send_stats(target_message) -> None:
    try:
        s = database.get_stats()
        growth = database.get_daily_growth(7)
        tops = database.get_top_numbers()
    except Exception:
        logger.exception("خطا در خواندن آمار")
        await target_message.reply_text("مشکلی در خواندن آمار پیش اومد.")
        return

    lines = [
        "📊 *آمار ربات*\n",
        f"👥 تعداد کاربران یکتا: {s['unique_users']}",
        f"🧮 تعداد کل محاسبات: {s['total_submissions']}\n",
        "*۵ محاسبه‌ی اخیر:*",
    ]
    for r in s["latest"]:
        lines.append(f"• {r['first_name']} {r['family_name']} — {r['created_at'][:16]}")

    def _fmt_top(name, rows):
        if not rows:
            return f"{name}: داده‌ای نیست"
        parts = [f"{r['val']} ({r['c']} نفر)" for r in rows]
        return f"{name}: " + " ، ".join(parts)

    lines.append("\n📈 *پرتکرارترین اعداد:*")
    lines.append(_fmt_top("سرنوشت", tops["destiny"]))
    lines.append(_fmt_top("تقدیر", tops["fate"]))
    lines.append(_fmt_top("ارتعاش", tops["vibration"]))
    lines.append(_fmt_top("باطن", tops["baten"]))

    await target_message.reply_text("\n".join(lines), parse_mode="Markdown")

    try:
        chart_buf = analytics_chart.render_growth_chart(growth)
        await target_message.reply_photo(photo=chart_buf, caption="رشد کاربران جدید — ۷ روز اخیر")
    except Exception:
        logger.exception("خطا در ساخت نمودار رشد")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return
    await _send_stats(update.message)


async def _send_export(target_message) -> None:
    try:
        rows = database.get_all_submissions()
    except Exception:
        logger.exception("خطا در خواندن اطلاعات برای خروجی")
        await target_message.reply_text("مشکلی در ساخت خروجی پیش اومد.")
        return

    if not rows:
        await target_message.reply_text("هنوز هیچ رکوردی ثبت نشده.")
        return

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    csv_bytes = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    csv_bytes.name = "cosmic_bot_users.csv"

    await target_message.reply_document(
        document=csv_bytes,
        filename="cosmic_bot_users.csv",
        caption=f"📋 لیست کامل کاربران ({len(rows)} رکورد)",
    )


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return
    await _send_export(update.message)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return

    message_text = " ".join(context.args) if context.args else ""
    if not message_text:
        await update.message.reply_text("استفاده: /broadcast متن پیام همگانی")
        return

    try:
        user_ids = database.get_all_user_ids()
    except Exception:
        logger.exception("خطا در خواندن لیست کاربران")
        await update.message.reply_text("مشکلی در خواندن لیست کاربران پیش اومد.")
        return

    await update.message.reply_text(f"⏳ در حال ارسال پیام به {len(user_ids)} کاربر...")

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message_text)
            sent += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)  # جلوگیری از محدودیت نرخ تلگرام

    await update.message.reply_text(f"✅ ارسال شد به {sent} نفر. ناموفق: {failed}")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("استفاده: /ban آیدی_عددی_تلگرام")
        return
    target_id = int(context.args[0])
    ok = database.ban_user(target_id)
    await update.message.reply_text("✅ مسدود شد." if ok else "کاربری با این آیدی پیدا نشد.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("استفاده: /unban آیدی_عددی_تلگرام")
        return
    target_id = int(context.args[0])
    ok = database.unban_user(target_id)
    await update.message.reply_text("✅ رفع مسدودی شد." if ok else "کاربری با این آیدی پیدا نشد.")


async def daily_backup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """هر شب فایل دیتابیس رو برای ادمین می‌فرسته (چون دیسک Railway ممکنه پایدار نباشه)."""
    if not ADMIN_ID:
        return
    try:
        with open(database.DB_PATH, "rb") as f:
            await context.bot.send_document(
                chat_id=int(ADMIN_ID),
                document=f,
                filename="cosmic_bot_backup.db",
                caption="📦 بکاپ روزانه‌ی دیتابیس ربات عدد کیهانی",
            )
    except FileNotFoundError:
        logger.warning("فایل دیتابیس برای بکاپ پیدا نشد.")
    except Exception:
        logger.exception("خطا در ارسال بکاپ روزانه")


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هر خطای مدیریت‌نشده رو کامل توی logs/bot.log ثبت می‌کنه و به ادمین اطلاع می‌ده."""
    logger.error("خطای مدیریت‌نشده رخ داد", exc_info=context.error)

    if not ADMIN_ID:
        return
    try:
        err_summary = f"{type(context.error).__name__}: {context.error}"
        await context.bot.send_message(
            chat_id=int(ADMIN_ID),
            text=f"⚠️ خطای مدیریت‌نشده در ربات:\n`{err_summary}`\n\nجزئیات کامل در logs/bot.log",
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("حتی اطلاع‌رسانی خطا به ادمین هم ناموفق بود")


def main() -> None:
    if TOKEN == "PUT-YOUR-TOKEN-HERE":
        raise SystemExit(
            "توکن ربات تنظیم نشده. متغیر محیطی BOT_TOKEN رو ست کن یا مستقیم توی bot.py بذار."
        )

    database.init_db()

    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_from_button, pattern="^new_calc$"),
        ],
        states={
            FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
            FAMILY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family_name)],
            MOTHER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_mother_name),
                CallbackQueryHandler(skip_mother_name, pattern="^skip_mother$"),
            ],
            BIRTH_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_day)],
            BIRTH_MONTH: [CallbackQueryHandler(get_birth_month, pattern="^month_")],
            BIRTH_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_year)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    compare_handler = ConversationHandler(
        entry_points=[
            CommandHandler("compare", compare_start),
            CallbackQueryHandler(compare_start_from_button, pattern="^open_compare$"),
        ],
        states={
            CMP_CHOICE: [
                CallbackQueryHandler(compare_choice, pattern="^cmp_(self|new)$"),
                CallbackQueryHandler(compare_pick_contact, pattern="^cmp_contact$"),
                CallbackQueryHandler(compare_contact_selected, pattern="^contact_\\d+$"),
            ],
            CMP_P2_FIRST: [MessageHandler(filters.TEXT & ~filters.COMMAND, compare_get_first_name)],
            CMP_P2_FAMILY: [MessageHandler(filters.TEXT & ~filters.COMMAND, compare_get_family_name)],
            CMP_P2_MOTHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, compare_get_mother_name),
                CallbackQueryHandler(compare_skip_mother, pattern="^skip_mother$"),
            ],
            CMP_P2_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, compare_get_day)],
            CMP_P2_MONTH: [CallbackQueryHandler(compare_get_month, pattern="^month_")],
            CMP_P2_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, compare_get_year)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(compare_handler)

    natal_handler = ConversationHandler(
        entry_points=[CommandHandler("natal", natal_start)],
        states={
            NATAL_HOUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, natal_get_hour)],
            NATAL_MINUTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, natal_get_minute)],
            NATAL_CITY: [CallbackQueryHandler(natal_get_city, pattern="^city_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(natal_handler)

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CallbackQueryHandler(history_from_button, pattern="^show_history$"))
    application.add_handler(CallbackQueryHandler(help_from_button, pattern="^show_help$"))
    application.add_handler(CallbackQueryHandler(stats_from_button, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(export_from_button, pattern="^admin_export$"))
    application.add_handler(CallbackQueryHandler(save_contact_button, pattern="^save_contact$"))
    application.add_handler(CallbackQueryHandler(delete_contact_button, pattern="^delcontact_\\d+$"))
    application.add_handler(CommandHandler("contacts", contacts_command))
    application.add_handler(CommandHandler("hafez", hafez_command))
    application.add_handler(CommandHandler("zodiac", zodiac_command))
    application.add_handler(CallbackQueryHandler(zodiac_command, pattern="^open_zodiac$"))
    application.add_handler(CallbackQueryHandler(zodiac_month_selected, pattern="^zmonth_\\d+$"))
    application.add_handler(CallbackQueryHandler(hafez_from_button, pattern="^open_hafez$"))
    application.add_handler(CallbackQueryHandler(hafez_reveal, pattern="^get_hafez$"))
    application.add_error_handler(global_error_handler)

    async def _setup_commands(app: Application) -> None:
        await app.bot.set_my_commands(
            [BotCommand(cmd, desc) for cmd, desc in USER_COMMANDS]
        )
        if ADMIN_ID:
            try:
                await app.bot.set_my_commands(
                    [BotCommand(cmd, desc) for cmd, desc in USER_COMMANDS + ADMIN_EXTRA_COMMANDS],
                    scope=BotCommandScopeChat(chat_id=int(ADMIN_ID)),
                )
            except Exception:
                logger.exception("تنظیم منوی دستورهای ادمین ناموفق بود")

    application.post_init = _setup_commands

    if application.job_queue is not None and ADMIN_ID:
        application.job_queue.run_daily(daily_backup_job, time=dt_time(hour=23, minute=55))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
