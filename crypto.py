"""
crypto.py — Шифрование данных (Fernet / AES-128)

Ключ генерируется один раз и хранится в baza.key рядом с базой.
Без этого файла данные в baza.db нечитаемы.
"""
import os
from functools import lru_cache
from cryptography.fernet import Fernet
from config import KEY_PATH


_fernet: Fernet | None = None


def init_crypto() -> None:
    """Инициализация: создать ключ если нет, или загрузить существующий."""
    global _fernet
    if not os.path.exists(KEY_PATH):
        key = Fernet.generate_key()
        with open(KEY_PATH, "wb") as f:
            f.write(key)
        # Скрываем атрибут файла на Windows
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(KEY_PATH, 0x02)  # FILE_ATTRIBUTE_HIDDEN
        except Exception:
            pass
    else:
        with open(KEY_PATH, "rb") as f:
            key = f.read()
    _fernet = Fernet(key)


def _get_fernet() -> Fernet:
    if _fernet is None:
        init_crypto()
    return _fernet


def encrypt(value: str) -> str:
    """Зашифровать строку → base64-строка."""
    if not value:
        return value
    return _get_fernet().encrypt(value.encode("utf-8")).decode("ascii")


@lru_cache(maxsize=16384)
def decrypt(token: str) -> str:
    """Расшифровать base64-строку → исходная строка."""
    if not token:
        return token
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:
        return token  # Вернуть как есть если не зашифровано (миграция)


def is_encrypted(value: str) -> bool:
    """Проверить, похоже ли значение на зашифрованное (начинается с 'gAAAAA')."""
    return isinstance(value, str) and value.startswith("gAAAAA")
