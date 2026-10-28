@echo off
setlocal EnableDelayedExpansion
title CapCut Multi-Thread Automation - Installer Komputer Baru
chcp 65001 >nul

echo =====================================================================
echo       CAPCUT MULTI-THREAD AUTOMATION - INSTALLER KOMPUTER BARU
echo =====================================================================
echo.

:: 1. Cek apakah Python sudah terpasang
echo [1/4] Memeriksa instalasi Python...
set "PY_CMD="

python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :python_ready
)

py -3 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3"
    goto :python_ready
)

:: Jika Python belum ada, unduh dan pasang otomatis
echo [!] Python belum terpasang pada komputer ini.
echo [*] Mengunduh installer resmi Python 3.11 64-bit dari python.org...

set "INSTALLER_PATH=%TEMP%\python_311_installer.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', $env:INSTALLER_PATH)"

if not exist "%INSTALLER_PATH%" (
    echo [x] Gagal mengunduh installer Python. Pastikan komputer terhubung ke internet.
    pause
    exit /b 1
)

echo [*] Memasang Python ke sistem pengguna secara otomatis...
"%INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Shortcuts=0
del "%INSTALLER_PATH%" >nul 2>&1

:: Perbarui PATH untuk sesi cmd saat ini
set "PATH=%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;%PATH%"

python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :python_ready
) else (
    echo [x] Python telah dipasang namun belum aktif pada sesi terminal ini.
    echo [!] Silakan restart komputer Anda, lalu jalankan kembali install_requirements.bat
    pause
    exit /b 1
)

:python_ready
for /f "delims=" %%v in ('!PY_CMD! --version 2^>^&1') do echo [+] Menggunakan: %%v

echo.
echo [2/4] Memperbarui pip dan memasang library dependencies...
!PY_CMD! -m pip install --upgrade pip --quiet
!PY_CMD! -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [x] Gagal memasang dependencies dari requirements.txt.
    pause
    exit /b 1
)
echo [+] Library Python berhasil dipasang.

echo.
echo [3/4] Memasang browser engine Playwright Chromium...
!PY_CMD! -m playwright install chromium
if !errorlevel! neq 0 (
    echo [x] Gagal memasang browser Playwright Chromium.
    pause
    exit /b 1
)
echo [+] Browser Playwright Chromium siap digunakan.

echo.
echo [4/4] Memeriksa file konfigurasi proyek...
if not exist ".env" (
    echo [*] Membuat file .env default...
    (
        echo MAX_THREADS=3
        echo DELAY_BETWEEN_ACCOUNTS=30
        echo MAX_PROXY_LATENCY_MS=2500
        echo PORT=5000
    ) > .env
    echo [+] File .env berhasil dibuat.
) else (
    echo [+] File .env sudah ada.
)

if not exist "proxy.txt" (
    echo [*] Membuat file proxy.txt kosong...
    type nul > proxy.txt
    echo [+] File proxy.txt dibuat. Format: hostname:port:login:password
) else (
    echo [+] File proxy.txt sudah ada.
)

if not exist "accounts.txt" (
    echo [*] Membuat file accounts.txt kosong...
    type nul > accounts.txt
    echo [+] File accounts.txt dibuat. Format: email^|password
) else (
    echo [+] File accounts.txt sudah ada.
)

echo.
echo =====================================================================
echo               [+] SEMUA INSTALASI BERHASIL DISIAPKAN!
echo =====================================================================
echo.
echo Sekarang Anda dapat menjalankan aplikasi dengan:
echo   1. Klik ganda pada: run_dashboard.bat  (Web Dashboard di http://localhost:5000)
echo   2. Atau jalankan: python main.py        (Mode CLI / Terminal)
echo.
pause
