"""
database.py — HTTP-клиент к FastAPI-серверу.
Интерфейс полностью совпадает со старым database.py (SQLite),
остальной код приложения не изменяется.
"""
import threading
from typing import Optional

import requests
import urllib3

from config import SERVER_URL, CONTACT_PERSON

# Подавляем предупреждение о самоподписанном сертификате
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_session = requests.Session()
_cert_path: Optional[str] = None  # путь к cert.pem; если None — verify=False


def _verify():
    return _cert_path if _cert_path else False


def set_token(token: str) -> None:
    """Установить JWT-токен для всех последующих запросов."""
    _session.headers.update({"Authorization": f"Bearer {token}"})


def set_cert(path: str) -> None:
    """Указать путь к SSL-сертификату сервера для проверки."""
    global _cert_path
    _cert_path = path


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _get(path: str, **params):
    r = _session.get(f"{SERVER_URL}{path}", params=params, verify=_verify(), timeout=20)
    r.raise_for_status()
    return r.json()


def _post(path: str, data: dict = None):
    r = _session.post(f"{SERVER_URL}{path}", json=data or {}, verify=_verify(), timeout=20)
    r.raise_for_status()
    return r.json()


def _put(path: str, data: dict):
    r = _session.put(f"{SERVER_URL}{path}", json=data, verify=_verify(), timeout=20)
    r.raise_for_status()
    return r.json()


def _delete(path: str, data: dict = None):
    r = _session.delete(f"{SERVER_URL}{path}", json=data or {}, verify=_verify(), timeout=20)
    r.raise_for_status()
    return r.json()


# ─── INIT (no-op: сервер управляет БД) ──────────────────────────────────────

def init_db() -> None:
    """Проверить доступность сервера."""
    r = requests.get(f"{SERVER_URL}/health", verify=_verify(), timeout=10)
    r.raise_for_status()


# ─── CONTACTS ────────────────────────────────────────────────────────────────

def get_contacts_raw(status_filter: str = "", type_filter: str = "",
                     hide_irrelevant: bool = False,
                     date_from: str = "", date_to: str = "") -> list[dict]:
    """Возвращает расшифрованные контакты (сервер расшифровывает)."""
    return _get("/contacts",
                status_filter=status_filter,
                type_filter=type_filter,
                hide_irrelevant=hide_irrelevant,
                date_from=date_from,
                date_to=date_to)


def decrypt_contact(raw: dict) -> dict:
    """Сервер уже вернул расшифрованные данные — просто передаём дальше."""
    return raw


def get_contacts(search: str = "", status_filter: str = "",
                 type_filter: str = "", hide_irrelevant: bool = False,
                 date_from: str = "", date_to: str = "") -> list[dict]:
    contacts = get_contacts_raw(
        status_filter=status_filter, type_filter=type_filter,
        hide_irrelevant=hide_irrelevant, date_from=date_from, date_to=date_to,
    )
    if not search:
        return contacts
    s = search.lower()
    return [c for c in contacts
            if s in c["name"].lower()
            or s in c["phone"].lower()
            or s in c["company"].lower()]


def get_contacts_count() -> dict:
    return _get("/contacts/count")


def create_contact(name: str, phone: str, company: str, comment: str,
                   user_id: int, position: str = "",
                   contact_type: str = CONTACT_PERSON) -> int:
    result = _post("/contacts", {
        "name": name, "phone": phone, "company": company,
        "comment": comment, "position": position, "contact_type": contact_type,
    })
    return result["id"]


def update_contact(contact_id: int, name: str, phone: str, company: str,
                   comment: str, position: str = "",
                   contact_type: str = CONTACT_PERSON) -> None:
    _put(f"/contacts/{contact_id}", {
        "name": name, "phone": phone, "company": company,
        "comment": comment, "position": position, "contact_type": contact_type,
    })


def mark_called(contact_id: int, status: str, call_result: str, user_id: int,
                callback_datetime: str = "") -> None:
    _post(f"/contacts/{contact_id}/call",
          {"status": status, "call_result": call_result,
           "callback_datetime": callback_datetime})


def delete_contacts_bulk(ids: list[int]) -> None:
    _delete("/contacts", {"ids": ids})


def import_contacts_bulk(rows: list[dict], user_id: int) -> int:
    result = _post("/contacts/import", {"rows": rows})
    return result["count"]


def get_stats(date_from: str = "", date_to: str = "") -> dict:
    return _get("/stats", date_from=date_from, date_to=date_to)


def get_pending_reminders() -> list:
    try:
        return _get("/contacts/reminders")
    except Exception:
        return []


def get_duplicates() -> list:
    return _get("/contacts/duplicates")


def merge_contacts(keep_id: int, delete_ids: list) -> int:
    result = _post("/contacts/merge", {"keep_id": keep_id, "delete_ids": delete_ids})
    return result["count"]


def fix_bitrix_company_fields() -> int:
    result = _post("/contacts/fix-bitrix")
    return result["count"]


# ─── USERS ───────────────────────────────────────────────────────────────────

def get_all_users() -> list:
    return _get("/users")


def create_user(username: str, password_hash: str, role: str, full_name: str) -> int:
    result = _post("/users", {
        "username": username, "password_hash": password_hash,
        "role": role, "full_name": full_name,
    })
    return result["id"]


def update_user(user_id: int, full_name: str, role: str, active: int,
                password_hash: Optional[str] = None) -> None:
    _put(f"/users/{user_id}", {
        "full_name": full_name, "role": role, "active": active,
        "password_hash": password_hash,
    })


def delete_user(user_id: int) -> None:
    _delete(f"/users/{user_id}")


# ─── AUDIT ───────────────────────────────────────────────────────────────────

def get_audit_log(limit: int = 500) -> list:
    return _get("/audit", limit=limit)


def log_action(user_id: int, action: str, details: str = "") -> None:
    """Отправка записи в лог — асинхронно, не блокирует UI."""
    def _send():
        try:
            _post("/log", {"action": action, "details": details})
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()


# ─── STUBS (больше не нужны, но сохранены для совместимости) ─────────────────

def get_user_by_username(username: str):
    return None  # логин через /login


def get_user_by_session_token(token: str):
    return None  # JWT не хранится в БД


def set_session_token(user_id: int, token: str) -> None:
    pass


def clear_session_token(user_id: int) -> None:
    pass


def get_connection():
    raise RuntimeError("Прямое подключение к БД недоступно — используйте API-сервер")
