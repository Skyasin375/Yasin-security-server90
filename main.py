"""
╔══════════════════════════════════════════════════════════════════╗
║   RBC GUILD GLORY BOT — God Level Edition                        ║
║   Guild Glory  +  AutoLike  +  Credit Coupons                    ║
║   +  RBC Reseller Coupon Purchase API (idempotent)               ║
╚══════════════════════════════════════════════════════════════════╝

pip install "python-telegram-bot>=22.5" aiohttp tzdata
"""

import asyncio
import html
import json
import logging
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiohttp
import telegram
from aiohttp import web
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)


# ═══════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN", "8832391914:AAGQ2DINCHneELqtzJqchyB-gmp4tajBZuw").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "8020955980"))
ADMIN_CHAT_ID = OWNER_ID
DB_FILE = os.getenv("DB_FILE", "guild_glory.db")

DEFAULT_OWNER_NAME = "@RexBullYasin"
DEFAULT_OWNER_USERNAME = "RexBullYasin"
DEFAULT_UPI = "skbapon353@ybl"
DEFAULT_WEBSITE = "https://example.com/redeem"
CREATE_ORDER_URL = "http://fampaygateway.site/api/create_order.php"
VERIFY_ORDER_URL = "https://fampaygateway.site/api/verify.php"

DEFAULT_GLORY_API_URL = os.getenv(
    "GUILD_GLORY_API_URL",
    "https://bkkipacektwmktplrxps.supabase.co/functions/v1/rbc-api",
)
DEFAULT_GLORY_API_KEY = os.getenv("GUILD_GLORY_API_KEY", "")

RBC_MASTER_API_URL = os.getenv(
    "RBC_MASTER_API_URL",
    "https://bkkipacektwmktplrxps.supabase.co/functions/v1/rbc-api",
)

# ── VPS PUBLIC ADDRESS ─────────────────────────────────────────────
VPS_PUBLIC_HOST = os.getenv("VPS_PUBLIC_HOST", "194.62.248.6").strip()
VPS_PUBLIC_PORT = int(os.getenv("VPS_PUBLIC_PORT", "25002"))
VPS_PUBLIC_SCHEME = os.getenv("VPS_PUBLIC_SCHEME", "http").strip() or "http"
VPS_PUBLIC_URL = f"{VPS_PUBLIC_SCHEME}://{VPS_PUBLIC_HOST}:{VPS_PUBLIC_PORT}"

API_PORT = int(os.getenv("PORT", os.getenv("API_PORT", str(VPS_PUBLIC_PORT))))
API_HOST = os.getenv("API_HOST", "0.0.0.0")

DEFAULT_GLORY_FLAT_PRICE = 80
DEFAULT_GLORY_ACCOUNTS = 4

DEFAULT_MAX_BOTS = 4
DEFAULT_MIN_ADD_BALANCE = 10
MIN_BALANCE_FOR_KEY = 0
DAILY_LIKES = 220

DEFAULT_WHOLESALE_RATIO = 0.7   # wholesale = 70% of retail by default

TYPING_DELAY = 0.55
LOADING_DELAY = 0.9

DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
DIVIDER_DOT = "•───────•───────•───────•"
DIVIDER_THIN = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"

try:
    IST = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    IST = timezone(timedelta(hours=5, minutes=30), name="IST")

AUTOLIKE_PACKAGES = {
    1: {"price": 20, "likes": DAILY_LIKES},
    7: {"price": 90, "likes": DAILY_LIKES},
    15: {"price": 100, "likes": DAILY_LIKES},
    30: {"price": 200, "likes": DAILY_LIKES},
    60: {"price": 400, "likes": DAILY_LIKES},
    120: {"price": 600, "likes": DAILY_LIKES},
}

GLORY_REGIONS = {
    "ind": "🇮🇳 India",
    "br":  "🇧🇷 Brazil",
    "sg":  "🇸🇬 Singapore",
    "id":  "🇮🇩 Indonesia",
    "th":  "🇹🇭 Thailand",
    "vn":  "🇻🇳 Vietnam",
    "pk":  "🇵🇰 Pakistan",
    "bd":  "🇧🇩 Bangladesh",
    "me":  "🇲🇽 Mexico",
    "eg":  "🇪🇬 Egypt",
}

