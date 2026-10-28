@echo off
setlocal
cd /d "%~dp0frontend"
if not exist .env copy .env.example .env >nul
if not exist node_modules (
  echo Installing frontend dependencies...
  call npm install
  if errorlevel 1 ( echo npm install failed & pause & exit /b 1 )
)
echo Frontend: http://127.0.0.1:5173
call npm run dev
endlocal
