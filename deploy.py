"""
deploy.py -- Публикация новой версии через GitHub Releases.
Запускать из папки проекта после сборки: pyinstaller build.spec
"""
import os
import sys
import json
import urllib.request
import urllib.error

try:
    from gh_token import GITHUB_TOKEN
except ImportError:
    GITHUB_TOKEN = ""

GITHUB_REPO = "Pasking200087/Holdcall"
SRC_EXE     = os.path.join("dist", "baza.exe")
VER_FILE    = "version.txt"
_API_BASE   = "https://api.github.com"
_UPLOAD_BASE = "https://uploads.github.com"


def fail(msg):
    print(f"[ОШИБКА] {msg}")
    input("Нажмите Enter для выхода...")
    sys.exit(1)


def _headers(extra: dict = None) -> dict:
    h = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if extra:
        h.update(extra)
    return h


def _api(method: str, path: str, body: dict = None) -> dict:
    url = f"{_API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=_headers({"Content-Type": "application/json"}), method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def create_release(version: str) -> dict:
    print(f"Создаю релиз v{version} на GitHub...")
    return _api("POST", f"/repos/{GITHUB_REPO}/releases", {
        "tag_name": f"v{version}",
        "name": f"v{version}",
        "body": f"Версия {version}",
        "draft": False,
        "prerelease": False,
    })


def upload_asset(release: dict, exe_path: str) -> None:
    release_id = release["id"]
    upload_url = f"{_UPLOAD_BASE}/repos/{GITHUB_REPO}/releases/{release_id}/assets?name=baza.exe"
    print(f"Загружаю baza.exe ({os.path.getsize(exe_path) // 1024} КБ)...")

    with open(exe_path, "rb") as f:
        data = f.read()

    req = urllib.request.Request(
        upload_url, data=data,
        headers=_headers({"Content-Type": "application/octet-stream"}),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())
    print(f"[OK] Загружено: {result['browser_download_url']}")


def main():
    if not GITHUB_TOKEN:
        fail("GITHUB_TOKEN не найден. Проверь secrets.py")

    if not os.path.exists(SRC_EXE):
        fail(f"Файл {SRC_EXE} не найден. Сначала запусти: pyinstaller build.spec")

    if not os.path.exists(VER_FILE):
        fail(f"Файл {VER_FILE} не найден.")

    with open(VER_FILE, encoding="utf-8") as f:
        version = f.read().strip()

    print(f"Публикация версии {version}...")

    # Проверяем — вдруг релиз уже существует
    try:
        existing = _api("GET", f"/repos/{GITHUB_REPO}/releases/tags/v{version}")
        fail(f"Релиз v{version} уже существует на GitHub. Обнови версию в version.txt и config.py")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            fail(f"Ошибка при проверке релиза: {e}")

    try:
        release = create_release(version)
    except Exception as e:
        fail(f"Не удалось создать релиз:\n{e}")

    try:
        upload_asset(release, SRC_EXE)
    except Exception as e:
        fail(f"Не удалось загрузить exe:\n{e}")

    print()
    print(f"[OK] Версия {version} опубликована на GitHub.")
    print(f"     https://github.com/{GITHUB_REPO}/releases/tag/v{version}")
    print(f"     Пользователи получат обновление при следующей проверке.")
    input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    main()