logging.basicConfig(
    format="%(asctime)s • %(name)s • %(levelname)s • %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("guild_glory_bot")
logging.getLogger("httpx").setLevel(logging.WARNING)


# ═══════════════════════════════════════════════════════════════════
#  UNICODE FONT HELPERS
# ═══════════════════════════════════════════════════════════════════
def _build_alpha_map(base_upper, base_lower, base_digit=None,
                     upper_exc=None, lower_exc=None):
    m: dict = {}
    ue = upper_exc or {}
    le = lower_exc or {}
    for i in range(26):
        cu = chr(ord("A") + i)
        cl = chr(ord("a") + i)
        m[cu] = ue.get(cu, chr(base_upper + i))
        m[cl] = le.get(cl, chr(base_lower + i))
    if base_digit is not None:
        for i in range(10):
            m[str(i)] = chr(base_digit + i)
    return m


_BOLD_MAP = _build_alpha_map(0x1D400, 0x1D41A, 0x1D7CE)
_ITALIC_MAP = _build_alpha_map(0x1D434, 0x1D44E)
_BOLD_ITALIC_MAP = _build_alpha_map(0x1D468, 0x1D482)
_MONO_MAP = _build_alpha_map(0x1D670, 0x1D68A, 0x1D7F6)
_DOUBLE_STRUCK_MAP = _build_alpha_map(
    0x1D538, 0x1D552, 0x1D7D8,
    upper_exc={"C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ",
               "Q": "ℚ", "R": "ℝ", "Z": "ℤ"},
)
_SCRIPT_MAP = _build_alpha_map(
    0x1D49C, 0x1D4B6,
    upper_exc={"B": "ℬ", "E": "ℰ", "F": "ℱ", "H": "ℋ",
               "I": "ℐ", "L": "ℒ", "M": "ℳ", "R": "ℛ"},
    lower_exc={"e": "ℯ", "g": "ℊ", "o": "ℴ"},
)
_FRAKTUR_MAP = _build_alpha_map(
    0x1D504, 0x1D51E,
    upper_exc={"C": "ℭ", "H": "ℌ", "I": "ℑ", "R": "ℜ", "Z": "ℨ"},
)


def _apply(text, mp): return "".join(mp.get(c, c) for c in str(text))
def bold(t):          return _apply(t, _BOLD_MAP)
def italic(t):        return _apply(t, _ITALIC_MAP)
def bolditalic(t):    return _apply(t, _BOLD_ITALIC_MAP)
def mono(t):          return _apply(t, _MONO_MAP)
def double(t):        return _apply(t, _DOUBLE_STRUCK_MAP)
def script(t):        return _apply(t, _SCRIPT_MAP)
def fraktur(t):       return _apply(t, _FRAKTUR_MAP)


# ═══════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════
@contextmanager
def db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")     # Enable WAL for better concurrency
    conn.execute("PRAGMA synchronous=NORMAL")   # Reduce disk I/O blocking
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_column_if_missing(conn, table, column, definition):
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def table_exists(conn, table) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return bool(row)


def ensure_new_table_schema(conn, table, required_cols, create_sql,
                            description="new feature table"):
    if table_exists(conn, table):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not required_cols.issubset(cols):
            missing = sorted(required_cols - cols)
            logger.warning(
                "Schema mismatch on %s (%s) — missing %s. Recreating.",
                table, description, missing,
            )
            conn.execute(f"DROP TABLE {table}")
    conn.execute(create_sql)


def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            balance INTEGER DEFAULT 0, total_added INTEGER DEFAULT 0,
            spent INTEGER DEFAULT 0, referrals INTEGER DEFAULT 0,
            referrer_id INTEGER,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credits INTEGER NOT NULL, price INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER NOT NULL, code TEXT UNIQUE NOT NULL,
            is_used INTEGER DEFAULT 0, used_by INTEGER, used_date TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            amount INTEGER, utr TEXT UNIQUE, screenshot_id TEXT,
            status TEXT DEFAULT 'pending',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("""CREATE TABLE IF NOT EXISTS payment_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER NOT NULL,
            order_id TEXT UNIQUE NOT NULL, service_type TEXT NOT NULL,
            package_id TEXT, amount INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            details_json TEXT NOT NULL DEFAULT '{}', qr_url TEXT, utr TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, paid_at TEXT,
            processed_at TEXT, last_error TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS autolike_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER NOT NULL, uid TEXT NOT NULL,
            region TEXT NOT NULL, plan_days INTEGER NOT NULL,
            price INTEGER NOT NULL, start_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL, remaining_days INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            player_name TEXT DEFAULT '', player_level INTEGER DEFAULT 0,
            current_likes INTEGER DEFAULT 0,
            likes_per_day INTEGER NOT NULL DEFAULT 220,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS autolike_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            days INTEGER UNIQUE NOT NULL, price INTEGER NOT NULL,
            likes_per_day INTEGER NOT NULL DEFAULT 220,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS autolike_daily_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL, update_date TEXT NOT NULL,
            before_likes INTEGER NOT NULL, likes_given INTEGER NOT NULL,
            after_likes INTEGER NOT NULL, days_left INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(service_id, update_date))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS autolike_manual_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL, before_likes INTEGER NOT NULL,
            likes_given INTEGER NOT NULL, after_likes INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS player_profiles (
            uid TEXT PRIMARY KEY, player_name TEXT DEFAULT '',
            region TEXT DEFAULT '', player_level INTEGER DEFAULT 0,
            current_likes INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS users_reseller (
            user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0,
            own_rbc_key TEXT DEFAULT '', banned INTEGER DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, api_key TEXT UNIQUE NOT NULL,
            label TEXT DEFAULT '', status TEXT DEFAULT 'active',
            launches INTEGER DEFAULT 0, orders INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0, last_used TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS reseller_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, order_id TEXT UNIQUE NOT NULL,
            amount INTEGER NOT NULL, purpose TEXT DEFAULT 'balance',
            status TEXT DEFAULT 'pending', qr_url TEXT, upi_id TEXT,
            utr TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            paid_at TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS balance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, amount INTEGER NOT NULL,
            log_type TEXT NOT NULL, reason TEXT DEFAULT '',
            ref TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS order_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, api_key_id INTEGER,
            order_type TEXT NOT NULL, payload_json TEXT NOT NULL,
            response_json TEXT, cost INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS autolike_pricing (
            package TEXT PRIMARY KEY, price INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1)""")
        conn.execute("CREATE TABLE IF NOT EXISTS reseller_settings (key TEXT PRIMARY KEY, value TEXT)")

        ensure_new_table_schema(
            conn, "reseller_credit_packages",
            required_cols={"id", "credits", "wholesale_price", "is_active", "created_at"},
            create_sql="""CREATE TABLE IF NOT EXISTS reseller_credit_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credits INTEGER NOT NULL,
                wholesale_price INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            description="reseller credit packages",
        )

        ensure_new_table_schema(
            conn, "reseller_transactions",
            required_cols={"id", "user_id", "package_id", "credits", "amount",
                           "coupon_code", "idempotency_key", "status", "created_at"},
            create_sql="""CREATE TABLE IF NOT EXISTS reseller_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                package_id INTEGER NOT NULL,
                credits INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                coupon_code TEXT,
                idempotency_key TEXT,
                status TEXT DEFAULT 'success',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            description="reseller coupon transactions",
        )

        add_column_if_missing(conn, "payment_orders", "details_json", "TEXT NOT NULL DEFAULT '{}'")
        add_column_if_missing(conn, "payment_orders", "qr_url", "TEXT")
        add_column_if_missing(conn, "payment_orders", "last_error", "TEXT")
        add_column_if_missing(conn, "autolike_services", "player_name", "TEXT DEFAULT ''")
        add_column_if_missing(conn, "autolike_services", "player_level", "INTEGER DEFAULT 0")
        add_column_if_missing(conn, "autolike_services", "current_likes", "INTEGER DEFAULT 0")
        add_column_if_missing(conn, "autolike_services", "likes_per_day", "INTEGER NOT NULL DEFAULT 220")
        add_column_if_missing(conn, "coupons", "credits", "INTEGER DEFAULT 0")
        add_column_if_missing(conn, "coupons", "created_at", "TIMESTAMP")

        conn.execute("""UPDATE coupons SET credits = (
                SELECT p.credits FROM packages p WHERE p.id = coupons.package_id
            ) WHERE (credits IS NULL OR credits = 0) AND package_id IN (SELECT id FROM packages)""")

        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_rs_tx_idem
            ON reseller_transactions(user_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rs_tx_user ON reseller_transactions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coupons_credits ON coupons(credits, is_used)")
        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_active_uid_per_user
            ON autolike_services(telegram_user_id, uid) WHERE status = 'active'""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_order_logs_user ON order_logs(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_balance_logs_user ON balance_logs(user_id)")

        for k, v in {
            "upi_id": DEFAULT_UPI, "website_link": DEFAULT_WEBSITE,
            "maintenance": "0", "owner_name": DEFAULT_OWNER_NAME,
            "owner_username": DEFAULT_OWNER_USERNAME, "payment_api_key": "",
            "glory_api_url": DEFAULT_GLORY_API_URL,
            "glory_api_key": DEFAULT_GLORY_API_KEY,
            "glory_flat_price": str(DEFAULT_GLORY_FLAT_PRICE),
            "glory_accounts": str(DEFAULT_GLORY_ACCOUNTS),
            "redeem_website": DEFAULT_WEBSITE,
        }.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        for k, v in {
            "rbc_master_key": "", "fampay_api_key": "",
            "glory_cost": "70",
            "max_bots": str(DEFAULT_MAX_BOTS),
            "min_add_balance": str(DEFAULT_MIN_ADD_BALANCE),
            "maintenance": "0",
        }.items():
            conn.execute("INSERT OR IGNORE INTO reseller_settings (key, value) VALUES (?, ?)", (k, v))

        if conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 0:
            conn.executemany("INSERT INTO packages (credits, price) VALUES (?, ?)",
                             [(1, 100), (2, 200), (3, 300)])
        if conn.execute("SELECT COUNT(*) FROM autolike_packages").fetchone()[0] == 0:
            conn.executemany("INSERT INTO autolike_packages (days, price, likes_per_day) VALUES (?, ?, ?)",
                             [(d, p["price"], p["likes"]) for d, p in AUTOLIKE_PACKAGES.items()])
        if conn.execute("SELECT COUNT(*) FROM autolike_pricing").fetchone()[0] == 0:
            conn.executemany("INSERT INTO autolike_pricing (package, price) VALUES (?, ?)",
                             [("1day", 30), ("7days", 150), ("15days", 250), ("30days", 450)])


init_db()


# ═══════════════════════════════════════════════════════════════════
#  SAFE CALLBACK ANSWER (Prevents "Query is too old" crash)
# ═══════════════════════════════════════════════════════════════════
async def safe_answer(query, text: Optional[str] = None, show_alert: bool = False):
    try:
        await query.answer(text=text, show_alert=show_alert)
    except telegram.error.BadRequest as exc:
        if "Query is too old" in str(exc) or "query id is invalid" in str(exc):
            logger.warning("Ignored expired callback query.")
        else:
            logger.warning("BadRequest on answer: %s", exc)
    except Exception as exc:
        logger.warning("Failed to answer callback query: %s", exc)


# ═══════════════════════════════════════════════════════════════════
#  PACKAGE SYNC  (retail → reseller pool)
# ═══════════════════════════════════════════════════════════════════
def sync_retail_to_reseller():
    """
    For every retail package tier (packages.credits), ensure there is a
    matching row in reseller_credit_packages so the reseller API can sell
    it. Default wholesale = 70% of retail price. Admin can override later.
    """
    with db() as conn:
        retail = conn.execute(
            "SELECT credits, price FROM packages ORDER BY credits ASC"
        ).fetchall()
        existing = {
            int(r["credits"]) for r in conn.execute(
                "SELECT credits FROM reseller_credit_packages"
            ).fetchall()
        }
        for r in retail:
            credits = int(r["credits"])
            if credits not in existing:
                wholesale = max(1, int(int(r["price"]) * DEFAULT_WHOLESALE_RATIO))
                conn.execute(
                    """INSERT INTO reseller_credit_packages (credits, wholesale_price)
                       VALUES (?, ?)""",
                    (credits, wholesale),
                )


# ═══════════════════════════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════════════════════════
def get_setting(key, default=""):
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default


def update_setting(key, value):
    with db() as conn:
        conn.execute("""INSERT INTO settings(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value""", (key, str(value)))


def get_setting_int(key, default):
    try:
        return int(get_setting(key, str(default)))
    except (TypeError, ValueError):
        return default


def get_rs_setting(key, default=""):
    with db() as conn:
        row = conn.execute("SELECT value FROM reseller_settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default


def set_rs_setting(key, value):
    with db() as conn:
        conn.execute("""INSERT INTO reseller_settings(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value""", (key, str(value)))


def get_rs_int(key, default):
    try:
        return int(get_rs_setting(key, str(default)))
    except (TypeError, ValueError):
        return default


def is_owner(uid): return uid == OWNER_ID
def now_ist(): return datetime.now(IST)
def iso_now(): return now_ist().isoformat(timespec="seconds")
def esc(v): return html.escape(str(v if v is not None else ""))
def owner_name(): return get_setting("owner_name", DEFAULT_OWNER_NAME)
def owner_username(): return get_setting("owner_username", DEFAULT_OWNER_USERNAME).lstrip("@")
def owner_contact_url(): return f"https://t.me/{quote(owner_username())}"
def redeem_url(): return get_setting("redeem_website", get_setting("website_link", DEFAULT_WEBSITE))


def ensure_user(user):
    with db() as conn:
        conn.execute("""INSERT INTO users(user_id, username, first_name) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username, first_name = excluded.first_name""",
                     (user.id, user.username, user.first_name or ""))


# ═══════════════════════════════════════════════════════════════════
#  RESELLER HELPERS
# ═══════════════════════════════════════════════════════════════════
def ensure_reseller_user(user_id):
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO users_reseller(user_id, balance) VALUES (?, 0)", (user_id,))


def get_reseller_balance(user_id):
    with db() as conn:
        row = conn.execute("SELECT balance FROM users_reseller WHERE user_id = ?", (user_id,)).fetchone()
        return int(row["balance"]) if row else 0


def reseller_is_banned(user_id):
    with db() as conn:
        row = conn.execute("SELECT banned FROM users_reseller WHERE user_id = ?", (user_id,)).fetchone()
        return bool(row["banned"]) if row else False


def get_user_own_rbc_key(user_id):
    with db() as conn:
        row = conn.execute("SELECT own_rbc_key FROM users_reseller WHERE user_id = ?", (user_id,)).fetchone()
        return str(row["own_rbc_key"] or "") if row else ""


def set_user_own_rbc_key(user_id, key):
    ensure_reseller_user(user_id)
    with db() as conn:
        conn.execute("UPDATE users_reseller SET own_rbc_key = ? WHERE user_id = ?", (key, user_id))


def generate_api_key(): return "rbc_live_" + secrets.token_hex(16)


def count_active_keys(user_id):
    with db() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM api_keys WHERE user_id = ? AND status = 'active'",
                           (user_id,)).fetchone()
        return int(row["n"]) if row else 0


def list_user_keys(user_id):
    with db() as conn:
        return conn.execute("SELECT * FROM api_keys WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()


def lookup_api_key(api_key):
    with db() as conn:
        return conn.execute("SELECT * FROM api_keys WHERE api_key = ?", (api_key,)).fetchone()


def add_balance_log(conn, user_id, amount, log_type, reason="", ref=""):
    conn.execute("""INSERT INTO balance_logs(user_id, amount, log_type, reason, ref)
        VALUES (?, ?, ?, ?, ?)""", (user_id, amount, log_type, reason, ref))


def credit_reseller_balance(user_id, amount, reason="", ref=""):
    ensure_reseller_user(user_id)
    with db() as conn:
        conn.execute("UPDATE users_reseller SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        add_balance_log(conn, user_id, amount, "credit", reason, ref)
        row = conn.execute("SELECT balance FROM users_reseller WHERE user_id = ?", (user_id,)).fetchone()
        return int(row["balance"]) if row else 0


def set_reseller_balance(user_id, new_balance, reason=""):
    ensure_reseller_user(user_id)
    new_balance = max(0, int(new_balance))
    with db() as conn:
        cur = conn.execute("SELECT balance FROM users_reseller WHERE user_id = ?", (user_id,)).fetchone()
        cur_bal = int(cur["balance"]) if cur else 0
        diff = new_balance - cur_bal
        conn.execute("UPDATE users_reseller SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        if diff != 0:
            add_balance_log(conn, user_id, abs(diff),
                            "credit" if diff > 0 else "debit", reason or "admin set")
    return new_balance


def try_debit_balance(user_id, amount, reason="", ref=""):
    ensure_reseller_user(user_id)
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT balance, banned FROM users_reseller WHERE user_id = ?",
                           (user_id,)).fetchone()
        if not row:
            conn.rollback(); return False, "User not found"
        if row["banned"]:
            conn.rollback(); return False, "User is banned"
        bal = int(row["balance"])
        if bal < amount:
            conn.rollback(); return False, "Insufficient balance"
        conn.execute("UPDATE users_reseller SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        add_balance_log(conn, user_id, amount, "debit", reason, ref)
        nrow = conn.execute("SELECT balance FROM users_reseller WHERE user_id = ?", (user_id,)).fetchone()
        return True, int(nrow["balance"])


# ═══════════════════════════════════════════════════════════════════
#  COUPON STOCK HELPERS
# ═══════════════════════════════════════════════════════════════════
def count_unused_coupons_for_credits(credits):
    with db() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM coupons WHERE credits = ? AND is_used = 0",
                           (credits,)).fetchone()
        return int(row["c"]) if row else 0


def conn_count_coupons(package_id):
    with db() as conn:
        pkg = conn.execute("SELECT credits FROM packages WHERE id = ?", (package_id,)).fetchone()
        if not pkg:
            return 0
        return count_unused_coupons_for_credits(int(pkg["credits"]))


def list_reseller_credit_packages(active_only=True):
    with db() as conn:
        q = "SELECT * FROM reseller_credit_packages"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY credits ASC"
        return conn.execute(q).fetchall()


def get_reseller_credit_package(package_id):
    with db() as conn:
        return conn.execute("SELECT * FROM reseller_credit_packages WHERE id = ?",
                            (package_id,)).fetchone()


# ═══════════════════════════════════════════════════════════════════
#  RESELLER COUPON PURCHASE
# ═══════════════════════════════════════════════════════════════════
async def purchase_coupon_for_reseller(user_id, package_id, idempotency_key,
                                        api_key_id=None):
    ensure_reseller_user(user_id)
    idem = (idempotency_key or "").strip() or None

    def _dup_response(row):
        return {
            "success": True,
            "duplicate_request": True,
            "transaction_id": int(row["id"]),
            "coupon_code": row["coupon_code"],
            "credits": int(row["credits"]),
            "amount": int(row["amount"]),
            "redeem_url": redeem_url(),
            "balance_left": get_reseller_balance(user_id),
        }

    if idem:
        with db() as conn:
            existing = conn.execute("""SELECT * FROM reseller_transactions
                WHERE user_id = ? AND idempotency_key = ?""",
                                    (user_id, idem)).fetchone()
            if existing:
                return _dup_response(existing)

    pkg = get_reseller_credit_package(package_id)
    if not pkg or not pkg["is_active"]:
        return {"success": False, "code": "PACKAGE_NOT_FOUND",
                "error": "Package not found or inactive."}

    credits = int(pkg["credits"])
    cost = int(pkg["wholesale_price"])

    try:
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")

            if idem:
                existing = conn.execute("""SELECT * FROM reseller_transactions
                    WHERE user_id = ? AND idempotency_key = ?""",
                                        (user_id, idem)).fetchone()
                if existing:
                    conn.rollback()
                    return _dup_response(existing)

            user_row = conn.execute("SELECT balance, banned FROM users_reseller WHERE user_id = ?",
                                    (user_id,)).fetchone()
            if not user_row:
                conn.rollback()
                return {"success": False, "code": "USER_NOT_FOUND",
                        "error": "Reseller account not found."}
            if user_row["banned"]:
                conn.rollback()
                return {"success": False, "code": "USER_BANNED",
                        "error": "Reseller account is banned."}

            bal = int(user_row["balance"])
            if bal < cost:
                conn.rollback()
                return {"success": False, "code": "INSUFFICIENT_RESELLER_BALANCE",
                        "error": f"Insufficient balance. Required ₹{cost}, available ₹{bal}.",
                        "required": cost, "available": bal}

            coupon = conn.execute("""SELECT id, code FROM coupons
                WHERE credits = ? AND is_used = 0
                ORDER BY id ASC LIMIT 1""", (credits,)).fetchone()
            if not coupon:
                conn.rollback()
                return {"success": False, "code": "OUT_OF_STOCK",
                        "error": f"No unused coupon available for {credits} credits."}

            conn.execute("UPDATE users_reseller SET balance = balance - ? WHERE user_id = ?",
                         (cost, user_id))
            add_balance_log(conn, user_id, cost, "debit",
                            reason=f"Coupon purchase ({credits} credits)",
                            ref=idem or "telegram")

            used_at = iso_now()
            updated = conn.execute("""UPDATE coupons
                SET is_used = 1, used_by = ?, used_date = ?
                WHERE id = ? AND is_used = 0""",
                                 (user_id, used_at, coupon["id"])).rowcount
            if not updated:
                conn.rollback()
                return {"success": False, "code": "RACE",
                        "error": "Coupon was taken by another request. Please retry."}

            tx_cursor = conn.execute("""INSERT INTO reseller_transactions
                (user_id, package_id, credits, amount, coupon_code,
                 idempotency_key, status)
                VALUES (?, ?, ?, ?, ?, ?, 'success')""",
                                   (user_id, package_id, credits, cost,
                                    coupon["code"], idem))
            tx_id = tx_cursor.lastrowid

            conn.execute("""INSERT INTO order_logs
                (user_id, api_key_id, order_type, payload_json,
                 response_json, cost, status)
                VALUES (?, ?, 'coupon_purchase', ?, ?, ?, 'success')""",
                         (user_id, api_key_id,
                          json.dumps({"package_id": package_id, "idempotency_key": idem}),
                          json.dumps({"coupon_code": coupon["code"],
                                      "transaction_id": tx_id, "credits": credits}),
                          cost))

            new_bal = conn.execute("SELECT balance FROM users_reseller WHERE user_id = ?",
                                   (user_id,)).fetchone()["balance"]

            if api_key_id:
                conn.execute("""UPDATE api_keys
                    SET orders = orders + 1, total_spent = total_spent + ?, last_used = ?
                    WHERE id = ?""", (cost, iso_now(), api_key_id))

        return {
            "success": True,
            "duplicate_request": False,
            "transaction_id": int(tx_id),
            "coupon_code": coupon["code"],
            "credits": credits,
            "amount": cost,
            "redeem_url": redeem_url(),
            "balance_left": int(new_bal),
        }
    except sqlite3.IntegrityError as exc:
        if idem:
            with db() as conn:
                existing = conn.execute("""SELECT * FROM reseller_transactions
                    WHERE user_id = ? AND idempotency_key = ?""",
                                    (user_id, idem)).fetchone()
                if existing:
                    return _dup_response(existing)
        logger.exception("Coupon purchase integrity error")
        return {"success": False, "code": "INTEGRITY", "error": f"Integrity error: {exc}"}
    except Exception as exc:
        logger.exception("Coupon purchase failed")
        return {"success": False, "code": "ERROR", "error": str(exc)}


# ═══════════════════════════════════════════════════════════════════
#  PUBLIC URL
# ═══════════════════════════════════════════════════════════════════
_cached_public_url = None


def detect_public_url():
    """
    Priority order:
      1. PUBLIC_BASE_URL env override
      2. Known hosting providers (Railway/Render/Heroku/Fly/Koyeb)
      3. Hard-coded VPS public address (VPS_PUBLIC_URL)
    """
    global _cached_public_url
    if _cached_public_url:
        return _cached_public_url

    candidates = [
        ("PUBLIC_BASE_URL", lambda v: v.rstrip("/")),
        ("RAILWAY_PUBLIC_DOMAIN", lambda v: f"https://{v}".rstrip("/")),
        ("RAILWAY_STATIC_URL", lambda v: v.rstrip("/")),
        ("HEROKU_APP_NAME", lambda v: f"https://{v}.herokuapp.com"),
        ("RENDER_EXTERNAL_URL", lambda v: v.rstrip("/")),
        ("FLY_APP_NAME", lambda v: f"https://{v}.fly.dev"),
        ("KOYEB_PUBLIC_DOMAIN", lambda v: f"https://{v}".rstrip("/")),
    ]
    for env, fn in candidates:
        val = os.getenv(env, "").strip()
        if val:
            _cached_public_url = fn(val)
            return _cached_public_url

    # Fallback: use the VPS public URL configured at the top of this file.
    _cached_public_url = VPS_PUBLIC_URL
    return _cached_public_url


# ═══════════════════════════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════════════════════════
BUTTON_STYLES = {"primary", "success", "danger"}
PREMIUM_BRAND = "GUILD GLORY OFFICIAL SHOP"


def premium_header(title, icon="💎", description=""):
    """Shared luxury header used by every customer, reseller and admin view."""
    body = (
        f"♛  <b>{DIVIDER}</b>  ♛\n"
        f"{icon}  <b>{bold(str(title).upper())}</b>  {icon}\n"
        f"♛  <b>{DIVIDER}</b>  ♛"
    )
    if description:
        body += f"\n<i>{esc(description)}</i>"
    return body


def premium_section(title, icon="✦"):
    return f"\n<b>{DIVIDER}</b>\n{icon}  <b>{bold(title.upper())}</b>  {icon}\n<b>{DIVIDER}</b>"


def premium_back_label(label):
    """Keep navigation buttons visually consistent without changing callbacks."""
    label = str(label or "").replace("🔙", "").strip()
    if not label or label.lower() == "back":
        return "↩️  " + bold("BACK")
    if label.lower() == "cancel":
        return "✖️  " + bold("CANCEL")
    return "↩️  " + label


def _mk_rbtn(text, callback_data=None, *, url=None, style="primary"):
    """Create a colored inline button with an older-PTB compatibility fallback."""
    if callback_data is None and url is None:
        raise ValueError("A button needs callback_data or url.")
    if callback_data is not None and url is not None:
        raise ValueError("A button cannot have both callback_data and url.")
    normalized_style = style if style in BUTTON_STYLES else "primary"
    kwargs = {"callback_data": callback_data} if callback_data is not None else {"url": url}
    try:
        return InlineKeyboardButton(text, style=normalized_style, **kwargs)
    except TypeError:
        return InlineKeyboardButton(text, **kwargs)


def back_button(callback="main_menu", label="🔙  Back"):
    return InlineKeyboardMarkup([[
        _mk_rbtn(premium_back_label(label), callback, style="primary")
    ]])


def main_menu_text(user):
    return (
        f"♛  <b>{DIVIDER}</b>  ♛\n"
        f"★  <b>{bold(PREMIUM_BRAND)}</b>  ★\n"
        f"♛  <b>{DIVIDER}</b>  ♛\n\n"
        f"➤  <b>Yo, 『{bold(user.first_name)}』 ! Welcome Back!</b>  ◢\n\n"
        f"<b>{DIVIDER_THIN}</b>\n"
        f"━━  <b>{bold('WHY CHOOSE US?')}</b>  ━━\n"
        f"⚡  <b>Instant Auto Delivery</b>\n"
        f"🛡️  <b>Secure UPI Payments</b>\n"
        f"➤  <b>Genuine Guild Glory Services</b>\n"
        f"▬  <b>Real 24/7 Support</b>\n"
        f"★  <b>Unbeatable Prices</b>\n"
        f"<b>{DIVIDER_THIN}</b>\n\n"
        f"🛒  <b>{bold('SELECT AN OPTION BELOW')}</b>  👇"
    )


def main_menu_keyboard(user_id):
    rows = [
        [_mk_rbtn("🛒  " + bold("SHOP NOW"), "shop_now", style="success")],
        [
            _mk_rbtn("📦  " + bold("MY ORDERS"), "my_services", style="primary"),
            _mk_rbtn("👤  " + bold("PROFILE"), "my_stats", style="primary"),
        ],
        [
            _mk_rbtn("📊  " + bold("HOW TO BUY"), "how_to_buy", style="primary"),
            _mk_rbtn("🆘  " + bold("SUPPORT"), url=owner_contact_url(), style="primary"),
        ],
        [_mk_rbtn("🔑  " + bold("RESELLER SUITE"), "rs_menu", style="success")],
    ]
    if is_owner(user_id):
        rows.append([_mk_rbtn("👑  " + bold("CONTROL CENTER"), "admin_menu", style="danger")])
    return InlineKeyboardMarkup(rows)


async def send_main_menu(update, context):
    user = update.effective_user
    ensure_user(user)
    context.user_data.clear()
    try:
        await context.bot.send_chat_action(chat_id=user.id, action="typing")
        loading = await update.effective_message.reply_text(
            f"✨ <b>{italic('Opening')} {bold('RBC Guild Glory Shop')}…</b>", parse_mode="HTML")
        await asyncio.sleep(LOADING_DELAY)
        await loading.edit_text(main_menu_text(user),
                                reply_markup=main_menu_keyboard(user.id),
                                parse_mode="HTML")
    except Exception:
        await update.effective_message.reply_text(main_menu_text(user),
                                                  reply_markup=main_menu_keyboard(user.id),
                                                  parse_mode="HTML")


async def start(update, context):
    user = update.effective_user
    if get_setting("maintenance") == "1" and not is_owner(user.id):
        return await update.message.reply_text(
            "🛠️ <b>Bot is currently under maintenance.</b>\nPlease check back later.",
            parse_mode="HTML")
    ensure_user(user)
    await send_main_menu(update, context)


async def edit_or_send(query, text, reply_markup=None, photo=None):
    if photo:
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.get_bot().send_photo(chat_id=query.from_user.id, photo=photo,
                                                caption=text, reply_markup=reply_markup,
                                                parse_mode="HTML")
    try:
        return await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.get_bot().send_message(chat_id=query.from_user.id, text=text,
                                                  reply_markup=reply_markup, parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  PAYMENT GATEWAY
# ═══════════════════════════════════════════════════════════════════
def response_data(payload):
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("data")
    return nested if isinstance(nested, dict) else payload


def api_success(payload):
    data = response_data(payload)
    if isinstance(payload, dict) and payload.get("success") is True:
        return True
    if isinstance(data, dict) and data.get("success") is True:
        return True
    st = str(payload.get("status", "") if isinstance(payload, dict) else "").lower()
    ns = str(data.get("status", "")).lower()
    return st in {"success", "successful", "paid", "true", "1"} or \
           ns in {"success", "successful", "paid", "true", "1"}


async def get_json(session, url, params):
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=25),
                           headers={"Accept": "application/json"}) as r:
        raw = await r.text()
        if r.status >= 400:
            raise RuntimeError(f"Payment API HTTP {r.status}")
        try:
            v = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Payment API returned invalid JSON") from exc
        if not isinstance(v, dict):
            raise RuntimeError("Payment API returned an unexpected response")
        return v


async def create_payment_order(amount, api_key):
    if not api_key:
        raise RuntimeError("Payment API key is not configured by the owner.")
    async with aiohttp.ClientSession() as s:
        payload = await get_json(s, CREATE_ORDER_URL, {"amount": amount, "api_key": api_key})
    if not api_success(payload):
        raise RuntimeError(str(payload.get("message", "Payment order creation failed")))
    data = response_data(payload)
    oid = data.get("order_id") or data.get("orderId") or payload.get("order_id")
    qr = data.get("qr_url") or data.get("qr") or payload.get("qr_url")
    if not oid or not qr:
        raise RuntimeError("Payment API did not return order_id and qr_url.")
    return {"order_id": str(oid), "qr_url": str(qr),
            "upi_id": data.get("upi_id") or payload.get("upi_id"),
            "amount": int(data.get("amount") or payload.get("amount") or amount),
            "expires_at": data.get("expires_at") or payload.get("expires_at")}


async def verify_payment_order(order_id, api_key):
    if not api_key:
        raise RuntimeError("Payment API key is not configured by the owner.")
    async with aiohttp.ClientSession() as s:
        payload = await get_json(s, VERIFY_ORDER_URL, {"order_id": order_id, "api_key": api_key})
    data = response_data(payload)
    roid = data.get("order_id") or payload.get("order_id")
    amount = data.get("amount") or payload.get("amount")
    utr = data.get("utr") or data.get("reference") or payload.get("utr")
    return {"success": api_success(payload),
            "order_id": str(roid) if roid is not None else "",
            "amount": int(amount) if amount is not None else None,
            "utr": str(utr) if utr else None,
            "payment_time": data.get("payment_time") or payload.get("payment_time"),
            "status": str(data.get("status") or payload.get("status") or "").lower(),
            "message": str(data.get("message") or payload.get("message") or "").strip()}


async def create_and_store_payment(user_id, service_type, package_id, amount, details, api_key):
    payment = await create_payment_order(amount, api_key)
    with db() as conn:
        conn.execute("""INSERT INTO payment_orders
            (telegram_user_id, order_id, service_type, package_id, amount, details_json, qr_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (user_id, payment["order_id"], service_type, package_id,
                      amount, json.dumps(details), payment["qr_url"]))
    return payment


def payment_text(payment):
    extra = ""
    if payment.get("upi_id"):
        extra += f"\n📲  <b>UPI ID</b>   •  <code>{esc(payment['upi_id'])}</code>"
    if payment.get("expires_at"):
        extra += f"\n⏳  <b>Expires</b>  •  <code>{esc(payment['expires_at'])}</code>"
    return (
        f"{premium_header('Payment required', '💳', 'Complete your order securely using the QR above.')}\n\n"
        f"<blockquote>📲  Scan the QR above and pay the exact amount.</blockquote>\n"
        f"💰  <b>Amount</b>    •  <b><code>{mono('₹' + f'{payment["amount"]:.2f}')}</code></b>\n"
        f"🧾  <b>Order ID</b>  •  <code>{esc(payment['order_id'])}</code>{extra}\n\n"
        f"{premium_section('Payment flow', '📋')}\n"
        f"1️⃣   Scan the QR code\n"
        f"2️⃣   Complete the payment\n"
        f"3️⃣   Tap <b>Verify Payment</b> below\n\n"
        f"🛡️  <i>Verification is automatic and instant.</i>"
    )


def payment_keyboard(order_id):
    return InlineKeyboardMarkup([
        [_mk_rbtn("✅  " + bold("VERIFY PAYMENT"), f"verify_{order_id}", style="success")],
        [_mk_rbtn("✖️  Cancel Payment", f"cancel_payment_{order_id}", style="danger")],
    ])


async def show_payment(query, payment):
    await edit_or_send(query, payment_text(payment),
                       payment_keyboard(payment["order_id"]), photo=payment["qr_url"])


# ═══════════════════════════════════════════════════════════════════
#  GUILD GLORY  (simplified: Region → Guild ID → ₹80 flat, 4 bots)
# ═══════════════════════════════════════════════════════════════════
def glory_flat_price():
    return get_setting_int("glory_flat_price", DEFAULT_GLORY_FLAT_PRICE)


def glory_accounts_count():
    return get_setting_int("glory_accounts", DEFAULT_GLORY_ACCOUNTS)


async def show_glory_menu(query):
    price = glory_flat_price()
    bots = glory_accounts_count()
    text = (f"{premium_header('Guild Glory launch', '💎', 'Launch Guild Glory credits directly to your Free Fire guild.')}\n\n"
            f"💰  <b>Flat Price</b>   •  <b><code>{mono('₹' + str(price))}</code></b>\n"
            f"🤖  <b>Bots</b>         •  <code>{mono(str(bots) + ' auto-selected')}</code>\n\n"
            f"<b>{DIVIDER}</b>\n"
            f"🌍  <b>{bold('SELECT YOUR REGION')}</b>\n"
            f"<i>Choose the service region to continue.</i>")
    kb = []
    row = []
    for code, label in GLORY_REGIONS.items():
        row.append(_mk_rbtn(label, f"glory_region_{code}", style="primary"))
        if len(row) == 2:
            kb.append(row); row = []
    if row:
        kb.append(row)
    kb.append([_mk_rbtn("↩️  " + bold("BACK TO SHOP"), "shop_now", style="primary")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def glory_select_region(query, context, region):
    if region not in GLORY_REGIONS:
        return await safe_answer(query, "Unknown region.", show_alert=True)
    context.user_data.clear()
    context.user_data["state"] = "WAITING_GLORY_GUILD_ID"
    context.user_data["glory_region"] = region
    price = glory_flat_price()
    bots = glory_accounts_count()
    await query.edit_message_text(
        f"{premium_header('Guild Glory launch', '💎', 'One last detail before we prepare your order.')}\n"
        f"🌍  <b>Region</b>      •  {esc(GLORY_REGIONS[region])}\n"
        f"💰  <b>Flat Price</b>  •  <b><code>{mono('₹' + str(price))}</code></b>\n"
        f"🤖  <b>Bots</b>        •  <code>{mono(str(bots) + ' auto')}</code>\n\n"
        f"🛡️  <b>SEND YOUR GUILD ID</b>\n<i>Numbers only · 6–15 digits</i>",
        reply_markup=back_button("glory_menu", "🔙  Cancel"), parse_mode="HTML")


async def glory_show_confirm(update_or_query, context, guild_id):
    region = context.user_data.get("glory_region")
    if not region:
        return
    price = glory_flat_price()
    bots = glory_accounts_count()
    context.user_data["glory_guild_id"] = guild_id
    context.user_data["glory_accounts"] = bots
    context.user_data["glory_total"] = price
    text = (f"{premium_header('Confirm Guild Glory order', '💎', 'Review the details before generating your secure payment QR.')}\n"
            f"🛡  <b>Guild ID</b>  •  <code>{esc(guild_id)}</code>\n"
            f"🌍  <b>Region</b>    •  {esc(GLORY_REGIONS.get(region, region))}\n"
            f"🤖  <b>Bots</b>      •  <code>{mono(str(bots) + ' auto-selected')}</code>\n"
            f"💰  <b>Total</b>     •  <b><code>{mono('₹' + str(price))}</code></b>\n\n"
            f"<blockquote>Confirm to generate your payment QR.</blockquote>")
    kb = InlineKeyboardMarkup([
        [_mk_rbtn("✅  " + bold("Confirm & Pay"), "glory_confirm", style="success")],
        [_mk_rbtn("✖️  Cancel", "glory_menu", style="danger")],
    ])
    if hasattr(update_or_query, "message") and hasattr(update_or_query.message, "reply_text"):
        await update_or_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update_or_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def create_glory_payment(query, context):
    guild_id = context.user_data.get("glory_guild_id")
    region = context.user_data.get("glory_region")
    accounts = context.user_data.get("glory_accounts")
    total = context.user_data.get("glory_total")
    if not all([guild_id, region, accounts, total]):
        return await safe_answer(query, "Session expired, please restart.", show_alert=True)
    api_key = get_setting("payment_api_key")
    try:
        payment = await create_and_store_payment(
            query.from_user.id, "guild_glory_launch", "launch",
            int(total),
            {"guild_id": str(guild_id), "region": str(region), "accounts": int(accounts)},
            api_key)
    except Exception as exc:
        logger.exception("Guild Glory payment creation failed")
        return await safe_answer(query, str(exc)[:180], show_alert=True)
    context.user_data.clear()
    await show_payment(query, payment)


def glory_success_text(details, amount, resp):
    return (f"{premium_header('Guild Glory launched', '🎉', 'Your order was accepted by the fulfilment API.')}\n\n"
            f"✅  <i>Your Guild Glory order was accepted by our API.</i>\n\n"
            f"🛡  <b>Guild ID</b>  •  <code>{esc(details.get('guild_id'))}</code>\n"
            f"🌍  <b>Region</b>    •  {esc(GLORY_REGIONS.get(details.get('region'), details.get('region')))}\n"
            f"🤖  <b>Bots</b>      •  <code>{mono(details.get('accounts'))}</code>\n"
            f"💰  <b>Paid</b>      •  <b><code>{mono('₹' + str(amount))}</code></b>\n"
            f"🕒  <b>Time</b>      •  <code>{mono(now_ist().strftime('%d-%m-%Y %I:%M %p'))} IST</code>\n"
            f"{premium_section('Order completed', '🛡️')}\n"
            f"👑  <b>{italic('Powered by')}</b>  {esc(owner_name())}")


# ═══════════════════════════════════════════════════════════════════
#  CREDIT COUPON SHOP (customer side)
# ═══════════════════════════════════════════════════════════════════
async def show_coupon_menu(query):
    with db() as conn:
        packages = conn.execute("SELECT id, credits, price FROM packages ORDER BY credits ASC").fetchall()
    text = (f"{premium_header('Credit coupon shop', '🎟', 'Buy redeemable credits for your official website.')}\n\n")
    kb = []
    for p in packages:
        stock = count_unused_coupons_for_credits(int(p["credits"]))
        st = f"✅ {stock} in stock" if stock else "❌ Out of Stock"
        text += (f"💎  <b>{p['credits']} Credit Coupon</b>  •  "
                 f"<b><code>{mono('₹' + str(p['price']))}</code></b>  •  <i>{st}</i>\n")
        if stock:
            kb.append([_mk_rbtn(
                f"🛒  {p['credits']} Credit  •  ₹{p['price']}",
                f"coupon_pkg_{p['id']}", style="success")])
    kb.append([_mk_rbtn("↩️  " + bold("BACK TO SHOP"), "shop_now", style="primary")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def begin_coupon_payment(query, context, package_id):
    with db() as conn:
        package = conn.execute("SELECT id, credits, price FROM packages WHERE id = ?",
                               (package_id,)).fetchone()
    if not package:
        return await safe_answer(query, "Package not found.", show_alert=True)
    if count_unused_coupons_for_credits(int(package["credits"])) == 0:
        return await safe_answer(query, "This package is out of stock.", show_alert=True)
    context.user_data["pending_coupon_package"] = package_id
    text = (f"{premium_header('Credit coupon', '🎟', 'Your redeem code will be delivered after payment.')}\n\n"
            f"💎  <b>Credits</b>  •  <code>{mono(package['credits'])}</code>\n"
            f"💰  <b>Price</b>    •  <b><code>{mono('₹' + str(package['price']))}</code></b>\n\n"
            f"<blockquote>You'll receive a redeem code after payment.</blockquote>\n\n"
            f"🛡️  <i>Confirm your purchase?</i>")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[
        _mk_rbtn("✅  Confirm", f"coupon_confirm_{package_id}", style="success"),
        _mk_rbtn("✖️  Cancel", "coupon_menu", style="danger"),
    ]]), parse_mode="HTML")


async def create_coupon_payment(query, context, package_id):
    with db() as conn:
        package = conn.execute("SELECT id, credits, price FROM packages WHERE id = ?",
                               (package_id,)).fetchone()
    if not package:
        return await safe_answer(query, "Package not found.", show_alert=True)
    api_key = get_setting("payment_api_key")
    try:
        payment = await create_and_store_payment(
            query.from_user.id, "credit_coupon", str(package_id),
            int(package["price"]),
            {"credits": int(package["credits"])}, api_key)
    except Exception as exc:
        logger.exception("Coupon payment creation failed")
        return await safe_answer(query, str(exc)[:180], show_alert=True)
    context.user_data.pop("pending_coupon_package", None)
    await show_payment(query, payment)


def coupon_success_text(credits, coupon):
    return (f"{premium_header('Coupon delivered', '🎉', 'Your private redeem code is ready.')}\n\n"
            f"<i>Your credit coupon is ready.</i>  ✅\n\n"
            f"💎  <b>Credits</b>  •  <code>{mono(credits)}</code>\n"
            f"🎟  <b>Redeem Code</b>\n"
            f"<code>{esc(coupon)}</code>\n\n"
            f"{premium_section('Redeem instructions', '🌐')}\n"
            f"<blockquote>Use this code on our official website to claim your credits.\n"
            f"🔒 Keep it private — do not share with anyone.</blockquote>\n\n"
            f"{premium_section('Thank you', '❤️‍🔥')}\n"
            f"✨  <i>Thank you for choosing us!</i>\n"
            f"👑  <b>Powered By</b>  {esc(owner_name())}\n"
            f"<i>Keep your code private.</i>")


# ═══════════════════════════════════════════════════════════════════
#  AUTOLIKE
# ═══════════════════════════════════════════════════════════════════
async def show_autolike_menu(query):
    await query.edit_message_text(
        f"{premium_header('Free Fire autolike', '❤️‍🔥', 'Daily likes with automatic service tracking.')}\n\n"
        f"<i>Choose an experience below.</i>",
        reply_markup=InlineKeyboardMarkup([
            [_mk_rbtn("🛒  " + bold("BUY AUTOLIKES"), "autolike_buy", style="success")],
            [_mk_rbtn("📋  " + bold("MY AUTOLIKES"), "my_autolikes", style="primary")],
            [_mk_rbtn("↩️  " + bold("BACK TO SHOP"), "shop_now", style="primary")],
        ]), parse_mode="HTML")


async def show_autolike_packages(query):
    with db() as conn:
        plans = conn.execute("""SELECT days, price, likes_per_day FROM autolike_packages
            WHERE is_active = 1 ORDER BY days ASC""").fetchall()
    text = (f"{premium_header('Autolike packages', '❤️‍🔥', 'Select the validity that fits your player.')}\n\n")
    if not plans:
        text += "<i>No plans available right now.</i>"
    else:
        for p in plans:
            suffix = "s" if p["days"] != 1 else ""
            text += (f"➡️  <b><code>{mono('₹' + str(p['price']))}</code></b>  •  "
                     f"<b>{p['days']} Day{suffix}</b>  "
                     f"<i>({p['likes_per_day']} likes/day)</i>\n")
    kb = [[_mk_rbtn(f"🛒  {p['days']} Day{'s' if p['days'] != 1 else ''}  •  ₹{p['price']}",
                    f"autolike_pkg_{p['days']}", style="success")] for p in plans]
    kb.append([_mk_rbtn("↩️  " + bold("BACK TO AUTOLIKE"), "autolike_menu", style="primary")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def show_autolike_confirmation(query, days):
    with db() as conn:
        plan = conn.execute("""SELECT days, price, likes_per_day FROM autolike_packages
            WHERE days = ? AND is_active = 1""", (days,)).fetchone()
    if not plan:
        return await safe_answer(query, "This package is no longer available.", show_alert=True)
    text = (f"{premium_header('Confirm autolikes', '❤️‍🔥', 'Review your selected plan before activation.')}\n\n"
            f"📅  <b>Plan</b>   •  <code>{mono(str(days) + ' Day' + ('s' if days != 1 else ''))}</code>\n"
            f"💰  <b>Price</b>  •  <b><code>{mono('₹' + f'{plan["price"]:.2f}')}</code></b>\n"
            f"👍  <b>Likes</b>  •  <code>{mono(str(plan['likes_per_day']) + '+ / day')}</code>\n\n"
            f"<i>Payment required to activate.</i>\n\n"
            f"Confirm purchase?")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[
        _mk_rbtn("✅  Confirm", f"autolike_confirm_{days}", style="success"),
        _mk_rbtn("✖️  Cancel", "autolike_buy", style="danger"),
    ]]), parse_mode="HTML")


def active_service_for_uid(user_id, uid):
    with db() as conn:
        return conn.execute("""SELECT * FROM autolike_services
            WHERE telegram_user_id = ? AND uid = ? AND status = 'active'""",
                            (user_id, uid)).fetchone()


def get_autolike_plan(days, active_only=True):
    with db() as conn:
        q = ("SELECT id, days, price, likes_per_day, is_active "
             "FROM autolike_packages WHERE days = ?")
        if active_only:
            q += " AND is_active = 1"
        return conn.execute(q, (days,)).fetchone()


def service_status(service):
    today = now_ist().date()
    expiry = datetime.fromisoformat(service["expiry_date"]).date()
    left = max(0, (expiry - today).days)
    status = "Active" if service["status"] == "active" and left > 0 else "Expired"
    return status, left


async def start_autolike_uid_collection(query, context, days):
    context.user_data.clear()
    context.user_data.update({"state": "WAITING_AUTOLIKE_UID", "autolike_days": days})
    await query.edit_message_text(
        f"{premium_header('Player verification', '🆔', 'We use your UID only to activate and track the selected service.')}\n\n"
        f"<b>SEND YOUR FREE FIRE UID</b>\n"
        f"<i>Type /cancel to abort.</i>\n\n"
        f"🔒  <i>Your order details stay linked to your account.</i>",
        reply_markup=back_button("autolike_buy", "🔙  Cancel"), parse_mode="HTML")


async def show_my_autolikes(query):
    with db() as conn:
        services = conn.execute("""SELECT * FROM autolike_services
            WHERE telegram_user_id = ? ORDER BY created_at DESC""", (query.from_user.id,)).fetchall()
    if not services:
        return await query.edit_message_text(
            f"{premium_header('Your autolikes', '📋', 'Track every active and completed player service.')}\n\n"
            f"<i>No services found.</i>",
            reply_markup=back_button("autolike_menu"), parse_mode="HTML")
    blocks = [premium_header("Your autolikes", "📋", "Track every active and completed player service.")]
    for s in services:
        st, left = service_status(s)
        icon = "🟢" if st == "Active" else "🔴"
        blocks.append(f"<b>{DIVIDER}</b>\n"
                      f"🆔  <b>UID</b>       •  <code>{esc(s['uid'])}</code>\n"
                      f"🌍  <b>Region</b>    •  {esc(s['region'])}\n"
                      f"📅  <b>Plan</b>      •  <code>{mono(str(s['plan_days']) + ' Days')}</code>\n"
                      f"⏳  <b>Days Left</b> •  <code>{mono(left)}</code>\n"
                      f"📊  <b>Likes</b>     •  <code>{mono(s['current_likes'])}</code>\n"
                      f"📆  <b>Start</b>     •  <code>{esc(s['start_date'])}</code>\n"
                      f"📆  <b>Expiry</b>    •  <code>{esc(s['expiry_date'])}</code>\n"
                      f"{icon}  <b>Status</b>    •  <b>{st}</b>")
    await query.edit_message_text("\n".join(blocks),
                                  reply_markup=back_button("autolike_menu"),
                                  parse_mode="HTML")


async def show_my_services(query):
    with db() as conn:
        payments = conn.execute("""SELECT order_id, service_type, amount, status, created_at
            FROM payment_orders WHERE telegram_user_id = ? ORDER BY id DESC LIMIT 10""",
                                (query.from_user.id,)).fetchall()
        services = conn.execute("""SELECT uid, region, plan_days, status, expiry_date
            FROM autolike_services WHERE telegram_user_id = ? ORDER BY id DESC LIMIT 10""",
                                (query.from_user.id,)).fetchall()
    lines = [premium_header("My orders & services", "📦", "A private overview of your purchases and activations.")]
    if services:
        lines.append(premium_section("Autolike services", "🔥"))
        for s in services:
            st, left = service_status(s)
            lines.append(f"• <code>{esc(s['uid'])}</code> • {esc(s['region'])} • "
                         f"{s['plan_days']}d • {st} ({left} left)")
    if payments:
        lines.append(premium_section("Recent payments", "💳"))
        for p in payments:
            lines.append(f"• <code>{esc(p['order_id'])}</code> • ₹{p['amount']} • {esc(p['status'])}")
    if len(lines) == 1:
        lines.append("\n<i>No orders or services found.</i>")
    await query.edit_message_text("\n".join(lines),
                                  reply_markup=back_button("main_menu"),
                                  parse_mode="HTML")


async def show_my_stats(query):
    with db() as conn:
        user = conn.execute("SELECT total_added, spent, join_date FROM users WHERE user_id = ?",
                            (query.from_user.id,)).fetchone()
        payments = conn.execute("""SELECT COUNT(*) AS c FROM payment_orders
            WHERE telegram_user_id = ? AND status = 'processed'""",
                                (query.from_user.id,)).fetchone()["c"]
        services = conn.execute("SELECT COUNT(*) AS c FROM autolike_services WHERE telegram_user_id = ?",
                                (query.from_user.id,)).fetchone()["c"]
        coupons = conn.execute("SELECT COUNT(*) AS c FROM coupons WHERE used_by = ?",
                               (query.from_user.id,)).fetchone()["c"]
    joined = str(user["join_date"])[:10] if user else "Unknown"
    await query.edit_message_text(
        f"{premium_header('Your statistics', '📊', 'A concise view of your store activity.')}\n"
        f"💳  Completed Payments  •  <code>{mono(payments)}</code>\n"
        f"🎟  Credit Coupons      •  <code>{mono(coupons)}</code>\n"
        f"🔥  Autolike Services   •  <code>{mono(services)}</code>\n"
        f"📅  Joined              •  <code>{esc(joined)}</code>\n"
        f"<b>{DIVIDER}</b>",
        reply_markup=back_button("main_menu"), parse_mode="HTML")


async def show_shop_menu(query):
    price = glory_flat_price()
    await query.edit_message_text(
        f"{premium_header('Premium service menu', '🛒', 'Choose a verified service and continue in a few taps.')}\n\n"
        f"💎  <b>Guild Glory Launch</b>\n"
        f"       <code>{mono('₹' + str(price) + ' flat')}</code>  •  Auto-selected bots\n\n"
        f"❤️  <b>Free Fire Autolikes</b>\n"
        f"       <i>Daily likes with auto verification</i>\n\n"
        f"🎟  <b>Credit Coupons</b>\n"
        f"       <i>Redeemable coupon codes</i>",
        reply_markup=InlineKeyboardMarkup([
            [_mk_rbtn("💎  " + bold("GUILD GLORY LAUNCH"), "glory_menu", style="success")],
            [_mk_rbtn("❤️‍🔥  " + bold("FREE FIRE AUTOLIKES"), "autolike_menu", style="success")],
            [_mk_rbtn("🎟  " + bold("CREDIT COUPONS"), "coupon_menu", style="success")],
            [_mk_rbtn("↩️  " + bold("BACK TO HOME"), "main_menu", style="primary")],
        ]), parse_mode="HTML")


async def show_how_to_buy(query):
    await query.edit_message_text(
        f"{premium_header('How to buy', '📖', 'A simple, secure flow from selection to fulfilment.')}\n\n"
        f"1️⃣   Tap <b>SHOP NOW</b>\n"
        f"2️⃣   Choose a service\n"
        f"3️⃣   Select your package / region\n"
        f"4️⃣   Complete the payment\n"
        f"5️⃣   Tap <b>Verify Payment</b>\n\n"
        f"\n<b>{DIVIDER}</b>\n"
        f"✅  Automatic verification\n"
        f"✅  Instant delivery\n"
        f"✅  Saved to your account\n\n"
        f"<i>Need help? Contact</i>  {esc(owner_name())}",
        reply_markup=InlineKeyboardMarkup([
            [_mk_rbtn("🛒  " + bold("SHOP NOW"), "shop_now", style="success")],
            [_mk_rbtn("🆘  " + bold("CONTACT SUPPORT"), url=owner_contact_url(), style="primary")],
            [_mk_rbtn("↩️  " + bold("BACK TO HOME"), "main_menu", style="primary")],
        ]), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  PAYMENT VERIFY / FULFIL
# ═══════════════════════════════════════════════════════════════════
async def _execute_glory_api(guild_id, region, accounts):
    api_url = get_setting("glory_api_url", DEFAULT_GLORY_API_URL)
    api_key = get_setting("glory_api_key", DEFAULT_GLORY_API_KEY)
    if not api_key:
        raise RuntimeError("Guild Glory API key is not configured. Contact owner.")
    payload = {"guild_id": str(guild_id), "region": str(region),
               "type": "glory", "accounts": int(accounts)}
    async with aiohttp.ClientSession() as s:
        async with s.post(api_url,
                          headers={"X-RBC-Key": api_key, "Content-Type": "application/json"},
                          json=payload,
                          timeout=aiohttp.ClientTimeout(total=30)) as r:
            raw = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"Glory API HTTP {r.status}: {raw[:150]}")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Glory API returned invalid JSON") from exc
            if not isinstance(data, dict):
                raise RuntimeError("Glory API returned unexpected data")
            return data


async def process_verified_payment(order_row, verification):
    if verification["order_id"] != str(order_row["order_id"]):
        return "error", "Payment API order ID did not match this order."
    if verification["amount"] is not None and int(verification["amount"]) != int(order_row["amount"]):
        return "error", "Payment API amount did not match this order."
    if not verification["success"]:
        return "not_verified", verification

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT * FROM payment_orders WHERE id = ?",
                               (order_row["id"],)).fetchone()
        if not current:
            return "error", "Payment order no longer exists."
        if current["status"] == "processed":
            return "already_processed", current
        if current["status"] == "cancelled":
            return "error", "This payment was cancelled."

        details = json.loads(current["details_json"] or "{}")
        paid_at = iso_now()
        conn.execute("""UPDATE payment_orders SET status = 'paid', utr = ?, paid_at = ?,
            last_error = NULL WHERE id = ? AND status IN ('pending', 'paid')""",
                     (verification.get("utr"), paid_at, current["id"]))

        if current["service_type"] == "guild_glory_launch":
            guild_id = details.get("guild_id")
            region = details.get("region")
            accounts = int(details.get("accounts", 1))
            try:
                api_resp = await _execute_glory_api(guild_id, region, accounts)
            except Exception as exc:
                conn.execute("UPDATE payment_orders SET last_error = ? WHERE id = ?",
                             (str(exc)[:200], current["id"]))
                return "glory_api_error", {"error": str(exc),
                                            "details": details,
                                            "order_id": current["order_id"]}
            if not bool(api_resp.get("success", True)):
                err = str(api_resp.get("error") or "Glory API rejected the order")
                conn.execute("UPDATE payment_orders SET last_error = ? WHERE id = ?",
                             (err[:200], current["id"]))
                return "glory_api_error", {"error": err,
                                            "details": details,
                                            "order_id": current["order_id"]}
            conn.execute("""UPDATE payment_orders SET status = 'processed', processed_at = ?
                WHERE id = ? AND status = 'paid'""", (paid_at, current["id"]))
            return "glory_success", {"details": details,
                                     "amount": current["amount"],
                                     "response": api_resp,
                                     "user_id": current["telegram_user_id"]}

        if current["service_type"] in ("credit_coupon", "guild_glory"):
            package_id = int(current["package_id"])
            package = conn.execute("SELECT credits FROM packages WHERE id = ?",
                                   (package_id,)).fetchone()
            if not package:
                conn.execute("UPDATE payment_orders SET last_error = ? WHERE id = ?",
                             ("Package missing.", current["id"]))
                return "paid_waiting_stock", current
            credits = int(package["credits"])
            coupon = conn.execute("""SELECT id, code FROM coupons
                WHERE credits = ? AND is_used = 0
                ORDER BY id ASC LIMIT 1""", (credits,)).fetchone()
            if not coupon:
                conn.execute("UPDATE payment_orders SET last_error = ? WHERE id = ?",
                             ("No coupon stock available.", current["id"]))
                return "paid_waiting_stock", current
            conn.execute("""UPDATE coupons SET is_used = 1, used_by = ?, used_date = ?
                WHERE id = ? AND is_used = 0""",
                         (current["telegram_user_id"], paid_at, coupon["id"]))
            conn.execute("""UPDATE payment_orders SET status = 'processed', processed_at = ?
                WHERE id = ? AND status = 'paid'""", (paid_at, current["id"]))
            return "coupon_success", {"credits": credits,
                                      "coupon": coupon["code"],
                                      "user_id": current["telegram_user_id"]}

        if current["service_type"] == "autolike":
            days = int(details["days"])
            uid = str(details["uid"]).strip()
            region = str(details["region"]).strip()
            dup = conn.execute("""SELECT id FROM autolike_services WHERE telegram_user_id = ?
                AND uid = ? AND status = 'active'""",
                               (current["telegram_user_id"], uid)).fetchone()
            if dup:
                conn.execute("UPDATE payment_orders SET last_error = ? WHERE id = ?",
                             ("Active service exists for this UID.", current["id"]))
                return "duplicate_service", current
            start = now_ist().date()
            expiry = start + timedelta(days=days)
            conn.execute("""INSERT INTO autolike_services
                (telegram_user_id, uid, region, plan_days, price,
                 start_date, expiry_date, remaining_days, status, likes_per_day)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
                         (current["telegram_user_id"], uid, region, days, current["amount"],
                          start.isoformat(), expiry.isoformat(), days,
                          int(details.get("likes_per_day") or DAILY_LIKES)))
            conn.execute("""UPDATE payment_orders SET status = 'processed', processed_at = ?
                WHERE id = ? AND status = 'paid'""", (paid_at, current["id"]))
            service = conn.execute("""SELECT * FROM autolike_services WHERE telegram_user_id = ?
                AND uid = ? AND status = 'active' ORDER BY id DESC LIMIT 1""",
                                   (current["telegram_user_id"], uid)).fetchone()
            return "autolike_success", service

        return "error", "Unknown payment service type."


async def verify_and_fulfil(query, order_id):
    with db() as conn:
        order = conn.execute("""SELECT * FROM payment_orders WHERE order_id = ?
            AND telegram_user_id = ?""", (order_id, query.from_user.id)).fetchone()
    if not order:
        return await safe_answer(query, "Order not found.", show_alert=True)
    if order["status"] == "processed":
        return await edit_or_send(query, "✅ This order has already been processed.",
                                  reply_markup=back_button("main_menu"))
    api_key = get_setting("payment_api_key")
    try:
        verification = await verify_payment_order(order_id, api_key)
        result, value = await process_verified_payment(order, verification)
    except Exception:
        logger.exception("Payment verification failed for %s", order_id)
        return await edit_or_send(
            query,
            "⚠️  <b>Verification temporarily unavailable.</b>\n"
            "<i>Please try again shortly.</i>",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("🔄  Recheck Payment", f"verify_{order_id}", style="success")],
                [_mk_rbtn("📞  Contact Admin", url=owner_contact_url(), style="primary")],
                [_mk_rbtn("🔙  Back", "main_menu", style="danger")],
            ]))

    if result == "not_verified":
        api_msg = value.get("message") if isinstance(value, dict) else ""
        st = value.get("status") if isinstance(value, dict) else ""
        reason = api_msg or ("Payment is still pending at the payment gateway."
                             if st == "pending" else "Your payment has not been verified yet.")
        return await edit_or_send(
            query,
             f"{premium_header('Payment pending', '⏳', 'The gateway has not confirmed this payment yet.')}\n"
            f"<i>{esc(reason)}</i>\n\n"
            f"🧾  <b>Order ID</b>  •  <code>{esc(order_id)}</code>\n\n"
            f"<i>Please wait a few seconds, then recheck.</i>",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("🔄  Recheck Payment", f"verify_{order_id}", style="success")],
                [_mk_rbtn("📞  Contact Admin", url=owner_contact_url(), style="primary")],
                [_mk_rbtn("🔙  Back", "main_menu", style="danger")],
            ]))
    if result == "already_processed":
        return await edit_or_send(query, "✅ This order has already been processed.",
                                  reply_markup=back_button("main_menu"))
    if result == "paid_waiting_stock":
        return await edit_or_send(
            query,
            "✅  <b>Payment verified</b>\n"
            "<i>But this package is temporarily out of stock.</i>\n\n"
            "Please contact the owner.",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("📞  Contact Owner", url=owner_contact_url(), style="primary")],
            ]))
    if result == "duplicate_service":
        return await edit_or_send(
            query,
            "✅  <b>Payment verified</b>\n"
            "<i>But this UID already has an active service.</i>\n\n"
            "Please contact the owner.",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("📞  Contact Owner", url=owner_contact_url(), style="primary")],
            ]))
    if result == "glory_api_error":
        err = value.get("error", "Unknown error")
        return await edit_or_send(
            query,
             f"{premium_header('Payment verified', '⚠️', 'The gateway accepted the payment, but fulfilment needs attention.')}\n"
            f"But the Guild Glory API rejected the order:\n\n"
            f"<code>{esc(err)}</code>\n\n"
            f"🧾  <b>Order ID</b>  •  <code>{esc(order_id)}</code>\n\n"
            f"<i>Please contact support with your Order ID.</i>",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("🔄  Retry Launch", f"verify_{order_id}", style="success")],
                [_mk_rbtn("📞  Contact Admin", url=owner_contact_url(), style="primary")],
                [_mk_rbtn("🔙  Back", "main_menu", style="danger")],
            ]))
    if result == "error":
        return await edit_or_send(query, f"❌ {esc(value)}", reply_markup=back_button("main_menu"))
    if result == "glory_success":
        return await edit_or_send(
            query,
            glory_success_text(value["details"], value["amount"], value["response"]),
            reply_markup=back_button("main_menu"))
    if result == "coupon_success":
        return await edit_or_send(
            query, coupon_success_text(value["credits"], value["coupon"]),
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("🌐  Redeem Credits", url=redeem_url(), style="success")],
                [_mk_rbtn("🔙  Back to Menu", "main_menu", style="primary")],
            ]))
    if result == "autolike_success":
        s = value
        return await edit_or_send(
            query,
             f"{premium_header('Autolike enabled', '🌟', 'Your player service is now active.')}\n"
            f"🆔  <b>UID</b>       •  <code>{esc(s['uid'])}</code>\n"
            f"🌍  <b>Region</b>    •  {esc(s['region'])}\n"
            f"📅  <b>Validity</b>  •  <code>{mono(str(s['plan_days']) + ' Days')}</code>\n"
            f"⏰  <b>Time</b>      •  <code>{mono(now_ist().strftime('%d-%m-%Y %I:%M %p'))} IST</code>\n"
            f"👤  <b>Added By</b>  •  {esc(owner_name())}\n"
            f"<b>{DIVIDER}</b>",
            reply_markup=back_button("main_menu"))


