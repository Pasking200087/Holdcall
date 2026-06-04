"""
auth.py — Аутентификация через JWT (FastAPI-сервер).
"""
import json
import os
from typing import Optional

import bcrypt
import jwt
import requests
import urllib3

from config import ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_SPECIALIST, SESSION_PATH, SERVER_URL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_VERIFY = False  # cert.pem подставляется через set_cert()
_cert_path: Optional[str] = None


def set_cert(path: str) -> None:
    global _VERIFY, _cert_path
    _cert_path = path
    _VERIFY = path


def _verify():
    return _cert_path if _cert_path else False


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


# ─── SESSION ─────────────────────────────────────────────────────────────────

class Session:
    """Глобальная сессия текущего пользователя."""
    user_id: Optional[int] = None
    username: str = ""
    full_name: str = ""
    role: str = ""
    _jwt_token: str = ""

    @classmethod
    def login_from_payload(cls, payload: dict, token: str) -> None:
        import database as db
        cls.user_id   = int(payload["sub"])
        cls.username  = payload["username"]
        cls.full_name = payload.get("full_name") or payload["username"]
        cls.role      = payload["role"]
        cls._jwt_token = token
        db.set_token(token)

    @classmethod
    def logout(cls) -> None:
        cls.user_id = None
        cls.username = ""
        cls.full_name = ""
        cls.role = ""
        cls._jwt_token = ""

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


# ─── AUTO LOGIN ──────────────────────────────────────────────────────────────

def try_auto_login() -> bool:
    """Автовход по сохранённому JWT. Проверяет токен у сервера."""
    username, token = _load_local_token()
    if not username or not token:
        return False
    try:
        r = requests.get(
            f"{SERVER_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            verify=_verify(), timeout=10,
        )
        if r.status_code != 200:
            _clear_local_token()
            return False
        user = r.json()
        # Декодируем payload (без проверки подписи — она уже проверена сервером)
        payload = jwt.decode(token, options={"verify_signature": False})
        Session.login_from_payload(payload, token)
        import database as db
        db.log_action(Session.user_id, "AUTO_LOGIN", f"Автовход: {username}")
        return True
    except Exception:
        _clear_local_token()
        return False


# ─── VERIFY LOGIN ────────────────────────────────────────────────────────────

def verify_login(username: str, password: str) -> tuple[bool, str]:
    """Логин через сервер. Возвращает (True, "") или (False, "сообщение")."""
    if not username or not password:
        return False, "Введите логин и пароль"
    try:
        r = requests.post(
            f"{SERVER_URL}/login",
            json={"username": username.strip(), "password": password},
            verify=_verify(), timeout=10,
        )
    except requests.exceptions.ConnectionError:
        return False, f"Нет связи с сервером.\nПроверьте интернет-подключение.\n({SERVER_URL})"
    except requests.exceptions.Timeout:
        return False, "Сервер не отвечает (таймаут). Попробуйте позже."
    except Exception as e:
        return False, f"Ошибка соединения: {e}"

    if r.status_code == 401:
        return False, "Неверный логин или пароль"
    if r.status_code != 200:
        return False, f"Ошибка сервера: {r.status_code}"

    data = r.json()
    token = data["token"]
    payload = jwt.decode(token, options={"verify_signature": False})
    Session.login_from_payload(payload, token)

    import database as db
    db.log_action(Session.user_id, "LOGIN", f"Вход: {username}")
    _save_local_token(username, token)
    return True, ""


# ─── LOGOUT ──────────────────────────────────────────────────────────────────

def logout() -> None:
    if Session.is_logged_in():
        try:
            import database as db
            db.log_action(Session.user_id, "LOGOUT", "Выход из системы")
        except Exception:
            pass
    _clear_local_token()
    Session.logout()


# ─── CHANGE PASSWORD ─────────────────────────────────────────────────────────

def change_password(user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
    if len(new_password) < 4:
        return False, "Новый пароль должен быть не менее 4 символов"
    try:
        r = requests.put(
            f"{SERVER_URL}/users/{user_id}/password",
            json={"old_password": old_password, "new_password": new_password},
            headers={"Authorization": f"Bearer {Session._jwt_token}"},
            verify=_verify(), timeout=10,
        )
    except Exception as e:
        return False, f"Ошибка соединения: {e}"

    if r.status_code == 400:
        return False, r.json().get("detail", "Ошибка")
    if r.status_code != 200:
        return False, f"Ошибка сервера: {r.status_code}"
    return True, ""


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Хэширует пароль на клиенте (bcrypt) — для create_user / update_user."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
