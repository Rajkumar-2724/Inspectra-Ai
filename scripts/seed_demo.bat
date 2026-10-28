@echo off
REM Creates the admin user (from backend\.env), sample products and 60 SIMULATED demo inspections. Development only.
cd /d "%~dp0..\backend"
call .venv\Scripts\activate.bat
python -m app.scripts.seed --demo-data --n 60
pause
