"""
telegram_bot.py — Telegram-бот для статистики звонков (с инлайн-кнопками).

Запуск:
    export TELEGRAM_BOT_TOKEN=<токен>
    export BAZA_DATA_DIR=/opt/baza/data
    python3 telegram_bot.py
"""

import os
import sqlite3
import logging
import calendar as _calendar
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DATA_DIR  = os.environ.get("BAZA_DATA_DIR", "/opt/baza/data")
DB_PATH   = os.path.join(DATA_DIR, "baza.db")
KEY_PATH  = os.path.join(DATA_DIR, "baza.key")

_raw_ids = os.environ.get("TELEGRAM_ALLOWED_IDS", "")
ALLOWED_IDS: set[int] = {int(x) for x in _raw_ids.split(",") if x.strip().isdigit()}

# Хранит состояние ввода своего периода: chat_id -> "awaiting_from" | "awaiting_to"
_custom_state: dict[int, dict] = {}

# ─── CRYPTO ──────────────────────────────────────────────────────────────────

_fernet = None

def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = Path(KEY_PATH).read_bytes().strip()
        _fernet = Fernet(key)
    return _fernet

def _dec(text: str) -> str:
    if not text:
        return ""
    try:
        return _get_fernet().decrypt(text.encode()).decode()
    except Exception:
        return text

# ─── DB ──────────────────────────────────────────────────────────────────────

def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c

def _get_stats(date_from: str, date_to: str) -> dict:
    where = "WHERE c.is_deleted=0 AND c.call_date != '' AND c.call_date IS NOT NULL"
    params: list = []
    if date_from:
        where += " AND c.call_date >= ?"
        params.append(date_from)
    if date_to:
        where += " AND c.call_date <= ?"
        params.append(date_to + " 23:59:59")

    c = _conn()
    try:
        rows = c.execute(
            f"SELECT c.status, c.called_by, u.full_name, u.username "
            f"FROM contacts c LEFT JOIN users u ON c.called_by=u.id {where}",
            params,
        ).fetchall()
    finally:
        c.close()

    total      = len(rows)
    productive = sum(1 for r in rows if r["status"] in ("productive", "done"))
    callback   = sum(1 for r in rows if r["status"] == "callback")

    by_user: dict = defaultdict(lambda: {"calls": 0, "productive": 0, "callback": 0})
    for r in rows:
        name = r["full_name"] or r["username"] or "—"
        by_user[name]["calls"] += 1
        if r["status"] in ("productive", "done"):
            by_user[name]["productive"] += 1
        if r["status"] == "callback":
            by_user[name]["callback"] += 1

    return {
        "total":      total,
        "productive": productive,
        "callback":   callback,
        "by_user":    sorted(by_user.items(), key=lambda x: -x[1]["calls"]),
    }

# ─── FORMAT ──────────────────────────────────────────────────────────────────

def _fmt_stats(data: dict, label: str) -> str:
    lines = [
        f"📊 *Статистика — {label}*\n",
        f"📞 Всего звонков: *{data['total']}*",
        f"✅ Результативных: *{data['productive']}*",
        f"🔄 Перезвонить: *{data['callback']}*",
    ]
    if data["by_user"]:
        lines.append("\n👥 *По сотрудникам:*")
        for name, s in data["by_user"]:
            lines.append(
                f"  • {name}: {s['calls']} зв. / {s['productive']} рез. / {s['callback']} перезв."
            )
    return "\n".join(lines)

def _period(days_back: int) -> tuple[str, str]:
    today = datetime.now().date()
    return str(today - timedelta(days=days_back)), str(today)

def _parse_date(text: str):
    """Принимает DD.MM.YYYY или DD.MM.YY, возвращает date или None."""
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None

# ─── KEYBOARDS ───────────────────────────────────────────────────────────────

def _main_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Сегодня", callback_data="stats:0:Сегодня"),
            InlineKeyboardButton("📅 7 дней",  callback_data="stats:6:7 дней"),
            InlineKeyboardButton("📅 Месяц",   callback_data="stats:29:Месяц"),
        ],
        [
            InlineKeyboardButton("🗓 Свой период", callback_data="stats:custom"),
            InlineKeyboardButton("🔄 Обновить",    callback_data="stats:refresh"),
        ],
    ])

def _cancel_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="stats:cancel")],
    ])

