"""
database.py — SQLite база данных: схема, подключение, CRUD операции
"""
import sqlite3
import os
import threading
from datetime import datetime
from typing import Optional

from config import DB_PATH, ROLE_OWNER, ROLE_ADMIN, STATUS_NEW, STATUS_HIDDEN_FROM_MANAGERS, CONTACT_PERSON
import crypto


def _invalidate_decrypt_cache() -> None:
    """Сбросить кэш расшифровки после изменения данных."""
    crypto.decrypt.cache_clear()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Создать таблицы если не существуют, добавить владельца по умолчанию."""
    crypto.init_crypto()
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE,
                password    TEXT    NOT NULL,
                role        TEXT    NOT NULL DEFAULT 'specialist',
                full_name   TEXT    DEFAULT '',
                active      INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL DEFAULT '',
                phone        TEXT    NOT NULL,
                company      TEXT    DEFAULT '',
                position     TEXT    DEFAULT '',
                contact_type TEXT    NOT NULL DEFAULT 'person',
                comment     TEXT    DEFAULT '',
                status      TEXT    NOT NULL DEFAULT 'new',
                call_result TEXT    DEFAULT '',
                called_by   INTEGER REFERENCES users(id),
                call_date   TEXT    DEFAULT '',
                created_at  TEXT    NOT NULL,
                created_by  INTEGER REFERENCES users(id),
                is_deleted  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER REFERENCES users(id),
                action      TEXT    NOT NULL,
                details     TEXT    DEFAULT '',
                ts          TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_contacts_deleted ON contacts(is_deleted);
            CREATE INDEX IF NOT EXISTS idx_contacts_status  ON contacts(status);
            CREATE INDEX IF NOT EXISTS idx_audit_ts         ON audit_log(ts);
        """)
        conn.commit()

        # WAL + быстрая запись — устанавливается один раз, сохраняется в файле БД
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.commit()

        # Миграции для старых БД
        for migration in [
            "ALTER TABLE contacts ADD COLUMN position TEXT DEFAULT ''",
            "ALTER TABLE contacts ADD COLUMN contact_type TEXT NOT NULL DEFAULT 'person'",
            "ALTER TABLE users ADD COLUMN session_token TEXT DEFAULT NULL",
            "CREATE INDEX IF NOT EXISTS idx_users_session ON users(session_token)",
        ]:
            try:
                conn.execute(migration)
                conn.commit()
            except Exception:
                pass  # Колонка уже существует

        # Создать владельца по умолчанию если пользователей нет
        cur = conn.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            _create_default_owner(conn)
    finally:
        conn.close()


def _create_default_owner(conn: sqlite3.Connection) -> None:
    """Создать учётную запись owner/owner при первом запуске."""
    import bcrypt
    pw_hash = bcrypt.hashpw("owner".encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT INTO users (username, password, role, full_name, active, created_at) VALUES (?,?,?,?,1,?)",
        ("owner", pw_hash, ROLE_OWNER, "Владелец (по умолчанию)", _now())
    )
    conn.commit()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─── USERS ─────────────────────────────────────────────────────────────────

def get_user_by_session_token(token: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE session_token=? AND active=1", (token,)
        ).fetchone()
    finally:
        conn.close()


def set_session_token(user_id: int, token: str) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET session_token=? WHERE id=?", (token, user_id))
        conn.commit()
    finally:
        conn.close()


def clear_session_token(user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET session_token=NULL WHERE id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (username,)
        ).fetchone()
    finally:
        conn.close()


def get_all_users() -> list:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM users ORDER BY role, username"
        ).fetchall()
    finally:
        conn.close()


def create_user(username: str, password_hash: str, role: str, full_name: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password, role, full_name, active, created_at) VALUES (?,?,?,?,1,?)",
            (username, password_hash, role, full_name, _now())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_user(user_id: int, full_name: str, role: str, active: int,
                password_hash: Optional[str] = None) -> None:
    conn = get_connection()
    try:
        if password_hash:
            conn.execute(
                "UPDATE users SET full_name=?, role=?, active=?, password=? WHERE id=?",
                (full_name, role, active, password_hash, user_id)
            )
        else:
            conn.execute(
                "UPDATE users SET full_name=?, role=?, active=? WHERE id=?",
                (full_name, role, active, user_id)
            )
        conn.commit()
    finally:
        conn.close()