# ═══════════════════════════════════════════════════════════════════
#  RBC RESELLER — USER PANEL
# ═══════════════════════════════════════════════════════════════════
def reseller_panel_text(user_id):
    bal = get_reseller_balance(user_id)
    active = count_active_keys(user_id)
    maxb = get_rs_int("max_bots", DEFAULT_MAX_BOTS)
    glory = get_rs_int("glory_cost", 70)
    own = get_user_own_rbc_key(user_id)
    own_disp = "✅ Saved" if own else "❌ Not Set"

    with db() as conn:
        held = conn.execute("""SELECT COUNT(*) AS c FROM coupons
            WHERE used_by = ? AND is_used = 1""", (user_id,)).fetchone()["c"]
        available_pkgs = conn.execute(
            "SELECT COUNT(*) AS c FROM reseller_credit_packages WHERE is_active = 1"
        ).fetchone()["c"]

    return (f"{premium_header('RBC reseller suite', '🔑', 'Wholesale tools for creators, agencies and automation teams.')}\n"
            f"💰  <b>Balance</b>          •  <b><code>{mono('₹' + str(bal))}</code></b>\n"
            f"🎟  <b>Coupons Bought</b>   •  <code>{mono(held)}</code>\n"
            f"📦  <b>Credit Packages</b>  •  <code>{mono(available_pkgs)}</code>\n"
            f"🤖  <b>Active Bots</b>      •  <code>{mono(str(active) + ' / ' + str(maxb))}</code>\n"
            f"💎  <b>Glory Cost</b>       •  <code>{mono('₹' + str(glory))}</code>\n"
            f"🔐  <b>Own RBC Key</b>      •  {own_disp}\n"
            f"{premium_section('Workspace actions', '⚡')}\n"
            f"<i>Choose a workspace action below.</i>")


def reseller_panel_keyboard():
    return InlineKeyboardMarkup([
        [_mk_rbtn("🛒  " + bold("BUY COUPONS"), "rs_buy_coupons", style="success")],
        [_mk_rbtn("🎟  " + bold("MY COUPONS"), "rs_my_coupons", style="primary"),
         _mk_rbtn("📊  " + bold("TRANSACTIONS"), "rs_my_tx", style="primary")],
        [_mk_rbtn("💰  " + bold("ADD BALANCE"), "rs_add_bal", style="success")],
        [_mk_rbtn("🔑  " + bold("GENERATE API KEY"), "rs_gen_key", style="success")],
        [_mk_rbtn("🔐  " + bold("SAVE API KEY"), "rs_add_key", style="primary")],
        [_mk_rbtn("💎  " + bold("GUILD GLORY"), "rs_glory", style="primary"),
         _mk_rbtn("❤️‍🔥  " + bold("AUTOLIKE"), "rs_autolike", style="primary")],
        [_mk_rbtn("📖  " + bold("API DOCUMENTATION"), "rs_docs", style="primary")],
        [_mk_rbtn("🤖  " + bold("MY BOTS"), "rs_my_bots", style="primary")],
        [_mk_rbtn("↩️  " + bold("BACK TO HOME"), "main_menu", style="primary")],
    ])


async def show_reseller_panel(query):
    ensure_reseller_user(query.from_user.id)
    if reseller_is_banned(query.from_user.id):
        return await edit_or_send(query, "🚫  You have been banned from the reseller panel.",
                                  reply_markup=back_button("main_menu"))
    await edit_or_send(query, reseller_panel_text(query.from_user.id), reseller_panel_keyboard())


