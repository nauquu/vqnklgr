@echo off
title Dong Goi setup.exe Tu Dong
echo ===================================================
echo   DONG GOI TU DONG SETUP.EXE (DUNG LUONG TOI UU)
echo ===================================================
echo.

cd /d "%~dp0"

if not exist "clean_env\Scripts\pyinstaller.exe" (
    echo [ERR] Khong tim thay thu muc moi truong ao "clean_env".
    echo Vui long dam bao ban dang chay dung thu muc va thu muc "clean_env" ton tai.
    pause
    exit /b
)

echo [*] Dang tien hanh dong goi file setup.exe ...
"clean_env\Scripts\pyinstaller.exe" --onefile --noconsole --clean --name setup --hidden-import playwright --hidden-import pynput.keyboard._win32 --exclude-module numpy --exclude-module cv2 klg.py

echo.
if %errorlevel% equ 0 (
    echo [*] Dang don dep cac file va thu muc tam...
    
    if exist "dist\setup.exe" (
        move /Y "dist\setup.exe" ".\setup.exe" >nul
    )
    if exist "build" (
        rd /S /Q "build"
    )
    if exist "dist" (
        rd /S /Q "dist"
    )
    if exist "setup.spec" (
        del /F /Q "setup.spec"
    )
    
    echo ===================================================
    echo [OK] Dong goi thanh cong!
    echo File dau ra da duoc di chuyen ra ngoai: klg/setup.exe
    echo ===================================================
) else (
    echo [ERR] Dong goi that bai! Vui long kiem tra thong tin loi phia tren.
)
pause