def delete_user(user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()


# ─── CONTACTS ──────────────────────────────────────────────────────────────

def _encrypt_contact(name: str, phone: str, company: str) -> tuple:
    return crypto.encrypt(name), crypto.encrypt(phone), crypto.encrypt(company)


def _decrypt_row(row: sqlite3.Row) -> dict:
    """Превратить Row в dict с расшифрованными полями."""
    d = dict(row)
    d["name"] = crypto.decrypt(d.get("name", ""))
    d["phone"] = crypto.decrypt(d.get("phone", ""))
    d["company"] = crypto.decrypt(d.get("company", ""))
    return d


def _contacts_where(status_filter: str, type_filter: str,
                    hide_irrelevant: bool, date_from: str, date_to: str):
    where = "WHERE c.is_deleted=0"
    params: list = []
    if status_filter:
        where += " AND c.status=?"
        params.append(status_filter)
    elif hide_irrelevant:
        placeholders = ",".join("?" * len(STATUS_HIDDEN_FROM_MANAGERS))
        where += f" AND c.status NOT IN ({placeholders})"
        params.extend(STATUS_HIDDEN_FROM_MANAGERS)
    if type_filter:
        where += " AND c.contact_type=?"
        params.append(type_filter)
    if date_from:
        where += " AND c.call_date >= ?"
        params.append(date_from)
    if date_to:
        where += " AND c.call_date <= ?"
        params.append(date_to + " 23:59:59")
    return where, params


_CONTACTS_SQL = (
    "SELECT c.*, u.full_name as caller_name, u.username as caller_username "
    "FROM contacts c LEFT JOIN users u ON c.called_by = u.id "
    "{where} ORDER BY c.call_date DESC, c.id DESC"
)


def get_contacts_raw(status_filter: str = "", type_filter: str = "",
                     hide_irrelevant: bool = False,
                     date_from: str = "", date_to: str = "") -> list[dict]:
    """Получить контакты из БД без расшифровки (поля зашифрованы)."""
    where, params = _contacts_where(status_filter, type_filter, hide_irrelevant, date_from, date_to)
    conn = get_connection()
    try:
        rows = conn.execute(_CONTACTS_SQL.format(where=where), params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def decrypt_contact(raw: dict) -> dict:
    """Расшифровать поля одного контакта (результат get_contacts_raw)."""
    return _decrypt_row(raw)


def get_contacts(search: str = "", status_filter: str = "",
                 type_filter: str = "", hide_irrelevant: bool = False,
                 date_from: str = "", date_to: str = "") -> list[dict]:
    where, params = _contacts_where(status_filter, type_filter, hide_irrelevant, date_from, date_to)
    conn = get_connection()
    try:
        rows = conn.execute(_CONTACTS_SQL.format(where=where), params).fetchall()
    finally:
        conn.close()

    if not search:
        return [_decrypt_row(r) for r in rows]

    s = search.lower()
    result = []
    for row in rows:
        d = _decrypt_row(row)
        if s in d["name"].lower() or s in d["phone"].lower() or s in d["company"].lower():
            result.append(d)
    return result


def get_contact_by_id(contact_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM contacts WHERE id=? AND is_deleted=0", (contact_id,)
        ).fetchone()
    finally:
        conn.close()
    if row:
        return _decrypt_row(row)
    return None


def create_contact(name: str, phone: str, company: str,
                   comment: str, user_id: int, position: str = "",
                   contact_type: str = CONTACT_PERSON) -> int:
    enc_name, enc_phone, enc_company = _encrypt_contact(name, phone, company)
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO contacts (name, phone, company, position, contact_type, comment, status, created_at, created_by) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (enc_name, enc_phone, enc_company, position, contact_type, comment, STATUS_NEW, _now(), user_id)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_contact(contact_id: int, name: str, phone: str,
                   company: str, comment: str, position: str = "",
                   contact_type: str = CONTACT_PERSON) -> None:
    enc_name, enc_phone, enc_company = _encrypt_contact(name, phone, company)
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE contacts SET name=?, phone=?, company=?, position=?, contact_type=?, comment=? WHERE id=?",
            (enc_name, enc_phone, enc_company, position, contact_type, comment, contact_id)
        )
        conn.commit()
    finally:
        conn.close()
    _invalidate_decrypt_cache()


def mark_called(contact_id: int, status: str, call_result: str, user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE contacts SET status=?, call_result=?, called_by=?, call_date=? WHERE id=?",
            (status, call_result, user_id, _now(), contact_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_contact(contact_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE contacts SET is_deleted=1 WHERE id=?", (contact_id,)
        )
        conn.commit()
    finally:
        conn.close()


def delete_contacts_bulk(ids: list[int]) -> None:
    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE contacts SET is_deleted=1 WHERE id IN ({placeholders})", ids
        )
        conn.commit()
    finally:
        conn.close()


def import_contacts_bulk(rows: list[dict], user_id: int) -> int:
    """Массовый импорт. rows: список {name, phone, company, position, contact_type, comment}. Возвращает кол-во добавленных."""
    conn = get_connection()
    count = 0
    try:
        for r in rows:
            phone = r.get("phone", "").strip()
            if not phone:
                continue
            enc_name, enc_phone, enc_company = _encrypt_contact(
                r.get("name", "").strip(),
                phone,
                r.get("company", "").strip()
            )
            conn.execute(
                "INSERT INTO contacts (name, phone, company, position, contact_type, comment, status, created_at, created_by) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (enc_name, enc_phone, enc_company,
                 r.get("position", "").strip(),
                 r.get("contact_type", CONTACT_PERSON),
                 r.get("comment", "").strip(),
                 STATUS_NEW, _now(), user_id)
            )
            count += 1
        conn.commit()
    finally:
        conn.close()
    if count:
        _invalidate_decrypt_cache()
    return count


def fix_bitrix_company_fields() -> int:
    """
    Исправить контакты, где company содержит метку типа из Битрикса
    ("Юр. лицо" / "Физ. лицо") вместо реального названия.
    Меняет местами company ↔ position и очищает position.
    Возвращает количество исправленных записей.
    """
    _TYPE_LABELS = {"юр. лицо", "физ. лицо"}
    conn = get_connection()
    fixed = 0
    try:
        rows = conn.execute(
            "SELECT id, name, company, position FROM contacts WHERE is_deleted=0"
        ).fetchall()
        for row in rows:
            company_dec = crypto.decrypt(row["company"])
            if company_dec.strip().lower() not in _TYPE_LABELS:
                continue
            # company содержит метку типа, position — реальное название
            new_company = row["position"] or ""
            new_position = ""
            enc_new_company = crypto.encrypt(new_company) if new_company else ""
            conn.execute(
                "UPDATE contacts SET company=?, position=? WHERE id=?",
                (enc_new_company, new_position, row["id"])
            )
            fixed += 1
        if fixed:
            conn.commit()
    finally:
        conn.close()
    if fixed:
        _invalidate_decrypt_cache()
    return fixed


def get_contacts_count() -> dict:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM contacts WHERE is_deleted=0 GROUP BY status"
        ).fetchall()
    finally:
        conn.close()
    return {r["status"]: r["cnt"] for r in rows}


# ─── AUDIT LOG ─────────────────────────────────────────────────────────────

def log_action(user_id: int, action: str, details: str = "") -> None:
    """Запись в лог — асинхронно, не блокирует UI."""
    ts = _now()
    def _write():
        try:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO audit_log (user_id, action, details, ts) VALUES (?,?,?,?)",
                    (user_id, action, details, ts)
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass
    threading.Thread(target=_write, daemon=True).start()


def get_audit_log(limit: int = 500) -> list:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT a.ts, u.username, u.full_name, a.action, a.details "
            "FROM audit_log a "
            "LEFT JOIN users u ON a.user_id = u.id "
            "ORDER BY a.ts DESC LIMIT ?",
            (limit,)
        ).fetchall()
    finally:
        conn.close()