async def reseller_show_buy_coupons(query):
    pkgs = list_reseller_credit_packages(active_only=True)
    if not pkgs:
        return await edit_or_send(
            query,
            f"{premium_header('Buy coupons', '🛒', 'Wholesale coupon inventory for your customers.')}\n\n"
            f"<i>No credit packages are configured yet.</i>",
            reply_markup=back_button("rs_menu"))

    bal = get_reseller_balance(query.from_user.id)
    lines = [premium_header("Buy coupons", "🛒", "Wholesale coupon inventory for your customers."),
             f"💰  <b>Your Balance</b>  •  <b><code>{mono('₹' + str(bal))}</code></b>",
             premium_section("Available inventory", "📦"),
             "<i>Select a package to purchase 1 coupon:</i>\n"]
    kb = []
    for p in pkgs:
        stock = count_unused_coupons_for_credits(int(p["credits"]))
        status_icon = "✅" if stock else "❌"
        lines.append(f"{status_icon}  <b>{p['credits']} Credits</b>  •  "
                     f"<b><code>{mono('₹' + str(p['wholesale_price']))}</code></b>  •  "
                     f"<i>Stock: <code>{mono(stock)}</code></i>")
        if stock:
            kb.append([_mk_rbtn(
                f"🛒  {p['credits']} Credits  •  ₹{p['wholesale_price']}",
                f"rs_buy_pkg_{p['id']}", style="success")])
    kb.append([_mk_rbtn("↩️  " + bold("BACK TO RESELLER"), "rs_menu", style="primary")])
    await edit_or_send(query, "\n".join(lines), InlineKeyboardMarkup(kb))


async def reseller_confirm_buy_coupon(query, context, package_id):
    pkg = get_reseller_credit_package(package_id)
    if not pkg or not pkg["is_active"]:
        return await safe_answer(query, "Package not available.", show_alert=True)
    stock = count_unused_coupons_for_credits(int(pkg["credits"]))
    if stock == 0:
        return await safe_answer(query, "Out of stock for this package.", show_alert=True)
    bal = get_reseller_balance(query.from_user.id)
    if bal < int(pkg["wholesale_price"]):
        return await safe_answer(
            query,
            f"Insufficient balance. Required ₹{pkg['wholesale_price']}, available ₹{bal}.",
            show_alert=True)

    text = (f"{premium_header('Confirm coupon purchase', '🛒', 'One coupon will be charged from your reseller balance.')}\n"
            f"💎  <b>Credits</b>          •  <code>{mono(pkg['credits'])}</code>\n"
            f"💰  <b>Cost</b>             •  <b><code>{mono('₹' + str(pkg['wholesale_price']))}</code></b>\n"
            f"📦  <b>Stock</b>            •  <code>{mono(str(stock) + ' available')}</code>\n"
            f"💼  <b>Your Balance</b>     •  <code>{mono('₹' + str(bal))}</code>\n"
            f"<b>{DIVIDER}</b>\n"
            f"<blockquote>You will receive <b>1 coupon</b> for the selected credits.\n"
            f"Amount will be deducted from your reseller balance.</blockquote>")
    await edit_or_send(query, text, InlineKeyboardMarkup([
        [_mk_rbtn("✅  " + bold("CONFIRM PURCHASE"), f"rs_buy_do_{package_id}", style="success")],
        [_mk_rbtn("✖️  Cancel", "rs_buy_coupons", style="danger")],
    ]))


async def reseller_execute_buy_coupon(query, context, package_id):
    idem = "tg_" + secrets.token_hex(10)
    result = await purchase_coupon_for_reseller(
        query.from_user.id, int(package_id), idempotency_key=idem, api_key_id=None)

    if not result["success"]:
        code = result.get("code")
        err = result.get("error", "Purchase failed.")
        if code == "OUT_OF_STOCK":
            return await safe_answer(query, "❌ Out of stock.", show_alert=True)
        if code == "INSUFFICIENT_RESELLER_BALANCE":
            return await safe_answer(query, f"❌ {err}", show_alert=True)
        return await safe_answer(query, f"❌ {err}"[:180], show_alert=True)

    body = (f"{premium_header('Coupon purchased', '🎉', 'Your wholesale coupon is ready to deliver.')}\n\n"
            f"💎  <b>Credits</b>       •  <code>{mono(result['credits'])}</code>\n"
            f"💰  <b>Paid</b>          •  <b><code>{mono('₹' + str(result['amount']))}</code></b>\n"
            f"🧾  <b>Transaction</b>   •  <code>#{mono(result['transaction_id'])}</code>\n"
            f"💼  <b>New Balance</b>   •  <b><code>{mono('₹' + str(result['balance_left']))}</code></b>\n\n"
            f"🎟  <b>Coupon Code</b>\n"
            f"<code>{esc(result['coupon_code'])}</code>\n\n"
            f"{premium_section('Redemption', '🌐')}\n"
            f"🌐  <b>Redeem at:</b>\n{esc(result['redeem_url'])}\n\n"
            f"<i>Give this coupon to your customer for redemption.</i>")
    await edit_or_send(query, body, InlineKeyboardMarkup([
        [_mk_rbtn("🌐  " + bold("REDEEM WEBSITE"), url=result["redeem_url"], style="success")],
        [_mk_rbtn("🛒  " + bold("BUY MORE"), "rs_buy_coupons", style="success")],
        [_mk_rbtn("↩️  " + bold("BACK TO RESELLER"), "rs_menu", style="primary")],
    ]))


async def reseller_show_my_coupons(query):
    with db() as conn:
        rows = conn.execute("""SELECT code, credits, used_date FROM coupons
            WHERE used_by = ? AND is_used = 1
            ORDER BY used_date DESC LIMIT 50""", (query.from_user.id,)).fetchall()
    if not rows:
        return await edit_or_send(
            query,
            f"{premium_header('My coupons', '🎟', 'Your purchased coupon inventory.')}\n\n"
            f"<i>You have not purchased any coupons yet.</i>",
            reply_markup=back_button("rs_menu"))
    lines = [premium_header("My coupons", "🎟", "Your purchased coupon inventory.")]
    for r in rows:
        lines.append(f"💎 <code>{mono(r['credits'])}</code> Credits  •  "
                     f"<code>{esc(r['code'])}</code>")
    lines.append(f"<b>{DIVIDER}</b>")
    lines.append(f"🌐 Redeem: {esc(redeem_url())}")
    await edit_or_send(query, "\n".join(lines),
                       InlineKeyboardMarkup([
                            [_mk_rbtn("🌐  " + bold("REDEEM WEBSITE"), url=redeem_url(), style="success")],
                            [_mk_rbtn("↩️  " + bold("BACK TO RESELLER"), "rs_menu", style="primary")],
                       ]))


async def reseller_show_my_transactions(query):
    with db() as conn:
        rows = conn.execute("""SELECT id, credits, amount, coupon_code, status, created_at
            FROM reseller_transactions WHERE user_id = ?
            ORDER BY id DESC LIMIT 30""", (query.from_user.id,)).fetchall()
    if not rows:
        return await edit_or_send(
            query,
            f"{premium_header('My transactions', '📊', 'Your reseller purchase history.')}\n\n"
            f"<i>No transactions yet.</i>",
            reply_markup=back_button("rs_menu"))
    lines = [premium_header("My transactions", "📊", "Your reseller purchase history.")]
    for r in rows:
        icon = "✅" if r["status"] == "success" else "⏳"
        lines.append(
            f"{icon}  <b>#{mono(r['id'])}</b>  •  "
            f"<code>{mono(str(r['credits']) + ' cr')}</code>  •  "
            f"<b><code>{mono('₹' + str(r['amount']))}</code></b>\n"
            f"     🎟 <code>{esc(r['coupon_code'])}</code>\n"
            f"     🕒 <i>{esc(str(r['created_at'])[:19])}</i>")
    await edit_or_send(query, "\n".join(lines), reply_markup=back_button("rs_menu"))


async def reseller_add_balance_start(query, context):
    min_bal = get_rs_int("min_add_balance", DEFAULT_MIN_ADD_BALANCE)
    context.user_data.clear()
    context.user_data["state"] = "RS_WAITING_ADD_AMOUNT"
    await edit_or_send(
        query,
        f"{premium_header('Add balance', '💰', 'Top up your reseller wallet to unlock wholesale purchasing.')}\n"
        f"<blockquote>Enter the amount in ₹ you want to add.\n\n"
        f"<i>Minimum: <b>₹{min_bal}</b></i></blockquote>",
        reply_markup=back_button("rs_menu", "🔙  Cancel"))


async def create_reseller_payment(user_id, amount):
    fampay_key = get_rs_setting("fampay_api_key", "")
    if not fampay_key:
        raise RuntimeError("Fampay API key is not configured by the owner.")
    async with aiohttp.ClientSession() as s:
        payload = await get_json(s, CREATE_ORDER_URL, {"amount": amount, "api_key": fampay_key})
    if not api_success(payload):
        raise RuntimeError(str(payload.get("message", "Payment order creation failed")))
    data = response_data(payload)
    oid = data.get("order_id") or data.get("orderId") or payload.get("order_id")
    qr = data.get("qr_url") or data.get("qr") or payload.get("qr_url")
    upi = data.get("upi_id") or payload.get("upi_id")
    if not oid or not qr:
        raise RuntimeError("Payment API did not return order_id and qr_url.")
    with db() as conn:
        conn.execute("""INSERT INTO reseller_payments(user_id, order_id, amount, qr_url, upi_id)
            VALUES (?, ?, ?, ?, ?)""",
                     (user_id, str(oid), int(amount), str(qr), str(upi or "")))
    return {"order_id": str(oid), "qr_url": str(qr), "upi_id": str(upi or ""),
            "amount": int(amount),
            "expires_at": data.get("expires_at") or payload.get("expires_at")}


def reseller_payment_text(payment):
    extra = ""
    if payment.get("upi_id"):
        extra += f"\n📲  <b>UPI</b>      •  <code>{esc(payment['upi_id'])}</code>"
    if payment.get("expires_at"):
        extra += f"\n⏳  <b>Expires</b>  •  <code>{esc(payment['expires_at'])}</code>"
    return (f"{premium_header('Complete payment', '💳', 'Add balance securely to your reseller wallet.')}\n"
            f"<blockquote>Scan the QR above and pay the exact amount.</blockquote>\n\n"
            f"💰  <b>Amount</b>    •  <b><code>{mono('₹' + str(payment['amount']))}</code></b>\n"
            f"🧾  <b>Order ID</b>  •  <code>{esc(payment['order_id'])}</code>{extra}\n\n"
            f"<i>After paying, tap the Verify button below.</i>")


def reseller_payment_keyboard(order_id):
    return InlineKeyboardMarkup([
        [_mk_rbtn("✅  " + bold("VERIFY PAYMENT"), f"rs_verify_{order_id}", style="success")],
        [_mk_rbtn("✖️  " + bold("CANCEL PAYMENT"), f"rs_cancel_{order_id}", style="danger")],
    ])


async def reseller_show_payment(query, payment):
    await edit_or_send(query, reseller_payment_text(payment),
                       reseller_payment_keyboard(payment["order_id"]),
                       photo=payment["qr_url"])


async def reseller_verify_payment(query, order_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM reseller_payments WHERE order_id = ? AND user_id = ?",
                           (order_id, query.from_user.id)).fetchone()
    if not row:
        return await safe_answer(query, "Payment not found.", show_alert=True)
    if row["status"] == "success":
        bal = get_reseller_balance(query.from_user.id)
        return await edit_or_send(
            query, f"✅  <b>Payment already credited.</b>\n\n"
                   f"💰  Balance  •  <b><code>{mono('₹' + str(bal))}</code></b>",
            reply_markup=back_button("rs_menu", "🔙  Back to Panel"))
    fampay_key = get_rs_setting("fampay_api_key", "")
    if not fampay_key:
        return await safe_answer(query, "Payment gateway not configured.", show_alert=True)
    try:
        async with aiohttp.ClientSession() as s:
            payload = await get_json(s, VERIFY_ORDER_URL,
                                     {"order_id": order_id, "api_key": fampay_key})
    except Exception:
        logger.exception("Reseller verify failed for %s", order_id)
        return await edit_or_send(
            query,
            "⚠️  <b>Could not verify right now.</b>\n<i>Please retry in a few seconds.</i>",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("🔄  Retry", f"rs_verify_{order_id}", style="success")],
                [_mk_rbtn("🔙  Back", "rs_menu", style="primary")],
            ]))
    data = response_data(payload)
    verified_amount = int(data.get("amount") or payload.get("amount") or 0)
    if not api_success(payload) or verified_amount != int(row["amount"]):
        return await edit_or_send(
            query,
            "⏳  <b>Payment not received yet.</b>\n<i>Please wait and retry.</i>",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("🔄  Retry", f"rs_verify_{order_id}", style="success")],
                [_mk_rbtn("🔙  Back", "rs_menu", style="primary")],
            ]))
    utr = str(data.get("utr") or payload.get("utr") or "")
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT * FROM reseller_payments WHERE order_id = ?",
                               (order_id,)).fetchone()
        if not current or current["status"] == "success":
            return await edit_or_send(query, "✅ Already credited.",
                                      reply_markup=back_button("rs_menu"))
        conn.execute("""UPDATE reseller_payments SET status = 'success', utr = ?, paid_at = ?
            WHERE order_id = ?""", (utr, iso_now(), order_id))
    new_bal = credit_reseller_balance(query.from_user.id, int(row["amount"]),
                                      reason="Reseller top-up", ref=order_id)
    await edit_or_send(
        query,
        f"{premium_header('Balance added', '✅', 'Your reseller wallet is ready for the next order.')}\n"
        f"💰  <b>Added</b>        •  <code>{mono('₹' + str(row['amount']))}</code>\n"
        f"🧾  <b>Order</b>        •  <code>{esc(order_id)}</code>\n"
        f"💼  <b>New Balance</b>  •  <b><code>{mono('₹' + str(new_bal))}</code></b>",
        reply_markup=back_button("rs_menu", "🔙  Back to Panel"))
    try:
        await query.get_bot().send_message(
            chat_id=OWNER_ID,
            text=(f"💰  <b>Reseller Top-Up</b>\n"
                  f"User  •  <code>{query.from_user.id}</code>\n"
                  f"Amount  •  <code>{mono('₹' + str(row['amount']))}</code>\n"
                  f"Order  •  <code>{esc(order_id)}</code>"),
            parse_mode="HTML")
    except Exception:
        pass


async def reseller_cancel_payment(query, order_id):
    with db() as conn:
        conn.execute("""UPDATE reseller_payments SET status = 'cancelled'
            WHERE order_id = ? AND user_id = ? AND status = 'pending'""",
                     (order_id, query.from_user.id))
    await edit_or_send(query, "✖️  <b>Payment cancelled.</b>",
                       reply_markup=back_button("rs_menu", "🔙  Back to Panel"))


async def reseller_generate_key(query):
    user_id = query.from_user.id
    ensure_reseller_user(user_id)
    bal = get_reseller_balance(user_id)
    if MIN_BALANCE_FOR_KEY > 0 and bal < MIN_BALANCE_FOR_KEY:
        return await safe_answer(
            query,
            f"Minimum ₹{MIN_BALANCE_FOR_KEY} balance required to generate an API key.",
            show_alert=True)
    max_bots = get_rs_int("max_bots", DEFAULT_MAX_BOTS)
    if count_active_keys(user_id) >= max_bots:
        return await safe_answer(query, f"You have reached the max of {max_bots} active bots.",
                                 show_alert=True)
    key = generate_api_key()
    with db() as conn:
        conn.execute("INSERT INTO api_keys(user_id, api_key, label) VALUES (?, ?, ?)",
                     (user_id, key, "Bot"))
    endpoint = f"{detect_public_url()}/v1/order"
    purchase_endpoint = f"{detect_public_url()}/v1/purchase"
    text = (f"{premium_header('API key generated', '🔑', 'Use this private key to connect your automation.')}\n"
            f"<blockquote>⚠️  <b>Save this key now.</b>\nIt will not be shown again.</blockquote>\n\n"
            f"🔐  <b>API Key</b>\n<code>{esc(key)}</code>\n\n"
            f"🌐  <b>Order Endpoint</b>\n<code>{esc(endpoint)}</code>\n\n"
            f"🛒  <b>Purchase Coupon Endpoint</b>\n<code>{esc(purchase_endpoint)}</code>\n\n"
            f"📩  <b>Header</b>\n<code>X-RBC-Key: {esc(key)}</code>\n\n"
            f"<b>{DIVIDER}</b>\n"
            f"<i>Use this key in your own bot to send orders to us.</i>")
    await edit_or_send(query, text, reply_markup=back_button("rs_menu", "🔙  Back to Panel"))


async def reseller_add_key_start(query, context):
    context.user_data.clear()
    context.user_data["state"] = "RS_WAITING_OWN_KEY"
    current = get_user_own_rbc_key(query.from_user.id)
    shown = f"Currently  •  <code>{esc(current[:10])}…</code>" if current else "Currently  •  <i>(not set)</i>"
    await edit_or_send(
        query,
        f"{premium_header('Save your RBC API key', '🔐', 'Keep your external key private and linked to this account.')}\n"
        f"{shown}\n\n"
        f"<blockquote>Send your own RBC API key (must start with <code>rbc_</code>).\n"
        f"Stored privately and used only for your account.</blockquote>",
        reply_markup=back_button("rs_menu", "🔙  Cancel"))


def get_reseller_autolike_pricing():
    with db() as conn:
        return conn.execute("""SELECT package, price FROM autolike_pricing
            WHERE is_active = 1 ORDER BY package""").fetchall()


async def reseller_glory_start(query, context):
    context.user_data.clear()
    context.user_data["state"] = "RS_WAITING_GLORY_GUILD"
    await edit_or_send(query,
                       f"{premium_header('Guild Glory order', '💎', 'Send the details for your reseller launch request.')}\n"
                       f"Send the <b>Guild ID</b> to continue.",
                       reply_markup=back_button("rs_menu", "🔙  Cancel"))


async def reseller_glory_execute(query, context):
    guild = context.user_data.get("rs_glory_guild")
    region = context.user_data.get("rs_glory_region")
    accounts = context.user_data.get("rs_glory_accounts")
    if not (guild and region and accounts):
        return await safe_answer(query, "Order data missing.", show_alert=True)
    cost = get_rs_int("glory_cost", 70)
    payload = {"guild_id": str(guild), "region": str(region),
               "type": "glory", "accounts": int(accounts)}
    result = await reseller_execute_order(query.from_user.id, "glory", payload, cost, None)
    context.user_data.clear()
    if result["success"]:
        await edit_or_send(
            query,
             f"{premium_header('Order placed', '✅', 'Your reseller order was accepted.')}\n"
            f"🛡  <b>Guild</b>     •  <code>{esc(guild)}</code>\n"
            f"🌍  <b>Region</b>    •  {esc(region)}\n"
            f"🤖  <b>Accounts</b>  •  <code>{mono(accounts)}</code>\n"
            f"💰  <b>Charged</b>   •  <b><code>{mono('₹' + str(cost))}</code></b>\n"
            f"💼  <b>Balance</b>   •  <b><code>{mono('₹' + str(result['balance_left']))}</code></b>",
            reply_markup=back_button("rs_menu", "🔙  Back to Panel"))
    else:
        msg = f"❌  <b>Order failed:</b> {esc(result['error'])}"
        if result.get("refunded"):
            msg += "\n<i>Your balance was not charged (auto-refunded).</i>"
        await edit_or_send(query, msg, reply_markup=back_button("rs_menu", "🔙  Back to Panel"))


async def reseller_autolike_start(query, context):
    if not get_reseller_autolike_pricing():
        return await safe_answer(query, "No autolike packages configured.", show_alert=True)
    context.user_data.clear()
    context.user_data["state"] = "RS_WAITING_AUTOLIKE_UID"
    await edit_or_send(query,
                       f"{premium_header('Autolike order', '❤️‍🔥', 'Send the player UID to begin.')}\n"
                       f"Send the player <b>UID</b>.",
                       reply_markup=back_button("rs_menu", "🔙  Cancel"))


async def reseller_autolike_package_confirm(query, context, package):
    with db() as conn:
        row = conn.execute("""SELECT package, price FROM autolike_pricing
            WHERE package = ? AND is_active = 1""", (package,)).fetchone()
    if not row:
        return await safe_answer(query, "Package not available.", show_alert=True)
    uid = context.user_data.get("rs_al_uid")
    region = context.user_data.get("rs_al_region")
    if not (uid and region):
        return await safe_answer(query, "Order data missing, please restart.", show_alert=True)
    cost = int(row["price"])
    context.user_data["rs_al_pkg"] = package
    context.user_data["state"] = "RS_WAITING_AUTOLIKE_CONFIRM"
    await edit_or_send(
        query,
        f"{premium_header('Confirm autolike order', '❤️‍🔥', 'Review the player and plan before charging your balance.')}\n"
        f"🆔  <b>UID</b>       •  <code>{esc(uid)}</code>\n"
        f"🌍  <b>Region</b>    •  {esc(region)}\n"
        f"📦  <b>Package</b>   •  {esc(package)}\n"
        f"💰  <b>Cost</b>      •  <b><code>{mono('₹' + str(cost))}</code></b>\n\n"
        f"<blockquote>Tap Confirm to charge ₹{cost} from your reseller balance.</blockquote>",
        reply_markup=InlineKeyboardMarkup([
            [_mk_rbtn("✅  Confirm", "rs_al_do", style="success")],
            [_mk_rbtn("✖️  Cancel", "rs_menu", style="danger")],
        ]))


async def reseller_autolike_execute(query, context):
    uid = context.user_data.get("rs_al_uid")
    region = context.user_data.get("rs_al_region")
    package = context.user_data.get("rs_al_pkg")
    if not (uid and region and package):
        return await safe_answer(query, "Order data missing.", show_alert=True)
    with db() as conn:
        row = conn.execute("""SELECT price FROM autolike_pricing
            WHERE package = ? AND is_active = 1""", (package,)).fetchone()
    if not row:
        context.user_data.clear()
        return await safe_answer(query, "Package not available.", show_alert=True)
    cost = int(row["price"])
    payload = {"uid": str(uid), "region": str(region),
               "type": "autolike", "package": str(package)}
    result = await reseller_execute_order(query.from_user.id, "autolike", payload, cost, None)
    context.user_data.clear()
    if result["success"]:
        await edit_or_send(
            query,
             f"{premium_header('Autolike order placed', '✅', 'The reseller service accepted your request.')}\n"
            f"🆔  <b>UID</b>       •  <code>{esc(uid)}</code>\n"
            f"🌍  <b>Region</b>    •  {esc(region)}\n"
            f"📦  <b>Package</b>   •  {esc(package)}\n"
            f"💰  <b>Charged</b>   •  <b><code>{mono('₹' + str(cost))}</code></b>\n"
            f"💼  <b>Balance</b>   •  <b><code>{mono('₹' + str(result['balance_left']))}</code></b>",
            reply_markup=back_button("rs_menu", "🔙  Back to Panel"))
    else:
        msg = f"❌  <b>Order failed:</b> {esc(result['error'])}"
        if result.get("refunded"):
            msg += "\n<i>Your balance was refunded.</i>"
        await edit_or_send(query, msg, reply_markup=back_button("rs_menu", "🔙  Back to Panel"))


# ═══════════════════════════════════════════════════════════════════
#  API DOCS — now shows EVERY package (retail + reseller-synced)
# ═══════════════════════════════════════════════════════════════════
def build_pid_list_text():
    """Dynamic PID list pulled from reseller_credit_packages (auto-synced)."""
    pkgs = list_reseller_credit_packages(active_only=True)
    if not pkgs:
        return "   <i>⚠️  No credit packages configured yet.</i>"
    lines = []
    for p in pkgs:
        stock = count_unused_coupons_for_credits(int(p["credits"]))
        stock_icon = "🟢" if stock > 0 else "🔴"
        lines.append(
            f"   {stock_icon}  <b>PID</b> <b><code>{mono(str(p['id']).rjust(2))}</code></b>  "
            f"→  <b>{str(p['credits']).rjust(3)} Credit</b>  •  "
            f"<code>{mono('₹' + str(p['wholesale_price']).rjust(5))}</code>  •  "
            f"<i>stock <code>{mono(str(stock).rjust(3))}</code></i>"
        )
    return "\n".join(lines)


def build_order_example_json():
    pkgs = list_reseller_credit_packages(active_only=True)
    first_pid = int(pkgs[0]["id"]) if pkgs else 1
    return json.dumps({"package_id": first_pid,
                       "idempotency_key": "MYBOT-ORDER-001"},
                      separators=(",", ":"))


