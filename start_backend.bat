@echo off
setlocal
cd /d "%~dp0backend"
if not exist .venv (
  echo Creating Python virtual environment...
  py -3.11 -m venv .venv 2>nul || python -m venv .venv
)
call .venv\Scripts\activate.bat
if not exist .env (
  copy .env.example .env >nul
  echo Created backend\.env from .env.example - edit SECRET_KEY and ADMIN_PASSWORD before real use.
)
python -m pip install -q -r requirements.txt
if errorlevel 1 ( echo Dependency installation failed & pause & exit /b 1 )
echo Applying database migrations...
alembic upgrade head
if errorlevel 1 ( echo Migration failed & pause & exit /b 1 )
echo Backend: http://127.0.0.1:8000   API docs: http://127.0.0.1:8000/docs
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
endlocal
