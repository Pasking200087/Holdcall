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
    # Репозиторий публичный — токен не нужен для чтения релизов
    return {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


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
    """Скачать baza.exe напрямую по browser_download_url (публичное репо, без токена)."""
    assets = release.get("assets", [])
    asset = next((a for a in assets if a["name"] == _ASSET_NAME), None)
    if not asset:
        raise RuntimeError(f"Файл {_ASSET_NAME} не найден в релизе")

    url = asset["browser_download_url"]
    req = urllib.request.Request(url, headers={"User-Agent": "baza-updater"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(resp, f)


def apply_update() -> None:
    """
    Обновление в два этапа:
    1. Скачиваем новый exe во временную папку на ЛОКАЛЬНОМ диске.
    2. PowerShell копирует его на сетевой диск через robocopy (retry + проверка
       размера). Если сеть не даёт перезаписать файл — запускаем прямо из
       локального temp, сохранив путь к данным в datapath.txt.
    """
    if not getattr(sys, "frozen", False):
        return

    release = _cached_release or _get_latest_release()
    if not release:
        raise RuntimeError("Не удалось получить данные о релизе")

    assets = release.get("assets", [])
    asset = next((a for a in assets if a["name"] == _ASSET_NAME), None)
    expected_size = asset["size"] if asset else 0

    exe_path  = sys.executable
    exe_dir   = os.path.dirname(exe_path)
    exe_name  = os.path.basename(exe_path)
    tmp_dir   = tempfile.gettempdir()
    local_tmp = os.path.join(tmp_dir, "_baza_new.exe")

    _download_asset(release, local_tmp)

    # Сохраняем путь к данным (на случай запуска из локального temp)
    from config import _local_app_dir, DATA_PTR_PATH
    os.makedirs(_local_app_dir, exist_ok=True)
    with open(DATA_PTR_PATH, "w", encoding="utf-8") as f:
        f.write(exe_dir)

    current_pid = os.getpid()

    # PowerShell-скрипт:
    # • ждёт завершения процесса
    # • пробует robocopy (3 попытки) + проверяет размер
    # • при успехе — запускает с сетевого диска и удаляет temp
    # • при неудаче — запускает прямо из temp (путь к данным в datapath.txt)
    ps = f"""
$local_tmp   = "{local_tmp}"
$exe_path    = "{exe_path}"
$exe_dir     = "{exe_dir}"
$exe_name    = "{exe_name}"
$tmp_name    = "_baza_new.exe"
$expect_size = {expected_size}

Start-Sleep -Seconds 2
Stop-Process -Id {current_pid} -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

$copied = $false
for ($i = 1; $i -le 3; $i++) {{
    try {{
        # robocopy: /Z — перезапускаемый режим, /R:1 /W:2 — одна попытка с паузой
        $rc = (robocopy $env:TEMP $exe_dir $tmp_name /Z /R:1 /W:2 /NP /NJH /NJS) 2>&1
        if ($LASTEXITCODE -lt 8) {{
            $dst = Join-Path $exe_dir $tmp_name
            if (Test-Path $dst) {{
                # Заменяем старый exe: переименовываем старый в .bak, новый -> baza.exe
                $bak = "$exe_path.bak"
                Remove-Item $bak -Force -ErrorAction SilentlyContinue
                Rename-Item $exe_path $bak -ErrorAction SilentlyContinue
                Rename-Item $dst $exe_name -Force -ErrorAction Stop
                # Проверяем размер если известен
                if ($expect_size -gt 0) {{
                    $actual = (Get-Item $exe_path).Length
                    if ($actual -eq $expect_size) {{
                        $copied = $true
                        Remove-Item $bak -Force -ErrorAction SilentlyContinue
                    }} else {{
                        # Размер не совпал — восстанавливаем backup
                        Remove-Item $exe_path -Force -ErrorAction SilentlyContinue
                        Rename-Item $bak $exe_name -Force -ErrorAction SilentlyContinue
                    }}
                }} else {{
                    $copied = $true
                    Remove-Item $bak -Force -ErrorAction SilentlyContinue
                }}
            }}
        }}
    }} catch {{}}
    if ($copied) {{ break }}
    Start-Sleep -Seconds 3
}}

if ($copied) {{
    Remove-Item $local_tmp -Force -ErrorAction SilentlyContinue
    Start-Process $exe_path
}} else {{
    # Сеть не позволила — запускаем локальную копию (datapath.txt уже создан)
    Start-Process $local_tmp
}}
Remove-Item $MyInvocation.MyCommand.Path -ErrorAction SilentlyContinue
"""
    ps_path = os.path.join(tmp_dir, "baza_update.ps1")
    with open(ps_path, "w", encoding="utf-8-sig") as f:
        f.write(ps)

    subprocess.Popen(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-WindowStyle", "Hidden", "-File", ps_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    sys.exit(0)