def reseller_api_docs_text():
    base = detect_public_url()
    pid_list = build_pid_list_text()
    order_example = build_order_example_json()
    return (
        f"{premium_header('RBC reseller API docs', '📖', 'Build on the same verified catalog using your private API key.')}\n\n"

        f"🌐  <b>Base URL</b>\n"
        f"<code>{esc(base)}</code>\n\n"

        f"🔐  <b>Authentication Header</b>\n"
        f"<code>X-RBC-Key: rbc_live_xxxxxxxx</code>\n\n"

        f"<b>{DIVIDER}</b>\n"
        f"<b>   📦  {bold('AVAILABLE PACKAGES (PID LIST)')}</b>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<i>Admin ne jo bhi packages add kiye hain,\n"
        f"unka PID automatic yahin show hoga.</i>\n\n"
        f"{pid_list}\n\n"
        f"<blockquote>ℹ️  <b>PID = Package ID</b>\n"
        f"API me <code>package_id</code> field me yahi PID dalna hai.\n"
        f"<b>Example:</b> PID <code>1</code> dalenge to 1-credit wala coupon milega.</blockquote>\n\n"

        f"<b>{DIVIDER}</b>\n"
        f"<b>   🛒  {bold('PURCHASE COUPON API')}</b>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<b>POST</b> <code>{esc(base)}/v1/purchase</code>\n\n"
        f"<b>Headers:</b>\n"
        f"<code>X-RBC-Key: rbc_live_xxxx</code>\n"
        f"<code>Content-Type: application/json</code>\n\n"
        f"<b>Body Example:</b>\n"
        f"<pre>{esc(order_example)}</pre>\n\n"

        f"<b>{DIVIDER}</b>\n"
        f"<b>   ♻️  {bold('IDEMPOTENCY KEY KYA HAI?')}</b>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<i>Yeh ek UNIQUE ORDER REFERENCE hai jo <b>AAPKA BOT</b> banata hai.</i>\n\n"

        f"<b>🎯 Kaam kya karta hai:</b>\n"
        f"   • Agar aapke bot se same order <b>2 baar</b> chala jaye\n"
        f"   • Lekin <b>same idempotency_key</b> ho\n"
        f"   • Toh <b>DOBARA CHARGE NAHI hoga</b>\n"
        f"   • Wahi <b>same coupon</b> dobara return hoga ✅\n\n"

        f"<b>📝 Kaise generate karein:</b>\n"
        f"   • Har naye order ke liye <b>naya</b> key banao\n"
        f"   • Simple example:\n"
        f"<pre>MYBOT-ORDER-001\nMYBOT-ORDER-002\nMYBOT-ORDER-003</pre>\n"
        f"   • Ya timestamp use karo:\n"
        f"<pre>order_{mono(now_ist().strftime('%Y%m%d%H%M%S'))}</pre>\n\n"

        f"<blockquote>⚠️  <b>ZAROORI:</b>\n"
        f"Do alag orders ke liye same key <b>kabhi</b> mat bhejna.\n"
        f"Warna dusra order reject ho jayega duplicate samajh ke.</blockquote>\n\n"

        f"<b>{DIVIDER}</b>\n"
        f"<b>   ✅  {bold('SUCCESS RESPONSE')}</b>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<pre>{{\"success\":true,\"coupon_code\":\"RBC-ABC-1234\","
        f"\"credits\":1,\"amount\":100,\"balance_left\":900,"
        f"\"redeem_url\":\"https://...\"}}</pre>\n\n"

        f"<b>{DIVIDER}</b>\n"
        f"<b>   ♻️  {bold('DUPLICATE REQUEST RESPONSE')}</b>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<i>(Same idempotency_key dobara bhejne par)</i>\n"
        f"<pre>{{\"success\":true,\"duplicate_request\":true,"
        f"\"coupon_code\":\"RBC-ABC-1234\",\"balance_left\":900}}</pre>\n"
        f"<i>Balance se kuch nahi katega, same coupon milega.</i>\n\n"

        f"<b>{DIVIDER}</b>\n"
        f"<b>   ❌  {bold('ERROR RESPONSES')}</b>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<b>Out of stock (HTTP 409):</b>\n"
        f"<pre>{{\"success\":false,\"error_code\":\"OUT_OF_STOCK\","
        f"\"error\":\"No unused coupon available for 1 credits.\"}}</pre>\n\n"
        f"<b>Insufficient balance (HTTP 402):</b>\n"
        f"<pre>{{\"success\":false,\"error_code\":\"INSUFFICIENT_RESELLER_BALANCE\","
        f"\"required\":800,\"available\":300}}</pre>\n\n"

        f"<b>{DIVIDER}</b>\n"
        f"<b>   📦  {bold('GUILD GLORY ORDER')}</b>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<b>POST</b> <code>{esc(base)}/v1/order</code>\n"
        f"<pre>{{\"guild_id\":\"123456789\",\"region\":\"ind\","
        f"\"type\":\"glory\",\"accounts\":4}}</pre>\n\n"

        f"<b>{DIVIDER}</b>\n"
        f"<b>   ❤️  {bold('AUTO LIKE ORDER')}</b>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<b>POST</b> <code>{esc(base)}/v1/order</code>\n"
        f"<pre>{{\"uid\":\"PLAYER_UID\",\"region\":\"ind\","
        f"\"type\":\"autolike\",\"package\":\"1day\"}}</pre>\n\n"

        f"<b>{DIVIDER}</b>\n"
        f"<b>   🏥  {bold('HEALTH CHECK')}</b>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<code>GET {esc(base)}/v1/health</code>\n"
        f"<i>Response: {{\"status\":\"ok\"}}</i>"
    )


async def reseller_show_docs(query):
    await edit_or_send(query, reseller_api_docs_text(),
                       reply_markup=back_button("rs_menu", "🔙  Back to Panel"))


