@echo off
:: deploy.bat -- Publikaciya novoj versii na NAS
:: Zapuskat iz papki proekta posle sborki: pyinstaller build.spec

setlocal

:: --- NASTROJKA ---
:: Osnovnaya papka na NAS (kuda kladyotsya rabochij exe)
set NAS_MAIN=Z:\Programma dlya holodnyh zvonkov
:: Papka obnovlenij (dlya avtobnovleniya u zapushchennyh polzovatelej)
set NAS_UPDATE=Z:\Programma dlya holodnyh zvonkov\update
:: -----------------

set SRC_EXE=dist\baza.exe
set VER_FILE=version.txt

if not exist "%SRC_EXE%" (
    echo [ERROR] File %SRC_EXE% not found. Run first: pyinstaller build.spec
    pause
    exit /b 1
)

if not exist "%VER_FILE%" (
    echo 1.0.0 > "%VER_FILE%"
)

set /p NEW_VER=< "%VER_FILE%"
set NEW_VER=%NEW_VER: =%

echo Publishing version %NEW_VER%...

:: 1. Kopируем основной exe
if not exist "%NAS_MAIN%" mkdir "%NAS_MAIN%"
copy /y "%SRC_EXE%" "%NAS_MAIN%\baza.exe"
if errorlevel 1 (
    echo [ERROR] Failed to copy exe to main folder
    pause
    exit /b 1
)
echo [OK] Main exe updated: %NAS_MAIN%\baza.exe

:: 2. Kopируем в папку обновлений
if not exist "%NAS_UPDATE%" mkdir "%NAS_UPDATE%"
copy /y "%SRC_EXE%" "%NAS_UPDATE%\baza.exe"
if errorlevel 1 (
    echo [ERROR] Failed to copy exe to update folder
    pause
    exit /b 1
)
echo %NEW_VER%> "%NAS_UPDATE%\version.txt"
echo [OK] Update folder updated: %NAS_UPDATE%

echo.
echo [OK] Version %NEW_VER% published. Users will get the update on next launch.
pause