_MONTHS_RU = ["Январь","Февраль","Март","Апрель","Май","Июнь",
               "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]

def _fmt_date(d: str) -> str:
    """YYYY-MM-DD → DD.MM.YYYY"""
    return f"{d[8:]}.{d[5:7]}.{d[:4]}"

def _build_calendar(year: int, month: int, mode: str):
    """Инлайн-клавиатура с календарём месяца. mode: 'from' | 'to'."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
    ny, nm = (year + 1, 1)  if month == 12 else (year, month + 1)
    rows = [
        [
            InlineKeyboardButton("‹", callback_data=f"cal:nav:{py}-{pm:02d}:{mode}"),
            InlineKeyboardButton(f"  {_MONTHS_RU[month-1]} {year}  ", callback_data="cal:x"),
            InlineKeyboardButton("›", callback_data=f"cal:nav:{ny}-{nm:02d}:{mode}"),
        ],
        [InlineKeyboardButton(d, callback_data="cal:x")
         for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]],
    ]
    for week in _calendar.monthcalendar(year, month):
        rows.append([
            InlineKeyboardButton(str(day), callback_data=f"cal:day:{year}-{month:02d}-{day:02d}:{mode}")
            if day else InlineKeyboardButton(" ", callback_data="cal:x")
            for day in week
        ])
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="stats:cancel")])
    return InlineKeyboardMarkup(rows)

# ─── BOT ─────────────────────────────────────────────────────────────────────

def run_bot():
    try:
        from telegram import Update
        from telegram.ext import (
            ApplicationBuilder, CommandHandler,
            CallbackQueryHandler, MessageHandler,
            ContextTypes, filters,
        )
    except ImportError:
        log.error("Установите: pip install python-telegram-bot")
        return

    if not BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN не задан. Бот не запущен.")
        return

    def _is_allowed(update: Update) -> bool:
        if not ALLOWED_IDS:
            return True
        cid = update.effective_chat.id if update.effective_chat else None
        return cid in ALLOWED_IDS

    async def _send_stats(target, date_from: str, date_to: str, label: str, edit=False):
        try:
            data = _get_stats(date_from, date_to)
            msg  = _fmt_stats(data, label)
        except Exception as e:
            msg = f"❌ Ошибка: {e}"

        if edit:
            await target.edit_message_text(msg, parse_mode="Markdown",
                                           reply_markup=_main_keyboard())
        else:
            await target.reply_text(msg, parse_mode="Markdown",
                                    reply_markup=_main_keyboard())

    async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not _is_allowed(update):
            return
        chat_id = update.effective_chat.id
        await update.message.reply_text(
            f"👋 *База контактов — статистика*\n\n"
            f"Ваш chat\\_id: `{chat_id}`\n\n"
            "Выберите период:",
            parse_mode="Markdown",
            reply_markup=_main_keyboard(),
        )

    async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not _is_allowed(update):
            return
        await update.message.reply_text(
            "Выберите период статистики:",
            reply_markup=_main_keyboard(),
        )

    async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if not _is_allowed(update):
            return

        data    = query.data
        chat_id = query.message.chat.id

        # ── Быстрые периоды ──────────────────────────────────────────────
        if data.startswith("stats:") and data.count(":") == 2:
            _, days_str, label = data.split(":", 2)
            date_from, date_to = _period(int(days_str))
            await _send_stats(query, date_from, date_to, label, edit=True)
            return

        # ── Обновить ──────────────────────────────────────────────────────
        if data == "stats:refresh":
            state = _custom_state.get(chat_id, {})
            df, dt = state.get("date_from", ""), state.get("date_to", "")
            if df and dt:
                await _send_stats(query, df, dt, f"{_fmt_date(df)} — {_fmt_date(dt)}", edit=True)
                return
            text = query.message.text or ""
            days, label = 0, "Сегодня"
            for d, lbl in [(0, "Сегодня"), (6, "7 дней"), (29, "Месяц")]:
                if lbl in text:
                    days, label = d, lbl
                    break
            date_from, date_to = _period(days)
            await _send_stats(query, date_from, date_to, label, edit=True)
            return

        # ── Свой период → показать календарь ─────────────────────────────
        if data == "stats:custom":
            today = datetime.now().date()
            _custom_state[chat_id] = {}
            await query.edit_message_text(
                "📅 *Выберите дату начала:*",
                parse_mode="Markdown",
                reply_markup=_build_calendar(today.year, today.month, "from"),
            )
            return

        # ── Отмена ────────────────────────────────────────────────────────
        if data == "stats:cancel":
            _custom_state.pop(chat_id, None)
            await query.edit_message_text(
                "Выберите период статистики:",
                reply_markup=_main_keyboard(),
            )
            return

        # ── Заглушка для заголовков календаря ────────────────────────────
        if data == "cal:x":
            return

        # ── Навигация по месяцам ──────────────────────────────────────────
        if data.startswith("cal:nav:"):
            # cal:nav:YYYY-MM:mode
            _, _, ym, mode = data.split(":", 3)
            year, month = int(ym[:4]), int(ym[5:7])
            await query.edit_message_reply_markup(
                reply_markup=_build_calendar(year, month, mode)
            )
            return

        # ── Выбор дня ─────────────────────────────────────────────────────
        if data.startswith("cal:day:"):
            # cal:day:YYYY-MM-DD:mode
            _, _, date_str, mode = data.split(":", 3)
            if mode == "from":
                _custom_state[chat_id] = {"date_from": date_str}
                year, month = int(date_str[:4]), int(date_str[5:7])
                await query.edit_message_text(
                    f"📅 Начало: *{_fmt_date(date_str)}*\n\nВыберите дату конца:",
                    parse_mode="Markdown",
                    reply_markup=_build_calendar(year, month, "to"),
                )
            elif mode == "to":
                date_from = _custom_state.get(chat_id, {}).get("date_from", "")
                if not date_from:
                    await query.edit_message_text("Ошибка. Начните заново /stats")
                    return
                if date_str < date_from:
                    await query.answer("❌ Дата конца раньше даты начала!", show_alert=True)
                    return
                _custom_state[chat_id] = {"date_from": date_from, "date_to": date_str}
                label = f"{_fmt_date(date_from)} — {_fmt_date(date_str)}"
                await _send_stats(query, date_from, date_str, label, edit=True)
            return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(on_button, pattern=r"^(stats:|cal:)"))

    log.info("Бот запущен. Allowed IDs: %s", ALLOWED_IDS or "все")
    app.run_polling()


if __name__ == "__main__":
    run_bot()