async def reseller_show_my_bots(query):
    keys = list_user_keys(query.from_user.id)
    if not keys:
        return await edit_or_send(query,
                                  f"{premium_header('My bots', '🤖', 'Manage keys created for your reseller automations.')}\n\n"
                                  f"<i>You haven't generated any API keys yet.</i>",
                                  reply_markup=back_button("rs_menu", "🔙  Back to Panel"))
    lines = [premium_header("My bots", "🤖", "Manage keys created for your reseller automations.")]
    rows = []
    for k in keys:
        icon = "🟢" if k["status"] == "active" else "🔴"
        lines.append(f"{icon}  <b>{esc(k['label'] or 'Bot')}</b>\n"
                     f"🔐 <code>{esc(k['api_key'][:16])}…</code>\n"
                     f"📦 Orders  •  <code>{mono(k['orders'])}</code>   |   "
                     f"💰 Spent  •  <b><code>{mono('₹' + str(k['total_spent']))}</code></b>\n"
                     f"📅 <i>{esc(str(k['created_at'])[:10])}</i>")
        action = "Disable" if k["status"] == "active" else "Enable"
        rows.append([_mk_rbtn(f"{action}  •  {k['api_key'][:12]}…", f"rs_toggle_{k['id']}",
                              style="danger" if k["status"] == "active" else "success")])
    rows.append([_mk_rbtn("🔙  Back", "rs_menu", style="primary")])
    await edit_or_send(query, "\n\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def reseller_toggle_key(query, key_id):
    with db() as conn:
        row = conn.execute("SELECT id, status, user_id FROM api_keys WHERE id = ?",
                           (key_id,)).fetchone()
        if not row or int(row["user_id"]) != int(query.from_user.id):
            return await safe_answer(query, "Not found.", show_alert=True)
        new_status = "disabled" if row["status"] == "active" else "active"
        conn.execute("UPDATE api_keys SET status = ? WHERE id = ?", (new_status, key_id))
    await safe_answer(query, f"Key {new_status}.")
    await reseller_show_my_bots(query)


# ═══════════════════════════════════════════════════════════════════
#  RBC RESELLER — ADMIN
# ═══════════════════════════════════════════════════════════════════
async def show_reseller_admin(query):
    if not is_owner(query.from_user.id):
        return await safe_answer(query, "❌ Access Denied!", show_alert=True)
    master = get_rs_setting("rbc_master_key")
    fampay = get_rs_setting("fampay_api_key")
    mdisp = f"••••{master[-4:]}" if len(master) >= 4 else "❌ Not set"
    fdisp = f"••••{fampay[-4:]}" if len(fampay) >= 4 else "❌ Not set"
    text = (f"{premium_header('Reseller control center', '👑', 'Configure wholesale pricing, access and operational limits.')}\n"
            f"🔐  <b>RBC Master Key</b>    •  <code>{mdisp}</code>\n"
            f"💳  <b>Fampay API Key</b>    •  <code>{fdisp}</code>\n"
            f"💎  <b>Glory Cost</b>        •  <code>{mono('₹' + str(get_rs_int('glory_cost', 70)))}</code>\n"
            f"🤖  <b>Max Bots / User</b>   •  <code>{mono(get_rs_int('max_bots', DEFAULT_MAX_BOTS))}</code>\n"
            f"💰  <b>Min Add Balance</b>   •  <code>{mono('₹' + str(get_rs_int('min_add_balance', DEFAULT_MIN_ADD_BALANCE)))}</code>\n"
            f"<b>{DIVIDER}</b>")
    kb = [
        [_mk_rbtn("💎  " + bold("Credit Packages"), "rs_admin_credit_pkgs", style="success")],
        [_mk_rbtn("🎁  " + bold("Coupon Stock"), "rs_admin_stock", style="success"),
         _mk_rbtn("➕  " + bold("Add Coupons"), "rs_admin_bulk_coupon", style="success")],
        [_mk_rbtn("🌐  " + bold("Redeem Website"), "rs_admin_redeem", style="primary")],
        [_mk_rbtn("🔐  Set RBC Master Key", "rs_admin_master_key", style="primary")],
        [_mk_rbtn("💳  Set Fampay API Key", "rs_admin_fampay_key", style="primary")],
        [_mk_rbtn("⚙️  Pricing & Limits", "rs_admin_pricing", style="primary")],
        [_mk_rbtn("🎁  Auto Like Packages", "rs_admin_autolike", style="primary")],
        [_mk_rbtn("💰  Manage User Balance", "rs_admin_bal", style="success")],
        [_mk_rbtn("👥  Users", "rs_admin_users", style="primary"),
         _mk_rbtn("📊  Stats", "rs_admin_stats", style="primary")],
        [_mk_rbtn("📢  Broadcast", "rs_admin_broadcast", style="primary"),
         _mk_rbtn("👤  Owner Info", "rs_admin_owner", style="primary")],
        [_mk_rbtn("🔙  Back", "admin_menu", style="primary")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def show_admin_credit_pkgs(query):
    sync_retail_to_reseller()   # keep in sync whenever this panel opens
    pkgs = list_reseller_credit_packages(active_only=False)
    lines = [premium_header("Reseller credit packages", "💎", "Retail packages sync into the reseller catalog automatically."),
             "<i>Yeh list automatic sync hoti hai retail packages se.</i>\n"]
    kb = []
    if not pkgs:
        lines.append("<i>No credit packages yet.</i>")
    for p in pkgs:
        stock = count_unused_coupons_for_credits(int(p["credits"]))
        icon = "🟢" if p["is_active"] else "🔴"
        lines.append(f"\n{icon}  <b>PID {mono(p['id'])}</b>  →  "
                     f"<b>{p['credits']} Credits</b>  •  "
                     f"<b><code>{mono('₹' + str(p['wholesale_price']))}</code></b>\n"
                     f"      📦 Stock: <code>{mono(stock)}</code>")
        kb.append([
            _mk_rbtn(f"✏️ Price PID {p['id']}", f"rs_admin_edit_cp_{p['id']}", style="primary"),
            _mk_rbtn("🗑", f"rs_admin_del_cp_{p['id']}", style="danger"),
        ])
    kb.append([_mk_rbtn("➕  Add Credit Package", "rs_admin_add_cp", style="success")])
    kb.append([_mk_rbtn("🔙  Back", "rs_admin", style="primary")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                                  parse_mode="HTML")


async def show_admin_coupon_stock(query):
    with db() as conn:
        rows = conn.execute("""
            SELECT credits,
                   SUM(CASE WHEN is_used = 0 THEN 1 ELSE 0 END) AS unused,
                   SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) AS used,
                   COUNT(*) AS total
            FROM coupons GROUP BY credits ORDER BY credits ASC
        """).fetchall()
    lines = [premium_header("Coupon stock overview", "🎁", "Monitor shared inventory across retail and reseller flows.")]
    if not rows:
        lines.append("<i>No coupons in stock.</i>")
    for r in rows:
        lines.append(f"💎  <b>{r['credits']} Credits</b>  •  "
                     f"✅ <code>{mono(r['unused'])}</code> unused  •  "
                     f"🎫 <code>{mono(r['used'])}</code> used  •  "
                     f"Σ <code>{mono(r['total'])}</code>")
    lines.append(f"<b>{DIVIDER}</b>")
    kb = [
        [_mk_rbtn("➕ Add Coupons", "rs_admin_bulk_coupon", style="success")],
        [_mk_rbtn("🔙 Back", "rs_admin", style="primary")],
    ]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                                  parse_mode="HTML")


async def show_admin_bulk_coupon_picker(query):
    with db() as conn:
        tiers = [r["credits"] for r in conn.execute(
            "SELECT DISTINCT credits FROM packages ORDER BY credits ASC").fetchall()]
        tiers_rs = [r["credits"] for r in conn.execute(
            "SELECT DISTINCT credits FROM reseller_credit_packages ORDER BY credits ASC").fetchall()]
    all_tiers = sorted(set(tiers + tiers_rs))
    kb = [[_mk_rbtn(f"💎 {c} Credits", f"rs_admin_bc_tier_{c}", style="success")]
          for c in all_tiers]
    kb.append([_mk_rbtn("✏️ Custom Credits", "rs_admin_bc_tier_custom", style="primary")])
    kb.append([_mk_rbtn("🔙 Back", "rs_admin", style="primary")])
    await query.edit_message_text(
        f"{premium_header('Add coupons in bulk', '➕', 'Shared stock is available to retail customers and resellers.')}\n"
        f"<i>Select the credits tier for these coupons.\n"
        f"Coupons will be shared stock — available to both retail customers and resellers.</i>",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def show_reseller_admin_pricing(query):
    text = (f"{premium_header('Pricing & limits', '⚙️', 'Control the commercial rules for reseller orders.')}\n"
            f"💎  <b>Glory Cost (per launch)</b>  •  <code>{mono('₹' + str(get_rs_int('glory_cost', 70)))}</code>\n"
            f"🤖  <b>Max Bots / User</b>           •  <code>{mono(get_rs_int('max_bots', DEFAULT_MAX_BOTS))}</code>\n"
            f"💰  <b>Min Add Balance</b>           •  <code>{mono('₹' + str(get_rs_int('min_add_balance', DEFAULT_MIN_ADD_BALANCE)))}</code>")
    kb = [
        [_mk_rbtn("💎  Change Glory Cost", "rs_admin_edit_glory", style="primary")],
        [_mk_rbtn("🤖  Change Max Bots", "rs_admin_edit_maxbots", style="primary")],
        [_mk_rbtn("💰  Change Min Add Balance", "rs_admin_edit_minbal", style="primary")],
        [_mk_rbtn("🔙  Back", "rs_admin", style="primary")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def show_reseller_admin_autolike(query):
    with db() as conn:
        rows = conn.execute("""SELECT package, price, is_active FROM autolike_pricing
            ORDER BY package""").fetchall()
    lines = [premium_header("Reseller autolike packages", "🎁", "Manage wholesale autolike plans and pricing.")]
    kb = []
    for r in rows:
        icon = "🟢" if r["is_active"] else "🔴"
        lines.append(f"{icon}  <b>{esc(r['package'])}</b>  •  "
                     f"<b><code>{mono('₹' + str(r['price']))}</code></b>")
        kb.append([
            _mk_rbtn(f"✏️  {r['package']}", f"rs_al_edit_{r['package']}", style="primary"),
            _mk_rbtn("🗑", f"rs_al_del_{r['package']}", style="danger"),
        ])
    kb.append([_mk_rbtn("➕  Add Package", "rs_al_add", style="success")])
    kb.append([_mk_rbtn("🔙  Back", "rs_admin", style="primary")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                                  parse_mode="HTML")


async def show_reseller_admin_users(query):
    with db() as conn:
        rows = conn.execute("""SELECT r.user_id, r.balance, r.banned, u.first_name, u.username
            FROM users_reseller r LEFT JOIN users u ON u.user_id = r.user_id
            ORDER BY r.balance DESC LIMIT 50""").fetchall()
    if not rows:
        return await query.edit_message_text(f"{premium_header('Reseller users', '👥', 'Accounts currently using the reseller suite.')}\n\n"
                                             f"<i>No reseller users yet.</i>",
                                             reply_markup=back_button("rs_admin"), parse_mode="HTML")
    lines = [premium_header("Reseller users", "👥", "Accounts currently using the reseller suite.")]
    for r in rows:
        name = r["first_name"] or r["username"] or ""
        banned = " 🚫" if r["banned"] else ""
        lines.append(f"• <code>{r['user_id']}</code>  {esc(name)}  •  "
                     f"<b><code>{mono('₹' + str(r['balance']))}</code></b>{banned}")
    await query.edit_message_text("\n".join(lines), reply_markup=back_button("rs_admin"),
                                  parse_mode="HTML")


async def show_reseller_admin_stats(query):
    with db() as conn:
        users_n = conn.execute("SELECT COUNT(*) AS n FROM users_reseller").fetchone()["n"]
        keys_n = conn.execute("SELECT COUNT(*) AS n FROM api_keys WHERE status = 'active'").fetchone()["n"]
        orders_n = conn.execute("SELECT COUNT(*) AS n FROM order_logs").fetchone()["n"]
        revenue = conn.execute("""SELECT COALESCE(SUM(amount), 0) AS n FROM reseller_payments
            WHERE status = 'success'""").fetchone()["n"]
        credits = conn.execute("""SELECT COALESCE(SUM(amount), 0) AS n FROM balance_logs
            WHERE log_type = 'credit'""").fetchone()["n"]
        debits = conn.execute("""SELECT COALESCE(SUM(amount), 0) AS n FROM balance_logs
            WHERE log_type = 'debit'""").fetchone()["n"]
        total_bal = conn.execute("SELECT COALESCE(SUM(balance), 0) AS n FROM users_reseller").fetchone()["n"]
        tx_n = conn.execute("SELECT COUNT(*) AS n FROM reseller_transactions").fetchone()["n"]
        coupons_held = conn.execute("SELECT COUNT(*) AS n FROM coupons WHERE is_used = 1").fetchone()["n"]
    await query.edit_message_text(
        f"{premium_header('Reseller statistics', '📊', 'Operational metrics for the reseller suite.')}\n"
        f"👥  Reseller Users         •  <code>{mono(users_n)}</code>\n"
        f"🤖  Active Bots            •  <code>{mono(keys_n)}</code>\n"
        f"📦  Total Orders           •  <code>{mono(orders_n)}</code>\n"
        f"🎟  Coupon Transactions    •  <code>{mono(tx_n)}</code>\n"
        f"🎫  Coupons Assigned       •  <code>{mono(coupons_held)}</code>\n"
        f"💵  Revenue (top-ups)      •  <b><code>{mono('₹' + str(revenue))}</code></b>\n"
        f"💰  Total Credited         •  <b><code>{mono('₹' + str(credits))}</code></b>\n"
        f"🔥  Total Debited          •  <b><code>{mono('₹' + str(debits))}</code></b>\n"
        f"💼  Users Balance Held     •  <b><code>{mono('₹' + str(total_bal))}</code></b>",
        reply_markup=back_button("rs_admin"), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  RBC MASTER CLIENT
# ═══════════════════════════════════════════════════════════════════
async def call_rbc_master(payload, master_key):
    headers = {"X-RBC-Key": master_key, "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as s:
        async with s.post(RBC_MASTER_API_URL, headers=headers, json=payload,
                          timeout=aiohttp.ClientTimeout(total=30)) as r:
            raw = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"RBC API HTTP {r.status}: {raw[:200]}")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError("RBC API returned invalid JSON") from exc
            if not isinstance(data, dict):
                raise RuntimeError("RBC API returned an unexpected response")
            return data


async def reseller_execute_order(user_id, order_type, payload, cost, api_key_id):
    master_key = get_rs_setting("rbc_master_key", "")
    if not master_key:
        return {"success": False, "error": "RBC master key is not configured."}

    ok, value = try_debit_balance(user_id, cost,
                                   reason=f"{order_type} order",
                                   ref=json.dumps(payload)[:120])
    if not ok:
        return {"success": False, "error": str(value)}
    new_balance = int(value)

    with db() as conn:
        cursor = conn.execute("""INSERT INTO order_logs(user_id, api_key_id, order_type,
            payload_json, cost, status) VALUES (?, ?, ?, ?, ?, 'pending')""",
                              (user_id, api_key_id, order_type, json.dumps(payload), cost))
        order_log_id = cursor.lastrowid

    try:
        rbc_response = await call_rbc_master(payload, master_key)
        if not bool(rbc_response.get("success", True)):
            raise RuntimeError(str(rbc_response.get("error") or "RBC rejected the order"))
    except Exception as exc:
        logger.exception("RBC call failed for user %s", user_id)
        new_balance = credit_reseller_balance(user_id, cost,
            reason=f"Refund for failed {order_type} order",
            ref=f"order_log:{order_log_id}")
        with db() as conn:
            conn.execute("""UPDATE order_logs SET status = 'refunded', response_json = ?
                WHERE id = ?""", (json.dumps({"error": str(exc)}), order_log_id))
            if api_key_id:
                conn.execute("""UPDATE api_keys SET orders = orders + 1, last_used = ?
                    WHERE id = ?""", (iso_now(), api_key_id))
        return {"success": False, "error": str(exc), "refunded": True, "balance_left": new_balance}

    with db() as conn:
        conn.execute("""UPDATE order_logs SET status = 'success', response_json = ?
            WHERE id = ?""", (json.dumps(rbc_response), order_log_id))
        if api_key_id:
            conn.execute("""UPDATE api_keys SET orders = orders + 1,
                total_spent = total_spent + ?, last_used = ? WHERE id = ?""",
                         (cost, iso_now(), api_key_id))
    return {"success": True, "data": rbc_response, "charged": cost, "balance_left": new_balance}


# ═══════════════════════════════════════════════════════════════════
#  HTTP API SERVER
# ═══════════════════════════════════════════════════════════════════
def json_response(payload, status=200):
    return web.json_response(payload, status=status)


async def http_root(request):
    base = detect_public_url()
    return json_response({
        "service": "RBC Reseller API", "version": "1.3",
        "base_url": base,
        "endpoints": {
            "GET /v1/packages": "List all available packages (PID, credits, price, stock)",
            "POST /v1/purchase": "Purchase 1 coupon (X-RBC-Key, idempotent)",
            "POST /api/reseller/purchase": "Alias for /v1/purchase",
            "POST /v1/order": "Create a glory / autolike order (X-RBC-Key)",
            "GET /v1/health": "Health check",
        }
    })


async def http_health(request):
    return json_response({"status": "ok", "base_url": detect_public_url()})


async def http_list_packages(request):
    pkgs = list_reseller_credit_packages(active_only=True)
    return json_response({
        "success": True,
        "base_url": detect_public_url(),
        "packages": [
            {
                "package_id": int(p["id"]),
                "credits": int(p["credits"]),
                "price": int(p["wholesale_price"]),
                "stock": count_unused_coupons_for_credits(int(p["credits"])),
            }
            for p in pkgs
        ],
        "redeem_url": redeem_url(),
    })


async def _resolve_api_key_row(request):
    api_key = request.headers.get("X-RBC-Key", "").strip()
    if not api_key:
        return None, json_response({"success": False, "error": "Missing X-RBC-Key"}, 401)
    key_row = lookup_api_key(api_key)
    if not key_row:
        return None, json_response({"success": False, "error": "Invalid API key"}, 401)
    if key_row["status"] != "active":
        return None, json_response({"success": False, "error": "API key disabled"}, 403)
    user_id = int(key_row["user_id"])
    if reseller_is_banned(user_id):
        return None, json_response({"success": False, "error": "User is banned"}, 403)
    return key_row, None


async def http_purchase(request):
    key_row, err = await _resolve_api_key_row(request)
    if err:
        return err
    user_id = int(key_row["user_id"])

    try:
        body = await request.json()
    except Exception:
        return json_response({"success": False, "error": "Invalid JSON body"}, 400)
    if not isinstance(body, dict):
        return json_response({"success": False, "error": "Body must be an object"}, 400)

    package_id = body.get("package_id")
    idem = body.get("idempotency_key") or body.get("order_id") or body.get("client_order_id")
    if package_id is None:
        return json_response({"success": False, "error": "Missing package_id"}, 400)
    try:
        package_id = int(package_id)
    except (TypeError, ValueError):
        return json_response({"success": False, "error": "package_id must be an integer"}, 400)
    if not idem or not str(idem).strip():
        return json_response({"success": False, "error": "Missing idempotency_key"}, 400)

    result = await purchase_coupon_for_reseller(
        user_id, package_id, str(idem).strip(), api_key_id=int(key_row["id"]))

    if not result["success"]:
        code = result.get("code")
        status_map = {
            "OUT_OF_STOCK": 409,
            "INSUFFICIENT_RESELLER_BALANCE": 402,
            "PACKAGE_NOT_FOUND": 404,
            "USER_BANNED": 403,
            "USER_NOT_FOUND": 404,
        }
        http_status = status_map.get(code, 400)
        return json_response({
            "success": False,
            "error": result.get("error", "Purchase failed"),
            "error_code": code,
            "required": result.get("required"),
            "available": result.get("available"),
        }, http_status)

    return json_response({
        "success": True,
        "duplicate_request": bool(result.get("duplicate_request")),
        "transaction_id": result["transaction_id"],
        "coupon_code": result["coupon_code"],
        "credits": result["credits"],
        "amount": result["amount"],
        "redeem_url": result["redeem_url"],
        "balance_left": result["balance_left"],
    })


async def http_order(request):
    key_row, err = await _resolve_api_key_row(request)
    if err:
        return err
    user_id = int(key_row["user_id"])

    try:
        body = await request.json()
    except Exception:
        return json_response({"success": False, "error": "Invalid JSON body"}, 400)
    if not isinstance(body, dict):
        return json_response({"success": False, "error": "Body must be an object"}, 400)

    order_type = str(body.get("type", "")).lower()
    if order_type == "glory":
        cost = get_rs_int("glory_cost", 70)
        required = ["guild_id", "region", "accounts"]
    elif order_type == "autolike":
        package = str(body.get("package", "")).strip()
        if not package:
            return json_response({"success": False, "error": "Missing package"}, 400)
        with db() as conn:
            row = conn.execute("SELECT price, is_active FROM autolike_pricing WHERE package = ?",
                               (package,)).fetchone()
        if not row or not row["is_active"]:
            return json_response({"success": False, "error": "Unknown or inactive package"}, 400)
        cost = int(row["price"])
        required = ["uid", "region"]
    else:
        return json_response({"success": False,
                              "error": "type must be 'glory' or 'autolike'"}, 400)

    missing = [f for f in required if not body.get(f)]
    if missing:
        return json_response({"success": False, "error": f"Missing fields: {', '.join(missing)}"}, 400)

    result = await reseller_execute_order(user_id, order_type, body, cost,
                                           api_key_id=int(key_row["id"]))
    if not result["success"]:
        return json_response({"success": False, "error": result["error"],
                              "refunded": result.get("refunded", False),
                              "balance_left": result.get("balance_left")}, 400)
    return json_response({"success": True, "data": result["data"],
                          "charged": result["charged"],
                          "balance_left": result["balance_left"]})


def build_http_app():
    app = web.Application()
    app.router.add_get("/", http_root)
    app.router.add_get("/v1/health", http_health)
    app.router.add_get("/v1/packages", http_list_packages)
    app.router.add_post("/v1/purchase", http_purchase)
    app.router.add_post("/api/reseller/purchase", http_purchase)
    app.router.add_post("/v1/order", http_order)
    return app


async def start_http_server():
    app = build_http_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, API_HOST, API_PORT)
    await site.start()
    logger.info("HTTP API listening on %s:%s (public: %s)",
                API_HOST, API_PORT, detect_public_url())
    return runner


# ═══════════════════════════════════════════════════════════════════
#  MAIN ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════
async def show_admin_menu(query):
    if not is_owner(query.from_user.id):
        return await safe_answer(query, "❌ Access Denied!", show_alert=True)
    status = "🔴 ON" if get_setting("maintenance") == "1" else "🟢 OFF"
    text = (f"{premium_header('Admin control center', '👑', 'Operate the store, payments, catalog and reseller suite from one place.')}\n"
            f"🛠️  <b>Maintenance</b>  •  <b>{status}</b>\n"
            f"👤  <b>Owner</b>        •  <b>{esc(owner_name())}</b>\n\n"
            f"<i>Choose an operational area below.</i>")
    kb = [
        [_mk_rbtn("💳  " + bold("PAYMENT SETUP"), "admin_payment", style="primary")],
        [_mk_rbtn("💎  " + bold("GUILD GLORY SETUP"), "admin_glory_setup", style="success")],
        [_mk_rbtn("🔥  " + bold("AUTOLIKE MANAGEMENT"), "admin_autolike", style="success")],
        [_mk_rbtn("🎟  " + bold("COUPON MANAGEMENT"), "admin_add_coupon", style="primary")],
        [_mk_rbtn("📦  " + bold("COUPON PACKAGES"), "admin_packages", style="primary")],
        [_mk_rbtn("🔗  " + bold("WEBSITE SETTINGS"), "admin_set_web", style="primary"),
         _mk_rbtn("👤  " + bold("OWNER SETTINGS"), "admin_owner", style="primary")],
        [_mk_rbtn("📊  " + bold("STATISTICS"), "admin_stats", style="primary"),
         _mk_rbtn("📢  " + bold("BROADCAST"), "admin_broadcast", style="primary")],
        [_mk_rbtn("🔑  " + bold("RESELLER CONTROL"), "rs_admin", style="danger")],
        [_mk_rbtn("🛠️  " + bold("MAINTENANCE TOGGLE"), "admin_maintenance", style="danger")],
        [_mk_rbtn("↩️  " + bold("BACK TO HOME"), "main_menu", style="primary")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def show_glory_admin_setup(query):
    api_url = get_setting("glory_api_url", DEFAULT_GLORY_API_URL)
    api_key = get_setting("glory_api_key", "")
    kdisp = f"••••{api_key[-4:]}" if len(api_key) >= 4 else "❌ Not set"
    price = glory_flat_price()
    bots = glory_accounts_count()
    await query.edit_message_text(
        f"{premium_header('Guild Glory setup', '💎', 'Configure the customer-facing launch service.')}\n"
        f"🌐  <b>API URL</b>\n<code>{esc(api_url)}</code>\n\n"
        f"🔐  <b>API Key</b>       •  <code>{kdisp}</code>\n"
        f"💰  <b>Flat Price</b>    •  <b><code>{mono('₹' + str(price))}</code></b>\n"
        f"🤖  <b>Auto Bots</b>     •  <code>{mono(str(bots) + ' accounts')}</code>\n"
        f"<b>{DIVIDER}</b>\n"
        f"<i>These settings power the customer-facing Guild Glory launch flow.</i>",
        reply_markup=InlineKeyboardMarkup([
            [_mk_rbtn("🌐  Set API URL", "admin_glory_set_url", style="primary")],
            [_mk_rbtn("🔐  Set API Key", "admin_glory_set_key", style="primary")],
            [_mk_rbtn("💰  Set Flat Price", "admin_glory_set_price", style="primary")],
            [_mk_rbtn("🤖  Set Auto Bots", "admin_glory_set_accounts", style="primary")],
            [_mk_rbtn("🔙  Back", "admin_menu", style="primary")],
        ]), parse_mode="HTML")


async def show_payment_admin(query):
    key = get_setting("payment_api_key")
    masked = f"••••••••••••{key[-4:]}" if len(key) >= 4 else "Not configured"
    await query.edit_message_text(
        f"{premium_header('Payment setup', '💳', 'Configure the gateway used for all customer orders.')}\n"
        f"🔑  <b>API Key</b>  •  <code>{masked}</code>\n"
        f"🌐  <b>Create</b>   •  <code>{esc(CREATE_ORDER_URL)}</code>\n"
        f"🌐  <b>Verify</b>   •  <code>{esc(VERIFY_ORDER_URL)}</code>",
        reply_markup=InlineKeyboardMarkup([
            [_mk_rbtn("🔑  Set / Update API Key", "admin_set_key", style="success")],
            [_mk_rbtn("🔙  Back", "admin_menu", style="primary")],
        ]), parse_mode="HTML")


async def show_admin_packages(query):
    sync_retail_to_reseller()
    with db() as conn:
        packages = conn.execute("SELECT id, credits, price FROM packages ORDER BY credits").fetchall()
        rsp = {int(r["credits"]): (int(r["id"]), int(r["wholesale_price"]))
               for r in conn.execute("SELECT id, credits, wholesale_price FROM reseller_credit_packages").fetchall()}
    lines = [premium_header("Coupon package management", "📦", "Manage retail prices and shared coupon stock."),
             "<i>Retail price customer ke liye, wholesale reseller ke liye.</i>\n"]
    kb = []
    for p in packages:
        stock = count_unused_coupons_for_credits(int(p["credits"]))
        rs = rsp.get(int(p["credits"]))
        pid_txt = f"PID {mono(rs[0])}" if rs else "—"
        ws_txt = f"<code>{mono('₹' + str(rs[1]))}</code>" if rs else "—"
        lines.append(
            f"• <b>{p['credits']} Credits</b>  •  "
            f"Retail <b><code>{mono('₹' + str(p['price']))}</code></b>  •  "
            f"Wholesale {ws_txt}\n"
            f"     {pid_txt}  •  <i>stock <code>{mono(stock)}</code></i>")
        kb.append([
            _mk_rbtn(f"✏️ Retail ₹{p['credits']}C", f"admin_edit_pkg_{p['id']}", style="primary"),
            _mk_rbtn("🗑 Delete", f"admin_delete_pkg_{p['id']}", style="danger"),
        ])
    kb.extend([
        [_mk_rbtn("➕  Add Package", "admin_add_pkg", style="success")],
        [_mk_rbtn("💎  Edit Wholesale (Reseller)", "rs_admin_credit_pkgs", style="success")],
        [_mk_rbtn("🔙  Back", "admin_menu", style="primary")],
    ])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                                  parse_mode="HTML")


async def show_admin_like_plans(query):
    with db() as conn:
        plans = conn.execute("""SELECT id, days, price, likes_per_day, is_active
            FROM autolike_packages ORDER BY days ASC""").fetchall()
    lines = [premium_header("Like plan management", "🔥", "Manage customer-facing autolike plans.")]
    kb = []
    for p in plans:
        active = "🟢 Active" if p["is_active"] else "⚫ Disabled"
        lines.append(f"\n• ID <code>{mono(p['id'])}</code>  •  "
                     f"<b>{p['days']} days</b>  •  "
                     f"<b><code>{mono('₹' + str(p['price']))}</code></b>  •  "
                     f"<code>{mono(str(p['likes_per_day']) + ' likes/day')}</code>  •  {active}")
        kb.append([
            _mk_rbtn(f"✏️  Edit {p['days']}D", f"admin_edit_like_{p['id']}", style="primary"),
            _mk_rbtn("🗑 Delete", f"admin_delete_like_{p['id']}", style="danger"),
        ])
    kb.extend([
        [_mk_rbtn("➕  Add Like Plan", "admin_add_like", style="success")],
        [_mk_rbtn("🔙  Back", "admin_autolike", style="primary")],
    ])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
                                  parse_mode="HTML")


async def delete_guild_package(query, package_id):
    with db() as conn:
        p = conn.execute("SELECT credits, price FROM packages WHERE id = ?", (package_id,)).fetchone()
        if not p:
            return await safe_answer(query, "Package not found.", show_alert=True)
        pending = conn.execute("""SELECT COUNT(*) AS c FROM payment_orders
            WHERE service_type IN ('credit_coupon', 'guild_glory') AND package_id = ?
            AND status IN ('pending', 'paid')""", (str(package_id),)).fetchone()["c"]
        if pending:
            return await safe_answer(query, "This package has a pending payment and cannot be deleted yet.",
                                     show_alert=True)
        conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))
    await safe_answer(query, "Package deleted.")
    return await show_admin_packages(query)


async def delete_like_plan(query, plan_id):
    with db() as conn:
        p = conn.execute("SELECT days, price FROM autolike_packages WHERE id = ?", (plan_id,)).fetchone()
        if not p:
            return await safe_answer(query, "Like plan not found.", show_alert=True)
        pending = conn.execute("""SELECT COUNT(*) AS c FROM payment_orders
            WHERE service_type = 'autolike' AND package_id = ?
            AND status IN ('pending', 'paid')""", (str(p["days"]),)).fetchone()["c"]
        if pending:
            return await safe_answer(query, "This plan has a pending payment and cannot be deleted yet.",
                                     show_alert=True)
        conn.execute("DELETE FROM autolike_packages WHERE id = ?", (plan_id,))
    await safe_answer(query, "Like plan deleted.")
    return await show_admin_like_plans(query)


async def show_admin_autolike(query):
    await query.edit_message_text(
        f"{premium_header('Autolike management', '🔥', 'Maintain player records, plans and service fulfilment.')}\n\n"
        f"<i>Choose an operation.</i>",
        reply_markup=InlineKeyboardMarkup([
            [_mk_rbtn("➕  Add / Update Player", "admin_player_update", style="success")],
            [_mk_rbtn("🔍  Search UID", "admin_search_uid", style="primary")],
            [_mk_rbtn("👥  View Active Users", "admin_active", style="primary")],
            [_mk_rbtn("👍  Add Like Record", "admin_add_likes", style="success")],
            [_mk_rbtn("📊  Service Statistics", "admin_service_stats", style="primary")],
            [_mk_rbtn("💰  Manage Like Plans", "admin_like_plans", style="primary")],
            [_mk_rbtn("❌  Disable Service", "admin_disable", style="danger")],
            [_mk_rbtn("🗑  Delete Service", "admin_delete", style="danger")],
            [_mk_rbtn("🔙  Back", "admin_menu", style="primary")],
        ]), parse_mode="HTML")


async def admin_active_services(query):
    with db() as conn:
        services = conn.execute("""SELECT * FROM autolike_services
            WHERE status = 'active' ORDER BY id DESC LIMIT 20""").fetchall()
    if not services:
        text = "👥  <i>No active Autolike services.</i>"
    else:
        text = f"{premium_header('Active autolike users', '👥', 'Currently running player services.')}\n"
        for s in services:
            _, left = service_status(s)
            text += (f"🆔 <code>{esc(s['uid'])}</code>  •  {esc(s['region'])}\n"
                     f"👤 <code>{s['telegram_user_id']}</code>  •  "
                     f"👍 {s['current_likes']}  •  ⏳ {left}d\n\n")
    await query.edit_message_text(text, reply_markup=back_button("admin_autolike"), parse_mode="HTML")


def admin_state(context, state, **values):
    context.user_data.clear()
    context.user_data["state"] = state
    context.user_data.update(values)


async def process_admin_player_update(update, context):
    parts = [p.strip() for p in (update.message.text or "").split("|")]
    if len(parts) != 5:
        return await update.message.reply_text("❌ Format: UID | Player Name | Region | Level | Current Likes")
    uid, pname, region, level, likes = parts
    try:
        level, likes = int(level), int(likes)
    except ValueError:
        return await update.message.reply_text("❌ Level and likes must be numbers.")
    with db() as conn:
        service = conn.execute("SELECT id FROM autolike_services WHERE uid = ? ORDER BY id DESC LIMIT 1",
                               (uid,)).fetchone()
        conn.execute("""INSERT INTO player_profiles(uid, player_name, region,
            player_level, current_likes) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
            player_name = excluded.player_name, region = excluded.region,
            player_level = excluded.player_level, current_likes = excluded.current_likes,
            updated_at = CURRENT_TIMESTAMP""", (uid, pname, region, level, likes))
        if service:
            conn.execute("""UPDATE autolike_services SET player_name = ?, region = ?,
                player_level = ?, current_likes = ? WHERE id = ?""",
                         (pname, region, level, likes, service["id"]))
    context.user_data.clear()
    await update.message.reply_text("✅ Player details saved.",
                                    reply_markup=back_button("admin_autolike"), parse_mode="HTML")


async def process_admin_add_likes(update, context):
    parts = [p.strip() for p in (update.message.text or "").split("|")]
    if len(parts) != 2:
        return await update.message.reply_text("❌ Format: UID | Likes to add")
    uid, amount = parts
    try:
        amount = int(amount)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await update.message.reply_text("❌ Likes must be a positive number.")
    with db() as conn:
        s = conn.execute("""SELECT * FROM autolike_services WHERE uid = ?
            AND status = 'active' ORDER BY id DESC LIMIT 1""", (uid,)).fetchone()
        if not s:
            return await update.message.reply_text("❌ Active service not found.")
        before = s["current_likes"]
        after = before + amount
        conn.execute("UPDATE autolike_services SET current_likes = ? WHERE id = ?", (after, s["id"]))
        conn.execute("""INSERT INTO autolike_manual_updates(service_id, before_likes,
            likes_given, after_likes) VALUES (?, ?, ?, ?)""", (s["id"], before, amount, after))
    context.user_data.clear()
    await update.message.reply_text(f"✅ Added {amount} likes to UID {uid}.",
                                    reply_markup=back_button("admin_autolike"))


async def process_admin_uid_action(update, context, action):
    uid = (update.message.text or "").strip()
    if not uid:
        return await update.message.reply_text("❌ UID cannot be empty.")
    with db() as conn:
        s = conn.execute("SELECT * FROM autolike_services WHERE uid = ? ORDER BY id DESC LIMIT 1",
                         (uid,)).fetchone()
        if not s:
            context.user_data.clear()
            return await update.message.reply_text("❌ Service not found.")
        if action == "disable":
            conn.execute("UPDATE autolike_services SET status = 'disabled' WHERE id = ?", (s["id"],))
            result = "✅ Service disabled."
        elif action == "delete":
            conn.execute("DELETE FROM autolike_services WHERE id = ?", (s["id"],))
            result = "✅ Service deleted."
        else:
            st, left = service_status(s)
            result = (f"🆔  <b>UID</b>       •  <code>{esc(s['uid'])}</code>\n"
                      f"🌍  <b>Region</b>    •  {esc(s['region'])}\n"
                      f"👤  <b>Player</b>    •  {esc(s['player_name']) or 'Not set'}\n"
                      f"⭐  <b>Level</b>     •  <code>{mono(s['player_level'])}</code>\n"
                      f"👍  <b>Likes</b>     •  <code>{mono(s['current_likes'])}</code>\n"
                      f"⏳  <b>Days Left</b> •  <code>{mono(left)}</code>\n"
                      f"🟢  <b>Status</b>    •  <b>{st}</b>")
    context.user_data.clear()
    await update.message.reply_text(result, reply_markup=back_button("admin_autolike"), parse_mode="HTML")


async def admin_service_stats(query):
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM autolike_services").fetchone()["n"]
        active = conn.execute("SELECT COUNT(*) AS n FROM autolike_services WHERE status = 'active'").fetchone()["n"]
        disabled = conn.execute("SELECT COUNT(*) AS n FROM autolike_services WHERE status = 'disabled'").fetchone()["n"]
        likes = conn.execute("SELECT COALESCE(SUM(current_likes), 0) AS n FROM autolike_services").fetchone()["n"]
        updates = conn.execute("SELECT COUNT(*) AS n FROM autolike_daily_updates").fetchone()["n"]
    await query.edit_message_text(
        f"{premium_header('Autolike service statistics', '📊', 'A live view of service fulfilment.')}\n"
        f"👥  Total Services     •  <code>{mono(total)}</code>\n"
        f"🟢  Active             •  <code>{mono(active)}</code>\n"
        f"⚫  Disabled           •  <code>{mono(disabled)}</code>\n"
        f"👍  Recorded Likes     •  <code>{mono(likes)}</code>\n"
        f"📅  Daily Updates      •  <code>{mono(updates)}</code>",
        reply_markup=back_button("admin_autolike"), parse_mode="HTML")


async def show_admin_stats(query):
    with db() as conn:
        users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        payments = conn.execute("SELECT COUNT(*) AS n FROM payment_orders WHERE status = 'processed'").fetchone()["n"]
        revenue = conn.execute("""SELECT COALESCE(SUM(amount), 0) AS n FROM payment_orders
            WHERE status = 'processed'""").fetchone()["n"]
        coupons = conn.execute("SELECT COUNT(*) AS n FROM coupons").fetchone()["n"]
        used = conn.execute("SELECT COUNT(*) AS n FROM coupons WHERE is_used = 1").fetchone()["n"]
        active = conn.execute("SELECT COUNT(*) AS n FROM autolike_services WHERE status = 'active'").fetchone()["n"]
        rtx = conn.execute("SELECT COUNT(*) AS n FROM reseller_transactions").fetchone()["n"]
    await query.edit_message_text(
        f"{premium_header('Statistics dashboard', '📊', 'A live view of store-wide activity.')}\n"
        f"👥  Users                 •  <code>{mono(users)}</code>\n"
        f"💳  Completed Payments    •  <code>{mono(payments)}</code>\n"
        f"💰  Revenue               •  <b><code>{mono('₹' + str(revenue))}</code></b>\n"
        f"🎟  Coupons               •  <code>{mono(coupons)}</code>\n"
        f"🎫  Used Coupons          •  <code>{mono(used)}</code>\n"
        f"🔥  Active Autolikes      •  <code>{mono(active)}</code>\n"
        f"🔑  Reseller Coupon Tx    •  <code>{mono(rtx)}</code>",
        reply_markup=back_button("admin_menu"), parse_mode="HTML")


async def cancel_payment(query, order_id):
    with db() as conn:
        result = conn.execute("""UPDATE payment_orders SET status = 'cancelled'
            WHERE order_id = ? AND telegram_user_id = ? AND status = 'pending'""",
                              (order_id, query.from_user.id))
    if result.rowcount:
        await safe_answer(query, "Payment cancelled.")
    else:
        await safe_answer(query, "This payment cannot be cancelled.", show_alert=True)
    await query.edit_message_text("✖️ Payment cancelled.",
                                  reply_markup=back_button("main_menu"), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  CALLBACK ROUTER
# ═══════════════════════════════════════════════════════════════════
async def button_handler(update, context):
    query = update.callback_query
    await safe_answer(query)  # Use safe_answer instead of query.answer()
    user = query.from_user
    data = query.data or ""

    try:
        await context.bot.send_chat_action(chat_id=user.id, action="typing")
        await asyncio.sleep(TYPING_DELAY)
    except Exception:
        pass

    if get_setting("maintenance") == "1" and not is_owner(user.id):
        return await query.edit_message_text("🛠️ <b>Bot is under maintenance.</b>", parse_mode="HTML")
    ensure_user(user)

    # Public
    if data == "main_menu":
        context.user_data.clear()
        try:
            await query.message.delete()
        except Exception:
            pass
        return await context.bot.send_message(user.id, main_menu_text(user),
                                              reply_markup=main_menu_keyboard(user.id),
                                              parse_mode="HTML")
    if data == "shop_now":
        return await show_shop_menu(query)
    if data == "how_to_buy":
        return await show_how_to_buy(query)
    if data == "my_services":
        return await show_my_services(query)
    if data == "my_stats":
        return await show_my_stats(query)
    if data.startswith("verify_"):
        return await verify_and_fulfil(query, data[len("verify_"):])
    if data.startswith("cancel_payment_"):
        return await cancel_payment(query, data[len("cancel_payment_"):])

    # Guild Glory
    if data == "glory_menu":
        return await show_glory_menu(query)
    if data.startswith("glory_region_"):
        return await glory_select_region(query, context, data[len("glory_region_"):])
    if data == "glory_confirm":
        return await create_glory_payment(query, context)

    # Autolike
    if data == "autolike_menu":
        return await show_autolike_menu(query)
    if data == "autolike_buy":
        return await show_autolike_packages(query)
    if data.startswith("autolike_pkg_"):
        return await show_autolike_confirmation(query, int(data.rsplit("_", 1)[1]))
    if data.startswith("autolike_confirm_"):
        return await start_autolike_uid_collection(query, context, int(data.rsplit("_", 1)[1]))
    if data == "my_autolikes":
        return await show_my_autolikes(query)

    # Customer coupon
    if data == "coupon_menu":
        return await show_coupon_menu(query)
    if data.startswith("coupon_pkg_"):
        return await begin_coupon_payment(query, context, int(data.rsplit("_", 1)[1]))
    if data.startswith("coupon_confirm_"):
        return await create_coupon_payment(query, context, int(data.rsplit("_", 1)[1]))

    # Reseller user
    if data == "rs_menu":
        return await show_reseller_panel(query)
    if data == "rs_buy_coupons":
        return await reseller_show_buy_coupons(query)
    if data.startswith("rs_buy_pkg_"):
        return await reseller_confirm_buy_coupon(query, context, int(data.rsplit("_", 1)[1]))
    if data.startswith("rs_buy_do_"):
        return await reseller_execute_buy_coupon(query, context, int(data.rsplit("_", 1)[1]))
    if data == "rs_my_coupons":
        return await reseller_show_my_coupons(query)
    if data == "rs_my_tx":
        return await reseller_show_my_transactions(query)
    if data == "rs_add_bal":
        return await reseller_add_balance_start(query, context)
    if data.startswith("rs_add_confirm_"):
        amount = int(data[len("rs_add_confirm_"):])
        try:
            payment = await create_reseller_payment(user.id, amount)
        except Exception as exc:
            logger.exception("Reseller payment creation failed")
            return await safe_answer(query, str(exc)[:180], show_alert=True)
        return await reseller_show_payment(query, payment)
    if data.startswith("rs_verify_"):
        return await reseller_verify_payment(query, data[len("rs_verify_"):])
    if data.startswith("rs_cancel_"):
        return await reseller_cancel_payment(query, data[len("rs_cancel_"):])
    if data == "rs_gen_key":
        return await reseller_generate_key(query)
    if data == "rs_add_key":
        return await reseller_add_key_start(query, context)
    if data == "rs_docs":
        return await reseller_show_docs(query)
    if data == "rs_my_bots":
        return await reseller_show_my_bots(query)
    if data.startswith("rs_toggle_"):
        return await reseller_toggle_key(query, int(data[len("rs_toggle_"):]))
    if data == "rs_glory":
        return await reseller_glory_start(query, context)
    if data == "rs_glory_do":
        return await reseller_glory_execute(query, context)
    if data == "rs_autolike":
        return await reseller_autolike_start(query, context)
    if data.startswith("rs_al_pkg_"):
        return await reseller_autolike_package_confirm(query, context, data[len("rs_al_pkg_"):])
    if data == "rs_al_do":
        return await reseller_autolike_execute(query, context)

    # Admin only
    if not is_owner(user.id):
        return await safe_answer(query, "❌ Access Denied!", show_alert=True)

    if data == "admin_menu":
        return await show_admin_menu(query)
    if data == "admin_payment":
        return await show_payment_admin(query)
    if data == "admin_set_key":
        admin_state(context, "WAITING_PAYMENT_KEY")
        return await query.edit_message_text(
            "🔑 Send the payment API key.\n<i>It will not be displayed back.</i>",
            reply_markup=back_button("admin_payment", "🔙  Cancel"), parse_mode="HTML")
    if data == "admin_glory_setup":
        return await show_glory_admin_setup(query)
    if data == "admin_glory_set_url":
        admin_state(context, "WAITING_GLORY_API_URL")
        return await query.edit_message_text("🌐 Send the Guild Glory API URL.",
                                             reply_markup=back_button("admin_glory_setup", "🔙  Cancel"))
    if data == "admin_glory_set_key":
        admin_state(context, "WAITING_GLORY_API_KEY")
        return await query.edit_message_text("🔐 Send the Guild Glory API key.",
                                             reply_markup=back_button("admin_glory_setup", "🔙  Cancel"))
    if data == "admin_glory_set_price":
        admin_state(context, "WAITING_GLORY_PRICE")
        return await query.edit_message_text("💰 Send the flat price per order in ₹.",
                                             reply_markup=back_button("admin_glory_setup", "🔙  Cancel"))
    if data == "admin_glory_set_accounts":
        admin_state(context, "WAITING_GLORY_ACCOUNTS")
        return await query.edit_message_text("🤖 Send the number of auto-bots per launch.",
                                             reply_markup=back_button("admin_glory_setup", "🔙  Cancel"))
    if data == "admin_autolike":
        return await show_admin_autolike(query)
    if data == "admin_like_plans":
        return await show_admin_like_plans(query)
    if data == "admin_add_like":
        admin_state(context, "WAITING_LIKE_DAYS")
        return await query.edit_message_text(
            "🔥 Send the number of days for the new like plan.",
            reply_markup=back_button("admin_like_plans", "🔙  Cancel"))
    if data.startswith("admin_edit_like_"):
        plan_id = int(data.rsplit("_", 1)[1])
        with db() as conn:
            plan = conn.execute("""SELECT days, price, likes_per_day FROM autolike_packages
                WHERE id = ?""", (plan_id,)).fetchone()
        if not plan:
            return await safe_answer(query, "Like plan not found.", show_alert=True)
        admin_state(context, "WAITING_LIKE_EDIT", selected_like_id=plan_id)
        return await query.edit_message_text(
            f"✏️ <b>Edit {plan['days']}-day like plan</b>\n\n"
            f"Current price: ₹{plan['price']}\nCurrent likes/day: {plan['likes_per_day']}\n\n"
            f"Send new values:\n<code>PRICE | LIKES_PER_DAY</code>",
            reply_markup=back_button("admin_like_plans", "🔙  Cancel"), parse_mode="HTML")
    if data.startswith("admin_delete_like_"):
        plan_id = int(data.rsplit("_", 1)[1])
        with db() as conn:
            plan = conn.execute("SELECT days, price FROM autolike_packages WHERE id = ?",
                                (plan_id,)).fetchone()
        if not plan:
            return await safe_answer(query, "Like plan not found.", show_alert=True)
        return await query.edit_message_text(
            f"⚠️ Delete the <b>{plan['days']}-day</b> like plan priced at <b>₹{plan['price']}</b>?",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("✅  Yes, Delete", f"admin_confirm_delete_like_{plan_id}", style="danger")],
                [_mk_rbtn("🔙  No, Go Back", "admin_like_plans", style="primary")],
            ]), parse_mode="HTML")
    if data.startswith("admin_confirm_delete_like_"):
        return await delete_like_plan(query, int(data.rsplit("_", 1)[1]))
    if data == "admin_active":
        return await admin_active_services(query)
    if data == "admin_search_uid":
        admin_state(context, "WAITING_SEARCH_UID")
        return await query.edit_message_text("🔍 Send the UID to search.",
                                             reply_markup=back_button("admin_autolike", "🔙  Cancel"))
    if data == "admin_player_update":
        admin_state(context, "WAITING_PLAYER_DETAILS")
        return await query.edit_message_text(
            "✏️ Send:\n<code>UID | Player Name | Region | Level | Current Likes</code>",
            reply_markup=back_button("admin_autolike", "🔙  Cancel"), parse_mode="HTML")
    if data == "admin_add_likes":
        admin_state(context, "WAITING_ADD_LIKES")
        return await query.edit_message_text("👍 Send: <code>UID | Likes to add</code>",
                                             reply_markup=back_button("admin_autolike", "🔙  Cancel"),
                                             parse_mode="HTML")
    if data == "admin_service_stats":
        return await admin_service_stats(query)
    if data in {"admin_disable", "admin_delete"}:
        admin_state(context, "WAITING_DISABLE_UID" if data == "admin_disable" else "WAITING_DELETE_UID")
        return await query.edit_message_text("Send the UID.",
                                             reply_markup=back_button("admin_autolike", "🔙  Cancel"))
    if data == "admin_packages":
        return await show_admin_packages(query)
    if data == "admin_add_pkg":
        admin_state(context, "WAITING_PACKAGE_CREDITS")
        return await query.edit_message_text("📦 Send the number of credits for the new package.",
                                             reply_markup=back_button("admin_packages", "🔙  Cancel"))
    if data.startswith("admin_edit_pkg_"):
        package_id = int(data.rsplit("_", 1)[1])
        with db() as conn:
            package = conn.execute("SELECT credits, price FROM packages WHERE id = ?",
                                   (package_id,)).fetchone()
        if not package:
            return await safe_answer(query, "Package not found.", show_alert=True)
        admin_state(context, "WAITING_PACKAGE_PRICE_EDIT", selected_pkg_id=package_id)
        return await query.edit_message_text(
            f"✏️ <b>Edit {package['credits']}-credit package</b>\n\n"
            f"Current retail price: ₹{package['price']}\n\nSend new retail price in ₹.",
            reply_markup=back_button("admin_packages", "🔙  Cancel"), parse_mode="HTML")
    if data.startswith("admin_delete_pkg_"):
        package_id = int(data.rsplit("_", 1)[1])
        with db() as conn:
            package = conn.execute("SELECT credits, price FROM packages WHERE id = ?",
                                   (package_id,)).fetchone()
        if not package:
            return await safe_answer(query, "Package not found.", show_alert=True)
        return await query.edit_message_text(
            f"⚠️ Delete the <b>{package['credits']}-credit</b> package priced at "
            f"<b>₹{package['price']}</b>?",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("✅  Yes, Delete", f"admin_confirm_delete_pkg_{package_id}", style="danger")],
                [_mk_rbtn("🔙  No, Go Back", "admin_packages", style="primary")],
            ]), parse_mode="HTML")
    if data.startswith("admin_confirm_delete_pkg_"):
        return await delete_guild_package(query, int(data.rsplit("_", 1)[1]))
    if data == "admin_add_coupon":
        with db() as conn:
            packages = conn.execute("SELECT id, credits FROM packages ORDER BY credits").fetchall()
        kb = [[_mk_rbtn(f"Add for {p['credits']} Credits", f"select_coupon_pkg_{p['id']}",
                        style="success")] for p in packages]
        kb.append([_mk_rbtn("🔙 Back", "admin_menu", style="primary")])
        return await query.edit_message_text(
            f"🎟  <b>{double('COUPON MANAGEMENT')}</b>\n<b>{DIVIDER}</b>\nSelect a package:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    if data.startswith("select_coupon_pkg_"):
        pkg_id = int(data.rsplit("_", 1)[1])
        with db() as conn:
            pkg = conn.execute("SELECT credits FROM packages WHERE id = ?", (pkg_id,)).fetchone()
        if not pkg:
            return await safe_answer(query, "Package not found.", show_alert=True)
        admin_state(context, "WAITING_COUPON_CODE",
                    selected_pkg_id=pkg_id, selected_credits=int(pkg["credits"]))
        return await query.edit_message_text(
            f"🎟  <b>ADD COUPONS — {pkg['credits']} Credits</b>\n"
            f"<b>{DIVIDER}</b>\n"
            f"Send one or multiple codes (one per line or comma-separated).\n"
            f"<i>Example:</i>\n<code>RBC-ABC-1234\nRBC-DEF-5678</code>",
            reply_markup=back_button("admin_menu", "🔙  Done"), parse_mode="HTML")
    if data == "admin_set_web":
        admin_state(context, "WAITING_WEBSITE_LINK")
        return await query.edit_message_text(
            f"🔗 Current website:\n<code>{esc(get_setting('website_link'))}</code>\n\nSend the new URL.",
            reply_markup=back_button("admin_menu", "🔙  Cancel"), parse_mode="HTML")
    if data == "admin_owner":
        return await query.edit_message_text(
            f"👤  <b>{double('OWNER SETTINGS')}</b>\n"
            f"<b>{DIVIDER}</b>\n"
            f"Display name  •  <code>{esc(owner_name())}</code>\n"
            f"Username      •  <code>@{esc(owner_username())}</code>",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("✏️  Set Display Name", "admin_owner_name", style="primary")],
                [_mk_rbtn("✏️  Set Username", "admin_owner_username", style="primary")],
                [_mk_rbtn("🔙  Back", "admin_menu", style="primary")],
            ]), parse_mode="HTML")
    if data in {"admin_owner_name", "admin_owner_username"}:
        admin_state(context, "WAITING_OWNER_NAME" if data == "admin_owner_name" else "WAITING_OWNER_USERNAME")
        return await query.edit_message_text("Send the new value.",
                                             reply_markup=back_button("admin_owner", "🔙  Cancel"))
    if data == "admin_stats":
        return await show_admin_stats(query)
    if data == "admin_broadcast":
        admin_state(context, "WAITING_BROADCAST")
        return await query.edit_message_text(
            "📢 Send the text, photo, or video to broadcast.",
            reply_markup=back_button("admin_menu", "🔙  Cancel"))
    if data == "admin_maintenance":
        new_value = "0" if get_setting("maintenance") == "1" else "1"
        update_setting("maintenance", new_value)
        await safe_answer(query, f"Maintenance is now {'ON' if new_value == '1' else 'OFF'}.",
                          show_alert=True)
        return await show_admin_menu(query)

    # RBC Admin
    if data == "rs_admin":
        return await show_reseller_admin(query)
    if data == "rs_admin_credit_pkgs":
        return await show_admin_credit_pkgs(query)
    if data == "rs_admin_add_cp":
        admin_state(context, "RS_ADMIN_CP_CREDITS")
        return await query.edit_message_text(
            "💎 Send the number of credits for the new package.\n<i>Example: 10</i>",
            reply_markup=back_button("rs_admin_credit_pkgs", "🔙  Cancel"), parse_mode="HTML")
    if data.startswith("rs_admin_edit_cp_"):
        cp_id = int(data.rsplit("_", 1)[1])
        pkg = get_reseller_credit_package(cp_id)
        if not pkg:
            return await safe_answer(query, "Package not found.", show_alert=True)
        admin_state(context, "RS_ADMIN_CP_EDIT_PRICE", rs_cp_id=cp_id)
        return await query.edit_message_text(
            f"✏️ <b>PID {pkg['id']} — {pkg['credits']} Credits</b>\n\n"
            f"Current wholesale: ₹{pkg['wholesale_price']}\n\nSend new wholesale price in ₹.",
            reply_markup=back_button("rs_admin_credit_pkgs", "🔙  Cancel"), parse_mode="HTML")
    if data.startswith("rs_admin_del_cp_"):
        cp_id = int(data.rsplit("_", 1)[1])
        pkg = get_reseller_credit_package(cp_id)
        if not pkg:
            return await safe_answer(query, "Package not found.", show_alert=True)
        with db() as conn:
            conn.execute("DELETE FROM reseller_credit_packages WHERE id = ?", (cp_id,))
        await safe_answer(query, "Credit package deleted.")
        return await show_admin_credit_pkgs(query)
    if data == "rs_admin_stock":
        return await show_admin_coupon_stock(query)
    if data == "rs_admin_bulk_coupon":
        return await show_admin_bulk_coupon_picker(query)
    if data == "rs_admin_bc_tier_custom":
        admin_state(context, "RS_ADMIN_BC_CUSTOM_CREDITS")
        return await query.edit_message_text(
            "💎 Send the credits value for these coupons.\n<i>Example: 25</i>",
            reply_markup=back_button("rs_admin", "🔙  Cancel"), parse_mode="HTML")
    if data.startswith("rs_admin_bc_tier_"):
        credits = int(data.rsplit("_", 1)[1])
        admin_state(context, "RS_ADMIN_BC_CODES", rs_bc_credits=credits)
        return await query.edit_message_text(
            f"🎁 <b>ADD COUPONS — {credits} Credits</b>\n"
            f"<b>{DIVIDER}</b>\n"
            f"Send codes one per line or comma-separated.\n"
            f"<i>Example:</i>\n<code>RBC-TEST-1234\nRBC-TEST-5678</code>",
            reply_markup=back_button("rs_admin", "🔙  Cancel"), parse_mode="HTML")
    if data == "rs_admin_redeem":
        admin_state(context, "RS_ADMIN_REDEEM_URL")
        return await query.edit_message_text(
            f"🌐 Current redeem URL:\n<code>{esc(redeem_url())}</code>\n\nSend the new URL.",
            reply_markup=back_button("rs_admin", "🔙  Cancel"), parse_mode="HTML")
    if data == "rs_admin_master_key":
        admin_state(context, "RS_ADMIN_MASTER_KEY")
        return await query.edit_message_text(
            "🔐 Send the RBC master API key (starts with rbc_live_).",
            reply_markup=back_button("rs_admin", "🔙  Cancel"))
    if data == "rs_admin_fampay_key":
        admin_state(context, "RS_ADMIN_FAMPAY_KEY")
        return await query.edit_message_text("💳 Send the Fampay API key.",
                                             reply_markup=back_button("rs_admin", "🔙  Cancel"))
    if data == "rs_admin_pricing":
        return await show_reseller_admin_pricing(query)
    if data == "rs_admin_edit_glory":
        admin_state(context, "RS_ADMIN_EDIT_GLORY")
        return await query.edit_message_text("💎 Send the new Glory cost in ₹.",
                                             reply_markup=back_button("rs_admin_pricing", "🔙  Cancel"))
    if data == "rs_admin_edit_maxbots":
        admin_state(context, "RS_ADMIN_EDIT_MAXBOTS")
        return await query.edit_message_text("🤖 Send the new max bots per user.",
                                             reply_markup=back_button("rs_admin_pricing", "🔙  Cancel"))
    if data == "rs_admin_edit_minbal":
        admin_state(context, "RS_ADMIN_EDIT_MINBAL")
        return await query.edit_message_text("💰 Send the new minimum add balance in ₹.",
                                             reply_markup=back_button("rs_admin_pricing", "🔙  Cancel"))
    if data == "rs_admin_autolike":
        return await show_reseller_admin_autolike(query)
    if data == "rs_al_add":
        admin_state(context, "RS_ADMIN_AL_ADD_PKG")
        return await query.edit_message_text(
            "➕ Send the package name (e.g. <code>3days</code>).",
            reply_markup=back_button("rs_admin_autolike", "🔙  Cancel"), parse_mode="HTML")
    if data.startswith("rs_al_edit_"):
        pkg = data[len("rs_al_edit_"):]
        admin_state(context, "RS_ADMIN_AL_EDIT_PRICE", rs_al_pkg=pkg)
        return await query.edit_message_text(
            f"✏️ Send the new price in ₹ for <b>{esc(pkg)}</b>.",
            reply_markup=back_button("rs_admin_autolike", "🔙  Cancel"), parse_mode="HTML")
    if data.startswith("rs_al_del_"):
        pkg = data[len("rs_al_del_"):]
        with db() as conn:
            conn.execute("DELETE FROM autolike_pricing WHERE package = ?", (pkg,))
        await safe_answer(query, "Deleted.")
        return await show_reseller_admin_autolike(query)
    if data == "rs_admin_bal":
        admin_state(context, "RS_ADMIN_WAITING_BAL_UID")
        return await query.edit_message_text(
            f"💰  <b>MANAGE USER BALANCE</b>\n<b>{DIVIDER}</b>\nSend the user's Telegram ID.",
            reply_markup=back_button("rs_admin", "🔙  Cancel"), parse_mode="HTML")
    if data == "rs_admin_bal_add":
        uid = context.user_data.get("rs_admin_bal_uid")
        admin_state(context, "RS_ADMIN_BAL_ADD_AMT", rs_admin_bal_uid=uid)
        return await query.edit_message_text("➕ Send amount to add in ₹.",
                                             reply_markup=back_button("rs_admin", "🔙  Cancel"))
    if data == "rs_admin_bal_remove":
        uid = context.user_data.get("rs_admin_bal_uid")
        admin_state(context, "RS_ADMIN_BAL_REMOVE_AMT", rs_admin_bal_uid=uid)
        return await query.edit_message_text("➖ Send amount to remove in ₹.",
                                             reply_markup=back_button("rs_admin", "🔙  Cancel"))
    if data == "rs_admin_bal_set":
        uid = context.user_data.get("rs_admin_bal_uid")
        admin_state(context, "RS_ADMIN_BAL_SET_AMT", rs_admin_bal_uid=uid)
        return await query.edit_message_text("✏️ Send the exact new balance in ₹.",
                                             reply_markup=back_button("rs_admin", "🔙  Cancel"))
    if data == "rs_admin_users":
        return await show_reseller_admin_users(query)
    if data == "rs_admin_stats":
        return await show_reseller_admin_stats(query)
    if data == "rs_admin_broadcast":
        admin_state(context, "RS_ADMIN_BROADCAST")
        return await query.edit_message_text(
            "📢 Send the message to broadcast to all users.",
            reply_markup=back_button("rs_admin", "🔙  Cancel"))
    if data == "rs_admin_owner":
        return await query.edit_message_text(
            f"👤  <b>{double('OWNER INFO')}</b>\n"
            f"<b>{DIVIDER}</b>\n"
            f"Name      •  <b>{esc(owner_name())}</b>\n"
            f"Username  •  @{esc(owner_username())}\n\n"
            f"Contact link:\n{esc(owner_contact_url())}",
            reply_markup=back_button("rs_admin"), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════
async def handle_message(update, context):
    message = update.message
    if not message or message.chat.type != ChatType.PRIVATE:
        return
    user = update.effective_user
    ensure_user(user)
    text = (message.text or "").strip()
    state = context.user_data.get("state")

    if text.lower() == "/cancel":
        context.user_data.clear()
        return await message.reply_text("✅ Action cancelled.",
                                        reply_markup=main_menu_keyboard(user.id),
                                        parse_mode="HTML")
    if text == "/reseller":
        ensure_reseller_user(user.id)
        return await message.reply_text(reseller_panel_text(user.id),
                                        reply_markup=reseller_panel_keyboard(),
                                        parse_mode="HTML")
    if text == "/admin" and is_owner(user.id):
        return await message.reply_text(
            "👑  <b>Admin Panel</b>",
            reply_markup=InlineKeyboardMarkup([[
                _mk_rbtn("Open Admin Panel", "admin_menu", style="danger")
            ]]),
            parse_mode="HTML")
    if not state:
        return

    # Guild Glory — receive Guild ID → show confirm
    if state == "WAITING_GLORY_GUILD_ID":
        guild_id = text
        if not guild_id.isdigit() or not (6 <= len(guild_id) <= 15):
            return await message.reply_text("❌ Invalid Guild ID. Send a numeric ID (6–15 digits).")
        await glory_show_confirm(update, context, guild_id)
        return

    # Autolike
    if state == "WAITING_AUTOLIKE_UID":
        uid = text
        if not uid:
            return await message.reply_text("❌ UID cannot be empty.")
        if active_service_for_uid(user.id, uid):
            context.user_data.clear()
            return await message.reply_text("❌ This UID already has an active service.",
                                            reply_markup=main_menu_keyboard(user.id))
        context.user_data["autolike_uid"] = uid
        context.user_data["state"] = "WAITING_AUTOLIKE_REGION"
        return await message.reply_text("🌍 Now send your <b>Free Fire Region</b>.", parse_mode="HTML")
    if state == "WAITING_AUTOLIKE_REGION":
        region = text
        if not region:
            return await message.reply_text("❌ Region cannot be empty.")
        uid = context.user_data["autolike_uid"]
        days = int(context.user_data["autolike_days"])
        if active_service_for_uid(user.id, uid):
            context.user_data.clear()
            return await message.reply_text("❌ This UID already has an active service.")
        plan = get_autolike_plan(days)
        if not plan:
            context.user_data.clear()
            return await message.reply_text("❌ This like plan is no longer available.",
                                            reply_markup=main_menu_keyboard(user.id))
        api_key = get_setting("payment_api_key")
        try:
            payment = await create_and_store_payment(
                user.id, "autolike", str(days), plan["price"],
                {"uid": uid, "region": region, "days": days,
                 "likes_per_day": plan["likes_per_day"]}, api_key)
        except Exception as exc:
            logger.exception("Autolike order creation failed")
            context.user_data.clear()
            return await message.reply_text(f"❌ {esc(exc)}", parse_mode="HTML")
        context.user_data.clear()
        return await message.reply_photo(payment["qr_url"], caption=payment_text(payment),
                                         reply_markup=payment_keyboard(payment["order_id"]),
                                         parse_mode="HTML")

    # Reseller user states
    if state == "RS_WAITING_ADD_AMOUNT":
        try:
            amount = int(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        min_bal = get_rs_int("min_add_balance", DEFAULT_MIN_ADD_BALANCE)
        if amount < min_bal:
            return await message.reply_text(f"❌ Minimum is ₹{min_bal}.")
        context.user_data["state"] = None
        return await message.reply_text(
            f"💰  <b>{double('CONFIRM TOP-UP')}</b>\n"
            f"<b>{DIVIDER}</b>\n"
            f"Amount  •  <b><code>{mono('₹' + str(amount))}</code></b>\n\n"
            f"<blockquote>Tap Confirm to generate a payment QR.</blockquote>",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("✅  Confirm", f"rs_add_confirm_{amount}", style="success")],
                [_mk_rbtn("✖️  Cancel", "rs_menu", style="danger")],
            ]), parse_mode="HTML")
    if state == "RS_WAITING_OWN_KEY":
        key = text
        if not key.startswith("rbc_"):
            return await message.reply_text(
                "❌ Invalid key format. Must start with <code>rbc_</code>.", parse_mode="HTML")
        set_user_own_rbc_key(user.id, key)
        context.user_data.clear()
        return await message.reply_text("✅ Your RBC API key has been saved privately.",
                                        reply_markup=back_button("rs_menu", "🔙  Back to Panel"))
    if state == "RS_WAITING_GLORY_GUILD":
        context.user_data["rs_glory_guild"] = text
        context.user_data["state"] = "RS_WAITING_GLORY_REGION"
        return await message.reply_text("🌍 Now send the <b>Region</b> (e.g. ind).", parse_mode="HTML")
    if state == "RS_WAITING_GLORY_REGION":
        context.user_data["rs_glory_region"] = text
        context.user_data["state"] = "RS_WAITING_GLORY_ACCOUNTS"
        return await message.reply_text("👥 Now send the <b>number of accounts</b>.")
    if state == "RS_WAITING_GLORY_ACCOUNTS":
        try:
            accounts = int(text)
            if accounts <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        guild = context.user_data.get("rs_glory_guild", "")
        region = context.user_data.get("rs_glory_region", "")
        cost = get_rs_int("glory_cost", 70)
        bal = get_reseller_balance(user.id)
        if bal < cost:
            context.user_data.clear()
            return await message.reply_text(
                f"❌ Insufficient balance.\nRequired: ₹{cost}\nBalance: ₹{bal}")
        context.user_data["rs_glory_accounts"] = accounts
        context.user_data["state"] = "RS_WAITING_GLORY_CONFIRM"
        return await message.reply_text(
            f"💎  <b>{double('CONFIRM GLORY ORDER')}</b>\n"
            f"<b>{DIVIDER}</b>\n"
            f"🛡 Guild     •  <code>{esc(guild)}</code>\n"
            f"🌍 Region    •  {esc(region)}\n"
            f"🤖 Accounts  •  <code>{mono(accounts)}</code>\n"
            f"💰 Cost      •  <b><code>{mono('₹' + str(cost))}</code></b>\n\n"
            f"<blockquote>Tap Confirm to charge ₹{cost} from your balance.</blockquote>",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("✅  Confirm", "rs_glory_do", style="success")],
                [_mk_rbtn("✖️  Cancel", "rs_menu", style="danger")],
            ]), parse_mode="HTML")
    if state == "RS_WAITING_AUTOLIKE_UID":
        context.user_data["rs_al_uid"] = text
        context.user_data["state"] = "RS_WAITING_AUTOLIKE_REGION"
        return await message.reply_text("🌍 Now send the <b>Region</b>.")
    if state == "RS_WAITING_AUTOLIKE_REGION":
        context.user_data["rs_al_region"] = text
        packages = get_reseller_autolike_pricing()
        if not packages:
            context.user_data.clear()
            return await message.reply_text("❌ No packages configured.")
        context.user_data["state"] = "RS_WAITING_AUTOLIKE_PACKAGE"
        kb = [[_mk_rbtn(f"₹{p['price']}  •  {p['package']}",
                        f"rs_al_pkg_{p['package']}", style="success")] for p in packages]
        kb.append([_mk_rbtn("✖️  Cancel", "rs_menu", style="danger")])
        return await message.reply_text("📦 Choose a package:", reply_markup=InlineKeyboardMarkup(kb))

    # Admin states
    if not is_owner(user.id):
        return

    if state == "WAITING_PAYMENT_KEY":
        if not text:
            return await message.reply_text("❌ API key cannot be empty.")
        update_setting("payment_api_key", text)
        context.user_data.clear()
        return await message.reply_text("✅ Payment API key saved.",
                                        reply_markup=back_button("admin_payment"))
    if state == "WAITING_GLORY_API_URL":
        if not text.startswith("http"):
            return await message.reply_text("❌ URL must start with http:// or https://")
        update_setting("glory_api_url", text)
        context.user_data.clear()
        return await message.reply_text("✅ Guild Glory API URL saved.",
                                        reply_markup=back_button("admin_glory_setup"))
    if state == "WAITING_GLORY_API_KEY":
        if not text:
            return await message.reply_text("❌ Key cannot be empty.")
        update_setting("glory_api_key", text.strip())
        context.user_data.clear()
        return await message.reply_text("✅ Guild Glory API key saved.",
                                        reply_markup=back_button("admin_glory_setup"))
    if state == "WAITING_GLORY_PRICE":
        try:
            v = int(text)
            if v <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        update_setting("glory_flat_price", str(v))
        context.user_data.clear()
        return await message.reply_text(f"✅ Glory flat price set to ₹{v}.",
                                        reply_markup=back_button("admin_glory_setup"))
    if state == "WAITING_GLORY_ACCOUNTS":
        try:
            v = int(text)
            if v <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        update_setting("glory_accounts", str(v))
        context.user_data.clear()
        return await message.reply_text(f"✅ Auto-bots set to {v}.",
                                        reply_markup=back_button("admin_glory_setup"))
    if state == "WAITING_WEBSITE_LINK":
        update_setting("website_link", text)
        update_setting("redeem_website", text)
        context.user_data.clear()
        return await message.reply_text("✅ Website URL updated.",
                                        reply_markup=back_button("admin_menu"))
    if state == "WAITING_OWNER_NAME":
        update_setting("owner_name", text)
        context.user_data.clear()
        return await message.reply_text("✅ Owner display name updated.",
                                        reply_markup=back_button("admin_owner"))
    if state == "WAITING_OWNER_USERNAME":
        update_setting("owner_username", text.lstrip("@"))
        context.user_data.clear()
        return await message.reply_text("✅ Owner username updated.",
                                        reply_markup=back_button("admin_owner"))
    if state == "WAITING_PACKAGE_CREDITS":
        try:
            credits = int(text)
            if credits <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        context.user_data.update({"state": "WAITING_PACKAGE_PRICE", "pkg_credits": credits})
        return await message.reply_text("💰 Now send the package price in ₹.")
    if state == "WAITING_PACKAGE_PRICE":
        try:
            price = int(text)
            if price <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        with db() as conn:
            conn.execute("INSERT INTO packages(credits, price) VALUES (?, ?)",
                         (context.user_data["pkg_credits"], price))
        sync_retail_to_reseller()
        context.user_data.clear()
        return await message.reply_text(
            "✅ Package created & synced to reseller pool.",
            reply_markup=back_button("admin_packages"))
    if state == "WAITING_PACKAGE_PRICE_EDIT":
        try:
            price = int(text)
            if price <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number for the price.")
        with db() as conn:
            updated = conn.execute("UPDATE packages SET price = ? WHERE id = ?",
                                   (price, context.user_data["selected_pkg_id"])).rowcount
        context.user_data.clear()
        if not updated:
            return await message.reply_text("❌ Package not found.",
                                            reply_markup=back_button("admin_packages"))
        return await message.reply_text("✅ Package price updated.",
                                        reply_markup=back_button("admin_packages"))
    if state == "WAITING_LIKE_DAYS":
        try:
            days = int(text)
            if days <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number of days.")
        with db() as conn:
            exists = conn.execute("SELECT 1 FROM autolike_packages WHERE days = ?", (days,)).fetchone()
        if exists:
            return await message.reply_text("❌ A plan with these days already exists.")
        context.user_data.update({"state": "WAITING_LIKE_PRICE", "like_days": days})
        return await message.reply_text("💰 Now send the price in ₹.")
    if state == "WAITING_LIKE_PRICE":
        try:
            price = int(text)
            if price <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number for the price.")
        context.user_data.update({"state": "WAITING_LIKE_COUNT", "like_price": price})
        return await message.reply_text("👍 Now send the likes per day.")
    if state == "WAITING_LIKE_COUNT":
        try:
            likes_per_day = int(text)
            if likes_per_day <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number of likes.")
        try:
            with db() as conn:
                conn.execute("""INSERT INTO autolike_packages (days, price, likes_per_day)
                    VALUES (?, ?, ?)""",
                             (context.user_data["like_days"],
                              context.user_data["like_price"],
                              likes_per_day))
        except sqlite3.IntegrityError:
            context.user_data.clear()
            return await message.reply_text("❌ This like plan already exists.",
                                            reply_markup=back_button("admin_like_plans"))
        context.user_data.clear()
        return await message.reply_text("✅ Like plan created.",
                                        reply_markup=back_button("admin_like_plans"))
    if state == "WAITING_LIKE_EDIT":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 2:
            return await message.reply_text("❌ Format: <code>PRICE | LIKES_PER_DAY</code>",
                                            parse_mode="HTML")
        try:
            price, likes_per_day = (int(v) for v in parts)
            if price <= 0 or likes_per_day <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Both values must be positive whole numbers.")
        with db() as conn:
            updated = conn.execute("""UPDATE autolike_packages SET price = ?, likes_per_day = ?
                WHERE id = ?""", (price, likes_per_day, context.user_data["selected_like_id"])).rowcount
        context.user_data.clear()
        if not updated:
            return await message.reply_text("❌ Like plan not found.",
                                            reply_markup=back_button("admin_like_plans"))
        return await message.reply_text("✅ Like plan updated.",
                                        reply_markup=back_button("admin_like_plans"))
    if state == "WAITING_COUPON_CODE":
        raw = text.replace(",", "\n")
        codes = [c.strip() for c in raw.splitlines() if c.strip()]
        if not codes:
            return await message.reply_text("❌ No codes found in message.")
        added = 0
        skipped = 0
        pkg_id = context.user_data.get("selected_pkg_id", 0)
        credits = context.user_data.get("selected_credits", 0)
        with db() as conn:
            for c in codes:
                try:
                    conn.execute("""INSERT INTO coupons(package_id, code, credits)
                        VALUES (?, ?, ?)""", (pkg_id, c, credits))
                    added += 1
                except sqlite3.IntegrityError:
                    skipped += 1
        return await message.reply_text(
            f"✅ Coupons added: <b>{added}</b>  •  Skipped (duplicates): <b>{skipped}</b>\n\n"
            f"Send more codes or click <b>Done</b>.",
            reply_markup=back_button("admin_menu", "🔙  Done"), parse_mode="HTML")
    if state == "WAITING_SEARCH_UID":
        return await process_admin_uid_action(update, context, "search")
    if state == "WAITING_PLAYER_DETAILS":
        return await process_admin_player_update(update, context)
    if state == "WAITING_ADD_LIKES":
        return await process_admin_add_likes(update, context)
    if state == "WAITING_DISABLE_UID":
        return await process_admin_uid_action(update, context, "disable")
    if state == "WAITING_DELETE_UID":
        return await process_admin_uid_action(update, context, "delete")
    if state == "WAITING_BROADCAST":
        with db() as conn:
            users = [row["user_id"] for row in conn.execute("SELECT user_id FROM users")]
        sent = failed = 0
        for user_id in set(users):
            try:
                await message.copy(chat_id=user_id)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        context.user_data.clear()
        return await message.reply_text(
            f"✅ Broadcast complete.\n📨 Sent: {sent}\n❌ Failed: {failed}",
            reply_markup=back_button("admin_menu"))

    # RBC Admin states
    if state == "RS_ADMIN_MASTER_KEY":
        key = text.strip()
        if not key.startswith("rbc_"):
            return await message.reply_text("❌ RBC master key must start with <code>rbc_</code>.",
                                            parse_mode="HTML")
        set_rs_setting("rbc_master_key", key)
        context.user_data.clear()
        return await message.reply_text("✅ RBC master key saved.",
                                        reply_markup=back_button("rs_admin"))
    if state == "RS_ADMIN_FAMPAY_KEY":
        if not text:
            return await message.reply_text("❌ Key cannot be empty.")
        set_rs_setting("fampay_api_key", text.strip())
        context.user_data.clear()
        return await message.reply_text("✅ Fampay API key saved.",
                                        reply_markup=back_button("rs_admin"))
    if state == "RS_ADMIN_REDEEM_URL":
        if not text.startswith("http"):
            return await message.reply_text("❌ URL must start with http:// or https://")
        update_setting("redeem_website", text.strip())
        context.user_data.clear()
        return await message.reply_text("✅ Redeem website URL updated.",
                                        reply_markup=back_button("rs_admin"))
    if state == "RS_ADMIN_CP_CREDITS":
        try:
            c = int(text)
            if c <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number of credits.")
        context.user_data.update({"state": "RS_ADMIN_CP_PRICE", "rs_cp_credits": c})
        return await message.reply_text("💰 Now send the wholesale price in ₹.")
    if state == "RS_ADMIN_CP_PRICE":
        try:
            price = int(text)
            if price <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        credits_val = context.user_data["rs_cp_credits"]
        with db() as conn:
            cur = conn.execute("""INSERT INTO reseller_credit_packages
                (credits, wholesale_price) VALUES (?, ?)""", (credits_val, price))
            new_pid = cur.lastrowid
        context.user_data.clear()
        return await message.reply_text(
            f"✅ Credit package created.\n\n"
            f"<b>PID</b> <code>{mono(new_pid)}</code>  •  "
            f"<b>{credits_val} Credits</b>  •  <b>₹{price}</b>",
            reply_markup=back_button("rs_admin_credit_pkgs"), parse_mode="HTML")
    if state == "RS_ADMIN_CP_EDIT_PRICE":
        try:
            price = int(text)
            if price <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        with db() as conn:
            conn.execute("""UPDATE reseller_credit_packages SET wholesale_price = ?
                WHERE id = ?""", (price, context.user_data["rs_cp_id"]))
        context.user_data.clear()
        return await message.reply_text("✅ Wholesale price updated.",
                                        reply_markup=back_button("rs_admin_credit_pkgs"))
    if state == "RS_ADMIN_BC_CUSTOM_CREDITS":
        try:
            c = int(text)
            if c <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        context.user_data.update({"state": "RS_ADMIN_BC_CODES", "rs_bc_credits": c})
        # ensure matching reseller package exists
        sync_retail_to_reseller()
        with db() as conn:
            exists = conn.execute(
                "SELECT 1 FROM reseller_credit_packages WHERE credits = ?", (c,)).fetchone()
            if not exists:
                conn.execute("""INSERT INTO reseller_credit_packages (credits, wholesale_price)
                    VALUES (?, ?)""", (c, max(1, int(c * 70))))
        return await message.reply_text(
            f"🎁 Send coupon codes for <b>{c}</b> credits (one per line or comma-separated).",
            parse_mode="HTML")
    if state == "RS_ADMIN_BC_CODES":
        raw = text.replace(",", "\n")
        codes = [c.strip() for c in raw.splitlines() if c.strip()]
        if not codes:
            return await message.reply_text("❌ No codes found in message.")
        credits = int(context.user_data.get("rs_bc_credits", 0))
        with db() as conn:
            pkg = conn.execute("SELECT id FROM packages WHERE credits = ? LIMIT 1",
                               (credits,)).fetchone()
            pkg_id = int(pkg["id"]) if pkg else 0
        added = skipped = 0
        with db() as conn:
            for c in codes:
                try:
                    conn.execute("""INSERT INTO coupons(package_id, code, credits)
                        VALUES (?, ?, ?)""", (pkg_id, c, credits))
                    added += 1
                except sqlite3.IntegrityError:
                    skipped += 1
        context.user_data.clear()
        return await message.reply_text(
            f"✅ Added <b>{added}</b> coupons ({credits} credits each).\n"
            f"⏭ Skipped duplicates: {skipped}",
            reply_markup=back_button("rs_admin"))
    if state == "RS_ADMIN_EDIT_GLORY":
        try:
            v = int(text)
            if v <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        set_rs_setting("glory_cost", str(v))
        context.user_data.clear()
        return await message.reply_text(f"✅ Glory cost set to ₹{v}.",
                                        reply_markup=back_button("rs_admin_pricing"))
    if state == "RS_ADMIN_EDIT_MAXBOTS":
        try:
            v = int(text)
            if v <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        set_rs_setting("max_bots", str(v))
        context.user_data.clear()
        return await message.reply_text(f"✅ Max bots set to {v}.",
                                        reply_markup=back_button("rs_admin_pricing"))
    if state == "RS_ADMIN_EDIT_MINBAL":
        try:
            v = int(text)
            if v <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        set_rs_setting("min_add_balance", str(v))
        context.user_data.clear()
        return await message.reply_text(f"✅ Min add balance set to ₹{v}.",
                                        reply_markup=back_button("rs_admin_pricing"))
    if state == "RS_ADMIN_AL_ADD_PKG":
        pkg = text.strip()
        if not pkg:
            return await message.reply_text("❌ Package name cannot be empty.")
        with db() as conn:
            exists = conn.execute("SELECT 1 FROM autolike_pricing WHERE package = ?", (pkg,)).fetchone()
        if exists:
            return await message.reply_text("❌ Package already exists.")
        context.user_data.update({"state": "RS_ADMIN_AL_ADD_PRICE", "rs_al_new_pkg": pkg})
        return await message.reply_text(f"💰 Now send the price in ₹ for <b>{esc(pkg)}</b>.",
                                        parse_mode="HTML")
    if state == "RS_ADMIN_AL_ADD_PRICE":
        try:
            price = int(text)
            if price <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        with db() as conn:
            conn.execute("INSERT INTO autolike_pricing(package, price) VALUES (?, ?)",
                         (context.user_data["rs_al_new_pkg"], price))
        context.user_data.clear()
        return await message.reply_text("✅ Package added.",
                                        reply_markup=back_button("rs_admin_autolike"))
    if state == "RS_ADMIN_AL_EDIT_PRICE":
        try:
            price = int(text)
            if price <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        with db() as conn:
            conn.execute("UPDATE autolike_pricing SET price = ? WHERE package = ?",
                         (price, context.user_data["rs_al_pkg"]))
        context.user_data.clear()
        return await message.reply_text("✅ Price updated.",
                                        reply_markup=back_button("rs_admin_autolike"))
    if state == "RS_ADMIN_WAITING_BAL_UID":
        try:
            uid = int(text)
        except ValueError:
            return await message.reply_text("❌ Invalid Telegram ID.")
        ensure_reseller_user(uid)
        bal = get_reseller_balance(uid)
        context.user_data["rs_admin_bal_uid"] = uid
        context.user_data["state"] = "RS_ADMIN_BAL_ACTION"
        return await message.reply_text(
            f"💰  <b>User</b>  •  <code>{uid}</code>\n"
            f"Current balance  •  <b><code>{mono('₹' + str(bal))}</code></b>\n\nChoose an action:",
            reply_markup=InlineKeyboardMarkup([
                [_mk_rbtn("➕ Add", "rs_admin_bal_add", style="success"),
                 _mk_rbtn("➖ Remove", "rs_admin_bal_remove", style="danger")],
                [_mk_rbtn("✏️ Set Exact", "rs_admin_bal_set", style="primary")],
                [_mk_rbtn("🔙 Cancel", "rs_admin", style="primary")],
            ]), parse_mode="HTML")
    if state == "RS_ADMIN_BAL_ADD_AMT":
        try:
            amt = int(text)
            if amt <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        uid = context.user_data.get("rs_admin_bal_uid")
        new_bal = credit_reseller_balance(uid, amt, reason="Admin credit")
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"💰 <b>Balance Added</b>\n+ <code>{mono('₹' + str(amt))}</code>\n"
                     f"New Balance  •  <b><code>{mono('₹' + str(new_bal))}</code></b>",
                parse_mode="HTML")
        except Exception:
            pass
        context.user_data.clear()
        return await message.reply_text(f"✅ Added ₹{amt}. New balance: ₹{new_bal}.",
                                        reply_markup=back_button("rs_admin"))
    if state == "RS_ADMIN_BAL_REMOVE_AMT":
        try:
            amt = int(text)
            if amt <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a positive whole number.")
        uid = context.user_data.get("rs_admin_bal_uid")
        cur = get_reseller_balance(uid)
        if amt > cur:
            return await message.reply_text(f"❌ Cannot remove more than current balance ₹{cur}.")
        new_bal = set_reseller_balance(uid, cur - amt, reason="Admin debit")
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"⚠️ <b>Balance Removed</b>\n- <code>{mono('₹' + str(amt))}</code>\n"
                     f"New Balance  •  <b><code>{mono('₹' + str(new_bal))}</code></b>",
                parse_mode="HTML")
        except Exception:
            pass
        context.user_data.clear()
        return await message.reply_text(f"✅ Removed ₹{amt}. New balance: ₹{new_bal}.",
                                        reply_markup=back_button("rs_admin"))
    if state == "RS_ADMIN_BAL_SET_AMT":
        try:
            v = int(text)
            if v < 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Send a non-negative whole number.")
        uid = context.user_data.get("rs_admin_bal_uid")
        new_bal = set_reseller_balance(uid, v, reason="Admin set exact")
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"💰 <b>Balance Updated</b>\nNew Balance  •  "
                     f"<b><code>{mono('₹' + str(new_bal))}</code></b>",
                parse_mode="HTML")
        except Exception:
            pass
        context.user_data.clear()
        return await message.reply_text(f"✅ Balance set to ₹{new_bal}.",
                                        reply_markup=back_button("rs_admin"))
    if state == "RS_ADMIN_BROADCAST":
        with db() as conn:
            users = [row["user_id"] for row in conn.execute("SELECT user_id FROM users")]
        sent = failed = 0
        for user_id in set(users):
            try:
                await message.copy(chat_id=user_id)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        context.user_data.clear()
        return await message.reply_text(
            f"✅ Broadcast complete.\n📨 Sent: {sent}\n❌ Failed: {failed}",
            reply_markup=back_button("rs_admin"))


