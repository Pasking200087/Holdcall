"""
updater.py -- Автообновление через GitHub Releases
"""
import os
import sys
import json
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.error
from typing import Optional

from config import APP_VERSION, GITHUB_REPO

try:
    from gh_token import GITHUB_TOKEN
except ImportError:
    GITHUB_TOKEN = ""

_API_BASE = "https://api.github.com"
_ASSET_NAME = "baza.exe"
_cached_release: Optional[dict] = None


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except Exception:
        return (0,)


def _get_latest_release() -> Optional[dict]:
    url = f"{_API_BASE}/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def check_update() -> Optional[str]:
    """
    Проверить наличие обновления через GitHub Releases.
    Возвращает строку новой версии или None если обновления нет.
    """
    global _cached_release
    release = _get_latest_release()
    if not release:
        return None
    _cached_release = release
    tag = release.get("tag_name", "")
    new_ver = tag.lstrip("v")
    if _parse_version(new_ver) > _parse_version(APP_VERSION):
        return new_ver
    return None


class _StripAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """При редиректе (на CDN) убирает Authorization, чтобы не получить 404."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req:
            new_req.headers.pop("Authorization", None)
            new_req.headers.pop("authorization", None)
        return new_req


def _download_asset(release: dict, dest_path: str) -> None:
    """Скачать baza.exe из assets релиза (работает с приватным репозиторием)."""
    assets = release.get("assets", [])
    asset = next((a for a in assets if a["name"] == _ASSET_NAME), None)
    if not asset:
        raise RuntimeError(f"Файл {_ASSET_NAME} не найден в релизе")

    # Запрашиваем через API URL с токеном; на редиректе в CDN токен снимается
    api_url = asset["url"]
    req = urllib.request.Request(api_url, headers={
        **_headers(),
        "Accept": "application/octet-stream",
    })
    opener = urllib.request.build_opener(_StripAuthOnRedirect)
    with opener.open(req, timeout=60) as resp:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(resp, f)


def apply_update() -> None:
    """
    Скачать новый exe с GitHub и перезапустить через bat-скрипт.
    Вызывается только из замороженного exe.
    """
    if not getattr(sys, "frozen", False):
        return

    release = _cached_release or _get_latest_release()
    if not release:
        raise RuntimeError("Не удалось получить данные о релизе")

    exe_path = sys.executable
    exe_dir  = os.path.dirname(exe_path)
    new_tmp  = os.path.join(exe_dir, "_baza_new.exe")

    _download_asset(release, new_tmp)

    bat = (
        "@echo off\n"
        "ping 127.0.0.1 -n 3 >nul\n"
        f"move /y \"{new_tmp}\" \"{exe_path}\"\n"
        f"start \"\" \"{exe_path}\"\n"
        "del \"%~f0\"\n"
    )
    bat_path = os.path.join(tempfile.gettempdir(), "baza_update.bat")
    with open(bat_path, "w", encoding="ascii", errors="replace") as f:
        f.write(bat)

    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    sys.exit(0)
