"""
auth.py — Аутентификация и управление сессией
"""
import bcrypt
import json
import os
import secrets
from typing import Optional
from config import ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_SPECIALIST, SESSION_PATH
import database as db


# ─── ЛОКАЛЬНАЯ СЕССИЯ ────────────────────────────────────────────────────────

def _save_local_token(username: str, token: str) -> None:
    os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump({"username": username, "token": token}, f)


def _load_local_token() -> tuple[Optional[str], Optional[str]]:
    try:
        with open(SESSION_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("username"), data.get("token")
    except Exception:
        return None, None


def _clear_local_token() -> None:
    try:
        os.remove(SESSION_PATH)
    except Exception:
        pass


def try_auto_login() -> bool:
    """Попытаться войти автоматически по сохранённому токену. Возвращает True при успехе."""
    username, token = _load_local_token()
    if not username or not token:
        return False
    row = db.get_user_by_session_token(token)
    if row is None or row["username"] != username:
        _clear_local_token()
        return False
    Session.login(row)
    db.log_action(row["id"], "AUTO_LOGIN", f"Автовход: {username}")
    return True


def logout() -> None:
    """Выйти: очистить токен в БД и локальный файл сессии."""
    if Session.is_logged_in():
        db.clear_session_token(Session.user_id)
    _clear_local_token()
    Session.logout()


class Session:
    """Глобальная сессия текущего пользователя."""
    user_id: Optional[int] = None
    username: str = ""
    full_name: str = ""
    role: str = ""

    @classmethod
    def login(cls, row) -> None:
        cls.user_id = row["id"]
        cls.username = row["username"]
        cls.full_name = row["full_name"] or row["username"]
        cls.role = row["role"]

    @classmethod
    def logout(cls) -> None:
        cls.user_id = None
        cls.username = ""
        cls.full_name = ""
        cls.role = ""

    @classmethod
    def is_logged_in(cls) -> bool:
        return cls.user_id is not None

    @classmethod
    def is_owner(cls) -> bool:
        return cls.role == ROLE_OWNER

    @classmethod
    def is_admin_or_above(cls) -> bool:
        return cls.role in (ROLE_OWNER, ROLE_ADMIN)

    @classmethod
    def can_add_contact(cls) -> bool:
        return cls.role in (ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_SPECIALIST)

    @classmethod
    def display_role(cls) -> str:
        from config import ROLE_LABELS
        return ROLE_LABELS.get(cls.role, cls.role)


def verify_login(username: str, password: str) -> tuple[bool, str]:
    """
    Проверить логин/пароль.
    Возвращает (True, "") при успехе или (False, "сообщение") при ошибке.
    """
    if not username or not password:
        return False, "Введите логин и пароль"

    row = db.get_user_by_username(username.strip())
    if row is None:
        return False, "Пользователь не найден или отключён"

    try:
        ok = bcrypt.checkpw(password.encode(), row["password"].encode())
    except Exception:
        return False, "Ошибка проверки пароля"

    if not ok:
        return False, "Неверный пароль"

    Session.login(row)
    db.log_action(row["id"], "LOGIN", f"Вход в систему: {username}")
    token = secrets.token_hex(32)
    db.set_session_token(row["id"], token)
    _save_local_token(username, token)
    return True, ""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def change_password(user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
    conn_row = None
    import sqlite3
    conn = db.get_connection()
    try:
        conn_row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    finally:
        conn.close()

    if conn_row is None:
        return False, "Пользователь не найден"

    if not bcrypt.checkpw(old_password.encode(), conn_row["password"].encode()):
        return False, "Неверный текущий пароль"

    if len(new_password) < 4:
        return False, "Новый пароль должен быть не менее 4 символов"

    new_hash = hash_password(new_password)
    db.update_user(user_id, conn_row["full_name"], conn_row["role"],
                   conn_row["active"], new_hash)
    db.log_action(user_id, "CHANGE_PASSWORD", "Смена пароля")
    return True, ""
