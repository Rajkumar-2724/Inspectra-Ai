@echo off
cd /d "%~dp0"
start "AVIS Backend" cmd /k "%~dp0start_backend.bat"
timeout /t 8 /nobreak >nul
start "AVIS Frontend" cmd /k "%~dp0start_frontend.bat"
timeout /t 6 /nobreak >nul
start "" http://127.0.0.1:5173
