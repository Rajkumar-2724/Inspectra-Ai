@echo off
cd /d "%~dp0..\backend"
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements-dev.txt
python -m pytest tests -q
cd /d "%~dp0..\frontend"
call npm run typecheck && call npm test
