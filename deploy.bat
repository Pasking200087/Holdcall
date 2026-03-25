@echo off
:: deploy.bat — Публикация новой версии на NAS
:: Запускать из папки проекта после сборки: pyinstaller build.spec

chcp 65001 >nul
setlocal

:: ─── НАСТРОЙКА ───────────────────────────────────────────────────────────────
:: Основная папка на NAS (куда кладётся рабочий exe)
set NAS_MAIN=Z:\Программа для холодных звонков
:: Папка обновлений (для автообновления у запущенных пользователей)
set NAS_UPDATE=Z:\Программа для холодных звонков\update
:: ─────────────────────────────────────────────────────────────────────────────

set SRC_EXE=dist\baza.exe
set VER_FILE=version.txt

if not exist "%SRC_EXE%" (
    echo [ОШИБКА] Файл %SRC_EXE% не найден. Запусти сначала: pyinstaller build.spec
    pause
    exit /b 1
)

:: Читаем версию из version.txt (создаём если нет)
if not exist "%VER_FILE%" (
    echo 1.0.2 > "%VER_FILE%"
)

set /p NEW_VER=< "%VER_FILE%"
set NEW_VER=%NEW_VER: =%

echo Публикация версии %NEW_VER%...

:: 1. Копируем основной exe
if not exist "%NAS_MAIN%" mkdir "%NAS_MAIN%"
copy /y "%SRC_EXE%" "%NAS_MAIN%\baza.exe"
if errorlevel 1 (
    echo [ОШИБКА] Не удалось скопировать exe в основную папку
    pause
    exit /b 1
)
echo [OK] Основной exe обновлён: %NAS_MAIN%\baza.exe

:: 2. Копируем в папку обновлений (для уже запущенных пользователей)
if not exist "%NAS_UPDATE%" mkdir "%NAS_UPDATE%"
copy /y "%SRC_EXE%" "%NAS_UPDATE%\baza.exe"
if errorlevel 1 (
    echo [ОШИБКА] Не удалось скопировать exe в папку обновлений
    pause
    exit /b 1
)
echo %NEW_VER%> "%NAS_UPDATE%\version.txt"
echo [OK] Папка обновлений обновлена: %NAS_UPDATE%

echo.
echo [OK] Версия %NEW_VER% опубликована. Пользователи получат обновление при следующем запуске.
pause