# ═══════════════════════════════════════════════════════════════════
#  DAILY SCHEDULER
# ═══════════════════════════════════════════════════════════════════
async def process_daily_updates(application):
    today = now_ist().date()
    with db() as conn:
        services = conn.execute("SELECT * FROM autolike_services WHERE status = 'active'").fetchall()
        for service in services:
            expiry = datetime.fromisoformat(service["expiry_date"]).date()
            if expiry <= today:
                conn.execute("""UPDATE autolike_services SET status = 'expired',
                    remaining_days = 0 WHERE id = ?""", (service["id"],))
                continue
            try:
                conn.execute("BEGIN")
                before = int(service["current_likes"])
                likes_given = int(service["likes_per_day"] or DAILY_LIKES)
                after = before + likes_given
                days_left = max(0, (expiry - today).days)
                inserted = conn.execute("""INSERT OR IGNORE INTO autolike_daily_updates
                    (service_id, update_date, before_likes, likes_given, after_likes, days_left)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                                       (service["id"], today.isoformat(), before,
                                        likes_given, after, days_left)).rowcount
                if not inserted:
                    conn.rollback()
                    continue
                conn.execute("""UPDATE autolike_services SET current_likes = ?, remaining_days = ?
                    WHERE id = ?""", (after, days_left, service["id"]))
                conn.commit()
            except Exception:
                conn.rollback()
                logger.exception("Daily update failed for service %s", service["id"])
                continue

            try:
                await application.bot.send_message(
                    chat_id=service["telegram_user_id"],
                    text=(f"🔥  <b>{double('MANUAL LIKE SUCCESS')}</b>\n"
                          f"<b>{DIVIDER}</b>\n"
                          f"🎮  Player     •  {esc(service['player_name'] or 'Not set')}\n"
                          f"🌍  Region     •  {esc(service['region'])}\n"
                          f"🆔  UID        •  <code>{esc(service['uid'])}</code>\n"
                          f"👍  Before     •  <code>{mono(before)}</code>\n"
                          f"🚀  After      •  <code>{mono(after)}</code>\n"
                          f"🎯  Given      •  <code>{mono(likes_given)}</code>\n"
                          f"⏳  Days Left  •  <code>{mono(days_left)}</code>\n"
                          f"<b>{DIVIDER}</b>\n"
                          f"👑  OWNER - {esc(owner_name())}"),
                    parse_mode="HTML")
            except Exception:
                logger.exception("Could not notify user %s", service["telegram_user_id"])


async def daily_scheduler(application):
    while True:
        current = now_ist()
        target = current.replace(hour=4, minute=0, second=0, microsecond=0)
        if target <= current:
            target += timedelta(days=1)
        await asyncio.sleep(max(1, (target - current).total_seconds()))
        await process_daily_updates(application)


# ═══════════════════════════════════════════════════════════════════
#  GLOBAL ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, telegram.error.BadRequest):
        error_msg = str(context.error).lower()
        if "query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.warning("Ignored expired callback query in global handler.")
            return
    logger.error("Exception while handling an update:", exc_info=context.error)


# ═══════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set.")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reseller", handle_message))
    application.add_handler(CommandHandler("admin", handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    application.add_error_handler(global_error_handler)

    await application.initialize()
    await application.start()

    http_runner = await start_http_server()

    await application.updater.start_polling()
    scheduler = asyncio.create_task(daily_scheduler(application))

    logger.info("✅ Bot started. Public URL: %s", detect_public_url())
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        scheduler.cancel()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await http_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")